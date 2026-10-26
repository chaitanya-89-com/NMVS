import asyncio
import logging
import time

from app.monitoring.service import (
    persist_monitoring_results,
    update_device_status_from_monitor,
)
from app.monitoring.model import MonitoringHistory
from database.database import SessionLocal

logger = logging.getLogger(__name__)


async def monitor_devices(interval: int = 30):
    while True:
        cycle_started = time.monotonic()
        results = []
        try:
            results = await asyncio.to_thread(update_device_status_from_monitor)
            await asyncio.to_thread(persist_monitoring_results, results)
            for result in results:
                logger.info("Monitoring %s: %s", result["ip"], result["status"])

        except Exception as e:
            logger.exception("Monitoring cycle failed: %s", e)

        elapsed = time.monotonic() - cycle_started
        delay = max(0.0, interval - elapsed)
        logger.info(
            "Monitoring cycle checked %d device(s) in %.1fs; next cycle in %.1fs",
            len(results),
            elapsed,
            delay,
        )
        await asyncio.sleep(delay)

def get_device_history(ip: str, limit: int = 20):
    db = SessionLocal()
    try:
        return (
            db.query(MonitoringHistory)
            .filter(MonitoringHistory.ip == ip)
            .order_by(MonitoringHistory.checked_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()