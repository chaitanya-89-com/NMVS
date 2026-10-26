import socket
import subprocess
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.alerts.model import Alert
from app.alerts.service import process_monitoring_alerts
from app.devices.model import Device
from app.dependencies import get_current_user
from app.monitoring import monitor, service
from app.monitoring.model import MonitoringHistory
from app.monitoring.router import router as monitoring_router
from app.monitoring.schema import MonitoringResponse
from app.timezone import now_ist_naive
from database.database import Base


class MonitoringApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(monitoring_router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    @patch("app.monitoring.router.service.get_all_monitoring_history")
    def test_history_endpoint_serializes_diagnostic_fields(self, get_history):
        get_history.return_value = [SimpleNamespace(
            id=1,
            ip="192.0.2.1",
            status="Online",
            check_result="success",
            detail="ICMP echo reply received.",
            latency_ms=24.5,
            latency_method="ICMP",
            icmp_result="success",
            tcp_result=None,
            tcp_response_ms=None,
            http_status_code=None,
            http_response_ms=None,
            http_health_status=None,
            checked_at=now_ist_naive(),
        )]

        response = self.client.get("/monitoring/history", params={"limit": 10, "days": 7})

        self.assertEqual(response.status_code, 200)
        payload = response.json()[0]
        self.assertEqual(payload["latency_ms"], 24.5)
        self.assertEqual(payload["latency_method"], "ICMP")
        self.assertIn("checked_at", payload)
        get_history.assert_called_once_with(10, 7)

    @patch("app.monitoring.router.service.clear_monitoring_history", return_value=4)
    def test_clear_history_endpoint_returns_deleted_count(self, clear_history):
        response = self.client.delete("/monitoring/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted_count": 4})
        clear_history.assert_called_once_with()

    @patch("app.monitoring.router.service.get_availability")
    def test_availability_endpoint_returns_schema_and_validates_range(self, get_availability):
        get_availability.return_value = [{
            "device_id": 1,
            "device_name": "Router",
            "ip": "192.0.2.1",
            "range_days": 7,
            "latest_status": "Online",
            "successful_checks": 1,
            "failed_checks": 0,
            "unknown_checks": 0,
            "uptime_percent": 100.0,
            "average_latency_ms": 24.5,
            "latest_latency_ms": 24.5,
            "latest_latency_method": "ICMP",
        }]

        response = self.client.get("/monitoring/availability", params={"days": 7})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["uptime_percent"], 100.0)
        self.assertEqual(
            self.client.get("/monitoring/availability", params={"days": 2}).status_code,
            422,
        )


