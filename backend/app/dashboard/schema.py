from datetime import datetime
from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict, Field


class DashboardStats(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    offline_devices: int = 0
    network_health_score: float = 0.0
    unknown_devices: int = 0
    total_subnets: int = 0
    total_users: int = 0
    latest_download_mbps: float | None = None
    latest_upload_mbps: float | None = None
    latest_ping_ms: float | None = None


class DeviceTypeDistribution(BaseModel):
    device_type: str
    count: int


class RecentActivity(IndiaTimeModel):
    id: int
    ip: str
    device_name: str | None = None
    status: str
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecentSpeedTest(IndiaTimeModel):
    id: int
    ip: str
    download_mbps: float | None = None
    upload_mbps: float | None = None
    ping_ms: float | None = None
    measurement_source: str
    tested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardOverviewResponse(IndiaTimeModel):
    stats: DashboardStats
    device_types: list[DeviceTypeDistribution]
    recent_monitoring: list[RecentActivity]
    recent_speed_tests: list[RecentSpeedTest]
    generated_at: datetime
