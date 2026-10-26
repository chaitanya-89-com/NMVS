from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import logging

from sqlalchemy import and_, case, func, or_

from app.agent.schema import AgentDeviceResult
from app.alerts import service as alert_service
from app.devices.model import Device
from app.timezone import now_ist
from database.database import SessionLocal
from .model import MonitoringHistory
from app.speed_monitoring.model import AgentDiscoveredNetwork
from .monitor import check_device_status, check_http_health

logger = logging.getLogger(__name__)


def _run_checks(ip: str, service_port: int | None = None, health_check_url: str | None = None) -> dict:
    result = check_device_status(ip, service_port)
    if health_check_url:
        try:
            http_result = check_http_health(health_check_url)
        except ValueError as exc:
            http_result = {
                "http_status_code": None,
                "http_response_ms": None,
                "http_health_status": "unknown",
                "http_detail": f"HTTP health check configuration error: {exc}",
            }
        result.update(http_result)
        result["detail"] = " ".join(
            part for part in (result.get("detail"), http_result.get("http_detail")) if part
        )
    return result


def _history_from_result(ip: str, result: dict) -> MonitoringHistory:
    return MonitoringHistory(
        ip=ip,
        status=result["status"],
        check_result=result.get("check_result"),
        detail=result.get("detail"),
        latency_ms=result.get("latency_ms"),
        latency_method=result.get("latency_method"),
        icmp_result=result.get("icmp_result"),
        tcp_result=result.get("tcp_result"),
        tcp_response_ms=result.get("tcp_response_ms"),
        http_status_code=result.get("http_status_code"),
        http_response_ms=result.get("http_response_ms"),
        http_health_status=result.get("http_health_status"),
        checked_at=now_ist(),
    )


def get_device_status(ip: str):
    return check_device_status(ip)


def check_and_save_device(ip: str):
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.ip == ip).first()
        previous_history = (
            db.query(MonitoringHistory)
            .filter(MonitoringHistory.ip == ip)
            .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
            .first()
        )
        result = _run_checks(
            ip,
            device.service_port if device else None,
            device.health_check_url if device else None,
        )
        if device:
            device.status = result["status"]

        record = _history_from_result(ip, result)
        db.add(record)
        db.commit()
        db.refresh(record)
        device_name = device.name if device else ip
    finally:
        db.close()

    alert_service.process_monitoring_alerts(
        ip=ip,
        device_name=device_name,
        status=result["status"],
        check_result=result.get("check_result"),
        latency_ms=result.get("latency_ms"),
        http_health_status=result.get("http_health_status"),
        old_status=previous_history.status if previous_history else None,
    )
    return record


def save_agent_scan_results(
    devices: Sequence[AgentDeviceResult],
    network: str | None = None,
) -> dict[str, int]:
    """Persist the agent's measurements without re-probing from the backend."""
    db = SessionLocal()
    processed = 0
    created = 0
    updated = 0
    alert_events = []

    try:
        if network is not None:
            configured_network = (
                db.query(AgentDiscoveredNetwork)
                .filter(AgentDiscoveredNetwork.cidr == network)
                .first()
            )
            if configured_network is None:
                configured_network = AgentDiscoveredNetwork(cidr=network)
                db.add(configured_network)
            configured_network.last_reported_at = now_ist().replace(tzinfo=None)

        for reported in devices:
            ip = str(reported.ip)
            status = reported.status
            device = db.query(Device).filter(Device.ip == ip).first()
            previous_history = (
                db.query(MonitoringHistory)
                .filter(MonitoringHistory.ip == ip)
                .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
                .first()
            )

            if device is None:
                device = Device(
                    name=f"Agent discovered {ip}",
                    ip=ip,
                    device_type="Unknown Device",
                    network_type="Unknown",
                    source="agent",
                )
                db.add(device)
                created += 1
            else:
                updated += 1
                device.source = "agent"

            check_result = {
                "Online": "success",
                "Offline": "failed",
                "Unknown": "unknown",
            }[status]
            record = MonitoringHistory(
                ip=ip,
                status=status,
                check_result=check_result,
                detail="Reachability result reported by the local NMVS agent.",
                latency_ms=reported.latency_ms,
                latency_method="ICMP" if reported.latency_ms is not None else None,
                icmp_result=check_result,
                checked_at=now_ist(),
            )
            db.add(record)
            alert_events.append({
                "ip": ip,
                "device_name": device.name,
                "status": status,
                "check_result": check_result,
                "latency_ms": reported.latency_ms,
                "old_status": previous_history.status if previous_history else None,
            })
            processed += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    alert_failures = 0
    for event in alert_events:
        try:
            alert_service.process_monitoring_alerts(
                **event,
                http_health_status=None,
            )
        except Exception:
            alert_failures += 1
            logger.exception("Failed to update monitoring alerts for agent result")

    return {
        "processed": processed,
        "devices_created": created,
        "devices_updated": updated,
        "monitoring_records_created": processed,
        "alert_failures": alert_failures,
    }


def update_dynamic_status(ip: str, new_status: str):
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.ip == ip).first()
        if device:
            device.status = new_status
            db.commit()
        return device
    finally:
        db.close()


