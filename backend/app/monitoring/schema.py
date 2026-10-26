from datetime import datetime
from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict


class MonitoringResponse(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip: str
    status: str
    check_result: str | None = None
    detail: str | None = None
    latency_ms: float | None = None
    latency_method: str | None = None
    icmp_result: str | None = None
    tcp_result: str | None = None
    tcp_response_ms: float | None = None
    http_status_code: int | None = None
    http_response_ms: float | None = None
    http_health_status: str | None = None
    checked_at: datetime


class DeviceAvailability(BaseModel):
    device_id: int
    device_name: str
    ip: str
    range_days: int
    latest_status: str
    successful_checks: int
    failed_checks: int
    unknown_checks: int
    uptime_percent: float | None
    average_latency_ms: float | None
    latest_latency_ms: float | None
    latest_latency_method: str | None