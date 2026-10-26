from collections import defaultdict
import ipaddress
from typing import Any

from app.timezone import now_ist
from app.devices.detector import is_default_gateway, is_likely_gateway_ip
from app.devices.model import Device
from .schema import (
    SubnetInfo,
    TopologyEdge,
    TopologyGraphResponse,
    TopologyNode,
    TopologySummary
)


class TopologyGraphBuilder:
    """
    Builds the dynamic network topology graph by analyzing registered devices,
    grouping subnets, identifying default gateways, inferring network links,
    and calculating 2D visual layout coordinates.
    """

    def __init__(
        self,
        devices: list[Any],
        statuses: dict[str, str] | None = None,
        latencies: dict[str, float | None] | None = None,
        include_wan: bool = True,
        connected_only: bool = False,
        grouping_network: str | None = None,
    ):
        self.devices = devices
        self.statuses = statuses or {}
        self.latencies = latencies or {}
        self.include_wan = include_wan
        self.connected_only = connected_only
        self.grouping_network = (
            ipaddress.ip_network(grouping_network, strict=False)
            if grouping_network
            else None
        )

        self.nodes: dict[str, TopologyNode] = {}
        self.edges: dict[str, TopologyEdge] = {}
        self.subnets: dict[str, SubnetInfo] = {}

    def build(self) -> TopologyGraphResponse:
        """Run all phases to produce the final dynamic TopologyGraphResponse."""
        self._create_device_nodes()
        self._group_subnets_and_assign_roles()
        self._infer_automatic_links()
        self._calculate_coordinates()
        self._update_connection_counts()

        summary = self._generate_summary()

        return TopologyGraphResponse(
            nodes=list(self.nodes.values()),
            edges=list(self.edges.values()),
            subnets=list(self.subnets.values()),
            summary=summary,
            generated_at=now_ist()
        )
    def _create_device_nodes(self):
        """Convert each registered or discovered Device into a TopologyNode."""
        for dev in self.devices:
            if isinstance(dev, dict):
                dev_id = dev.get("id")
                ip = str(dev.get("ip", "")).strip()
                name = dev.get("name") or dev.get("hostname") or f"Device-{ip}"
                dev_type = dev.get("device_type") or "Unknown Device"
                source = dev.get("source", "discovery")
                mac_addr = dev.get("mac_address")
                open_ports = dev.get("open_ports") or []
                status = dev.get("status") or self.statuses.get(ip, "Online")
                is_gw_hint = dev.get("is_gateway", False)
                latency = dev.get("latency_ms") or self.latencies.get(ip)
            else:
                dev_id = getattr(dev, "id", None)
                ip = str(getattr(dev, "ip", "")).strip()
                name = getattr(dev, "name", None) or f"Device-{ip}"
                dev_type = getattr(dev, "device_type", None) or "Unknown Device"
                source = getattr(dev, "source", None) or "manual"
                mac_addr = getattr(dev, "mac_address", None)
                open_ports = getattr(dev, "open_ports", []) or []
                status = self.statuses.get(ip) or getattr(dev, "status", "Unknown")
                is_gw_hint = getattr(dev, "is_gateway", False)
                latency = self.latencies.get(ip) or getattr(dev, "latency_ms", None)

            if not ip:
                continue

            # If connected_only is enabled, skip any device that is not Online
            if self.connected_only and status != "Online":
                continue

            node_id = f"device-{dev_id}" if dev_id is not None else f"dev-{ip.replace('.', '-')}"

            is_gw = (
                is_gw_hint
                or is_default_gateway(ip)
                or is_likely_gateway_ip(ip)
                or "router" in dev_type.lower()
                or "gateway" in dev_type.lower()
            )

            dtype = dev_type.lower()
            if "router" in dtype or "gateway" in dtype:
                layer = 1
                role = "gateway"
            elif "switch" in dtype or "access point" in dtype or "hub" in dtype:
                layer = 2
                role = "switch"
            elif "server" in dtype or "database" in dtype or "nas" in dtype:
                layer = 3
                role = "server"
            elif "workstation" in dtype or "pc" in dtype or "laptop" in dtype:
                layer = 4
                role = "endpoint"
            elif "printer" in dtype or "camera" in dtype or "cctv" in dtype or "mobile" in dtype:
                layer = 5
                role = "peripheral"
            else:
                layer = 4
                role = "endpoint"

            self.nodes[node_id] = TopologyNode(
                id=node_id,
                device_id=dev_id if isinstance(dev_id, int) else None,
                name=name,
                ip=ip,
                mac_address=mac_addr,
                device_type=dev_type,
                source=source,
                status=status,
                role=role,
                layer=layer,
                subnet=None,
                is_gateway=is_gw,
                open_ports=open_ports,
                latency_ms=latency,
                x=0.0,
                y=0.0,
                connections_count=0
            )

    def _group_subnets_and_assign_roles(self):
        """Group devices into CIDR subnets and locate subnet gateways."""
        subnet_devices = defaultdict(list)

        for node in self.nodes.values():
            if node.role == "wan" or node.id == "wan-internet-root":
                continue
            try:
                ip_obj = ipaddress.ip_address(node.ip)
                prefix = 24 if ip_obj.version == 4 else 64
                network = ipaddress.ip_network(f"{ip_obj}/{prefix}", strict=False)
                if self.grouping_network and ip_obj in self.grouping_network:
                    network = self.grouping_network
                cidr = str(network)
                node.subnet = cidr
                subnet_devices[cidr].append(node)
            except Exception:
                node.subnet = "Unknown"

        # Build SubnetInfo objects
        for cidr, dev_list in subnet_devices.items():
            try:
                net = ipaddress.ip_network(cidr, strict=False)
                net_addr = str(net.network_address)
                netmask = str(net.netmask)
                total_hosts = net.num_addresses - 2 if net.num_addresses > 2 else net.num_addresses
            except Exception:
                net_addr = "0.0.0.0"
                netmask = "255.255.255.0"
                total_hosts = len(dev_list)

            online_count = sum(1 for d in dev_list if d.status == "Online")

            gw_node = next(
                (d for d in dev_list if d.is_gateway or d.role == "gateway"),
                None
            )
            if not gw_node:
                gw_node = next(
                    (d for d in dev_list if d.ip.endswith(".1") or d.ip.endswith(".254")),
                    None
                )
            if gw_node:
                gw_node.is_gateway = True
                gw_node.role = "gateway"
                gw_node.layer = 1

            self.subnets[cidr] = SubnetInfo(
                subnet=cidr,
                network_address=net_addr,
                netmask=netmask,
                total_hosts=max(total_hosts, len(dev_list)),
                device_count=len(dev_list),
                online_count=online_count,
                gateway_ip=gw_node.ip if gw_node else None,
                device_ips=[d.ip for d in dev_list]
            )

    def _infer_automatic_links(self):
        """
        Infer network topology links:
        1. WAN Root -> Gateway/Routers
        2. Gateway -> Switches
        3. Switches -> Subnet Endpoints
        4. If no switch on subnet: Gateway -> Subnet Endpoints directly
        """
        gateways = [n for n in self.nodes.values() if (n.is_gateway or n.role == "gateway") and n.role != "wan"]

        if not gateways and self.nodes:
            non_wan_nodes = [n for n in self.nodes.values() if n.role != "wan"]
            if non_wan_nodes:
                potential_gw = next(
                    (n for n in non_wan_nodes if n.ip.endswith(".1") or n.ip.endswith(".254")),
                    non_wan_nodes[0]
                )
                potential_gw.is_gateway = True
                potential_gw.role = "gateway"
                potential_gw.layer = 1
                gateways = [potential_gw]

        # 1. WAN Root Node Link
        if self.include_wan and gateways:
            online_gateways = [g for g in gateways if g.status == "Online"]
            gws_for_wan = online_gateways if self.connected_only else gateways

            if gws_for_wan:
                wan_id = "wan-internet-root"
                if wan_id not in self.nodes:
                    self.nodes[wan_id] = TopologyNode(
                        id=wan_id,
                        device_id=None,
                        name="Internet / WAN Gateway",
                        ip="0.0.0.0",
                        mac_address=None,
                        device_type="WAN",
                        source="system",
                        status="Online",
                        role="wan",
                        layer=0,
                        subnet="0.0.0.0/0",
                        is_gateway=True,
                        open_ports=[80, 443],
                        latency_ms=1.0,
                        x=450.0,
                        y=50.0,
                        connections_count=0
                    )

                for gw in gws_for_wan:
                    edge_key = self._canonical_edge_key(wan_id, gw.id)
                    if edge_key not in self.edges:
                        link_st = "active" if gw.status == "Online" else "down"
                        if self.connected_only and link_st != "active":
                            continue
                        self.edges[edge_key] = TopologyEdge(
                            id=f"edge-wan-{gw.id}",
                            source=wan_id,
                            target=gw.id,
                            source_ip="0.0.0.0",
                            target_ip=gw.ip,
                            link_type="uplink",
                            speed_mbps=1000.0,
                            status=link_st,
                            latency_ms=gw.latency_ms or 5.0,
                            interface_source="WAN0",
                            interface_target="eth0"
                        )

        # 2. Connect within each subnet
        for cidr in self.subnets:
            subnet_nodes = [
                n for n in self.nodes.values()
                if n.subnet == cidr and n.role != "wan"
            ]

            gw_in_subnet = next((n for n in subnet_nodes if n.role == "gateway"), None)
            if not gw_in_subnet and gateways:
                gw_in_subnet = gateways[0]

            switches = [n for n in subnet_nodes if n.role == "switch"]
            endpoints = [n for n in subnet_nodes if n.role in ("endpoint", "server", "peripheral")]

            if switches:
                for sw in switches:
                    if gw_in_subnet and sw.id != gw_in_subnet.id:
                        edge_key = self._canonical_edge_key(gw_in_subnet.id, sw.id)
                        if edge_key not in self.edges:
                            link_status = "active" if (gw_in_subnet.status == "Online" and sw.status == "Online") else "down"
                            if self.connected_only and link_status != "active":
                                continue
                            self.edges[edge_key] = TopologyEdge(
                                id=f"edge-{gw_in_subnet.id}-{sw.id}",
                                source=gw_in_subnet.id,
                                target=sw.id,
                                source_ip=gw_in_subnet.ip,
                                target_ip=sw.ip,
                                link_type="fiber" if "core" in sw.name.lower() else "ethernet",
                                speed_mbps=1000.0,
                                status=link_status,
                                latency_ms=sw.latency_ms or 1.0,
                                interface_source="Trunk1",
                                interface_target="Uplink1"
                            )

                for idx, ep in enumerate(endpoints):
                    assigned_switch = switches[idx % len(switches)]
                    edge_key = self._canonical_edge_key(assigned_switch.id, ep.id)
                    if edge_key not in self.edges:
                        link_status = "active" if (assigned_switch.status == "Online" and ep.status == "Online") else "down"
                        if self.connected_only and link_status != "active":
                            continue
                        self.edges[edge_key] = TopologyEdge(
                            id=f"edge-{assigned_switch.id}-{ep.id}",
                            source=assigned_switch.id,
                            target=ep.id,
                            source_ip=assigned_switch.ip,
                            target_ip=ep.ip,
                            link_type="wifi" if "mobile" in ep.device_type.lower() else "ethernet",
                            speed_mbps=1000.0,
                            status=link_status,
                            latency_ms=ep.latency_ms or 2.0,
                            interface_source=f"Port {idx + 1}",
                            interface_target="eth0"
                        )
            else:
                if gw_in_subnet:
                    for idx, ep in enumerate(endpoints):
                        if ep.id == gw_in_subnet.id:
                            continue
                        edge_key = self._canonical_edge_key(gw_in_subnet.id, ep.id)
                        if edge_key not in self.edges:
                            link_status = "active" if (gw_in_subnet.status == "Online" and ep.status == "Online") else "down"
                            if self.connected_only and link_status != "active":
                                continue
                            self.edges[edge_key] = TopologyEdge(
                                id=f"edge-{gw_in_subnet.id}-{ep.id}",
                                source=gw_in_subnet.id,
                                target=ep.id,
                                source_ip=gw_in_subnet.ip,
                                target_ip=ep.ip,
                                link_type="wifi" if "mobile" in ep.device_type.lower() else "ethernet",
                                speed_mbps=1000.0,
                                status=link_status,
                                latency_ms=ep.latency_ms or 2.0,
                                interface_source=f"LAN {idx + 1}",
                                interface_target="eth0"
                            )

    def _calculate_coordinates(self):
        """Organize nodes into visually balanced, hierarchical tiers."""
        layers = defaultdict(list)
        for node in self.nodes.values():
            layers[node.layer].append(node)

        y_step = 140.0
        start_y = 60.0

        for layer_num, layer_nodes in layers.items():
            count = len(layer_nodes)
            if count == 0:
                continue

            y_pos = start_y + (layer_num * y_step)
            spacing = 180.0
            total_width = (count - 1) * spacing
            start_x = 450.0 - (total_width / 2.0)

            for i, node in enumerate(layer_nodes):
                node.x = round(start_x + (i * spacing), 1)
                node.y = round(y_pos, 1)

    def _update_connection_counts(self):
        """Calculate degree of connectivity for each node."""
        counts = defaultdict(int)
        for edge in self.edges.values():
            counts[edge.source] += 1
            counts[edge.target] += 1

        for node_id, node in self.nodes.items():
            node.connections_count = counts[node_id]

    def _generate_summary(self) -> TopologySummary:
        """Calculate network aggregate summary statistics."""
        real_nodes = [n for n in self.nodes.values() if n.role != "wan" and n.id != "wan-internet-root"]
        total_nodes = len(real_nodes)
        online_nodes = sum(1 for n in real_nodes if n.status == "Online")
        offline_nodes = total_nodes - online_nodes

        routers = sum(1 for n in real_nodes if n.role == "gateway" or "router" in n.device_type.lower())
        switches = sum(1 for n in real_nodes if n.role == "switch" or "switch" in n.device_type.lower())
        servers = sum(1 for n in real_nodes if n.role == "server" or "server" in n.device_type.lower())
        workstations = sum(1 for n in real_nodes if n.role == "endpoint" or "workstation" in n.device_type.lower())
        printers = sum(1 for n in real_nodes if "printer" in n.device_type.lower())
        others = total_nodes - (routers + switches + servers + workstations + printers)

        total_edges = len(self.edges)
        active_edges = sum(1 for e in self.edges.values() if e.status == "active")

        health_score = round((online_nodes / total_nodes * 100.0), 1) if total_nodes > 0 else 100.0

        return TopologySummary(
            total_nodes=total_nodes,
            online_nodes=online_nodes,
            offline_nodes=offline_nodes,
            total_edges=total_edges,
            active_edges=active_edges,
            routers_count=routers,
            switches_count=switches,
            servers_count=servers,
            workstations_count=workstations,
            printers_count=printers,
            other_devices_count=max(others, 0),
            subnets_count=len(self.subnets),
            network_health_score=health_score
        )

    @staticmethod
    def _canonical_edge_key(node_a: str, node_b: str) -> str:
        """Create an undirected canonical key to prevent duplicate inverted edges."""
        return f"{min(node_a, node_b)}--{max(node_a, node_b)}"


def is_protected_gateway(device: Any) -> bool:
    """Protect devices the topology identifies as gateways or core routers."""
    ip = str(getattr(device, "ip", "")).strip()
    device_type = str(getattr(device, "device_type", "")).lower()
    name = str(getattr(device, "name", "")).lower()
    return (
        is_default_gateway(ip)
        or is_likely_gateway_ip(ip)
        or "router" in device_type
        or "gateway" in device_type
        or "router" in name
        or "gateway" in name
    )
