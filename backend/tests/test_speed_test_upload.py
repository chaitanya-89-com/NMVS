import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.speed_monitoring import service, speed_test
from app.devices.model import Device
from app.monitoring.model import MonitoringHistory
from app.speed_monitoring.model import DeviceBandwidthHistory
from app.speed_monitoring.model import AgentDiscoveredNetwork
from app.timezone import now_ist_naive
from database.database import Base


class SpeedTestUploadTests(unittest.TestCase):
    @patch("app.speed_monitoring.speed_test.requests.post")
    @patch("app.speed_monitoring.speed_test.os.urandom")
    def test_upload_streams_payload_in_bounded_chunks(self, urandom, post):
        payload = bytes(range(251)) * 100
        urandom.return_value = payload
        sent_chunks = []
        response = MagicMock()

        def consume_request(*_args, **kwargs):
            sent_chunks.extend(kwargs["data"])
            return response

        post.side_effect = consume_request

        uploaded_size = speed_test._upload_bytes(0)

        self.assertEqual(uploaded_size, len(payload))
        self.assertEqual(b"".join(sent_chunks), payload)
        self.assertTrue(all(
            len(chunk) <= speed_test._TRANSFER_CHUNK_SIZE
            for chunk in sent_chunks
        ))

    @patch("app.speed_monitoring.speed_test.time.perf_counter", side_effect=[0, 6])
    @patch("app.speed_monitoring.speed_test.requests.post")
    @patch("app.speed_monitoring.speed_test.os.urandom", return_value=b"x" * 100_000)
    def test_upload_stops_after_transfer_time_limit(self, _urandom, post, _clock):
        response = MagicMock()
        post.side_effect = lambda *_args, **kwargs: (
            list(kwargs["data"]) and response
        )

        with patch.object(speed_test, "_MAX_TRANSFER_SECONDS", 5):
            uploaded_size = speed_test._upload_bytes(0)

        self.assertEqual(uploaded_size, speed_test._TRANSFER_CHUNK_SIZE)
        response.raise_for_status.assert_called_once_with()

    @patch("app.speed_monitoring.speed_test.time.perf_counter", side_effect=[0, 1, 6])
    @patch("app.speed_monitoring.speed_test.requests.get")
    def test_download_stops_after_transfer_time_limit(self, get, _clock):
        response = get.return_value
        response.iter_content.return_value = [b"a" * 4096, b"b" * 4096, b"c" * 4096]

        with patch.object(speed_test, "_MAX_TRANSFER_SECONDS", 5):
            downloaded_size = speed_test._download_bytes(0)

        self.assertEqual(downloaded_size, 8_192)
        response.close.assert_called_once_with()

    @patch("app.speed_monitoring.speed_test.time.perf_counter", side_effect=[0, 0.01])
    @patch("app.speed_monitoring.speed_test.requests.Session")
    def test_ping_uses_one_session_sample(self, session_factory, _clock):
        session = session_factory.return_value.__enter__.return_value
        session.get.return_value.content = b"x"
        session.get.return_value.raise_for_status.return_value = None

        ping_ms = speed_test._get_ping_ms()

        self.assertEqual(ping_ms, 10.0)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(
            session.get.call_args.kwargs["timeout"],
            (speed_test._CONNECT_TIMEOUT_SECONDS, speed_test._READ_TIMEOUT_SECONDS),
        )

    @patch("app.speed_monitoring.speed_test._get_ping_ms", side_effect=speed_test.requests.ReadTimeout)
    def test_read_timeout_has_actionable_backend_connectivity_message(self, _ping):
        with self.assertRaisesRegex(
            RuntimeError,
            "timed out while waiting for a response.*outbound HTTPS",
        ):
            speed_test.run_speed_test()


class DeviceSpeedTestJobTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch("app.speed_monitoring.service.SessionLocal", self.session_factory)
        self.session_patch.start()
        self.db = self.session_factory()
        now = now_ist_naive()
        self.db.add(Device(
            name="Test device",
            ip="192.168.1.25",
            device_type="Test",
            network_type="Unknown",
            source="agent",
            speed_agent_seen_at=now,
        ))
        self.db.add(MonitoringHistory(
            ip="192.168.1.25",
            status="Online",
            checked_at=now,
        ))
        self.db.add(AgentDiscoveredNetwork(cidr="192.168.1.0/24"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_only_recently_online_agent_devices_can_be_tested(self):
        with self.assertRaisesRegex(LookupError, "Device not found"):
            service.request_device_test("192.168.1.26")

        old_check = self.db.query(MonitoringHistory).filter_by(ip="192.168.1.25").one()
        old_check.checked_at = now_ist_naive() - timedelta(minutes=5)
        self.db.commit()
        with self.assertRaisesRegex(ConnectionError, "offline or its Online report is stale"):
            service.request_device_test("192.168.1.25")

    def test_malformed_ipv4_is_rejected_before_database_or_agent_checks(self):
        for ip in ("10.20.56.888", "0.0.9.-90", "10.20.56", "10.20.56.abc"):
            with self.subTest(ip=ip):
                with self.assertRaisesRegex(ValueError, "valid IPv4"):
                    service.request_device_test(ip)

    def test_valid_ip_outside_configured_network_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the configured NMVS network"):
            service.request_device_test("10.20.56.25")

    def test_unknown_ip_without_a_configured_network_is_still_not_found(self):
        self.db.query(AgentDiscoveredNetwork).delete()
        self.db.commit()

        with self.assertRaisesRegex(LookupError, "Device not found"):
            service.request_device_test("192.168.1.26")

    def test_inside_network_but_undiscovered_ip_is_not_found(self):
        with self.assertRaisesRegex(LookupError, "Device not found"):
            service.request_device_test("192.168.1.26")

    def test_missing_or_stale_device_agent_is_unavailable(self):
        device = self.db.query(Device).filter_by(ip="192.168.1.25").one()
        device.speed_agent_seen_at = None
        self.db.commit()
        with self.assertRaisesRegex(ConnectionError, "device agent is not currently available"):
            service.request_device_test("192.168.1.25")

        device.speed_agent_seen_at = now_ist_naive() - timedelta(minutes=5)
        self.db.commit()
        with self.assertRaisesRegex(ConnectionError, "device agent is not currently available"):
            service.request_device_test("192.168.1.25")

    def test_device_agent_poll_makes_device_ready_for_a_test(self):
        device = self.db.query(Device).filter_by(ip="192.168.1.25").one()
        device.speed_agent_seen_at = None
        self.db.commit()

        with self.assertRaisesRegex(ConnectionError, "device agent is not currently available"):
            service.request_device_test("192.168.1.25")

        self.assertIsNone(service.claim_device_test(["192.168.1.25"]))
        self.db.refresh(device)
        self.assertIsNotNone(device.speed_agent_seen_at)
        job = service.request_device_test("192.168.1.25")
        self.assertEqual(job["status"], "queued")

    def test_target_agent_claims_and_completes_its_own_test(self):
        job = service.request_device_test("192.168.1.25")
        self.assertEqual(job["status"], "queued")
        self.assertIsNone(service.claim_device_test(["192.168.1.26"]))

        claimed = service.claim_device_test(["192.168.1.25"])
        self.assertEqual(claimed, {"id": job["id"], "ip": "192.168.1.25"})
        completed = service.complete_device_test(
            job_id=job["id"],
            ip="192.168.1.25",
            download_mbps=38.5,
            upload_mbps=12.25,
            ping_ms=18.0,
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["measurement_source"], "device-agent")
        self.assertEqual(completed["ping_ms"], 18.0)

        history = self.db.query(DeviceBandwidthHistory).one()
        self.assertEqual(history.ip, "192.168.1.25")
        self.assertEqual(history.download_mbps, 38.5)
        self.assertEqual(history.ping_ms, 18.0)
        self.assertEqual(history.to_dict()["ping_ms"], 18.0)
        self.assertEqual(history.measurement_source, "device-agent")
        self.assertEqual(history.to_dict()["measurement_source"], "device-agent")

    def test_job_result_cannot_be_submitted_for_a_different_device(self):
        job = service.request_device_test("192.168.1.25")
        service.claim_device_test(["192.168.1.25"])
        with self.assertRaisesRegex(ValueError, "does not match"):
            service.complete_device_test(
                job_id=job["id"],
                ip="192.168.1.26",
                download_mbps=1,
                upload_mbps=1,
            )


if __name__ == "__main__":
    unittest.main()
