from datetime import timedelta

from app.config import settings
from database.database import SessionLocal
from app.devices import crud as device_crud
from app.monitoring.model import MonitoringHistory
from app.timezone import now_ist
from . import crud
from .model import Alert
from .schema import AlertsSummary


def get_alerts(
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = 50
) -> list[Alert]:
    """Retrieve list of alerts with optional status, severity, and alert_type filters."""
    db = SessionLocal()
    try:
        return crud.get_alerts(
            db,
            status=status,
            severity=severity,
            alert_type=alert_type,
            limit=limit
        )
    finally:
        db.close()


def get_alert_by_id(alert_id: int) -> Alert | None:
    """Retrieve a single alert by ID."""
    db = SessionLocal()
    try:
        return crud.get_alert_by_id(db, alert_id)
    finally:
        db.close()


def create_alert(
    device_ip: str,
    message: str,
    title: str | None = None,
    device_id: int | None = None,
    device_name: str | None = None,
    alert_type: str = "DISCONNECTED",
    severity: str = "critical"
) -> Alert:
    """Manually or programmatically create an alert."""
    db = SessionLocal()
    try:
        if not device_id or not device_name:
            dev = device_crud.get_device_by_ip(device_ip.strip())
            if dev:
                device_id = device_id or dev.id
                device_name = device_name or dev.name

        return crud.create_alert(
            db=db,
            device_ip=device_ip.strip(),
            message=message.strip(),
            title=title,
            device_id=device_id,
            device_name=device_name,
            alert_type=alert_type,
            severity=severity,
            status="active"
        )
    finally:
        db.close()


def acknowledge_alert(alert_id: int) -> Alert | None:
    """Mark an alert as acknowledged."""
    db = SessionLocal()
    try:
        return crud.update_alert_status(db, alert_id, "acknowledged")
    finally:
        db.close()


def resolve_alert(alert_id: int) -> Alert | None:
    """Mark an alert as resolved."""
    db = SessionLocal()
    try:
        return crud.update_alert_status(db, alert_id, "resolved")
    finally:
        db.close()


def delete_alert(alert_id: int) -> bool:
    """Delete an alert by ID."""
    db = SessionLocal()
    try:
        return crud.delete_alert(db, alert_id)
    finally:
        db.close()


def get_summary() -> AlertsSummary:
    """Return counts of total, active, disconnected, connected, critical, warning, and resolved alerts."""
    db = SessionLocal()
    try:
        return crud.get_alerts_summary(db)
    finally:
        db.close()


def check_and_create_device_status_alert(ip: str, new_status: str, old_status: str | None = None):
    """
    Hook called during device monitoring:
    - If device went Offline: triggers a DISCONNECTED alert.
    - If device is newly observed Online or recovers to Online: resolves disconnect alerts
      and logs a CONNECTED alert.
    """
    db = SessionLocal()
    try:
        dev = device_crud.get_device_by_ip(ip)
        dev_name = dev.name if dev else ip
        dev_id = dev.id if dev else None
        current_status = new_status.strip().lower()
        previous_status = old_status.strip().lower() if old_status else None

        if current_status == "offline":
            # Check if active DISCONNECTED alert already exists for this IP to prevent duplicate spam
            existing_active = (
                db.query(Alert)
                .filter(
                    Alert.device_ip == ip,
                    Alert.status.in_(("active", "acknowledged")),
                    Alert.alert_type == "DISCONNECTED"
                )
                .first()
            )
            if not existing_active:
                crud.create_alert(
                    db=db,
                    device_id=dev_id,
                    device_name=dev_name,
                    device_ip=ip,
                    title=f"Device Disconnected: {dev_name}",
                    alert_type="DISCONNECTED",
                    severity="critical",
                    message=f"Device '{dev_name}' ({ip}) disconnected from the network and is unreachable.",
                    status="active"
                )

        elif current_status == "online":
            # Resolve disconnect alerts once the device is reachable again.
            active_disconnects = (
                db.query(Alert)
                .filter(
                    Alert.device_ip == ip,
                    Alert.status.in_(("active", "acknowledged")),
                    Alert.alert_type == "DISCONNECTED"
                )
                .all()
            )
            for a in active_disconnects:
                crud.update_alert_status(db, a.id, "resolved")

            # A missing previous status means this is the first monitoring check.
            if previous_status != "online" or active_disconnects:
                crud.create_alert(
                    db=db,
                    device_id=dev_id,
                    device_name=dev_name,
                    device_ip=ip,
                    title=f"Device Connected: {dev_name}",
                    alert_type="CONNECTED",
                    severity="info",
                    message=f"Device '{dev_name}' ({ip}) is connected to the network and responding.",
                    status="resolved"
                )

    finally:
        db.close()


