from sqlalchemy import Column, DateTime, Float, Integer, String

from app.timezone import now_ist
from database.database import Base


class MonitoringHistory(Base):
    __tablename__ = "monitoring_history"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    check_result = Column(String, nullable=True)
    detail = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    latency_method = Column(String(16), nullable=True)
    icmp_result = Column(String(16), nullable=True)
    tcp_result = Column(String(16), nullable=True)
    tcp_response_ms = Column(Float, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    http_response_ms = Column(Float, nullable=True)
    http_health_status = Column(String(16), nullable=True)
    checked_at = Column(
        DateTime(timezone=True),
        default=now_ist,
        nullable=False
    )