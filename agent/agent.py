
import ipaddress
import os
import platform
import re
import socket
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

if __package__:
    from .speed_test import run_device_speed_test
else:
    from speed_test import run_device_speed_test

DEFAULT_NETWORK = "192.168.43.0/24"
PING_RTT_PATTERN = re.compile(r"time=\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


class AgentSubmissionError(RuntimeError):
    pass


class AgentAuthenticationError(AgentSubmissionError):
    pass


class AgentValidationError(AgentSubmissionError):
    pass


class AgentServerError(AgentSubmissionError):
    pass


def ping_device(ip):
    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", "800", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
        )

        if result.returncode == 0:
            output = f"{result.stdout}\n{result.stderr}"
            rtt = PING_RTT_PATTERN.search(output)
            return {
                "ip": ip,
                "status": "Online",
                "latency_ms": float(rtt.group(1)) if rtt else None,
            }

        return None

    except (subprocess.TimeoutExpired, OSError):
        return None


def scan_network(network):
    net = ipaddress.ip_network(network, strict=False)

    if not net.is_private or net.num_addresses > 4096:
        raise ValueError("Invalid or excessively large private network")

    print(f"\nScanning authorized network: {network}\n")

    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(
            ping_device,
            (str(ip) for ip in net.hosts()),
        )

        online_devices = [result for result in results if result is not None]

    print("\n--- Scan Results ---")

    for device in online_devices:
        print(f"{device['ip']} - {device['status']}")

    print(f"\nOnline devices found: {len(online_devices)}")
    return online_devices


def get_agent_configuration():
    api_url = os.getenv("NMVS_AGENT_API_URL", "").strip().rstrip("/")
    token = os.getenv("NMVS_AGENT_TOKEN", "").strip()
    network = os.getenv("NMVS_AGENT_NETWORK", DEFAULT_NETWORK).strip()

    if not api_url:
        raise ValueError("Set NMVS_AGENT_API_URL in agent/.env.")
    if not token:
        raise ValueError("Set NMVS_AGENT_TOKEN in agent/.env.")

    parsed_url = urlsplit(api_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("NMVS_AGENT_API_URL must be an absolute HTTP(S) URL.")
    if parsed_url.scheme != "https" and parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Use HTTPS for NMVS_AGENT_API_URL outside localhost.")

    return f"{api_url}/agent/scan-results", token, network


def discover_local_ips(api_url):
    addresses = set()
    hostname = socket.gethostname()
    try:
        addresses.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass

    parsed_url = urlsplit(api_url)
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((parsed_url.hostname, port))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass

    return sorted(
        address
        for address in addresses
        if address not in {"0.0.0.0", "127.0.0.1"}
    )


def poll_device_speed_tests(api_url, token, local_ips, poll_interval=5):
    endpoint = f"{api_url}/agent/speed-tests"
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        try:
            response = requests.post(
                f"{endpoint}/claim",
                json={"local_ips": local_ips},
                headers=headers,
                timeout=(5, 15),
            )
            response.raise_for_status()
            payload = response.json()
            job = payload.get("job") if isinstance(payload, dict) else None
            if job:
                if (
                    not isinstance(job, dict)
                    or not isinstance(job.get("id"), int)
                    or not isinstance(job.get("ip"), str)
                    or job["ip"] not in local_ips
                ):
                    raise ValueError("Backend returned an invalid device speed-test job.")
                try:
                    result = run_device_speed_test()
                    result.update({"ip": job["ip"]})
                except (RuntimeError, requests.RequestException) as exc:
                    result = {"ip": job["ip"], "error": str(exc)}

                completion = requests.post(
                    f"{endpoint}/{job['id']}/complete",
                    json=result,
                    headers=headers,
                    timeout=(5, 30),
                )
                completion.raise_for_status()
                completion_payload = completion.json()
                if (
                    not isinstance(completion_payload, dict)
                    or completion_payload.get("status") not in {"completed", "failed"}
                ):
                    raise ValueError("Backend did not confirm the device speed-test result.")
                print(f"Device speed test {completion_payload['status']} for {job['ip']}.")
        except requests.HTTPError as exc:
            response = exc.response
            if response is not None and response.status_code in {401, 422}:
                print(
                    f"Device speed-test polling stopped (HTTP {response.status_code}); "
                    "check the agent token and configuration."
                )
                return
            print(f"Device speed-test polling failed; will retry: {exc}")
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"Device speed-test polling failed; will retry: {exc}")
        time.sleep(poll_interval)


