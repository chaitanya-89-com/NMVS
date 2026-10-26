from datetime import datetime
from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    device_id: int | None = None
    device_name: str | None = None
    device_ip: str
    title: str | None = None
    alert_type: str = Field(
        default="DISCONNECTED",
        description="Type: DISCONNECTED, CONNECTED, HIGH_LATENCY, NEW_DEVICE, etc."
    )
    severity: str = Field(
        default="critical",
        description="Severity: critical, warning, info"
    )
    message: str


class AlertResponse(IndiaTimeModel):
    id: int
    device_id: int | None = None
    device_name: str | None = None
    device_ip: str
    title: str | None = None
    alert_type: str
    severity: str
    message: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlertsSummary(BaseModel):
    total_alerts: int = 0
    active_alerts: int = 0
    disconnected_count: int = 0
    connected_count: int = 0
    critical_alerts: int = 0
    warning_alerts: int = 0
    resolved_alerts: int = 0
