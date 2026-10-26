import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.speed_monitoring import service
from app.speed_monitoring.router import router as speed_monitoring_router


class SpeedMonitoringApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(speed_monitoring_router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    @patch("app.speed_monitoring.service.request_device_test")
    def test_requests_per_device_speed_test_for_target_ip(self, request_test):
        request_test.return_value = {
            "id": 1,
            "ip": "192.168.1.25",
            "status": "queued",
            "tested_at": "2026-10-26T01:00:00+05:30",
        }
        response = self.client.post(
            "/speed-monitoring/run",
            json={"ip": "192.168.1.25"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["ip"], "192.168.1.25")
        request_test.assert_called_once_with("192.168.1.25")

    @patch(
        "app.speed_monitoring.service.request_device_test",
        side_effect=ConnectionError(
            "This device is not recently confirmed Online by the NMVS agent."
        ),
    )
    def test_device_without_recent_online_report_returns_conflict(
        self,
        request_test,
    ):
        response = self.client.post(
            "/speed-monitoring/run",
            json={"ip": "192.168.1.25"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "This device is not recently confirmed Online by the NMVS agent.",
        )
        request_test.assert_called_once_with("192.168.1.25")

    @patch(
        "app.speed_monitoring.service.request_device_test",
        side_effect=LookupError(
            "Device not found. Please enter an IP address belonging to a device discovered by NMVS."
        ),
    )
    def test_unknown_device_ip_returns_not_found(self, request_test):
        response = self.client.post(
            "/speed-monitoring/run",
            json={"ip": "192.168.1.25"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "Device not found. Please enter an IP address belonging to a device discovered by NMVS.",
        )
        request_test.assert_called_once_with("192.168.1.25")

    def test_invalid_device_ip_returns_validation_error(self):
        for ip in (
            "10.20.56.888",
            "0.0.9.-90",
            "10.20.56",
            "10.20.56.abc",
            "10.20.56.217.5",
            "",
        ):
            with self.subTest(ip=ip):
                response = self.client.post(
                    "/speed-monitoring/run",
                    json={"ip": ip},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["detail"],
                    "Invalid IP address. Please enter a valid IPv4 address.",
                )

    @patch(
        "app.speed_monitoring.service.request_device_test",
        side_effect=service.DeviceOutsideConfiguredNetwork(
            "Device IP is outside the configured NMVS network."
        ),
    )
    def test_ip_outside_configured_network_returns_unprocessable_entity(
        self,
        request_test,
    ):
        response = self.client.post(
            "/speed-monitoring/run",
            json={"ip": "10.20.56.25"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "Device IP is outside the configured NMVS network.",
        )

    @patch(
        "app.speed_monitoring.service.request_device_test",
        side_effect=RuntimeError("internal database details"),
    )
    def test_unexpected_error_is_logged_and_does_not_leak_details(
        self,
        request_test,
    ):
        with self.assertLogs("app.speed_monitoring.router", level="ERROR"):
            response = self.client.post(
                "/speed-monitoring/run",
                json={"ip": "192.168.1.25"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Unable to start the device speed test.",
        )
        self.assertNotIn("internal database details", response.text)


if __name__ == "__main__":
    unittest.main()
