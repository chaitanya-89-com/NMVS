from datetime import datetime
from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict, Field


class TopologyNode(BaseModel):
    """
    Representation of a node in the network topology graph.
    """
    id: str = Field(description="Unique node identifier (e.g. 'device-1' or 'wan-internet-root')")
    device_id: int | None = Field(default=None, description="Database Device ID if registered")
    name: str = Field(description="Human readable name or hostname")
    ip: str = Field(description="IP address or network gateway")
    mac_address: str | None = Field(default=None, description="MAC address if detected")
    device_type: str = Field(default="Unknown Device", description="Device type classification")
    source: str = Field(default="manual", description="Device source: manual or discovery")
    status: str = Field(default="Unknown", description="Online, Offline, or Unknown")
    role: str = Field(
        default="endpoint",
        description="Role in topology: wan, gateway, core, switch, server, endpoint, peripheral"
    )
    layer: int = Field(
        default=4,
        description="Hierarchical layer: 0=WAN, 1=Gateway, 2=Switch/AP, 3=Server, 4=Endpoint, 5=Peripheral"
    )
    subnet: str | None = Field(default=None, description="CIDR subnet prefix (e.g. 192.168.1.0/24)")
    is_gateway: bool = Field(default=False, description="Whether device functions as a gateway")
    open_ports: list[int] = Field(default_factory=list, description="List of detected open TCP ports")
    latency_ms: float | None = Field(default=None, description="Latest latency in milliseconds")
    x: float = Field(default=0.0, description="X coordinate in visual layout canvas")
    y: float = Field(default=0.0, description="Y coordinate in visual layout canvas")
    connections_count: int = Field(default=0, description="Number of connected links")

    model_config = ConfigDict(from_attributes=True)


class TopologyEdge(BaseModel):
    """
    Representation of an inferred connection/edge between two nodes in the network topology graph.
    """
    id: str = Field(description="Unique edge identifier")
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    source_ip: str = Field(description="Source device IP")
    target_ip: str = Field(description="Target device IP")
    link_type: str = Field(
        default="ethernet",
        description="Type of connection: ethernet, wifi, fiber, uplink"
    )
    speed_mbps: float | None = Field(default=1000.0, description="Estimated link speed in Mbps")
    status: str = Field(default="active", description="active or down")
    latency_ms: float | None = Field(default=None, description="Link latency in ms")
    interface_source: str | None = Field(default=None, description="Source port or interface")
    interface_target: str | None = Field(default=None, description="Target port or interface")

    model_config = ConfigDict(from_attributes=True)


class SubnetInfo(BaseModel):
    """
    Detailed information about a detected network subnet.
    """
    subnet: str
    network_address: str
    netmask: str
    total_hosts: int
    device_count: int
    online_count: int
    gateway_ip: str | None = None
    device_ips: list[str] = Field(default_factory=list)


class TopologySummary(BaseModel):
    """
    High-level aggregate statistics of the network topology.
    """
    total_nodes: int = 0
    online_nodes: int = 0
    offline_nodes: int = 0
    total_edges: int = 0
    active_edges: int = 0
    routers_count: int = 0
    switches_count: int = 0
    servers_count: int = 0
    workstations_count: int = 0
    printers_count: int = 0
    other_devices_count: int = 0
    subnets_count: int = 0
    network_health_score: float = 100.0


class TopologyGraphResponse(IndiaTimeModel):
    """
    Complete dynamic topology graph response for direct frontend canvas rendering.
    """
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    subnets: list[SubnetInfo]
    summary: TopologySummary
    generated_at: datetime
