
from sqlalchemy import desc

from app.timezone import as_ist
from app.monitoring.monitor import validate_health_check_url
from . import crud
from .detector import detect_device_info, detect_device_type, detect_network_provider


def create_device(
    name: str,
    ip: str,
    device_type: str | None = None,
    network_type: str | None = None,
    service_port: int | None = None,
    health_check_url: str | None = None,
):
    name = name.strip()
    ip = str(ip).strip()

    if not name:
        raise ValueError("Device name cannot be empty")

    existing_device = crud.get_device_by_ip(ip)

    if existing_device is not None:
        raise ValueError("A device with this IP address already exists")

    health_check_url = validate_health_check_url(health_check_url)

    # Detect the device type automatically unless explicitly supplied.
    if not device_type or not device_type.strip():
        device_type = detect_device_type(ip)

    if not network_type or not network_type.strip():
        network_type = detect_network_provider(ip).get("network_type")

    return crud.create_device(
        name=name,
        ip=ip,
        device_type=device_type,
        network_type=network_type,
        service_port=service_port,
        health_check_url=health_check_url,
    )


def _attach_monitoring_data(devices):
    """Attach the latest monitoring status and timestamp to each device."""
    if not devices:
        return devices

    try:
        from database.database import SessionLocal
        from app.monitoring.model import MonitoringHistory

        db = SessionLocal()

        try:
            for device in devices:
                record = (
                    db.query(MonitoringHistory)
                    .filter(MonitoringHistory.ip == device.ip)
                    .order_by(
                        desc(MonitoringHistory.checked_at),
                        desc(MonitoringHistory.id),
                    )
                    .first()
                )

                if record:
                    device.status = record.status
                    device.last_seen = (
                        as_ist(record.checked_at).isoformat()
                        if record.checked_at
                        else None
                    )
                else:
                    device.status = "Unknown"
                    device.last_seen = None

        finally:
            db.close()

    except Exception as exc:
        print(f"MONITORING STATUS ERROR: {exc}")

        for device in devices:
            device.status = "Unknown"
            device.last_seen = None

    return devices


def get_devices():
    devices = crud.get_all_devices()
    return _attach_monitoring_data(devices)


def get_device(device_id: int):
    device = crud.get_device_by_id(device_id)

    if device is None:
        return None

    _attach_monitoring_data([device])
    return device


def update_device(
    device_id: int,
    name: str | None = None,
    ip: str | None = None,
    device_type: str | None = None,
    network_type: str | None = None,
    service_port: int | None = None,
    health_check_url: str | None = None,
    update_service_port: bool = False,
    update_health_check_url: bool = False,
):
    current_device = crud.get_device_by_id(device_id)

    if current_device is None:
        return None

    if update_health_check_url:
        health_check_url = validate_health_check_url(health_check_url)

    if name is not None:
        name = name.strip()

        if not name:
            raise ValueError("Device name cannot be empty")

    if ip is not None:
        ip = str(ip).strip()

        existing_device = crud.get_device_by_ip(ip)

        if (
            existing_device is not None
            and existing_device.id != device_id
        ):
            raise ValueError(
                "A device with this IP address already exists"
            )

        # Re-detect the device type when its IP changes.
        if ip != current_device.ip:
            if not device_type:
                device_type = detect_device_type(ip)
            if not network_type:
                network_type = detect_network_provider(ip).get("network_type")

    return crud.update_device(
        device_id=device_id,
        name=name,
        ip=ip,
        device_type=device_type,
        network_type=network_type,
        service_port=service_port,
        health_check_url=health_check_url,
        update_service_port=update_service_port,
        update_health_check_url=update_health_check_url,
    )


def redetect_device(device_id: int):
    device = crud.get_device_by_id(device_id)

    if device is None:
        return None

    detected_type = detect_device_type(device.ip)
    network_type = detect_network_provider(device.ip).get("network_type")

    return crud.update_device(
        device_id=device_id,
        device_type=detected_type,
        network_type=network_type,
    )


def detect_ip(ip: str):
    return detect_device_info(ip)


def delete_device(device_id: int):
    return crud.delete_device(device_id)


def delete_all_devices():
    return crud.delete_all_devices()
