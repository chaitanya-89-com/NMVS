from concurrent.futures import ThreadPoolExecutor
import ipaddress
import logging

from app.devices import crud as device_crud
from app.devices.model import Device
from app.discovery.ping import check_device_status
from app.monitoring.model import MonitoringHistory
from app.timezone import now_ist, now_ist_naive
from database.database import SessionLocal

from .graph import TopologyGraphBuilder, is_protected_gateway
from .schema import (
    SubnetInfo,
    TopologyGraphResponse,
    TopologySummary
)

logger = logging.getLogger(__name__)


def get_topology_graph(
    refresh_status: bool = False,
    include_wan: bool = True,
    connected_only: bool = True,
    source: str | None = None,
    grouping_network: str | None = None,
) -> TopologyGraphResponse:
    """
    Build and return the dynamic network topology graph.
    Combines registered devices, live/cached statuses, inferred links, and subnets.
    If connected_only is True, filters to only connect Online/discovered active devices.
    """
    db = SessionLocal()
    try:
        devices = [
            device
            for device in device_crud.get_all_devices(source=source)
            if not device.topology_hidden
        ]

        statuses: dict[str, str] = {}
        latencies: dict[str, float | None] = {}

        if refresh_status and devices:
            # Concurrently check device statuses
            def _ping(dev):
                res = check_device_status(dev.ip)
                return dev.ip, res.get("status", "Offline")

            with ThreadPoolExecutor(max_workers=min(len(devices), 25)) as executor:
                results = list(executor.map(_ping, devices))
                for ip, st in results:
                    statuses[ip] = st
        else:
            try:
                recent_histories = (
                    db.query(MonitoringHistory)
                    .filter(MonitoringHistory.ip.in_([device.ip for device in devices]))
                    .order_by(MonitoringHistory.checked_at.desc())
                    .all()
                )
                for h in recent_histories:
                    if h.ip not in statuses:
                        statuses[h.ip] = h.status
            except Exception:
                recent_histories = []

            for d in devices:
                if d.ip not in statuses:
                    statuses[d.ip] = "Unknown"

        builder = TopologyGraphBuilder(
            devices=devices,
            statuses=statuses,
            latencies=latencies,
            include_wan=include_wan,
            connected_only=connected_only,
            grouping_network=grouping_network,
        )
        return builder.build()

    finally:
        db.close()


def get_topology_summary(connected_only: bool = True) -> TopologySummary:
    """Return high-level summary metrics of the network topology."""
    graph = get_topology_graph(refresh_status=False, include_wan=False, connected_only=connected_only)
    return graph.summary


def get_subnets(connected_only: bool = True) -> list[SubnetInfo]:
    """Return list of detected subnets and their host distribution."""
    graph = get_topology_graph(refresh_status=False, include_wan=False, connected_only=connected_only)
    return graph.subnets


