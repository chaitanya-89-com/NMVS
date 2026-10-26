import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.devices.model import Device
from app.dependencies import get_current_user
from app.monitoring.model import MonitoringHistory
from app.topology import service
from app.topology.graph import TopologyGraphBuilder
from app.topology.router import router as topology_router
from database.database import Base


class TopologyVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch("app.topology.service.SessionLocal", self.session_factory)
        self.device_session_patch = patch(
            "app.devices.crud.SessionLocal",
            self.session_factory,
        )
        self.session_patch.start()
        self.device_session_patch.start()
        self.db = self.session_factory()
        app = FastAPI()
        app.include_router(topology_router)
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self.client = TestClient(app)
        self.gateway = Device(
            name="Main Gateway",
            ip="192.168.1.1",
            mac_address="00:11:22:33:44:01",
            device_type="Router",
            network_type="Ethernet",
            source="discovery",
        )
        self.device = Device(
            name="Workstation",
            ip="192.168.1.10",
            mac_address="00:11:22:33:44:10",
            device_type="Workstation",
            network_type="Ethernet",
            source="discovery",
        )
        self.other_device = Device(
            name="Printer",
            ip="192.168.1.11",
            mac_address="00:11:22:33:44:11",
            device_type="Printer",
            network_type="Ethernet",
            source="discovery",
        )
        self.db.add_all([self.gateway, self.device, self.other_device])
        self.db.add_all([
            MonitoringHistory(ip=device.ip, status="Online")
            for device in (self.gateway, self.device, self.other_device)
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.client.close()
        self.device_session_patch.stop()
        self.session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_remove_preserves_inventory_and_history_and_hides_incident_edges(self):
        device_id = self.device.id
        self.assertIn(device_id, {
            node.device_id
            for node in service.get_topology_graph(include_wan=False).nodes
        })

        service.set_device_topology_hidden(device_id, True)
        service.set_device_topology_hidden(device_id, True)

        graph = service.get_topology_graph(include_wan=False)
        visible_ids = {node.device_id for node in graph.nodes}
        self.assertNotIn(device_id, visible_ids)
        self.assertTrue(all(
            edge.source != f"device-{device_id}"
            and edge.target != f"device-{device_id}"
            for edge in graph.edges
        ))
        self.assertEqual(
            self.db.query(Device).filter(Device.id == device_id).count(),
            1,
        )
        self.assertEqual(
            self.db.query(MonitoringHistory).filter_by(ip=self.device.ip).count(),
            1,
        )
        self.assertEqual([item["id"] for item in service.get_hidden_devices()], [device_id])

    def test_restore_reincludes_device_and_rebuilds_relationships(self):
        service.set_device_topology_hidden(self.device.id, True)
        service.set_device_topology_hidden(self.device.id, False)
        service.set_device_topology_hidden(self.device.id, False)

        graph = service.get_topology_graph(include_wan=False)
        visible_ids = {node.device_id for node in graph.nodes}
        self.assertIn(self.device.id, visible_ids)
        self.assertTrue(any(
            self.device.id in {int(edge.source.removeprefix("device-")), int(edge.target.removeprefix("device-"))}
            for edge in graph.edges
            if edge.source.startswith("device-") and edge.target.startswith("device-")
        ))
        self.assertEqual(service.get_hidden_devices(), [])

    def test_gateway_cannot_be_removed(self):
        with self.assertRaisesRegex(PermissionError, "Gateway and critical router"):
            service.set_device_topology_hidden(self.gateway.id, True)
        self.assertFalse(self.gateway.topology_hidden)

    def test_unknown_device_ids_return_not_found(self):
        with self.assertRaisesRegex(LookupError, "Device not found"):
            service.set_device_topology_hidden(9999, True)

    def test_visibility_endpoints_hide_and_restore_without_deleting_inventory(self):
        removed = self.client.post(f"/topology/devices/{self.device.id}/remove")
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertTrue(removed.json()["topology_hidden"])
        self.assertEqual(
            self.client.get("/topology/graph").json()["nodes"],
            [
                node.model_dump(mode="json")
                for node in service.get_topology_graph(
                    source=None,
                    connected_only=True,
                ).nodes
            ],
        )
        self.assertEqual(self.client.get("/topology/hidden-devices").json()[0]["id"], self.device.id)

        restored = self.client.post(f"/topology/devices/{self.device.id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertFalse(restored.json()["topology_hidden"])
        self.assertEqual(self.client.get("/topology/hidden-devices").json(), [])
        self.assertEqual(self.db.query(Device).filter_by(id=self.device.id).count(), 1)

    def test_visibility_endpoint_rejects_gateway_and_missing_ids(self):
        gateway_response = self.client.post(
            f"/topology/devices/{self.gateway.id}/remove"
        )
        missing_response = self.client.post("/topology/devices/9999/remove")

        self.assertEqual(gateway_response.status_code, 409)
        self.assertEqual(missing_response.status_code, 404)

    def test_suppressed_device_remains_monitored(self):
        service.set_device_topology_hidden(self.device.id, True)
        self.db.add(MonitoringHistory(
            ip=self.device.ip,
            status="Online",
        ))
        self.db.commit()

        self.assertEqual(
            self.db.query(MonitoringHistory).filter_by(ip=self.device.ip).count(),
            2,
        )
        self.db.expire_all()
        self.assertTrue(
            self.db.query(Device).filter_by(id=self.device.id).one().topology_hidden
        )
        self.assertNotIn(
            self.device.id,
            {node.device_id for node in service.get_topology_graph().nodes},
        )

    @patch("app.discovery.scanner.scan_network")
    @patch("app.devices.detector.detect_device_info")
    def test_rediscovery_updates_persisted_devices_without_duplicates_or_unhiding(
        self,
        detect_device,
        scan_network,
    ):
        service.set_device_topology_hidden(self.device.id, True)
        scan_network.return_value = [
            {"ip": self.device.ip, "status": "Online"},
            {"ip": self.other_device.ip, "status": "Online"},
            {"ip": "192.168.1.12", "status": "Online"},
        ]
        detect_device.side_effect = [
            {
                "ip": self.device.ip,
                "hostname": "Workstation",
                "device_type": "Workstation",
                "network_type": "Ethernet",
                "mac_address": self.device.mac_address,
                "status": "Online",
            },
            {
                "ip": self.other_device.ip,
                "hostname": "Printer",
                "device_type": "Printer",
                "network_type": "Ethernet",
                "mac_address": self.other_device.mac_address,
                "status": "Online",
            },
            {
                "ip": "192.168.1.12",
                "hostname": "Camera",
                "device_type": "Camera",
                "network_type": "Ethernet",
                "mac_address": "00:11:22:33:44:12",
                "status": "Online",
            },
        ] * 2

        first_graph = service.get_discovery_topology(
            "192.168.1.0/24",
            auto_register=True,
            include_wan=False,
        )
        second_graph = service.get_discovery_topology(
            "192.168.1.0/24",
            auto_register=True,
            include_wan=False,
        )

        self.assertNotIn(self.device.id, {node.device_id for node in second_graph.nodes})
        self.assertIn(self.other_device.id, {node.device_id for node in second_graph.nodes})
        self.assertIn("192.168.1.12", {node.ip for node in second_graph.nodes})
        self.assertEqual(self.db.query(Device).count(), 4)
        self.assertEqual(
            self.db.query(MonitoringHistory).filter_by(ip=self.other_device.ip).count(),
            3,
        )
        self.assertEqual(
            self.db.query(MonitoringHistory).filter_by(ip="192.168.1.12").count(),
            2,
        )
        self.assertEqual(
            len({edge.id for edge in second_graph.edges}),
            len(second_graph.edges),
        )
        self.assertEqual(
            len({(edge.source, edge.target) for edge in second_graph.edges}),
            len(second_graph.edges),
        )
        self.assertEqual(
            len({node.device_id for node in second_graph.nodes if node.device_id}),
            len([node for node in second_graph.nodes if node.device_id]),
        )

    @patch("app.discovery.scanner.scan_network")
    @patch("app.devices.detector.detect_device_info")
    def test_rediscovery_uses_mac_identity_when_device_ip_changes(
        self,
        detect_device,
        scan_network,
    ):
        scan_network.return_value = [{"ip": "192.168.1.20", "status": "Online"}]
        detect_device.return_value = {
            "ip": "192.168.1.20",
            "hostname": "Workstation",
            "device_type": "Workstation",
            "network_type": "Ethernet",
            "mac_address": self.device.mac_address,
            "status": "Online",
        }

        service.get_discovery_topology("192.168.1.0/24", auto_register=True)

        self.db.expire_all()
        self.assertEqual(self.db.query(Device).filter_by(mac_address=self.device.mac_address).count(), 1)
        self.assertEqual(
            self.db.query(Device).filter_by(mac_address=self.device.mac_address).one().ip,
            "192.168.1.20",
        )
        self.assertEqual(self.db.query(Device).count(), 3)

    @patch("app.discovery.scanner.scan_network")
    @patch("app.devices.detector.detect_device_info")
    def test_nonregistering_discovery_also_honors_suppression_by_mac(
        self,
        detect_device,
        scan_network,
    ):
        service.set_device_topology_hidden(self.device.id, True)
        scan_network.return_value = [{"ip": "192.168.1.20", "status": "Online"}]
        detect_device.return_value = {
            "ip": "192.168.1.20",
            "hostname": "Workstation",
            "device_type": "Workstation",
            "network_type": "Ethernet",
            "mac_address": self.device.mac_address,
            "status": "Online",
        }

        graph = service.get_discovery_topology(
            "192.168.1.0/24",
            auto_register=False,
            include_wan=False,
        )

        self.assertNotIn("192.168.1.20", {node.ip for node in graph.nodes})
        self.assertEqual(self.db.query(Device).filter_by(ip="192.168.1.20").count(), 0)

    @patch("app.discovery.scanner.scan_network")
    @patch("app.devices.detector.detect_device_info")
    def test_discovery_shows_new_mac_reusing_a_suppressed_device_ip(
        self,
        detect_device,
        scan_network,
    ):
        service.set_device_topology_hidden(self.device.id, True)
        scan_network.return_value = [{"ip": self.device.ip, "status": "Online"}]
        detect_device.return_value = {
            "ip": self.device.ip,
            "hostname": "Replacement",
            "device_type": "Workstation",
            "network_type": "Ethernet",
            "mac_address": "00:11:22:33:44:99",
            "status": "Online",
        }

        graph = service.get_discovery_topology(
            "192.168.1.0/24",
            auto_register=False,
            include_wan=False,
        )

        self.assertIn(self.device.ip, {node.ip for node in graph.nodes})

    @patch("app.discovery.scanner.scan_network")
    @patch("app.devices.detector.detect_device_info")
    def test_registered_discovery_replaces_suppressed_identity_at_reused_ip(
        self,
        detect_device,
        scan_network,
    ):
        service.set_device_topology_hidden(self.device.id, True)
        scan_network.return_value = [{"ip": self.device.ip, "status": "Online"}]
        detect_device.return_value = {
            "ip": self.device.ip,
            "hostname": "Replacement",
            "device_type": "Workstation",
            "network_type": "Ethernet",
            "mac_address": "00:11:22:33:44:99",
            "status": "Online",
        }

        graph = service.get_discovery_topology(
            "192.168.1.0/24",
            auto_register=True,
            include_wan=False,
        )
        self.db.expire_all()

        self.assertIn(self.device.ip, {node.ip for node in graph.nodes})
        self.assertEqual(self.db.query(Device).filter_by(ip=self.device.ip).count(), 1)
        self.assertFalse(
            self.db.query(Device).filter_by(id=self.device.id).one().topology_hidden
        )
    def test_graph_builder_generates_unique_edges(self):
        graph = TopologyGraphBuilder(
            [self.gateway, self.device, self.other_device],
            statuses={
                self.gateway.ip: "Online",
                self.device.ip: "Online",
                self.other_device.ip: "Online",
            },
            include_wan=True,
            connected_only=False,
        ).build()

        self.assertEqual(len({edge.id for edge in graph.edges}), len(graph.edges))
        self.assertEqual(
            len({frozenset((edge.source, edge.target)) for edge in graph.edges}),
            len(graph.edges),
        )


if __name__ == "__main__":
    unittest.main()
