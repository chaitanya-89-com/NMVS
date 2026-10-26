from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.timezone import as_ist, now_ist_naive
from database.database import Base


class Alert(Base):
    """
    Persisted alert generated when network devices connect, disconnect,
    experience high latency, or encounter network anomalies.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    device_name = Column(String, nullable=True)
    device_ip = Column(String, nullable=False, index=True)

    title = Column(
        String,
        nullable=True,
        default="Device Alert"
    )

    alert_type = Column(
        String,
        nullable=False,
        default="DISCONNECTED",
        index=True
    )  # DISCONNECTED, CONNECTED, HIGH_LATENCY, NEW_DEVICE, SYSTEM_ALERT

    severity = Column(
        String,
        nullable=False,
        default="warning",
        index=True
    )  # critical, warning, info

    message = Column(String, nullable=False)

    status = Column(
        String,
        nullable=False,
        default="active",
        index=True
    )  # active, acknowledged, resolved

    created_at = Column(
        DateTime,
        default=now_ist_naive,
        nullable=False,
        index=True
    )
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_ip": self.device_ip,
            "title": self.title,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "status": self.status,
            "created_at": as_ist(self.created_at).isoformat(),
            "resolved_at": as_ist(self.resolved_at).isoformat() if self.resolved_at else None
        }
