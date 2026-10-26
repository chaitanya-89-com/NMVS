
from datetime import datetime

from app.timezone import IndiaTimeModel
from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip: IPvAnyAddress
    network_type: str | None = Field(default=None, min_length=1, max_length=100)
    service_port: int | None = Field(default=None, ge=1, le=65535)
    health_check_url: str | None = Field(default=None, max_length=2048)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class DeviceUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    ip: IPvAnyAddress | None = None
    network_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    service_port: int | None = Field(default=None, ge=1, le=65535)
    health_check_url: str | None = Field(default=None, max_length=2048)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class DeviceResponse(IndiaTimeModel):
    id: int
    name: str
    ip: str
    device_type: str
    network_type: str
    source: str
    service_port: int | None = None
    health_check_url: str | None = None
    created_at: datetime
    updated_at: datetime
    status: str | None = None
    last_seen: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DeviceDetectResponse(BaseModel):
    ip: str
    device_type: str
    status: str

    hostname: str | None = None
    open_ports: list[int] = Field(default_factory=list)
    mac_address: str | None = None
    is_gateway: bool = False

    # Automatically detected network provider information
    isp: str | None = None
    asn: str | None = None
    network_type: str = "Unknown"
    public_ip: str | None = None

    model_config = ConfigDict(from_attributes=True)
