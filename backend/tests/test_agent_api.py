import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent.agent import send_scan_results
from app.agent.router import router as agent_router
from app.alerts.model import Alert
from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from database.database import Base


class AgentApiTests(unittest.TestCase):
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
        app = FastAPI()
        app.include_router(agent_router)
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"NMVS_AGENT_TOKEN": "test-agent-token"})
        self.env.start()
        self.session_patch = patch(
            "app.monitoring.service.SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()
        self.alert_patch = patch(
            "app.monitoring.service.alert_service.process_monitoring_alerts"
        )
        self.alert_process = self.alert_patch.start()

    def tearDown(self):
        self.alert_patch.stop()
        self.session_patch.stop()
        self.env.stop()
        self.client.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_agent_health_is_public(self):
        response = self.client.get("/agent/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_openapi_documents_bearer_authentication(self):
        operation = self.client.get("/openapi.json").json()["paths"][
            "/agent/scan-results"
        ]["post"]
        self.assertEqual(operation["security"], [{"HTTPBearer": []}])

    def test_scan_requires_valid_bearer_token(self):
        payload = {"devices": []}
        self.assertEqual(
            self.client.post("/agent/scan-results", json=payload).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/agent/scan-results",
                json=payload,
                headers={"Authorization": "Bearer wrong-token"},
            ).status_code,
            401,
        )

    def test_scan_persists_agent_status_and_latency(self):
        response = self.client.post(
            "/agent/scan-results",
            json={
                "devices": [
                    {
                        "ip": "192.168.43.217",
                        "status": "Online",
                        "latency_ms": 12.5,
                    },
                    {
                        "ip": "192.168.43.218",
                        "status": "Offline",
                        "latency_ms": None,
                    },
                ]
            },
            headers={"Authorization": "Bearer test-agent-token"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["received"], 2)
        self.assertEqual(response.json()["processed"], 2)
        self.assertEqual(response.json()["devices_created"], 2)
        self.assertEqual(response.json()["monitoring_records_created"], 2)

        with self.session_factory() as db:
            history = {
                record.ip: record
                for record in db.query(MonitoringHistory).all()
            }
            devices = db.query(Device).all()
        self.assertEqual(history["192.168.43.217"].status, "Online")
        self.assertEqual(history["192.168.43.217"].latency_ms, 12.5)
        self.assertEqual(history["192.168.43.217"].latency_method, "ICMP")
        self.assertEqual(history["192.168.43.218"].status, "Offline")
        self.assertIsNone(history["192.168.43.218"].latency_ms)
        self.assertEqual(len(devices), 2)
        self.assertTrue(all(device.source == "agent" for device in devices))
        self.alert_process.assert_called()

    def test_agent_client_to_api_to_database_workflow(self):
        def post_scan(_endpoint, **kwargs):
            kwargs.pop("timeout")
            response = self.client.post("/agent/scan-results", **kwargs)
            response.ok = response.status_code < 400
            return response

        with patch("agent.agent.requests.post", side_effect=post_scan):
            result = send_scan_results(
                "http://testserver/agent/scan-results",
                "test-agent-token",
                [{
                    "ip": "192.168.43.219",
                    "status": "Online",
                    "latency_ms": 4.25,
                }],
                network="192.168.43.0/24",
            )

        self.assertEqual(result["processed"], 1)
        with self.session_factory() as db:
            history = db.query(MonitoringHistory).one()
            device = db.query(Device).one()
        self.assertEqual(history.status, "Online")
        self.assertEqual(history.latency_ms, 4.25)
        self.assertEqual(device.ip, "192.168.43.219")

    def test_agent_scan_persists_configured_network_even_when_empty(self):
        response = self.client.post(
            "/agent/scan-results",
            json={"devices": [], "network": "192.168.43.0/24"},
            headers={"Authorization": "Bearer test-agent-token"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        from app.speed_monitoring.model import AgentDiscoveredNetwork

        with self.session_factory() as db:
            configured_networks = db.query(AgentDiscoveredNetwork).all()
        self.assertEqual([network.cidr for network in configured_networks], ["192.168.43.0/24"])

    def test_agent_scan_rejects_devices_outside_reported_network(self):
        response = self.client.post(
            "/agent/scan-results",
            json={
                "network": "192.168.43.0/24",
                "devices": [{
                    "ip": "192.168.44.2",
                    "status": "Online",
                    "latency_ms": 1,
                }],
            },
            headers={"Authorization": "Bearer test-agent-token"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["msg"],
            "Value error, Every scanned device must belong to the reported network.",
        )

    def test_existing_device_is_updated_and_result_is_not_rescanned(self):
        with self.session_factory() as db:
            db.add(Device(
                name="Existing",
                ip="192.168.43.217",
                device_type="Unknown Device",
                network_type="Unknown",
                source="manual",
            ))
            db.commit()

        with patch("app.monitoring.service.check_and_save_device") as rescan:
            response = self.client.post(
                "/agent/scan-results",
                json={"devices": [{
                    "ip": "192.168.43.217",
                    "status": "Unknown",
                    "latency_ms": None,
                }]},
                headers={"Authorization": "Bearer test-agent-token"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["devices_updated"], 1)
        rescan.assert_not_called()
        with self.session_factory() as db:
            self.assertEqual(db.query(Device).count(), 1)
            self.assertEqual(db.query(MonitoringHistory).one().status, "Unknown")

    def test_backend_scheduler_does_not_probe_agent_owned_devices(self):
        self.client.post(
            "/agent/scan-results",
            json={"devices": [{
                "ip": "192.168.43.220",
                "status": "Online",
                "latency_ms": 3,
            }]},
            headers={"Authorization": "Bearer test-agent-token"},
        )
        with patch("app.monitoring.service._run_checks") as run_checks:
            from app.monitoring.service import update_device_status_from_monitor

            results = update_device_status_from_monitor()
        self.assertEqual(results, [])
        run_checks.assert_not_called()

    def test_invalid_scan_data_returns_422(self):
        invalid_devices = [
            {"ip": "string", "status": "Online", "latency_ms": None},
            {"ip": "192.168.43.1", "status": "Down", "latency_ms": None},
            {"ip": "192.168.43.1", "status": "Online", "latency_ms": -1},
        ]
        for device in invalid_devices:
            with self.subTest(device=device):
                response = self.client.post(
                    "/agent/scan-results",
                    json={"devices": [device]},
                    headers={"Authorization": "Bearer test-agent-token"},
                )
                self.assertEqual(response.status_code, 422)

    def test_ipv6_is_accepted_and_oversized_batches_are_rejected(self):
        headers = {"Authorization": "Bearer test-agent-token"}
        ipv6_response = self.client.post(
            "/agent/scan-results",
            json={"devices": [{
                "ip": "2001:db8::1",
                "status": "Unknown",
                "latency_ms": None,
            }]},
            headers=headers,
        )
        self.assertEqual(ipv6_response.status_code, 200, ipv6_response.text)

        oversized = {
            "devices": [
                {
                    "ip": f"10.1.{index // 256}.{index % 256}",
                    "status": "Online",
                    "latency_ms": None,
                }
                for index in range(4097)
            ]
        }
        oversized_response = self.client.post(
            "/agent/scan-results",
            json=oversized,
            headers=headers,
        )
        self.assertEqual(oversized_response.status_code, 422)

    def test_empty_scan_is_accepted_and_duplicate_ips_are_rejected(self):
        headers = {"Authorization": "Bearer test-agent-token"}
        empty = self.client.post(
            "/agent/scan-results",
            json={"devices": []},
            headers=headers,
        )
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()["processed"], 0)

        duplicate = {
            "devices": [
                {"ip": "192.168.43.1", "status": "Online", "latency_ms": None},
                {"ip": "192.168.43.1", "status": "Offline", "latency_ms": None},
            ]
        }
        self.assertEqual(
            self.client.post(
                "/agent/scan-results",
                json=duplicate,
                headers=headers,
            ).status_code,
            422,
        )

    def test_missing_server_token_fails_closed(self):
        with patch.dict(os.environ, {"NMVS_AGENT_TOKEN": ""}):
            response = self.client.post(
                "/agent/scan-results",
                json={"devices": []},
                headers={"Authorization": "Bearer test-agent-token"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Agent authentication is not configured",
        )

    def test_database_error_returns_safe_server_error(self):
        with patch(
            "app.monitoring.service.save_agent_scan_results",
            side_effect=SQLAlchemyError("database details must not leak"),
        ):
            response = self.client.post(
                "/agent/scan-results",
                json={"devices": []},
                headers={"Authorization": "Bearer test-agent-token"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Unable to save agent scan results",
        )
        self.assertNotIn("database details", response.text)


if __name__ == "__main__":
    unittest.main()
