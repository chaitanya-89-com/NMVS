import os
import platform
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import requests


BASE_URL = "https://speed.cloudflare.com"
LATENCY_TARGET = "1.1.1.1"
LATENCY_SAMPLE_COUNT = 10
LATENCY_TIMEOUT_SECONDS = 15
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 15
MAX_TRANSFER_SECONDS = 3
CHUNK_SIZE = 4096
TIMEOUT = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
PING_RTT_PATTERN = re.compile(r"time[=<]\s*(\d+(?:[.,]\d+)?)\s*ms", re.IGNORECASE)


class LatencyMeasurementError(RuntimeError):
    pass


def _ping_ms() -> float:
    if platform.system().lower() == "windows":
        command = [
            "ping",
            "-n",
            str(LATENCY_SAMPLE_COUNT),
            "-w",
            "1000",
            LATENCY_TARGET,
        ]
    elif platform.system().lower() == "linux":
        command = [
            "ping",
            "-c",
            str(LATENCY_SAMPLE_COUNT),
            "-W",
            "1",
            LATENCY_TARGET,
        ]
    elif platform.system().lower() == "darwin":
        command = [
            "ping",
            "-c",
            str(LATENCY_SAMPLE_COUNT),
            "-W",
            "1000",
            LATENCY_TARGET,
        ]
    else:
        raise LatencyMeasurementError(
            "ICMP latency measurement is not supported on this operating system."
        )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=LATENCY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LatencyMeasurementError(
            f"The device could not measure ICMP latency to {LATENCY_TARGET}."
        ) from exc

    output = f"{result.stdout}\n{result.stderr}"
    samples = [
        float(match.replace(",", "."))
        for match in PING_RTT_PATTERN.findall(output)
    ]
    if not samples:
        raise LatencyMeasurementError(
            f"The device received no ICMP latency samples from {LATENCY_TARGET}."
        )
    return round(sum(samples) / len(samples), 2)


def _download(index: int) -> int:
    response = requests.get(
        f"{BASE_URL}/__down",
        params={"bytes": 20_000_000, "nonce": f"{time.time_ns()}-{index}"},
        headers={"Cache-Control": "no-cache"},
        timeout=TIMEOUT,
        stream=True,
    )
    received = 0
    started = time.perf_counter()
    try:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                received += len(chunk)
            if time.perf_counter() - started >= MAX_TRANSFER_SECONDS:
                break
    finally:
        response.close()
    if received <= 0:
        raise RuntimeError("Speed-test server returned an empty download.")
    return received


def _upload() -> int:
    payload = os.urandom(20_000_000)
    started = None
    uploaded = 0

    def chunks():
        nonlocal started, uploaded
        for offset in range(0, len(payload), CHUNK_SIZE):
            now = time.perf_counter()
            if started is None:
                started = now
            elif now - started >= MAX_TRANSFER_SECONDS:
                break
            chunk = payload[offset:offset + CHUNK_SIZE]
            uploaded += len(chunk)
            yield chunk

    response = requests.post(
        f"{BASE_URL}/__up",
        data=chunks(),
        headers={
            "Cache-Control": "no-cache",
            "Content-Type": "application/octet-stream",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    if uploaded <= 0:
        raise RuntimeError("Speed-test upload did not send any data.")
    return uploaded


def _measure(transfer, request_count: int) -> float:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=request_count) as executor:
        counts = list(executor.map(transfer, range(request_count)))
    elapsed = time.perf_counter() - started
    total_bytes = sum(counts)
    if not total_bytes or elapsed <= 0:
        raise RuntimeError("Speed test transferred no data.")
    return round(total_bytes * 8 / elapsed / 1_000_000, 2)


def run_device_speed_test() -> dict[str, float | None]:
    """Measure this device's own internet connection to Cloudflare."""
    try:
        try:
            ping_ms = _ping_ms()
        except LatencyMeasurementError:
            ping_ms = None
        download_mbps = _measure(_download, 2)
        upload_mbps = _measure(lambda _index: _upload(), 1)
    except requests.Timeout as exc:
        raise RuntimeError(
            "The device speed test timed out while contacting Cloudflare."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"The device could not complete its Cloudflare speed test ({type(exc).__name__})."
        ) from exc
    return {
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "ping_ms": ping_ms,
    }
