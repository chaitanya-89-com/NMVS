from pydantic import BaseModel, Field


class DeviceUptimeMetric(BaseModel):
    device_ip: str
    device_name: str
    device_type: str
    total_checks: int
    online_checks: int
    offline_checks: int
    unknown_checks: int = 0
    uptime_percentage: float | None = Field(default=None, description="Uptime percentage from 0.0 to 100.0%")
    current_status: str


class NetworkMetricsSummary(BaseModel):
    overall_network_uptime: float | None = None
    average_latency_ms: float | None = None
    average_download_mbps: float | None = None
    average_upload_mbps: float | None = None
    total_devices_evaluated: int = 0
    healthy_devices_count: int = 0
    degraded_devices_count: int = 0
    unmonitored_devices_count: int = 0
