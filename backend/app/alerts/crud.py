from sqlalchemy.orm import Session
from app.timezone import now_ist_naive
from .model import Alert
from .schema import AlertsSummary


def get_alerts(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    limit: int = 50
) -> list[Alert]:
    """Retrieve alerts with optional filtering by status, severity, and alert_type."""
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type.upper())
    return query.order_by(Alert.created_at.desc()).limit(limit).all()


def get_alert_by_id(db: Session, alert_id: int) -> Alert | None:
    """Retrieve single alert by ID."""
    return db.query(Alert).filter(Alert.id == alert_id).first()


def create_alert(
    db: Session,
    device_ip: str,
    message: str,
    title: str | None = None,
    device_id: int | None = None,
    device_name: str | None = None,
    alert_type: str = "DISCONNECTED",
    severity: str = "critical",
    status: str = "active"
) -> Alert:
    """Create and persist a new alert record."""
    clean_type = alert_type.upper().strip()

    if not title:
        if clean_type == "DISCONNECTED":
            title = f"Device Disconnected: {device_name or device_ip}"
        elif clean_type == "CONNECTED":
            title = f"Device Connected: {device_name or device_ip}"
        elif clean_type == "HIGH_LATENCY":
            title = f"High Latency: {device_name or device_ip}"
        else:
            title = f"Alert: {device_name or device_ip}"

    alert = Alert(
        device_id=device_id,
        device_name=device_name,
        device_ip=device_ip.strip(),
        title=title,
        alert_type=clean_type,
        severity=severity.lower(),
        message=message.strip(),
        status=status,
        created_at=now_ist_naive()
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def update_alert_status(
    db: Session,
    alert_id: int,
    new_status: str
) -> Alert | None:
    """Update status of an alert (e.g., acknowledged, resolved)."""
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        return None

    alert.status = new_status
    if new_status == "resolved":
        alert.resolved_at = now_ist_naive()

    db.commit()
    db.refresh(alert)
    return alert


def delete_alert(db: Session, alert_id: int) -> bool:
    """Delete an alert record by ID."""
    alert = get_alert_by_id(db, alert_id)
    if not alert:
        return False
    db.delete(alert)
    db.commit()
    return True


def get_alerts_summary(db: Session) -> AlertsSummary:
    """Return counts of total, active, disconnected, connected, critical, warning, and resolved alerts."""
    alerts = db.query(Alert).all()
    total = len(alerts)
    active = sum(1 for a in alerts if a.status == "active")
    disconnected = sum(1 for a in alerts if a.alert_type == "DISCONNECTED")
    connected = sum(1 for a in alerts if a.alert_type == "CONNECTED")
    critical = sum(1 for a in alerts if a.status == "active" and a.severity == "critical")
    warning = sum(1 for a in alerts if a.status == "active" and a.severity == "warning")
    resolved = sum(1 for a in alerts if a.status == "resolved")

    return AlertsSummary(
        total_alerts=total,
        active_alerts=active,
        disconnected_count=disconnected,
        connected_count=connected,
        critical_alerts=critical,
        warning_alerts=warning,
        resolved_alerts=resolved
    )
