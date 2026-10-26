import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.alerts.model import Alert
from app.alerts.service import (
    check_and_create_device_status_alert,
    process_monitoring_alerts,
)
from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from app.monitoring.service import update_device_status_from_monitor
from database.database import Base


class AlertStatusTransitionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                Device.__table__,
                MonitoringHistory.__table__,
                Alert.__table__,
            ],
        )
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[
                Alert.__table__,
                MonitoringHistory.__table__,
                Device.__table__,
            ],
        )
        self.engine.dispose()

    def test_monitoring_returns_previous_status(self):
        db = self.session_factory()
        db.add(Device(name="Router", ip="192.0.2.1"))
        db.add(MonitoringHistory(ip="192.0.2.1", status="Offline"))
        db.commit()
        db.close()

        with (
            patch("app.monitoring.service.SessionLocal", self.session_factory),
            patch(
                "app.monitoring.service.check_device_status",
                return_value={"status": "Online"},
            ),
        ):
            results = update_device_status_from_monitor()

        self.assertEqual(results[0]["old_status"], "Offline")
        self.assertEqual(results[0]["status"], "Online")

    def test_connection_and_disconnection_create_nonduplicate_alerts(self):
        device = SimpleNamespace(id=1, name="Router")
        with (
            patch("app.alerts.service.SessionLocal", self.session_factory),
            patch(
                "app.alerts.service.device_crud.get_device_by_ip",
                return_value=device,
            ),
        ):
            check_and_create_device_status_alert("192.0.2.1", "Online")
            check_and_create_device_status_alert(
                "192.0.2.1", "Online", "Online"
            )
            check_and_create_device_status_alert(
                "192.0.2.1", "Offline", "Online"
            )
            db = self.session_factory()
            db.query(Alert).filter(
                Alert.device_ip == "192.0.2.1",
                Alert.alert_type == "DISCONNECTED",
            ).update({"status": "acknowledged"})
            db.commit()
            db.close()
            check_and_create_device_status_alert(
                "192.0.2.1", "Offline", "Offline"
            )
            check_and_create_device_status_alert(
                "192.0.2.1", "Online", "Offline"
            )

        db = self.session_factory()
        alerts = db.query(Alert).order_by(Alert.id).all()
        db.close()

        self.assertEqual(
            [alert.alert_type for alert in alerts],
            ["CONNECTED", "DISCONNECTED", "CONNECTED"],
        )
        self.assertIn("connected to the network", alerts[0].message)
        self.assertEqual(alerts[1].status, "resolved")
        self.assertEqual(alerts[2].status, "resolved")

    def test_explicit_offline_creates_one_immediate_alert(self):
        with patch("app.alerts.service.SessionLocal", self.session_factory):
            for previous_status in ("Online", "Offline"):
                process_monitoring_alerts(
                    ip="192.0.2.10",
                    device_name="Switch",
                    status="Offline",
                    check_result="failed",
                    latency_ms=None,
                    http_health_status=None,
                    old_status=previous_status,
                )

        db = self.session_factory()
        alerts = db.query(Alert).filter(Alert.alert_type == "DISCONNECTED").all()
        db.close()

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].status, "active")
        self.assertEqual(alerts[0].severity, "critical")
        self.assertIn("exact cause is unknown", alerts[0].message)

    def test_online_to_unknown_warns_once_and_recovery_resolves_it(self):
        with patch("app.alerts.service.SessionLocal", self.session_factory):
            for _ in range(2):
                process_monitoring_alerts(
                    ip="192.0.2.11",
                    device_name="Access point",
                    status="Unknown",
                    check_result="timeout",
                    latency_ms=None,
                    http_health_status=None,
                    old_status="Online",
                )
            process_monitoring_alerts(
                ip="192.0.2.11",
                device_name="Access point",
                status="Online",
                check_result="success",
                latency_ms=None,
                http_health_status=None,
                old_status="Unknown",
            )

        db = self.session_factory()
        unknown_alerts = (
            db.query(Alert)
            .filter(Alert.alert_type == "STATUS_UNKNOWN")
            .all()
        )
        connected_alerts = (
            db.query(Alert)
            .filter(Alert.alert_type == "CONNECTED")
            .all()
        )
        db.close()

        self.assertEqual(len(unknown_alerts), 1)
        self.assertEqual(unknown_alerts[0].status, "resolved")
        self.assertIn("not proof", unknown_alerts[0].message)
        self.assertEqual(len(connected_alerts), 1)
        self.assertEqual(connected_alerts[0].status, "resolved")

    def test_three_consecutive_unknown_checks_raise_one_disconnect_alert(self):
        with patch("app.alerts.service.SessionLocal", self.session_factory):
            for _ in range(3):
                db = self.session_factory()
                db.add(MonitoringHistory(
                    ip="192.0.2.12",
                    status="Unknown",
                    check_result="unknown",
                ))
                db.commit()
                db.close()
                process_monitoring_alerts(
                    ip="192.0.2.12",
                    device_name="Printer",
                    status="Unknown",
                    check_result="unknown",
                    latency_ms=None,
                    http_health_status=None,
                    old_status="Online",
                )

        db = self.session_factory()
        disconnected_alerts = (
            db.query(Alert)
            .filter(
                Alert.device_ip == "192.0.2.12",
                Alert.alert_type == "DISCONNECTED",
            )
            .all()
        )
        unknown_alerts = (
            db.query(Alert)
            .filter(
                Alert.device_ip == "192.0.2.12",
                Alert.alert_type == "STATUS_UNKNOWN",
            )
            .all()
        )
        db.close()

        self.assertEqual(len(disconnected_alerts), 1)
        self.assertEqual(disconnected_alerts[0].status, "active")
        self.assertIn("3 consecutive checks", disconnected_alerts[0].message)
        self.assertEqual(len(unknown_alerts), 1)
        self.assertEqual(unknown_alerts[0].status, "resolved")


if __name__ == "__main__":
    unittest.main()
