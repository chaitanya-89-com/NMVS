from collections import Counter
import ipaddress
from sqlalchemy import func

from app.timezone import now_ist
from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import DeviceBandwidthHistory
from app.users.model import User
from database.database import SessionLocal

from .schema import (
    DashboardOverviewResponse,
    DashboardStats,
    DeviceTypeDistribution,
    RecentActivity,
    RecentSpeedTest
)


def get_dashboard_overview() -> DashboardOverviewResponse:
    """
    Aggregate system metrics, device status breakdown, bandwidth speeds,
    and recent activity into a single unified dashboard payload.
    """
    db = SessionLocal()
    try:
        # 1. Fetch devices
        devices = db.query(Device).all()
        total_devices = len(devices)
        ip_to_name = {d.ip: d.name for d in devices}

        # Device type breakdown
        type_counts = Counter(d.device_type or "Unknown Device" for d in devices)
        device_types = [
            DeviceTypeDistribution(device_type=dtype, count=cnt)
            for dtype, cnt in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Subnet counts
        subnets_set = set()
        for d in devices:
            try:
                net = ipaddress.ip_interface(f"{d.ip}/24").network
                subnets_set.add(str(net))
            except Exception:
                pass
        total_subnets = len(subnets_set)

        # 2. Latest status per device from MonitoringHistory
        recent_monitoring_records = (
            db.query(MonitoringHistory)
            .order_by(MonitoringHistory.checked_at.desc())
            .limit(10)
            .all()
        )

        device_statuses: dict[str, str] = {}
        # Fetch sufficient history to know current status of all devices
        latest_history_ids = (
            db.query(
                MonitoringHistory.ip,
                func.max(MonitoringHistory.id).label("latest_id"),
            )
            .group_by(MonitoringHistory.ip)
            .subquery()
        )
        latest_history = (
            db.query(MonitoringHistory)
            .join(latest_history_ids, MonitoringHistory.id == latest_history_ids.c.latest_id)
            .all()
        )
        latest_status = {record.ip: record.status for record in latest_history}
        device_statuses = {
            device.ip: latest_status.get(device.ip, "Unknown")
            for device in devices
        }
        online_devices = sum(1 for status in device_statuses.values() if status == "Online")
        offline_devices = sum(1 for status in device_statuses.values() if status == "Offline")
        unknown_devices = total_devices - online_devices - offline_devices
        known_devices = online_devices + offline_devices
        health_score = round(online_devices / known_devices * 100.0, 1) if known_devices else 0.0

        recent_monitoring = [
            RecentActivity(
                id=rec.id,
                ip=rec.ip,
                device_name=ip_to_name.get(rec.ip),
                status=rec.status,
                checked_at=rec.checked_at
            )
            for rec in recent_monitoring_records
        ]

        # 3. Latest bandwidth tests
        recent_speed_records = (
            db.query(DeviceBandwidthHistory)
            .order_by(DeviceBandwidthHistory.tested_at.desc())
            .limit(5)
            .all()
        )
        recent_speed_tests = [
            RecentSpeedTest(
                id=sp.id,
                ip=sp.ip,
                download_mbps=sp.download_mbps,
                upload_mbps=sp.upload_mbps,
                ping_ms=sp.ping_ms,
                measurement_source=sp.measurement_source,
                tested_at=sp.tested_at
            )
            for sp in recent_speed_records
        ]

        latest_speed = recent_speed_records[0] if recent_speed_records else None
        latest_download = latest_speed.download_mbps if latest_speed else None
        latest_upload = latest_speed.upload_mbps if latest_speed else None
        latest_ping = latest_speed.ping_ms if latest_speed else None

        # 4. User counts
        try:
            total_users = db.query(User).count()
        except Exception:
            total_users = 0

        stats = DashboardStats(
            total_devices=total_devices,
            online_devices=online_devices,
            offline_devices=offline_devices,
            network_health_score=health_score,
            unknown_devices=unknown_devices,
            total_subnets=total_subnets,
            total_users=total_users,
            latest_download_mbps=latest_download,
            latest_upload_mbps=latest_upload,
            latest_ping_ms=latest_ping
        )

        return DashboardOverviewResponse(
            stats=stats,
            device_types=device_types,
            recent_monitoring=recent_monitoring,
            recent_speed_tests=recent_speed_tests,
            generated_at=now_ist()
        )

    finally:
        db.close()


def get_dashboard_stats() -> DashboardStats:
    """Return quick KPI statistics without detailed record lists."""
    overview = get_dashboard_overview()
    return overview.stats
