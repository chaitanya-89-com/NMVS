import ipaddress
from datetime import datetime, timedelta

from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from app.timezone import as_ist, now_ist_naive
from database.database import SessionLocal
from . import crud
from .model import AgentDiscoveredNetwork, DeviceBandwidthHistory, DeviceSpeedTestJob
from .speed_test import run_speed_test


DEVICE_ONLINE_MAX_AGE_SECONDS = 120
DEVICE_SPEED_TEST_TIMEOUT_SECONDS = 180
DEVICE_SPEED_AGENT_MAX_AGE_SECONDS = 90

INVALID_IPV4_MESSAGE = "Invalid IP address. Please enter a valid IPv4 address."
DEVICE_NOT_FOUND_MESSAGE = (
    "Device not found. Please enter an IP address belonging to a device discovered by NMVS."
)
OUTSIDE_NETWORK_MESSAGE = "Device IP is outside the configured NMVS network."


class InvalidDeviceIPv4(ValueError):
    pass


class DeviceOutsideConfiguredNetwork(ValueError):
    pass


class ConfiguredNetworkUnavailable(ConnectionError):
    pass


class DeviceTestUnavailable(ConnectionError):
    pass


def _parse_device_ipv4(ip: str) -> ipaddress.IPv4Address:
    try:
        return ipaddress.IPv4Address(ip)
    except (ipaddress.AddressValueError, TypeError) as exc:
        raise InvalidDeviceIPv4(INVALID_IPV4_MESSAGE) from exc


def run_live_test() -> dict:
    """Measure the backend host's internet connection, not an individual device."""
    return run_speed_test()


def _latest_device_history(db, ip: str):
    return (
        db.query(MonitoringHistory)
        .filter(MonitoringHistory.ip == ip)
        .order_by(MonitoringHistory.checked_at.desc(), MonitoringHistory.id.desc())
        .first()
    )


def _is_recently_online(history, now: datetime) -> bool:
    if history is None or history.status != "Online":
        return False
    checked_at = as_ist(history.checked_at).replace(tzinfo=None)
    return checked_at >= now - timedelta(seconds=DEVICE_ONLINE_MAX_AGE_SECONDS)


