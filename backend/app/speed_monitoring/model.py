from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from app.timezone import as_ist, now_ist_naive
from database.database import Base


class DeviceBandwidthHistory(Base):
    __tablename__ = "device_bandwidth_history"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    download_mbps = Column(Float, nullable=True)
    upload_mbps = Column(Float, nullable=True)
    ping_ms = Column(Float, nullable=True)
    measurement_source = Column(
        String(32),
        nullable=False,
        default="legacy_backend_label",
        server_default="legacy_backend_label",
    )
    tested_at = Column(
        DateTime,
        default=now_ist_naive,
        nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ip": self.ip,
            "download_mbps": self.download_mbps,
            "upload_mbps": self.upload_mbps,
            "ping_ms": self.ping_ms,
            "measurement_source": self.measurement_source,
            "tested_at": as_ist(self.tested_at).isoformat()
        }


SpeedTestHistory = DeviceBandwidthHistory


class DeviceSpeedTestJob(Base):
    __tablename__ = "device_speed_test_jobs"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="queued", index=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_ist_naive, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    download_mbps = Column(Float, nullable=True)
    upload_mbps = Column(Float, nullable=True)
    ping_ms = Column(Float, nullable=True)


class AgentDiscoveredNetwork(Base):
    __tablename__ = "agent_discovered_networks"

    cidr = Column(String(43), primary_key=True)
    last_reported_at = Column(DateTime, nullable=False, default=now_ist_naive)