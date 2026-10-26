import ipaddress

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator, model_validator


class AgentDeviceResult(BaseModel):
    ip: IPvAnyAddress
    status: str = Field(pattern="^(Online|Offline|Unknown)$")
    latency_ms: float | None = Field(default=None, ge=0)


class AgentScanResults(BaseModel):
    devices: list[AgentDeviceResult] = Field(max_length=4096)
    network: str | None = None

    @field_validator("network")
    @classmethod
    def validate_network(cls, network):
        if network is None:
            return None
        try:
            parsed = ipaddress.ip_network(network, strict=False)
        except ValueError as exc:
            raise ValueError("Network must be a valid private IPv4 CIDR.") from exc
        if (
            not isinstance(parsed, ipaddress.IPv4Network)
            or not parsed.is_private
            or parsed.num_addresses > 4096
        ):
            raise ValueError(
                "Network must be a private IPv4 CIDR with at most 4096 addresses."
            )
        return str(parsed)

    @field_validator("devices")
    @classmethod
    def reject_duplicate_ips(cls, devices):
        ips = [str(device.ip) for device in devices]
        if len(ips) != len(set(ips)):
            raise ValueError("Each device IP may appear only once per scan")
        return devices

    @model_validator(mode="after")
    def devices_must_belong_to_reported_network(self):
        if self.network is not None:
            network = ipaddress.ip_network(self.network)
            for device in self.devices:
                try:
                    address = ipaddress.IPv4Address(str(device.ip))
                except ipaddress.AddressValueError as exc:
                    raise ValueError(
                        "Scanned device IPs must be IPv4 addresses."
                    ) from exc
                if address not in network:
                    raise ValueError(
                        "Every scanned device must belong to the reported network."
                    )
        return self


class AgentSpeedTestClaim(BaseModel):
    local_ips: list[IPvAnyAddress] = Field(min_length=1, max_length=16)


class AgentSpeedTestResult(BaseModel):
    ip: IPvAnyAddress
    download_mbps: float | None = Field(default=None, ge=0)
    upload_mbps: float | None = Field(default=None, ge=0)
    ping_ms: float | None = Field(default=None, ge=0)
    error: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_transfer_results_for_success(self):
        if self.error is None and (
            self.download_mbps is None or self.upload_mbps is None
        ):
            raise ValueError("Download and upload speeds are required for a successful test.")
        return self
