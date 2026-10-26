from database.database import SessionLocal
from .model import DeviceBandwidthHistory


def get_history(limit: int = 20, ip: str = None):
    db = SessionLocal()
    try:
        query = db.query(DeviceBandwidthHistory)
        if ip:
            query = query.filter(DeviceBandwidthHistory.ip == ip)
        return (
            query.order_by(DeviceBandwidthHistory.tested_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_history_by_id(history_id: int):
    db = SessionLocal()
    try:
        return (
            db.query(DeviceBandwidthHistory)
            .filter(DeviceBandwidthHistory.id == history_id)
            .first()
        )
    finally:
        db.close()


def delete_history_item(history_id: int):
    db = SessionLocal()
    try:
        record = (
            db.query(DeviceBandwidthHistory)
            .filter(DeviceBandwidthHistory.id == history_id)
            .first()
        )
        if record:
            db.delete(record)
            db.commit()
            return True
        return False
    finally:
        db.close()