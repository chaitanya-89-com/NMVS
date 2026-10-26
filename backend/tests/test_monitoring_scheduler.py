import asyncio
import unittest
from unittest.mock import MagicMock, patch

from app.monitoring.model import MonitoringHistory
from app.monitoring.scheduler import get_device_history, monitor_devices


class StopScheduler(Exception):
    pass


class MonitoringSchedulerTests(unittest.TestCase):
    def test_get_device_history_queries_requested_device(self):
        history_records = [object()]
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = history_records

        with patch("app.monitoring.scheduler.SessionLocal", return_value=session):
            result = get_device_history("192.0.2.1", limit=5)

        self.assertEqual(result, history_records)
        session.query.assert_called_once_with(MonitoringHistory)
        session.close.assert_called_once_with()

    def test_scheduler_waits_only_for_remaining_interval(self):
        delays = []
        results = [{"ip": "192.0.2.1", "status": "Online"}]

        async def stop_after_cycle(delay):
            delays.append(delay)
            raise StopScheduler()

        with (
            patch(
                "app.monitoring.scheduler.update_device_status_from_monitor",
                return_value=results,
            ),
            patch("app.monitoring.scheduler.persist_monitoring_results"),
            patch("app.monitoring.scheduler.asyncio.sleep", side_effect=stop_after_cycle),
        ):
            with self.assertRaises(StopScheduler):
                asyncio.run(monitor_devices(interval=30))

        self.assertEqual(len(delays), 1)
        self.assertGreaterEqual(delays[0], 0)
        self.assertLessEqual(delays[0], 30)


if __name__ == "__main__":
    unittest.main()
