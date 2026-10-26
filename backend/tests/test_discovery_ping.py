import socket
import subprocess
import unittest
from unittest.mock import patch

from app.discovery.ping import check_device_status


class CheckDeviceStatusTests(unittest.TestCase):
    @patch("app.discovery.ping.subprocess.run")
    def test_tcp_service_marks_device_online_when_icmp_fails(self, run_ping):
        run_ping.return_value.returncode = 1

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            result = check_device_status("127.0.0.1", tcp_port=port)

        self.assertEqual(result["status"], "Online")
        self.assertEqual(result["checked_by"], f"TCP/{port}")

    @patch("app.discovery.ping.subprocess.run")
    @patch("app.discovery.ping.socket.create_connection")
    def test_no_ping_or_tcp_response_is_unknown(
        self,
        create_connection,
        run_ping,
    ):
        run_ping.return_value.returncode = 1
        create_connection.side_effect = TimeoutError

        result = check_device_status("192.0.2.10", tcp_port=443)

        self.assertEqual(result["status"], "Unknown")
        self.assertIn("does not prove", result["detail"])

    @patch("app.discovery.ping.subprocess.run")
    @patch("app.discovery.ping.socket.create_connection")
    def test_tcp_refusal_confirms_the_device_responded(
        self,
        create_connection,
        run_ping,
    ):
        run_ping.return_value.returncode = 1
        create_connection.side_effect = ConnectionRefusedError

        result = check_device_status("192.0.2.10", tcp_port=443)

        self.assertEqual(result["status"], "Online")
        self.assertIn("refused", result["detail"])

    @patch("app.discovery.ping.subprocess.run")
    @patch("app.discovery.ping.socket.create_connection")
    def test_icmp_success_skips_tcp_fallback(
        self,
        create_connection,
        run_ping,
    ):
        run_ping.return_value.returncode = 0

        result = check_device_status("192.0.2.10", tcp_port=443)

        self.assertEqual(result["status"], "Online")
        self.assertEqual(result["checked_by"], "ICMP")
        create_connection.assert_not_called()

    def test_ping_process_has_a_timeout(self):
        with patch(
            "app.discovery.ping.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1),
        ) as run_ping:
            check_device_status("192.0.2.10")

        self.assertEqual(run_ping.call_args.kwargs["timeout"], 3)


if __name__ == "__main__":
    unittest.main()