def request_device_test(ip: str) -> dict:
    address = _parse_device_ipv4(ip)
    canonical_ip = str(address)
    db = SessionLocal()
    try:
        now = now_ist_naive()
        configured_networks = (
            db.query(AgentDiscoveredNetwork.cidr)
            .filter(
                AgentDiscoveredNetwork.last_reported_at
                >= now - timedelta(seconds=DEVICE_ONLINE_MAX_AGE_SECONDS)
            )
            .all()
        )
        networks = [ipaddress.ip_network(row.cidr) for row in configured_networks]
        if not networks:
            device = (
                db.query(Device)
                .filter(
                    Device.ip == canonical_ip,
                    Device.source.in_(("agent", "discovery")),
                )
                .first()
            )
            if device is None:
                raise LookupError(DEVICE_NOT_FOUND_MESSAGE)
            raise ConfiguredNetworkUnavailable(
                "The NMVS scanner has not recently reported its configured network. "
                "Start the scanner agent and try again."
            )
        if not any(address in network for network in networks):
            raise DeviceOutsideConfiguredNetwork(OUTSIDE_NETWORK_MESSAGE)

        device = (
            db.query(Device)
            .filter(
                Device.ip == canonical_ip,
                Device.source.in_(("agent", "discovery")),
            )
            .first()
        )
        if device is None:
            raise LookupError(DEVICE_NOT_FOUND_MESSAGE)

        latest = _latest_device_history(db, canonical_ip)
        if not _is_recently_online(latest, now):
            raise DeviceTestUnavailable(
                "This device is offline or its Online report is stale. "
                "Wait for the scanner agent to report it Online and try again."
            )
        if (
            device.speed_agent_seen_at is None
            or as_ist(device.speed_agent_seen_at).replace(tzinfo=None)
            < now - timedelta(seconds=DEVICE_SPEED_AGENT_MAX_AGE_SECONDS)
        ):
            raise DeviceTestUnavailable(
                "The NMVS device agent is not currently available on this device. "
                "Start its device-mode agent and try again."
            )

        existing_job = (
            db.query(DeviceSpeedTestJob)
            .filter(
                DeviceSpeedTestJob.ip == canonical_ip,
                DeviceSpeedTestJob.status.in_(("queued", "running")),
                DeviceSpeedTestJob.expires_at > now,
            )
            .first()
        )
        if existing_job is not None:
            raise DeviceTestUnavailable("A speed test is already in progress for this device.")

        job = DeviceSpeedTestJob(
            ip=canonical_ip,
            status="queued",
            expires_at=now + timedelta(seconds=DEVICE_SPEED_TEST_TIMEOUT_SECONDS),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return {
            "id": job.id,
            "ip": job.ip,
            "status": job.status,
            "created_at": job.created_at,
            "expires_at": job.expires_at,
            "error": None,
        }
    finally:
        db.close()


def claim_device_test(local_ips: list[str]) -> dict | None:
    if not local_ips:
        return None
    db = SessionLocal()
    try:
        now = now_ist_naive()
        (
            db.query(Device)
            .filter(
                Device.ip.in_(local_ips),
                Device.source.in_(("agent", "discovery")),
            )
            .update(
                {Device.speed_agent_seen_at: now},
                synchronize_session=False,
            )
        )
        db.commit()
        job = (
            db.query(DeviceSpeedTestJob)
            .filter(
                DeviceSpeedTestJob.ip.in_(local_ips),
                DeviceSpeedTestJob.status == "queued",
                DeviceSpeedTestJob.expires_at > now,
            )
            .order_by(DeviceSpeedTestJob.created_at.asc(), DeviceSpeedTestJob.id.asc())
            .first()
        )
        if job is None:
            return None
        device = db.query(Device).filter(Device.ip == job.ip).first()
        latest = _latest_device_history(db, job.ip)
        if not _is_recently_online(latest, now):
            job.status = "failed"
            job.error = "Device is no longer recently confirmed Online."
            job.completed_at = now
            db.commit()
            return None
        if device is None or device.source != "agent":
            job.status = "failed"
            job.error = "Device is no longer registered as an agent-discovered device."
            job.completed_at = now
            db.commit()
            return None
        updated = (
            db.query(DeviceSpeedTestJob)
            .filter(
                DeviceSpeedTestJob.id == job.id,
                DeviceSpeedTestJob.status == "queued",
                DeviceSpeedTestJob.expires_at > now,
            )
            .update(
                {DeviceSpeedTestJob.status: "running"},
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.rollback()
            return None
        db.commit()
        return {"id": job.id, "ip": job.ip}
    finally:
        db.close()


def complete_device_test(
    job_id: int,
    ip: str,
    download_mbps: float | None = None,
    upload_mbps: float | None = None,
    ping_ms: float | None = None,
    error: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        job = db.query(DeviceSpeedTestJob).filter(DeviceSpeedTestJob.id == job_id).first()
        if job is None:
            raise LookupError("Speed test job not found.")
        if job.ip != ip or job.status != "running":
            raise ValueError("Speed test result does not match an active device job.")
        if not error and (download_mbps is None or upload_mbps is None):
            raise ValueError("Device speed-test result must include download and upload measurements.")
        now = now_ist_naive()
        if error:
            job.status = "failed"
            job.error = error[:1000]
        else:
            job.download_mbps = download_mbps
            job.upload_mbps = upload_mbps
            job.ping_ms = ping_ms
            db.add(
                DeviceBandwidthHistory(
                    ip=job.ip,
                    download_mbps=download_mbps,
                    upload_mbps=upload_mbps,
                    ping_ms=ping_ms,
                    measurement_source="device-agent",
                )
            )
            job.status = "completed"
            job.error = None
        job.completed_at = now
        db.commit()
        return {
            "id": job.id,
            "ip": job.ip,
            "status": job.status,
            "error": job.error,
            "completed_at": job.completed_at,
            "download_mbps": job.download_mbps,
            "upload_mbps": job.upload_mbps,
            "ping_ms": job.ping_ms,
            "measurement_source": "device-agent" if job.status == "completed" else None,
        }
    finally:
        db.close()


def get_device_test_job(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(DeviceSpeedTestJob).filter(DeviceSpeedTestJob.id == job_id).first()
        if job is None:
            return None
        if job.status in {"queued", "running"} and job.expires_at <= now_ist_naive():
            job.status = "failed"
            job.error = "No device agent completed the test before the request expired."
            job.completed_at = now_ist_naive()
            db.commit()
        return {
            "id": job.id,
            "ip": job.ip,
            "status": job.status,
            "error": job.error,
            "created_at": job.created_at,
            "expires_at": job.expires_at,
            "completed_at": job.completed_at,
            "download_mbps": job.download_mbps,
            "upload_mbps": job.upload_mbps,
            "ping_ms": job.ping_ms,
            "measurement_source": "device-agent" if job.status == "completed" else None,
        }
    finally:
        db.close()


def get_history(limit: int = 20, ip: str = None) -> list:
    """
    Retrieve past speed test records from the database.
    """
    records = crud.get_history(limit=limit, ip=ip)
    return [r.to_dict() for r in records]


def get_history_by_id(history_id: int) -> dict | None:
    """
    Retrieve a specific speed test record by ID from the database.
    """
    record = crud.get_history_by_id(history_id)
    return record.to_dict() if record else None


def delete_history(history_id: int) -> bool:
    """
    Delete a specific speed test record from the database.
    """
    return crud.delete_history_item(history_id)
