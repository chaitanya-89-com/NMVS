import platform
import ipaddress
import re
import socket
import subprocess
import time
from urllib.parse import urlsplit

import requests

from app.config import settings


_PING_RTT_PATTERN = re.compile(r"time([=<])\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
_UNREACHABLE_TEXT = (
    "destination host unreachable",
    "destination net unreachable",
    "network is unreachable",
    "no route to host",
)


def validate_health_check_url(url: str | None) -> str | None:
    if url is None or not url.strip():
        return None

    normalized = url.strip()
    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Health-check URL is invalid") from exc

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError(
            "Health-check URL must be an HTTP(S) URL without credentials or a fragment"
        )

    normalized_host = hostname.lower().rstrip(".")
    if normalized_host not in settings.MONITORING_HTTP_ALLOWED_HOSTS:
        raise ValueError(
            "Health-check host is not approved. Ask the administrator to add it to "
            "MONITORING_HTTP_ALLOWED_HOSTS."
        )
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        try:
            resolved_addresses = {
                ipaddress.ip_address(address_info[4][0])
                for address_info in socket.getaddrinfo(
                    normalized_host,
                    port or (443 if parsed.scheme.lower() == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except OSError as exc:
            raise ValueError("Health-check host could not be resolved") from exc
        if not resolved_addresses:
            raise ValueError("Health-check host did not resolve to an address")
        if any(not address.is_global for address in resolved_addresses):
            raise ValueError(
                "Health-check host resolves to a non-public IP address; "
                "allowlist that IP explicitly if it is an approved internal service"
            )
    else:
        if not address.is_global and normalized_host not in settings.MONITORING_HTTP_ALLOWED_HOSTS:
            raise ValueError("Health-check URL cannot target a non-public IP address")

    return normalized


def check_device_status(ip: str, tcp_port: int | None = None) -> dict:
    """Probe reachability; never treat a missing ICMP reply alone as proof of outage."""
    ip_str = str(ip)
    try:
        address = socket.getaddrinfo(ip_str, None, type=socket.SOCK_STREAM)
        address = address[0][4][0]
    except (OSError, ValueError):
        return {
            "ip": ip_str,
            "status": "Unknown",
            "check_result": "unknown",
            "checked_by": "none",
            "detail": "The device address is invalid.",
            "icmp_result": "not_checked",
        }

    if tcp_port is not None and not 1 <= tcp_port <= 65535:
        raise ValueError("TCP port must be between 1 and 65535")

    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", "1000", ip_str]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip_str]

    icmp_result = "failed"
    icmp_detail = "The ICMP check could not be completed."
    try:
        started = time.monotonic()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
        )
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode == 0:
            match = _PING_RTT_PATTERN.search(output)
            exact_rtt = match and match.group(1) == "="
            return {
                "ip": ip_str,
                "status": "Online",
                "check_result": "success",
                "checked_by": "ICMP",
                "latency_ms": float(match.group(2)) if exact_rtt else None,
                "latency_method": "ICMP" if exact_rtt else None,
                "icmp_result": "success",
                "detail": (
                    "ICMP echo reply received."
                    if exact_rtt
                    else (
                        "ICMP echo reply received; RTT is below the ping tool's display resolution."
                        if match
                        else "ICMP echo reply received; the system did not report an RTT."
                    )
                ),
                "check_elapsed_ms": (time.monotonic() - started) * 1000,
            }
        lowered_output = output.lower()
        if any(message in lowered_output for message in _UNREACHABLE_TEXT):
            icmp_result = "unreachable"
            icmp_detail = "The network reported the destination as unreachable."
        else:
            icmp_result = "timeout"
            icmp_detail = "No ICMP echo reply was received."
    except subprocess.TimeoutExpired:
        icmp_result = "timeout"
        icmp_detail = "The ICMP command exceeded its time limit."
    except OSError:
        icmp_detail = "The ICMP check could not run on the monitoring server."

    if tcp_port is not None:
        started = time.monotonic()
        try:
            with socket.create_connection((str(address), tcp_port), timeout=1.5):
                tcp_ms = (time.monotonic() - started) * 1000
                return {
                    "ip": ip_str,
                    "status": "Online",
                    "check_result": "success",
                    "checked_by": f"TCP/{tcp_port}",
                    "latency_ms": round(tcp_ms, 2),
                    "latency_method": "TCP_CONNECT",
                    "icmp_result": icmp_result,
                    "tcp_result": "success",
                    "tcp_response_ms": round(tcp_ms, 2),
                    "detail": (
                        f"TCP connection to port {tcp_port} succeeded. "
                        "This measures connection setup, not application response time."
                    ),
                }
        except ConnectionRefusedError:
            tcp_ms = (time.monotonic() - started) * 1000
            return {
                "ip": ip_str,
                "status": "Online",
                "check_result": "success",
                "checked_by": f"TCP/{tcp_port}",
                "icmp_result": icmp_result,
                "tcp_result": "refused",
                "tcp_response_ms": round(tcp_ms, 2),
                "detail": (
                    f"The device responded but refused TCP port {tcp_port}; "
                    "the device is reachable, but that service did not accept the connection."
                ),
            }
        except (socket.timeout, TimeoutError):
            tcp_ms = (time.monotonic() - started) * 1000
            return {
                "ip": ip_str,
                "status": "Unknown",
                "check_result": "unknown",
                "checked_by": f"ICMP and TCP/{tcp_port}",
                "icmp_result": icmp_result,
                "tcp_result": "timeout",
                "tcp_response_ms": round(tcp_ms, 2),
                "detail": (
                    f"No ICMP reply and TCP port {tcp_port} timed out. "
                    "This does not prove the device is offline."
                ),
            }
        except OSError:
            tcp_ms = (time.monotonic() - started) * 1000
            return {
                "ip": ip_str,
                "status": "Offline" if icmp_result == "unreachable" else "Unknown",
                "check_result": "failed" if icmp_result == "unreachable" else "unknown",
                "checked_by": f"ICMP and TCP/{tcp_port}",
                "icmp_result": icmp_result,
                "tcp_result": "failed",
                "tcp_response_ms": round(tcp_ms, 2),
                "detail": f"{icmp_detail} TCP port {tcp_port} did not connect.",
            }

    offline = icmp_result == "unreachable"
    return {
        "ip": ip_str,
        "status": "Offline" if offline else "Unknown",
        "check_result": "failed" if offline else "unknown",
        "checked_by": "ICMP",
        "icmp_result": icmp_result,
        "detail": icmp_detail,
    }


def check_http_health(url: str) -> dict:
    """Check an explicitly administrator-allowlisted HTTP service without redirects."""
    validated_url = validate_health_check_url(url)
    if validated_url is None:
        raise ValueError("Health-check URL is required")

    started = time.monotonic()
    try:
        response = requests.get(
            validated_url,
            timeout=(2, settings.MONITORING_HTTP_TIMEOUT_SECONDS),
            allow_redirects=False,
            stream=True,
        )
    except requests.RequestException as exc:
        return {
            "http_status_code": None,
            "http_response_ms": round((time.monotonic() - started) * 1000, 2),
            "http_health_status": "unknown",
            "http_detail": f"HTTP health check could not complete ({type(exc).__name__}).",
        }

    try:
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        healthy = 200 <= response.status_code < 300
        return {
            "http_status_code": response.status_code,
            "http_response_ms": elapsed_ms,
            "http_health_status": "healthy" if healthy else "unhealthy",
            "http_detail": (
                f"HTTP service returned status {response.status_code}."
                if healthy
                else f"HTTP service returned unhealthy status {response.status_code}."
            ),
        }
    finally:
        response.close()
