
import ipaddress
import re
import socket
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

from app.discovery.ping import check_device_status


# Key ports probed to classify device types
COMMON_PORTS = [
    53, 80, 443, 8080, 22, 23, 161, 135, 139, 445, 3389,
    9100, 515, 631, 554, 8000, 37777, 3306, 5432, 27017,
    6379, 1433,
]


def detect_network_provider(ip: str | None = None) -> dict:
    """
    Automatically look up the ISP associated with a public IP.
    Without an IP, looks up the backend's public internet connection.
    """
    try:
        if ip:
            address = ipaddress.ip_address(str(ip).strip())

            if not address.is_global:
                return {
                    "isp": None,
                    "asn": None,
                    "network_type": "Private/Local Network",
                    "public_ip": None,
                }

            url = f"https://ipwho.is/{address}"
        else:
            url = "https://ipwho.is/"

        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            return {
                "isp": "Unknown",
                "asn": None,
                "network_type": "Unknown",
                "public_ip": data.get("ip"),
            }

        connection = data.get("connection") or {}
        isp = connection.get("isp") or "Unknown"

        return {
            "isp": isp,
            "asn": str(connection["asn"])
            if connection.get("asn") else None,
            "network_type": connection.get("org") or isp,
            "public_ip": data.get("ip"),
        }

    except (ValueError, requests.RequestException):
        return {
            "isp": "Unknown",
            "asn": None,
            "network_type": "Unknown",
            "public_ip": None,
        }


def check_tcp_port(
    ip: str,
    port: int,
    timeout: float = 0.3
) -> bool:
    """Check whether a TCP port is open on the target IP."""
    try:
        address = ipaddress.ip_address(ip)
        family = (
            socket.AF_INET6
            if address.version == 6
            else socket.AF_INET
        )

        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0

    except (ValueError, OSError):
        return False


def scan_ports(ip: str, timeout: float = 0.3) -> set[int]:
    """Scan common TCP ports concurrently."""
    open_ports = set()

    with ThreadPoolExecutor(
        max_workers=min(len(COMMON_PORTS), 20)
    ) as executor:
        future_to_port = {
            executor.submit(check_tcp_port, ip, port, timeout): port
            for port in COMMON_PORTS
        }

        for future, port in future_to_port.items():
            try:
                if future.result():
                    open_ports.add(port)
            except Exception:
                pass

    return open_ports


def get_hostname(ip: str, timeout: float = 0.4) -> str | None:
    """Perform a reverse DNS lookup with a timeout."""
    result = [None]

    def resolve():
        try:
            result[0] = socket.gethostbyaddr(ip)[0]
        except Exception:
            pass

    thread = threading.Thread(target=resolve, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    return result[0]


def is_default_gateway(ip: str) -> bool:
    """Check whether an IPv4 address matches the Windows default gateway."""
    try:
        proc = subprocess.run(
            ["route", "print", "0.0.0.0"],
            capture_output=True,
            text=True,
            timeout=0.8,
        )

        pattern = (
            r"0\.0\.0\.0\s+0\.0\.0\.0\s+"
            r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)"
        )

        for match in re.finditer(pattern, proc.stdout):
            if match.group(1) == ip:
                return True

    except Exception:
        pass

    return False


def is_likely_gateway_ip(ip_str: str) -> bool:
    """Heuristic: IPv4 addresses ending in .1 or .254 may be gateways."""
    try:
        address = ipaddress.ip_address(ip_str)

        if address.version == 4:
            last_octet = int(str(address).split(".")[-1])
            return last_octet in (1, 254)

    except ValueError:
        pass

    return False


def get_mac_address(ip: str) -> str | None:
    """Read the local ARP cache for a device's MAC address."""
    try:
        proc = subprocess.run(
            ["arp", "-a", ip],
            capture_output=True,
            text=True,
            timeout=0.6,
        )

        match = re.search(
            r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}",
            proc.stdout,
        )

        if match:
            return match.group(0).lower().replace("-", ":")

    except Exception:
        pass

    return None


def grab_http_banner(
    ip: str,
    port: int = 80,
    timeout: float = 0.5
) -> str:
    """Read an HTTP response to help identify device signatures."""
    try:
        address = ipaddress.ip_address(ip)
        family = (
            socket.AF_INET6
            if address.version == 6
            else socket.AF_INET
        )

        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((ip, port))

            request = (
                f"GET / HTTP/1.0\r\n"
                f"Host: {ip}\r\n"
                f"User-Agent: NMVS\r\n\r\n"
            )
            sock.sendall(request.encode("utf-8", errors="ignore"))

            return sock.recv(2048).decode(
                "utf-8", errors="ignore"
            ).lower()

    except Exception:
        return ""


