from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.timezone import now_ist_naive
from database.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )

    name = Column(
        String,
        nullable=False,
        index=True
    )

    ip = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )
    mac_address = Column(String(17), nullable=True, unique=True, index=True)

    device_type = Column(
        String,
        nullable=False,
        default="Unknown Device",
        index=True
    )

    network_type = Column(
        String,
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    source = Column(
        String(16),
        nullable=False,
        default="manual",
        server_default="manual",
        index=True,
    )

    service_port = Column(Integer, nullable=True)
    health_check_url = Column(String(2048), nullable=True)
    speed_agent_seen_at = Column(DateTime, nullable=True)
    topology_hidden = Column(Boolean, nullable=False, default=False, server_default="0")

    created_at = Column(
        DateTime,
        default=now_ist_naive,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=now_ist_naive,
        onupdate=now_ist_naive,
        nullable=False
    )