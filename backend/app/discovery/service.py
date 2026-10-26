from .ping import ping_device
from .scanner import scan_network


def check_device(ip: str, tcp_port: int | None = None):
    return ping_device(ip, tcp_port)


def discover_network(network: str):
    return scan_network(network)