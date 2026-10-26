from app.alerts.model import Alert
from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import DeviceBandwidthHistory
from app.topology.graph import TopologyGraphBuilder
from database.database import SessionLocal

from .csv_report import generate_devices_csv
from .pdf_report import generate_executive_summary_pdf


def get_devices_report_csv() -> str:
    """Generate and return CSV string of all registered devices."""
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        return generate_devices_csv(devices)
    finally:
        db.close()


def get_executive_summary_pdf() -> bytes:
    """Generate and return comprehensive executive network health PDF report."""
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        total_alert_count = db.query(Alert).count()
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(50).all()
        total_speed_test_count = db.query(DeviceBandwidthHistory).count()
        bw_records = (
            db.query(DeviceBandwidthHistory)
            .order_by(DeviceBandwidthHistory.tested_at.desc())
            .limit(50)
            .all()
        )

        recent_monitoring = (
            db.query(MonitoringHistory)
            .order_by(MonitoringHistory.checked_at.desc())
            .limit(100)
            .all()
        )
        latest_status = {}
        for m in recent_monitoring:
            if m.ip not in latest_status:
                latest_status[m.ip] = m.status

        for device in devices:
            latest_status.setdefault(device.ip, getattr(device, "status", "Unknown") or "Unknown")

        online_count = sum(1 for device in devices if latest_status.get(device.ip) == "Online")
        health = round(online_count / len(devices) * 100.0, 1) if devices else 100.0
        topology = TopologyGraphBuilder(
            devices=devices,
            statuses=latest_status,
            include_wan=True,
            connected_only=False,
        ).build()

        return generate_executive_summary_pdf(
            devices=devices,
            alerts=alerts,
            bandwidth_records=bw_records,
            health_score=health,
            monitoring_records=recent_monitoring,
            latest_status=latest_status,
            topology=topology,
            total_alert_count=total_alert_count,
            total_speed_test_count=total_speed_test_count,
        )
    finally:
        db.close()
