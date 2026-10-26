import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests


_BASE_URL = "https://speed.cloudflare.com"
_DOWNLOAD_SIZE = 20_000_000
_UPLOAD_SIZE = 20_000_000
_TRANSFER_CHUNK_SIZE = 4_096
_PARALLEL_REQUESTS = 2
_PING_SAMPLES = 1
_MAX_TRANSFER_SECONDS = 3
_CONNECT_TIMEOUT_SECONDS = 5
_READ_TIMEOUT_SECONDS = 15
_TIMEOUT = (_CONNECT_TIMEOUT_SECONDS, _READ_TIMEOUT_SECONDS)


def _get_ping_ms() -> float:
    samples = []
    with requests.Session() as session:
        for index in range(_PING_SAMPLES):
            started = time.perf_counter()
            response = session.get(
                f"{_BASE_URL}/__down",
                params={"bytes": 1, "nonce": f"{time.time_ns()}-{index}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("Speed-test server returned an empty ping response")
            samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 2)


def _download_bytes(index: int) -> int:
    response = requests.get(
        f"{_BASE_URL}/__down",
        params={"bytes": _DOWNLOAD_SIZE, "nonce": f"{time.time_ns()}-{index}"},
        headers={"Cache-Control": "no-cache"},
        timeout=_TIMEOUT,
        stream=True,
    )
    received = 0
    try:
        response.raise_for_status()
        started = time.perf_counter()
        for chunk in response.iter_content(chunk_size=_TRANSFER_CHUNK_SIZE):
            if not chunk:
                continue
            received += len(chunk)
            if time.perf_counter() - started >= _MAX_TRANSFER_SECONDS:
                break
    finally:
        response.close()
    if received <= 0:
        raise RuntimeError("Speed-test server returned an empty download")
    return received


def _upload_bytes(index: int) -> int:
    payload = os.urandom(_UPLOAD_SIZE)
    started = None
    uploaded = 0

    def chunks():
        nonlocal started, uploaded
        for offset in range(0, len(payload), _TRANSFER_CHUNK_SIZE):
            now = time.perf_counter()
            if started is None:
                started = now
            elif now - started >= _MAX_TRANSFER_SECONDS:
                break
            chunk = payload[offset:offset + _TRANSFER_CHUNK_SIZE]
            uploaded += len(chunk)
            yield chunk

    response = requests.post(
        f"{_BASE_URL}/__up",
        data=chunks(),
        headers={
            "Cache-Control": "no-cache",
            "Content-Type": "application/octet-stream",
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    if uploaded <= 0:
        raise RuntimeError("Speed-test upload did not send any data")
    return uploaded


def _measure_transfer(
    transfer,
    request_count: int = _PARALLEL_REQUESTS,
) -> float:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=request_count) as executor:
        byte_counts = list(executor.map(transfer, range(request_count)))
    elapsed = time.perf_counter() - started
    total_bytes = sum(byte_counts)
    if total_bytes <= 0 or elapsed <= 0:
        raise RuntimeError("Speed test transferred no data")
    return round((total_bytes * 8) / elapsed / 1_000_000, 2)


def run_speed_test() -> dict:
    """Measure the backend host's internet download, upload, and HTTP latency."""
    try:
        ping_ms = _get_ping_ms()
        download_mbps = _measure_transfer(_download_bytes)
        upload_mbps = _measure_transfer(_upload_bytes, request_count=1)
        return {
            "ip": "backend",
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "server": "Cloudflare",
            "isp": None,
            "client_ip": None,
            "error": None,
        }
    except requests.Timeout as exc:
        is_connect_timeout = isinstance(exc, requests.ConnectTimeout)
        phase = "connecting to" if is_connect_timeout else "waiting for a response from"
        timeout_seconds = (
            _CONNECT_TIMEOUT_SECONDS if is_connect_timeout else _READ_TIMEOUT_SECONDS
        )
        raise RuntimeError(
            f"Cloudflare speed test timed out while {phase} "
            f"speed.cloudflare.com after {timeout_seconds} seconds. "
            "Confirm the backend host allows outbound HTTPS traffic on port 443."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Cloudflare speed test request failed ({type(exc).__name__}). "
            "Confirm the backend host allows outbound HTTPS traffic on port 443 "
            "to speed.cloudflare.com."
        ) from exc
