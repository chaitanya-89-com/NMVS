import ipaddress
from concurrent.futures import ThreadPoolExecutor

from .ping import ping_device

MAX_SCAN_ADDRESSES = 4096


def scan_network(network: str):

    try:
        net = ipaddress.ip_network(
            network,
            strict=False
        )
    except ValueError:
        raise ValueError("Invalid network address")

    if net.num_addresses > MAX_SCAN_ADDRESSES:
        raise ValueError(
            f"Network is too large to scan; maximum is {MAX_SCAN_ADDRESSES} addresses"
        )

    ips = [str(ip) for ip in net.hosts()]

    def check(ip):
        result = ping_device(ip)

        print(f"Scanning {ip}: {result['status']}")

        if result["status"] == "Online":
            return result

        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check, ips))

    devices = [
        result
        for result in results
        if result is not None
    ]

    return devices