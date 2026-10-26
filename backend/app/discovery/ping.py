import platform
import socket
import subprocess
import ipaddress


def check_device_status(ip: str, tcp_port: int | None = None) -> dict[str, str | int]:
    """
    Check device reachability using ICMP and, optionally, one TCP service port.
    """
    ip_str = str(ip)

    try:
        ipaddress.ip_address(ip_str)
    except ValueError:
        return {"ip": ip_str, "status": "Offline", "checked_by": "none"}

    if tcp_port is not None and not 1 <= tcp_port <= 65535:
        raise ValueError("TCP port must be between 1 and 65535")

    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", "1000", ip_str]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip_str]

    ping_command_failed = False
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return {"ip": ip_str, "status": "Online", "checked_by": "ICMP"}
    except subprocess.TimeoutExpired:
        pass
    except OSError:
        ping_command_failed = True

    if tcp_port is not None:
        try:
            with socket.create_connection((ip_str, tcp_port), timeout=1):
                return {
                    "ip": ip_str,
                    "status": "Online",
                    "checked_by": f"TCP/{tcp_port}",
                }
        except ConnectionRefusedError:
            return {
                "ip": ip_str,
                "status": "Online",
                "checked_by": f"TCP/{tcp_port}",
                "detail": f"The device responded, but TCP port {tcp_port} refused the connection.",
            }
        except OSError:
            detail = (
                f"No response from TCP port {tcp_port}, and the ICMP check could not run."
                if ping_command_failed
                else (
                    f"No ICMP reply or connection to TCP port {tcp_port}. "
                    "This does not prove the device is offline."
                )
            )
            return {
                "ip": ip_str,
                "status": "Unknown",
                "checked_by": f"ICMP and TCP/{tcp_port}",
                "detail": detail,
            }

    return {
        "ip": ip_str,
        "status": "Unknown",
        "checked_by": "ICMP",
        "detail": (
            "The ICMP ping command could not run."
            if ping_command_failed
            else "No ICMP reply. The device may be online but block ping."
        ),
    }


def ping_device(ip: str, tcp_port: int | None = None) -> dict[str, str | int]:
    return check_device_status(ip, tcp_port)