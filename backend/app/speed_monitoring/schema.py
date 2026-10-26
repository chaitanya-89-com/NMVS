from datetime import datetime
from typing import Optional
from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict


class DeviceSpeedTestRequest(BaseModel):
    ip: str


class DeviceSpeedTestJobResponse(IndiaTimeModel):
    id: int
    ip: str
    status: str
    error: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    download_mbps: float | None = None
    upload_mbps: float | None = None
    ping_ms: float | None = None
    measurement_source: str | None = None

class SpeedTestResponse(BaseModel):
    ip: str = "backend"
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    server: Optional[str] = None
    isp: Optional[str] = None
    client_ip: Optional[str] = None
    error: Optional[str] = None


class SpeedTestHistoryItem(IndiaTimeModel):
    id: int
    ip: str
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    measurement_source: str
    tested_at: datetime

    model_config = ConfigDict(from_attributes=True)