class MonitoringProbeTests(unittest.TestCase):
    @patch("app.monitoring.monitor.subprocess.run")
    def test_successful_icmp_records_ping_rtt(self, run_ping):
        run_ping.return_value = SimpleNamespace(
            returncode=0,
            stdout="Reply from 192.0.2.1: time=23ms",
            stderr="",
        )

        result = monitor.check_device_status("192.0.2.1")

        self.assertEqual(result["status"], "Online")
        self.assertEqual(result["latency_ms"], 23.0)
        self.assertEqual(result["latency_method"], "ICMP")

    @patch("app.monitoring.monitor.subprocess.run")
    def test_icmp_timeout_is_unknown_not_definitively_offline(self, run_ping):
        run_ping.side_effect = subprocess.TimeoutExpired(["ping"], 3)

        result = monitor.check_device_status("192.0.2.1")

        self.assertEqual(result["status"], "Unknown")
        self.assertEqual(result["icmp_result"], "timeout")
        self.assertIsNone(result.get("latency_ms"))

    @patch("app.monitoring.monitor.subprocess.run")
    @patch("app.monitoring.monitor.socket.create_connection")
    def test_tcp_success_records_connection_setup_time(self, create_connection, run_ping):
        run_ping.return_value = SimpleNamespace(returncode=1, stdout="", stderr="")
        create_connection.return_value.__enter__.return_value = object()

        with patch(
            "app.monitoring.monitor.time.monotonic",
            side_effect=[10.0, 10.025, 10.05],
        ):
            result = monitor.check_device_status("192.0.2.1", 443)

        self.assertEqual(result["status"], "Online")
        self.assertEqual(result["latency_method"], "TCP_CONNECT")
        self.assertEqual(result["tcp_response_ms"], 25.0)
        self.assertIn("not application response time", result["detail"])

    @patch("app.monitoring.monitor.subprocess.run")
    @patch("app.monitoring.monitor.socket.create_connection")
    def test_tcp_timeout_is_unknown(self, create_connection, run_ping):
        run_ping.return_value = SimpleNamespace(returncode=1, stdout="", stderr="")
        create_connection.side_effect = socket.timeout()

        result = monitor.check_device_status("192.0.2.1", 443)

        self.assertEqual(result["status"], "Unknown")
        self.assertEqual(result["tcp_result"], "timeout")
        self.assertIsNone(result.get("latency_ms"))

    @patch("app.monitoring.monitor.subprocess.run")
    @patch("app.monitoring.monitor.socket.create_connection")
    def test_tcp_refusal_means_host_reachable_not_service_healthy(self, create_connection, run_ping):
        run_ping.return_value = SimpleNamespace(returncode=1, stdout="", stderr="")
        create_connection.side_effect = ConnectionRefusedError()

        result = monitor.check_device_status("192.0.2.1", 443)

        self.assertEqual(result["status"], "Online")
        self.assertEqual(result["tcp_result"], "refused")
        self.assertIsNone(result.get("latency_ms"))

    @patch("app.monitoring.monitor.socket.getaddrinfo")
    def test_private_dns_destination_is_rejected(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))
        ]
        with patch.object(
            monitor.settings,
            "MONITORING_HTTP_ALLOWED_HOSTS",
            frozenset({"health.example"}),
        ):
            with self.assertRaisesRegex(ValueError, "non-public IP"):
                monitor.validate_health_check_url("https://health.example/health")

    def test_unknown_http_health_host_is_rejected(self):
        with patch.object(
            monitor.settings,
            "MONITORING_HTTP_ALLOWED_HOSTS",
            frozenset(),
        ):
            with self.assertRaisesRegex(ValueError, "not approved"):
                monitor.validate_health_check_url("http://127.0.0.1/health")

    @patch("app.monitoring.monitor.socket.getaddrinfo")
    def test_http_health_url_requires_allowlist_and_no_userinfo(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        with patch.object(
            monitor.settings,
            "MONITORING_HTTP_ALLOWED_HOSTS",
            frozenset({"health.example"}),
        ):
            self.assertEqual(
                monitor.validate_health_check_url("https://health.example/health"),
                "https://health.example/health",
            )
            with self.assertRaisesRegex(ValueError, "without credentials"):
                monitor.validate_health_check_url(
                    "https://user:secret@health.example/health"
                )

    @patch("app.monitoring.monitor.requests.get")
    @patch("app.monitoring.monitor.socket.getaddrinfo")
    def test_http_health_check_does_not_follow_redirects(self, getaddrinfo, get):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        get.return_value.status_code = 503
        get.return_value.raise_for_status.return_value = None
        with patch.object(
            monitor.settings,
            "MONITORING_HTTP_ALLOWED_HOSTS",
            frozenset({"health.example"}),
        ):
            result = monitor.check_http_health("https://health.example/health")

        self.assertEqual(result["http_health_status"], "unhealthy")
        self.assertEqual(result["http_status_code"], 503)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])


class MonitoringDataTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[Device.__table__, MonitoringHistory.__table__, Alert.__table__],
        )
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(
            self.engine,
            tables=[Alert.__table__, MonitoringHistory.__table__, Device.__table__],
        )
        self.engine.dispose()

    def test_uptime_excludes_unknown_checks_and_averages_measured_latency(self):
        records = [
            SimpleNamespace(
                status="Online",
                check_result="success",
                latency_ms=20.0,
                latency_method="ICMP",
            ),
            SimpleNamespace(
                status="Offline",
                check_result="failed",
                latency_ms=None,
                latency_method=None,
            ),
            SimpleNamespace(
                status="Unknown",
                check_result="unknown",
                latency_ms=None,
                latency_method=None,
            ),
        ]

        result = service.calculate_availability(records)

        self.assertEqual(result["successful_checks"], 1)
        self.assertEqual(result["failed_checks"], 1)
        self.assertEqual(result["unknown_checks"], 1)
        self.assertEqual(result["uptime_percent"], 50.0)
        self.assertEqual(result["average_latency_ms"], 20.0)

    def test_uptime_is_unavailable_when_there_are_only_unknown_checks(self):
        result = service.calculate_availability([
            SimpleNamespace(status="Unknown", check_result="unknown", latency_ms=None),
        ])
        self.assertIsNone(result["uptime_percent"])
        self.assertEqual(result["unknown_checks"], 1)

    def test_clear_history_preserves_registered_devices(self):
        db = self.session_factory()
        db.add(Device(name="Router", ip="192.0.2.1"))
        db.add(MonitoringHistory(
            ip="192.0.2.1",
            status="Online",
            check_result="success",
        ))
        db.commit()
        db.close()

        with patch("app.monitoring.service.SessionLocal", self.session_factory):
            deleted_count = service.clear_monitoring_history()

        db = self.session_factory()
        self.assertEqual(deleted_count, 1)
        self.assertEqual(db.query(MonitoringHistory).count(), 0)
        self.assertEqual(db.query(Device).count(), 1)
        db.close()

    def test_availability_endpoint_summary_aggregates_range_records(self):
        db = self.session_factory()
        device = Device(name="Router", ip="192.0.2.1")
        db.add(device)
        db.flush()
        db.add_all([
            MonitoringHistory(
                ip=device.ip,
                status="Online",
                check_result="success",
                latency_ms=20.0,
                latency_method="ICMP",
                checked_at=now_ist_naive() - timedelta(minutes=2),
            ),
            MonitoringHistory(
                ip=device.ip,
                status="Unknown",
                check_result="unknown",
                checked_at=now_ist_naive() - timedelta(minutes=1),
            ),
        ])
        db.commit()
        db.close()

        with patch("app.monitoring.service.SessionLocal", self.session_factory):
            result = service.get_availability(1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["latest_status"], "Unknown")
        self.assertEqual(result[0]["successful_checks"], 1)
        self.assertEqual(result[0]["unknown_checks"], 1)
        self.assertEqual(result[0]["uptime_percent"], 100.0)
        self.assertEqual(result[0]["average_latency_ms"], 20.0)

    def test_monitoring_response_includes_diagnostics(self):
        checked_at = now_ist_naive()
        response = MonitoringResponse.model_validate(SimpleNamespace(
            id=7,
            ip="192.0.2.1",
            status="Online",
            check_result="success",
            detail="ICMP echo reply received.",
            latency_ms=23.0,
            latency_method="ICMP",
            icmp_result="success",
            tcp_result=None,
            tcp_response_ms=None,
            http_status_code=None,
            http_response_ms=None,
            http_health_status=None,
            checked_at=checked_at,
        ))
        self.assertEqual(response.latency_ms, 23.0)
        self.assertEqual(response.status, "Online")

    def test_consecutive_failure_alert_is_deduplicated_and_resolves_on_recovery(self):
        db = self.session_factory()
        db.add(Device(name="Router", ip="192.0.2.1"))
        for _ in range(2):
            db.add(MonitoringHistory(
                ip="192.0.2.1",
                status="Unknown",
                check_result="unknown",
                checked_at=now_ist_naive() - timedelta(seconds=20),
            ))
        db.commit()
        db.close()

        with (
            patch("app.alerts.service.SessionLocal", self.session_factory),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS",
                2,
            ),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_HIGH_LATENCY_MS",
                500.0,
            ),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_UPTIME_THRESHOLD_PERCENT",
                95.0,
            ),
        ):
            for _ in range(2):
                process_monitoring_alerts(
                    ip="192.0.2.1",
                    device_name="Router",
                    status="Unknown",
                    check_result="unknown",
                    latency_ms=None,
                    http_health_status=None,
                )

            db = self.session_factory()
            alert_count = db.query(Alert).filter(Alert.alert_type == "DISCONNECTED").count()
            db.close()
            self.assertEqual(alert_count, 1)

            process_monitoring_alerts(
                ip="192.0.2.1",
                device_name="Router",
                status="Online",
                check_result="success",
                latency_ms=20.0,
                http_health_status="healthy",
                old_status="Unknown",
            )

        db = self.session_factory()
        disconnect = db.query(Alert).filter(Alert.alert_type == "DISCONNECTED").first()
        connected = db.query(Alert).filter(Alert.alert_type == "CONNECTED").first()
        db.close()
        self.assertEqual(disconnect.status, "resolved")
        self.assertIsNotNone(connected)

    def test_high_latency_alert_is_deduplicated_and_recovers(self):
        with (
            patch("app.alerts.service.SessionLocal", self.session_factory),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_UNREACHABLE_CONSECUTIVE_CHECKS",
                3,
            ),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_HIGH_LATENCY_MS",
                100.0,
            ),
            patch.object(
                __import__("app.alerts.service", fromlist=["settings"]).settings,
                "MONITORING_UPTIME_THRESHOLD_PERCENT",
                95.0,
            ),
        ):
            for _ in range(2):
                process_monitoring_alerts(
                    ip="192.0.2.2",
                    device_name="Switch",
                    status="Online",
                    check_result="success",
                    latency_ms=125.0,
                    http_health_status=None,
                )

            db = self.session_factory()
            self.assertEqual(
                db.query(Alert).filter(Alert.alert_type == "HIGH_LATENCY").count(),
                1,
            )
            db.close()

            process_monitoring_alerts(
                ip="192.0.2.2",
                device_name="Switch",
                status="Online",
                check_result="success",
                latency_ms=20.0,
                http_health_status=None,
            )

        db = self.session_factory()
        high_latency = db.query(Alert).filter(Alert.alert_type == "HIGH_LATENCY").first()
        recovery = db.query(Alert).filter(Alert.alert_type == "RECOVERY").first()
        db.close()
        self.assertEqual(high_latency.status, "resolved")
        self.assertIsNotNone(recovery)


if __name__ == "__main__":
    unittest.main()