def get_discovery_topology(
    network: str | None = None,
    auto_register: bool = False,
    include_wan: bool = True
) -> TopologyGraphResponse:
    """
    Discovers connected devices on the network and constructs a
    dynamic connected topology graph for discovered connected devices only.
    """
    from app.discovery.scanner import scan_network
    from app.devices.detector import detect_device_info

    target_network = network
    if not target_network:
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            target_network = str(ipaddress.ip_interface(f"{local_ip}/24").network)
        except Exception:
            target_network = "192.168.1.0/24"

    raw_devices = scan_network(target_network)
    online_ips = [d["ip"] for d in raw_devices if d.get("status") == "Online"]

    discovered = []
    max_workers = min(len(online_ips), 20) if online_ips else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for info in executor.map(detect_device_info, online_ips):
            if info.get("status") == "Online":
                discovered.append({
                    "ip": info["ip"],
                    "name": info.get("hostname") or f"Device-{info['ip']}",
                    "device_type": info.get("device_type", "Unknown Device"),
                    "network_type": info.get("network_type", "Unknown"),
                    "source": "discovery",
                    "status": "Online",
                    "mac_address": info.get("mac_address"),
                    "open_ports": info.get("open_ports", []),
                    "is_gateway": info.get("is_gateway", False)
                })

    db = SessionLocal()
    try:
        suppressed_devices = (
                db.query(Device.ip, Device.mac_address)
                .filter(Device.topology_hidden.is_(True))
                .all()
        )
        suppressed_ips = {row.ip for row in suppressed_devices}
        suppressed_mac_by_ip = {
            row.ip: row.mac_address
            for row in suppressed_devices
            if row.mac_address
        }
        suppressed_macs = {
                row.mac_address for row in suppressed_devices if row.mac_address
        }
    finally:
        db.close()
    discovered = [
        device
        for device in discovered
        if not (
        device.get("mac_address") in suppressed_macs
        or (
            device["ip"] in suppressed_ips
            and (
                not device.get("mac_address")
                or not suppressed_mac_by_ip.get(device["ip"])
            )
        )
        )
    ]

    if not auto_register:
        return TopologyGraphBuilder(
            devices=discovered,
            statuses={d["ip"]: "Online" for d in discovered},
            include_wan=include_wan,
            connected_only=True,
            grouping_network=target_network,
        ).build()

    network_object = ipaddress.ip_network(target_network, strict=False)
    db = SessionLocal()
    try:
        for dev_data in discovered:
            device = None
            mac_address = dev_data.get("mac_address")
            if mac_address:
                device = (
                    db.query(Device)
                    .filter(Device.mac_address == mac_address)
                    .first()
                )
            ip_device = (
                db.query(Device)
                .filter(Device.ip == dev_data["ip"])
                .first()
            )
            if device is None:
                device = ip_device
            elif ip_device is not None and ip_device.id != device.id:
                raise ValueError(
                    "A discovered device IP is already assigned to a different inventory record."
                )

            if device is None:
                device = Device(
                    name=dev_data["name"],
                    ip=dev_data["ip"],
                    device_type=dev_data["device_type"],
                    network_type=dev_data["network_type"],
                    source="discovery",
                    mac_address=mac_address,
                    created_at=now_ist_naive(),
                    updated_at=now_ist_naive(),
                )
                db.add(device)
            else:
                if (
                    device.topology_hidden
                    and device.mac_address
                    and mac_address
                    and device.mac_address != mac_address
                ):
                    device.topology_hidden = False
                device.ip = dev_data["ip"]
                if device.source != "manual":
                    device.source = dev_data["source"]
                    device.name = dev_data["name"]
                    device.device_type = dev_data["device_type"]
                    device.network_type = dev_data["network_type"]
                if mac_address:
                    device.mac_address = mac_address
                device.updated_at = now_ist_naive()

            db.add(MonitoringHistory(
                ip=dev_data["ip"],
                status="Online",
                check_result="success",
                detail="Reachability result reported by network discovery.",
                checked_at=now_ist(),
            ))
        db.commit()

        devices = [
            device
            for device in device_crud.get_all_devices()
            if ipaddress.ip_address(device.ip) in network_object
            and not device.topology_hidden
        ]
        histories = (
            db.query(MonitoringHistory)
            .filter(MonitoringHistory.ip.in_([device.ip for device in devices]))
            .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
            .all()
        ) if devices else []
        statuses = {}
        for history in histories:
            statuses.setdefault(history.ip, history.status)
        return TopologyGraphBuilder(
            devices=devices,
            statuses=statuses,
            include_wan=include_wan,
            connected_only=True,
            grouping_network=target_network,
        ).build()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist latest network discovery results")
        raise
    finally:
        db.close()


def get_hidden_devices() -> list[dict]:
    db = SessionLocal()
    try:
        devices = (
            db.query(Device)
            .filter(Device.topology_hidden.is_(True))
            .order_by(Device.name.asc(), Device.id.asc())
            .all()
        )
        return [
            {
                "id": device.id,
                "name": device.name,
                "ip": device.ip,
                "mac_address": device.mac_address,
                "device_type": device.device_type,
                "source": device.source,
                "is_gateway": is_protected_gateway(device),
            }
            for device in devices
        ]
    finally:
        db.close()


def set_device_topology_hidden(device_id: int, hidden: bool) -> dict:
    if hidden:
        graph = get_topology_graph(
            refresh_status=False,
            include_wan=False,
            connected_only=False,
        )
        topology_node = next(
            (node for node in graph.nodes if node.device_id == device_id),
            None,
        )
        if topology_node is not None and topology_node.is_gateway:
            raise PermissionError(
                "Gateway and critical router devices cannot be removed from Topology."
            )
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device is None:
            raise LookupError("Device not found.")
        if hidden and is_protected_gateway(device):
            raise PermissionError("Gateway and critical router devices cannot be removed from Topology.")
        device.topology_hidden = hidden
        db.commit()
        return {
            "id": device.id,
            "name": device.name,
            "ip": device.ip,
            "topology_hidden": device.topology_hidden,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