def _send_scan_results_once(endpoint, token, devices, network=None):
    payload = {"devices": devices}
    if network is not None:
        payload["network"] = network
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=(5, 30),
    )

    if not response.ok:
        try:
            error_payload = response.json()
            detail = (
                error_payload.get("detail", response.text)
                if isinstance(error_payload, dict)
                else response.text
            )
        except ValueError:
            detail = response.text

        if response.status_code == 401:
            raise AgentAuthenticationError(
                "Agent authorization failed (HTTP 401). Confirm that "
                "NMVS_AGENT_TOKEN matches the backend setting."
            )

        message = f"Agent upload failed (HTTP {response.status_code}): {detail}"
        if response.status_code == 422:
            raise AgentValidationError(message)
        if 500 <= response.status_code < 600:
            raise AgentServerError(message)
        raise AgentSubmissionError(message)

    try:
        payload = response.json()
    except ValueError as exc:
        raise AgentSubmissionError(
            "Agent upload failed: backend returned invalid JSON."
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("message") != "Scan results processed"
        or payload.get("received") != len(devices)
        or payload.get("processed") != len(devices)
        or any(
            not isinstance(payload.get(field), int)
            or payload[field] < 0
            for field in (
                "devices_created",
                "devices_updated",
                "monitoring_records_created",
                "alert_failures",
            )
        )
    ):
        raise AgentSubmissionError(
            "Agent upload failed: backend did not confirm processing the scan."
        )

    return payload


def send_scan_results(
    endpoint,
    token,
    devices,
    attempts=3,
    retry_delay_seconds=1,
    network=None,
):
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(attempts):
        try:
            return _send_scan_results_once(endpoint, token, devices, network=network)
        except (requests.ConnectionError, requests.Timeout):
            if attempt + 1 == attempts:
                raise
        except AgentServerError:
            if attempt + 1 == attempts:
                raise
        if attempt + 1 < attempts:
            time.sleep(retry_delay_seconds * (2 ** attempt))

    raise AgentServerError("Agent upload failed after retrying transient errors.")


def run_agent():
    load_dotenv(Path(__file__).with_name(".env"))
    endpoint, token, network = get_agent_configuration()
    api_url = endpoint.removesuffix("/agent/scan-results")
    try:
        scan_interval = int(os.getenv("NMVS_AGENT_SCAN_INTERVAL_SECONDS", "30"))
    except ValueError as exc:
        raise ValueError("NMVS_AGENT_SCAN_INTERVAL_SECONDS must be an integer.") from exc
    if not 1 <= scan_interval <= 86400:
        raise ValueError(
            "NMVS_AGENT_SCAN_INTERVAL_SECONDS must be between 1 and 86400."
        )

    mode = os.getenv("NMVS_AGENT_MODE", "scanner").strip().lower()
    if mode not in {"scanner", "device"}:
        raise ValueError("NMVS_AGENT_MODE must be 'scanner' or 'device'.")
    poll_interval = int(os.getenv("NMVS_AGENT_SPEED_TEST_POLL_SECONDS", "5"))
    if not 1 <= poll_interval <= 60:
        raise ValueError("NMVS_AGENT_SPEED_TEST_POLL_SECONDS must be from 1 to 60.")

    local_ips = discover_local_ips(api_url)
    if not local_ips:
        raise ValueError(
            "Could not identify a local device IP. Check network connectivity "
            "or configure the agent host's DNS and routes."
        )
    threading.Thread(
        target=poll_device_speed_tests,
        args=(api_url, token, local_ips, poll_interval),
        daemon=True,
    ).start()
    print(
        f"NMVS {mode} agent started; device IP(s): {', '.join(local_ips)}. "
        f"Speed-test jobs are checked every {poll_interval} seconds."
    )
    while True:
        if mode == "scanner":
            print(f"Starting scan of authorized network {network}.")
            devices = scan_network(network)
            print(f"Scan complete: {len(devices)} responding device(s) found.")
            try:
                result = send_scan_results(endpoint, token, devices, network=network)
            except AgentAuthenticationError as exc:
                raise SystemExit(str(exc)) from exc
            except AgentValidationError as exc:
                raise SystemExit(str(exc)) from exc
            except AgentServerError as exc:
                print(f"Submission failed; will retry on the next scan: {exc}")
            except requests.RequestException as exc:
                print(f"Submission failed; will retry on the next scan: {exc}")
            except AgentSubmissionError as exc:
                raise SystemExit(str(exc)) from exc
            else:
                print(
                    "Submission successful: "
                    f"{result.get('processed', 0)} device(s) processed."
                )
        time.sleep(scan_interval)


if __name__ == "__main__":
    try:
        run_agent()
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