def update_device_status_from_monitor():
    db = SessionLocal()
    try:
        devices = db.query(Device).filter(Device.source != "agent").all()
        checks = []
        for device in devices:
            previous_history = (
                db.query(MonitoringHistory)
                .filter(MonitoringHistory.ip == device.ip)
                .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
                .first()
            )
            checks.append({
                "device_id": device.id,
                "device_name": device.name,
                "ip": device.ip,
                "service_port": device.service_port,
                "health_check_url": device.health_check_url,
                "old_status": previous_history.status if previous_history else None,
            })
    finally:
        db.close()

    if not checks:
        return []

    def run_check(check: dict) -> dict:
        result = _run_checks(
            check["ip"],
            check["service_port"],
            check["health_check_url"],
        )
        return {
            **result,
            "ip": check["ip"],
            "device_id": check["device_id"],
            "device_name": check["device_name"],
            "old_status": check["old_status"],
        }

    with ThreadPoolExecutor(max_workers=min(len(checks), 25)) as executor:
        results = list(executor.map(run_check, checks))

    db = SessionLocal()
    try:
        for result in results:
            device = db.query(Device).filter(Device.id == result["device_id"]).first()
            if device is not None:
                device.status = result["status"]
        db.commit()
    finally:
        db.close()

    return results


def persist_monitoring_results(results: list[dict]) -> None:
    db = SessionLocal()
    try:
        records = [_history_from_result(result["ip"], result) for result in results]
        db.add_all(records)
        db.commit()
    finally:
        db.close()

    for result in results:
        alert_service.process_monitoring_alerts(
            ip=result["ip"],
            device_name=result.get("device_name") or result["ip"],
            status=result["status"],
            check_result=result.get("check_result"),
            latency_ms=result.get("latency_ms"),
            http_health_status=result.get("http_health_status"),
            old_status=result.get("old_status"),
        )


def calculate_availability(records: list[MonitoringHistory]) -> dict:
    successful = sum(1 for record in records if record.status == "Online")
    failed = sum(
        1
        for record in records
        if record.status != "Online"
        and (record.status == "Offline" or record.check_result == "failed")
    )
    unknown = len(records) - successful - failed
    verified_checks = successful + failed
    latency_records = [record for record in records if record.latency_ms is not None]
    latest_latency = latency_records[0] if latency_records else None
    return {
        "successful_checks": successful,
        "failed_checks": failed,
        "unknown_checks": unknown,
        "uptime_percent": (
            round(successful * 100 / verified_checks, 2)
            if verified_checks
            else None
        ),
        "average_latency_ms": (
            round(sum(record.latency_ms for record in latency_records) / len(latency_records), 2)
            if latency_records
            else None
        ),
        "latest_latency_ms": latest_latency.latency_ms if latest_latency else None,
        "latest_latency_method": latest_latency.latency_method if latest_latency else None,
    }


def get_availability(days: int = 7) -> list[dict]:
    cutoff = now_ist() - timedelta(days=days)
    db = SessionLocal()
    try:
        devices = db.query(Device).order_by(Device.name).all()
        total_count = func.count(MonitoringHistory.id)
        successful_count = func.sum(
            case((MonitoringHistory.status == "Online", 1), else_=0)
        )
        failed_count = func.sum(
            case(
                (
                    and_(
                        MonitoringHistory.status != "Online",
                        or_(
                            MonitoringHistory.status == "Offline",
                            MonitoringHistory.check_result == "failed",
                        ),
                    ),
                    1,
                ),
                else_=0,
            )
        )
        aggregate_rows = (
            db.query(
                MonitoringHistory.ip,
                total_count.label("total"),
                successful_count.label("successful"),
                failed_count.label("failed"),
                func.avg(MonitoringHistory.latency_ms).label("average_latency"),
            )
            .filter(MonitoringHistory.checked_at >= cutoff)
            .group_by(MonitoringHistory.ip)
            .all()
        )
        aggregates = {row.ip: row for row in aggregate_rows}
        results = []
        for device in devices:
            summary = aggregates.get(device.ip)
            successful = int(summary.successful or 0) if summary else 0
            failed = int(summary.failed or 0) if summary else 0
            total = int(summary.total or 0) if summary else 0
            verified = successful + failed
            latest_record = (
                db.query(MonitoringHistory)
                .filter(MonitoringHistory.ip == device.ip)
                .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
                .first()
            )
            latest_latency = (
                db.query(MonitoringHistory)
                .filter(
                    MonitoringHistory.ip == device.ip,
                    MonitoringHistory.checked_at >= cutoff,
                    MonitoringHistory.latency_ms.is_not(None),
                )
                .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
                .first()
            )
            results.append({
                "device_id": device.id,
                "device_name": device.name,
                "ip": device.ip,
                "range_days": days,
                "latest_status": latest_record.status if latest_record else "Unknown",
                "successful_checks": successful,
                "failed_checks": failed,
                "unknown_checks": max(0, total - successful - failed),
                "uptime_percent": (
                    round(successful * 100 / verified, 2) if verified else None
                ),
                "average_latency_ms": (
                    round(float(summary.average_latency), 2)
                    if summary and summary.average_latency is not None
                    else None
                ),
                "latest_latency_ms": latest_latency.latency_ms if latest_latency else None,
                "latest_latency_method": latest_latency.latency_method if latest_latency else None,
            })
        return results
    finally:
        db.close()


def clear_monitoring_history() -> int:
    db = SessionLocal()
    try:
        deleted_count = db.query(MonitoringHistory).delete(synchronize_session=False)
        db.commit()
        return deleted_count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_monitoring_history(ip: str, limit: int = 20, days: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(MonitoringHistory).filter(MonitoringHistory.ip == ip)
        if days is not None:
            query = query.filter(
                MonitoringHistory.checked_at >= now_ist() - timedelta(days=days)
            )
        return (
            query.order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_all_monitoring_history(limit: int = 100, days: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(MonitoringHistory)
        if days is not None:
            query = query.filter(
                MonitoringHistory.checked_at >= now_ist() - timedelta(days=days)
            )
        return (
            query.order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()
