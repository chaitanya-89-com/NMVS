import subprocess
import unittest
from unittest.mock import Mock, patch

from agent import speed_test


class DeviceLatencyTests(unittest.TestCase):
    @patch("agent.speed_test.subprocess.run")
    @patch("agent.speed_test.platform.system", return_value="Windows")
    def test_latency_averages_icmp_samples_from_device(
        self,
        _system,
        run,
    ):
        run.return_value = Mock(
            stdout="\n".join(
                f"Reply from 1.1.1.1: bytes=32 time={latency}ms TTL=57"
                for latency in (65, 70, 75)
            ),
            stderr="",
            returncode=0,
        )

        latency = speed_test._ping_ms()

        self.assertEqual(latency, 70.0)
        run.assert_called_once_with(
            ["ping", "-n", "10", "-w", "1000", "1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    @patch("agent.speed_test.subprocess.run")
    @patch("agent.speed_test.platform.system", return_value="Linux")
    def test_latency_uses_platform_ping_arguments(self, _system, run):
        run.return_value = Mock(
            stdout="64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=70.25 ms",
            stderr="",
            returncode=0,
        )

        self.assertEqual(speed_test._ping_ms(), 70.25)
        self.assertEqual(
            run.call_args.args[0],
            ["ping", "-c", "10", "-W", "1", "1.1.1.1"],
        )

    @patch("agent.speed_test.subprocess.run")
    @patch("agent.speed_test.platform.system", return_value="Darwin")
    def test_latency_uses_millisecond_timeout_on_macos(self, _system, run):
        run.return_value = Mock(
            stdout="64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=70.25 ms",
            stderr="",
            returncode=0,
        )

        self.assertEqual(speed_test._ping_ms(), 70.25)
        self.assertEqual(
            run.call_args.args[0],
            ["ping", "-c", "10", "-W", "1000", "1.1.1.1"],
        )

    @patch("agent.speed_test.subprocess.run")
    def test_latency_fails_clearly_when_no_icmp_samples_are_received(self, run):
        run.return_value = Mock(
            stdout="Request timed out.",
            stderr="",
            returncode=1,
        )

        with self.assertRaisesRegex(RuntimeError, "no ICMP latency samples"):
            speed_test._ping_ms()

    @patch(
        "agent.speed_test.subprocess.run",
        side_effect=subprocess.TimeoutExpired("ping", 15),
    )
    def test_latency_reports_ping_command_timeout(self, _run):
        with self.assertRaisesRegex(
            speed_test.LatencyMeasurementError,
            "could not measure ICMP latency",
        ):
            speed_test._ping_ms()

    @patch("agent.speed_test._upload", return_value=100)
    @patch("agent.speed_test._download", return_value=100)
    @patch(
        "agent.speed_test._ping_ms",
        side_effect=speed_test.LatencyMeasurementError("ICMP unavailable"),
    )
    def test_speed_test_succeeds_without_icmp_latency(
        self,
        _ping,
        _download,
        _upload,
    ):
        with patch("agent.speed_test._measure", side_effect=[50.0, 10.0]):
            result = speed_test.run_device_speed_test()

        self.assertEqual(result, {
            "download_mbps": 50.0,
            "upload_mbps": 10.0,
            "ping_ms": None,
        })


if __name__ == "__main__":
    unittest.main()