def detect_device_info(ip: str) -> dict:
    """
    Detect a device's type, status, hostname, ports, MAC address,
    gateway status, and ISP associated with the backend's public IP.
    """
    ip_str = str(ip).strip()

    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return {
            "ip": ip_str,
            "device_type": "Unknown Device",
            "network_type": "Unknown",
            "isp": "Unknown",
            "asn": None,
            "public_ip": None,
            "status": "Offline",
            "hostname": None,
            "open_ports": [],
            "mac_address": None,
            "is_gateway": False,
        }

    # Provider lookup describes the backend's internet connection.
    # It does not infer the ISP from the scanned device's private IP.
    provider_info = detect_network_provider()

    # Special handling for loopback addresses
    if ip_obj.is_loopback:
        return {
            "ip": ip_str,
            "device_type": "Server",
            "network_type": "Loopback",
            "isp": provider_info["isp"],
            "asn": provider_info["asn"],
            "public_ip": provider_info["public_ip"],
            "status": "Online",
            "hostname": get_hostname(ip_str) or "localhost",
            "open_ports": sorted(scan_ports(ip_str)),
            "mac_address": None,
            "is_gateway": False,
        }

    # Run port scanning, reachability, and DNS lookup concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        ports_future = executor.submit(scan_ports, ip_str)
        ping_future = executor.submit(check_device_status, ip_str)
        hostname_future = executor.submit(get_hostname, ip_str)

        open_ports = ports_future.result()
        ping_result = ping_future.result()
        hostname = hostname_future.result()

    is_online = (
        ping_result.get("status") == "Online"
        or bool(open_ports)
    )

    mac_address = get_mac_address(ip_str)
    is_gateway = (
        is_default_gateway(ip_str)
        or is_likely_gateway_ip(ip_str)
    )

    host_lower = (hostname or "").lower()

    # Retrieve an HTTP banner if a web port is open
    banner = ""

    for port in (80, 8080):
        if port in open_ports:
            banner = grab_http_banner(ip_str, port)
            if banner:
                break

    device_type = _classify_device_type(
        open_ports=open_ports,
        hostname=host_lower,
        banner=banner,
        is_gateway=is_gateway,
        is_online=is_online,
    )

    return {
        "ip": ip_str,
        "device_type": device_type,
        "status": "Online" if is_online else "Offline",
        "hostname": hostname,
        "open_ports": sorted(open_ports),
        "mac_address": mac_address,
        "is_gateway": is_gateway,

        # Automatic ISP lookup results
        "isp": provider_info["isp"],
        "asn": provider_info["asn"],
        "network_type": provider_info["network_type"],
        "public_ip": provider_info["public_ip"],
    }


def _classify_device_type(
    open_ports: set[int],
    hostname: str,
    banner: str,
    is_gateway: bool,
    is_online: bool,
) -> str:
    """Classify a device using ports, hostname, and HTTP signatures."""

    # 1. Printer
    printer_ports = {9100, 515, 631}
    printer_keywords = (
        "printer", "cups", "jetdirect", "epson", "brother",
        "canon", "xerox", "laserjet", "deskjet", "officejet",
    )

    if open_ports.intersection(printer_ports) or any(
        keyword in hostname or keyword in banner
        for keyword in printer_keywords
    ):
        return "Printer"

    # 2. IP camera / CCTV
    camera_ports = {554, 37777}
    camera_keywords = (
        "camera", "cctv", "dvr", "nvr", "hikvision",
        "dahua", "amcrest", "reolink", "axis", "webcam",
    )

    if open_ports.intersection(camera_ports) or any(
        keyword in hostname or keyword in banner
        for keyword in camera_keywords
    ):
        return "IP Camera"

    # 3. Router / gateway
    router_keywords = (
        "router", "gateway", "openwrt", "asuswrt", "tplink",
        "tp-link", "netgear", "d-link", "linksys", "mikrotik",
        "dd-wrt", "huawei", "tenda", "zyxel", "fritz",
    )

    if any(
        keyword in hostname or keyword in banner
        for keyword in router_keywords
    ):
        return "Router"

    if is_gateway and open_ports.intersection({53, 80, 443, 8080, 23}):
        return "Router"

    # DNS service without typical Windows workstation ports
    if 53 in open_ports and not open_ports.intersection(
        {135, 139, 445, 3389}
    ):
        return "Router"

    # 4. Network switch
    switch_keywords = (
        "switch", "catalyst", "procurve", "managed switch"
    )

    if any(
        keyword in hostname or keyword in banner
        for keyword in switch_keywords
    ):
        return "Switch"

    if (
        open_ports.intersection({23, 161})
        and not open_ports.intersection({135, 139, 445, 3389})
    ):
        return "Switch"

    # 5. Database / application server
    database_ports = {3306, 5432, 27017, 6379, 1433}

    if open_ports.intersection(database_ports):
        return "Server"

    server_keywords = (
        "server", "srv", "linux", "ubuntu", "debian", "centos",
        "redhat", "nas", "synology", "qnap", "truenas", "freenas",
    )

    if any(
        keyword in hostname or keyword in banner
        for keyword in server_keywords
    ):
        return "Server"

    if (
        22 in open_ports
        and not open_ports.intersection({135, 139, 445, 3389})
    ):
        return "Server"

    # 6. Workstation / PC
    workstation_keywords = (
        "desktop", "laptop", "pc", "hp15", "win-",
        "macbook", "imac", "workstation", "surface",
    )

    if any(keyword in hostname for keyword in workstation_keywords):
        return "Workstation"

    if open_ports.intersection({135, 139, 445, 3389}):
        return "Workstation"

    # 7. Mobile device
    mobile_keywords = (
        "phone", "android", "iphone", "ipad", "galaxy", "pixel"
    )

    if any(keyword in hostname for keyword in mobile_keywords):
        return "Mobile Device"

    # 8. Gateway fallback
    if is_gateway:
        return "Router"

    # 9. Generic active device
    if is_online or open_ports:
        return "Network Device"

    # 10. Offline / unknown
    return "Unknown Device"


def detect_device_type(ip: str) -> str:
    """Return only the classified device type."""
    info = detect_device_info(ip)
    return info.get("device_type", "Unknown Device")
