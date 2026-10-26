import unittest
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.devices.model import Device
from app.metrics import service
from app.monitoring.model import MonitoringHistory
from app.timezone import now_ist_naive
from database.database import Base


class MetricsServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.session_patch = patch(
            "app.metrics.service.SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def add_device(self, ip):
        with self.session_factory() as db:
            device = Device(
                name=ip,
                ip=ip,
                device_type="Test device",
                network_type="Test",
                source="manual",
            )
            db.add(device)
            db.commit()

    def add_check(self, ip, status):
        with self.session_factory() as db:
            db.add(MonitoringHistory(
                ip=ip,
                status=status,
                check_result={
                    "Online": "success",
                    "Offline": "failed",
                    "Unknown": "unknown",
                }[status],
                checked_at=now_ist_naive() - timedelta(minutes=1),
            ))
            db.commit()

    def test_uptime_excludes_unknown_and_counts_unknown_separately(self):
        ip = "192.0.2.10"
        self.add_device(ip)
        self.add_check(ip, "Online")
        self.add_check(ip, "Offline")
        self.add_check(ip, "Unknown")

        metrics = service.get_devices_uptime()

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].total_checks, 3)
        self.assertEqual(metrics[0].online_checks, 1)
        self.assertEqual(metrics[0].offline_checks, 1)
        self.assertEqual(metrics[0].unknown_checks, 1)
        self.assertEqual(metrics[0].uptime_percentage, 50.0)
        self.assertEqual(metrics[0].current_status, "Unknown")

    def test_unknown_only_and_no_history_do_not_invent_uptime(self):
        unknown_ip = "192.0.2.11"
        unmonitored_ip = "192.0.2.12"
        self.add_device(unknown_ip)
        self.add_device(unmonitored_ip)
        self.add_check(unknown_ip, "Unknown")

        metrics = {
            item.device_ip: item
            for item in service.get_devices_uptime()
        }
        self.assertIsNone(metrics[unknown_ip].uptime_percentage)
        self.assertEqual(metrics[unknown_ip].unknown_checks, 1)
        self.assertIsNone(metrics[unmonitored_ip].uptime_percentage)
        self.assertEqual(metrics[unmonitored_ip].total_checks, 0)

    def test_network_summary_excludes_unknown_from_availability(self):
        online_ip = "192.0.2.13"
        unknown_ip = "192.0.2.14"
        self.add_device(online_ip)
        self.add_device(unknown_ip)
        self.add_check(online_ip, "Online")
        self.add_check(unknown_ip, "Unknown")

        summary = service.get_metrics_summary()

        self.assertEqual(summary.overall_network_uptime, 100.0)
        self.assertEqual(summary.total_devices_evaluated, 2)
        self.assertEqual(summary.healthy_devices_count, 1)
        self.assertEqual(summary.degraded_devices_count, 0)
        self.assertEqual(summary.unmonitored_devices_count, 1)


if __name__ == "__main__":
    unittest.main()