def process_monitoring_alerts(
    ip: str,
    device_name: str,
    status: str,
    check_result: str | None,
    latency_ms: float | None,
    http_health_status: str | None,
    old_status: str | None = None,
) -> None:
    """Apply configured monitoring thresholds with active-alert deduplication."""
    db = SessionLocal()
    try:
        def active_alert(alert_type: str):
            return (
                db.query(Alert)
                .filter(
                    Alert.device_ip == ip,
                    Alert.alert_type == alert_type,
                    Alert.status.in_(("active", "acknowledged")),
                )
                .first()
            )

        def raise_alert(alert_type: str, title: str, message: str, severity: str):
            if not active_alert(alert_type):
                crud.create_alert(
                    db=db,
                    device_ip=ip,
                    device_name=device_name,
                    title=title,
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    status="active",
                )

        def resolve_alert(alert_type: str) -> bool:
            resolved_any = False
            open_alerts = (
                db.query(Alert)
                .filter(
                    Alert.device_ip == ip,
                    Alert.alert_type == alert_type,
                    Alert.status.in_(("active", "acknowledged")),
                )
                .all()
            )
            for alert in open_alerts:
                crud.update_alert_status(db, alert.id, "resolved")
                resolved_any = True
            return resolved_any

        recovered_conditions = []
        if status == "Online":
            recovered_disconnect = resolve_alert("DISCONNECTED")
            recovered_unknown = resolve_alert("STATUS_UNKNOWN")
            if recovered_disconnect or recovered_unknown or old_status not in (None, "Online"):
                crud.create_alert(
                    db=db,
                    device_ip=ip,
                    device_name=device_name,
                    title=f"Device Connected: {device_name}",
                    alert_type="CONNECTED",
                    severity="info",
                    message=f"Device '{device_name}' ({ip}) responded to a reachability check.",
                    status="resolved",
                )
        elif status == "Offline":
            resolve_alert("STATUS_UNKNOWN")
            raise_alert(
                "DISCONNECTED",
                f"Device disconnected: {device_name}",
                (
                    f"The monitoring check explicitly reported '{device_name}' ({ip}) "
                    "as unreachable. The exact cause is unknown."
                ),
                "critical",
            )
        else:
            if old_status == "Online":
                raise_alert(
                    "STATUS_UNKNOWN",
                    f"Device status uncertain: {device_name}",
                    (
                        f"The latest scheduled check could not verify '{device_name}' ({ip}). "
                        "This is not proof that the device is offline; additional checks will continue."
                    ),
                    "warning",
                )
            recent_checks = (
                db.query(MonitoringHistory)
                .filter(MonitoringHistory.ip == ip)
                .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
                .limit(settings.MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS)
                .all()
            )
            consecutive_unreachable = 0
            for record in recent_checks:
                if record.status == "Online":
                    break
                consecutive_unreachable += 1
            if consecutive_unreachable >= settings.MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS:
                raise_alert(
                    "DISCONNECTED",
                    f"Device not responding: {device_name}",
                    (
                        f"No successful reachability check for '{device_name}' ({ip}) "
                        f"in {consecutive_unreachable} consecutive checks. Latest status: {status}. "
                        "A failed check does not establish the exact cause."
                    ),
                    "critical",
                )
                resolve_alert("STATUS_UNKNOWN")

        if latency_ms is not None and latency_ms > settings.MONITORING_HIGH_LATENCY_MS:
            raise_alert(
                "HIGH_LATENCY",
                f"High latency: {device_name}",
                (
                    f"Measured latency to '{device_name}' ({ip}) was {latency_ms:.2f} ms, "
                    f"above the configured {settings.MONITORING_HIGH_LATENCY_MS:.2f} ms threshold."
                ),
                "warning",
            )
        elif latency_ms is not None:
            if resolve_alert("HIGH_LATENCY"):
                recovered_conditions.append("latency returned below its threshold")

        uptime_records = (
            db.query(MonitoringHistory)
            .filter(
                MonitoringHistory.ip == ip,
                MonitoringHistory.checked_at
                >= now_ist() - timedelta(hours=24),
            )
            .all()
        )
        successful_checks = sum(record.status == "Online" for record in uptime_records)
        failed_checks = sum(
            record.status == "Offline" or record.check_result == "failed"
            for record in uptime_records
        )
        verified_checks = successful_checks + failed_checks
        uptime_percent = (
            successful_checks * 100 / verified_checks if verified_checks else None
        )
        if (
            uptime_percent is not None
            and uptime_percent < settings.MONITORING_UPTIME_THRESHOLD_PERCENT
        ):
            raise_alert(
                "UPTIME_LOW",
                f"Low uptime: {device_name}",
                (
                    f"Check-based uptime for '{device_name}' ({ip}) over the last 24 hours "
                    f"is {uptime_percent:.2f}%, below the configured "
                    f"{settings.MONITORING_UPTIME_THRESHOLD_PERCENT:.2f}% threshold. "
                    "Unknown checks and unobserved time are excluded."
                ),
                "warning",
            )
        elif uptime_percent is not None:
            if resolve_alert("UPTIME_LOW"):
                recovered_conditions.append("uptime returned above its threshold")

        if http_health_status == "unhealthy":
            raise_alert(
                "HTTP_UNHEALTHY",
                f"HTTP health check failed: {device_name}",
                f"The configured HTTP health check for '{device_name}' ({ip}) returned an unhealthy response.",
                "warning",
            )
        elif http_health_status == "healthy":
            if resolve_alert("HTTP_UNHEALTHY"):
                recovered_conditions.append("HTTP health check recovered")

        if recovered_conditions:
            crud.create_alert(
                db=db,
                device_ip=ip,
                device_name=device_name,
                title=f"Monitoring recovered: {device_name}",
                alert_type="RECOVERY",
                severity="info",
                message=f"'{device_name}' ({ip}): {'; '.join(recovered_conditions)}.",
                status="resolved",
            )
    finally:
        db.close()
