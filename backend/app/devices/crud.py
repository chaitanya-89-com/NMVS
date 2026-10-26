
from sqlalchemy.exc import IntegrityError

from app.timezone import now_ist_naive
from database.database import SessionLocal
from .model import Device


def create_device(
    name: str,
    ip: str,
    device_type: str | None = None,
    network_type: str | None = None,
    source: str = "manual",
    service_port: int | None = None,
    health_check_url: str | None = None,
):
    db = SessionLocal()

    try:
        now = now_ist_naive()

        device = Device(
            name=name.strip(),
            ip=str(ip).strip(),
            device_type=(
                device_type.strip()
                if device_type and device_type.strip()
                else "Unknown Device"
            ),
            network_type=(
                network_type.strip()
                if network_type and network_type.strip()
                else "Unknown"
            ),
            source=source,
            service_port=service_port,
            health_check_url=health_check_url,
            created_at=now,
            updated_at=now,
        )

        db.add(device)
        db.commit()
        db.refresh(device)

        return device

    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "A device with this IP address already exists"
        ) from exc

    finally:
        db.close()


def get_all_devices(source: str | None = None):
    db = SessionLocal()

    try:
        query = db.query(Device)
        if source is not None:
            query = query.filter(Device.source == source)
        return query.order_by(Device.id.desc()).all()
    finally:
        db.close()


def get_device_by_id(device_id: int):
    db = SessionLocal()

    try:
        return (
            db.query(Device)
            .filter(Device.id == device_id)
            .first()
        )
    finally:
        db.close()


def get_device_by_ip(ip: str):
    db = SessionLocal()

    try:
        return (
            db.query(Device)
            .filter(Device.ip == str(ip).strip())
            .first()
        )
    finally:
        db.close()


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
    db = SessionLocal()

    try:
        device = (
            db.query(Device)
            .filter(Device.id == device_id)
            .first()
        )

        if device is None:
            return None

        if name is not None:
            name = name.strip()

            if not name:
                raise ValueError("Device name cannot be empty")

            device.name = name

        if ip is not None:
            device.ip = str(ip).strip()

        if device_type is not None:
            device_type = device_type.strip()

            if device_type:
                device.device_type = device_type

        if network_type is not None:
            network_type = network_type.strip()

            if network_type:
                device.network_type = network_type

        if update_service_port:
            device.service_port = service_port

        if update_health_check_url:
            device.health_check_url = health_check_url

        device.updated_at = now_ist_naive()

        db.commit()
        db.refresh(device)

        return device

    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "A device with this IP address already exists"
        ) from exc

    finally:
        db.close()


def delete_device(device_id: int):
    db = SessionLocal()

    try:
        device = (
            db.query(Device)
            .filter(Device.id == device_id)
            .first()
        )

        if device is None:
            return None

        db.delete(device)
        db.commit()

        return True

    finally:
        db.close()


def delete_all_devices():
    db = SessionLocal()

    try:
        count = db.query(Device).delete(synchronize_session=False)
        db.commit()
        return count

    finally:
        db.close()
