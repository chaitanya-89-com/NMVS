import unittest
from unittest.mock import Mock, patch

import requests

from agent.agent import (
    AgentAuthenticationError,
    AgentServerError,
    AgentValidationError,
    ping_device,
    poll_device_speed_tests,
    send_scan_results,
)


def confirmation(received):
    return {
        "message": "Scan results processed",
        "received": received,
        "processed": received,
        "devices_created": received,
        "devices_updated": 0,
        "monitoring_records_created": received,
        "alert_failures": 0,
    }


class AgentSubmissionTests(unittest.TestCase):
    @patch("agent.agent.time.sleep", side_effect=KeyboardInterrupt)
    @patch("agent.agent.run_device_speed_test")
    @patch("agent.agent.requests.post")
    def test_device_agent_runs_and_submits_own_speed_measurement(
        self,
        post,
        run_speed_test,
        _sleep,
    ):
        claim = Mock()
        claim.raise_for_status.return_value = None
        claim.json.return_value = {
            "job": {"id": 42, "ip": "192.168.1.25"},
        }
        complete = Mock()
        complete.raise_for_status.return_value = None
        complete.json.return_value = {"status": "completed"}
        post.side_effect = [claim, complete]
        run_speed_test.return_value = {
            "download_mbps": 50.0,
            "upload_mbps": 20.0,
            "ping_ms": 9.5,
        }

        with self.assertRaises(KeyboardInterrupt):
            poll_device_speed_tests(
                "https://nmvs.example",
                "test-token",
                ["192.168.1.25"],
                poll_interval=1,
            )

        self.assertEqual(post.call_count, 2)
        self.assertEqual(
            post.call_args_list[0].kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )
        self.assertEqual(
            post.call_args_list[1].kwargs["json"],
            {
                "download_mbps": 50.0,
                "upload_mbps": 20.0,
                "ping_ms": 9.5,
                "ip": "192.168.1.25",
            },
        )
        self.assertEqual(
            post.call_args_list[1].kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )

    @patch("agent.agent.requests.post")
    def test_sends_bearer_token_and_json_results(self, post):
        response = Mock(ok=True)
        response.json.return_value = confirmation(1)
        post.return_value = response

        result = send_scan_results(
            "http://127.0.0.1:8000/agent/scan-results",
            "test-token",
            [{"ip": "192.168.1.2", "status": "Online", "latency_ms": 1.5}],
            network="192.168.1.0/24",
        )

        self.assertEqual(result["message"], "Scan results processed")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["devices"][0]["latency_ms"],
            1.5,
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["network"],
            "192.168.1.0/24",
        )
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 30))

    @patch("agent.agent.requests.post")
    def test_rejected_request_is_not_reported_as_success(self, post):
        response = Mock(ok=False, status_code=401)
        response.json.return_value = {"detail": "Unauthorized"}
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "wrong-token",
                [],
            )

    @patch("agent.agent.requests.post", side_effect=requests.ConnectionError("offline"))
    def test_backend_unavailable_propagates_connection_error(self, post):
        with self.assertRaises(requests.ConnectionError):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "test-token",
                [],
            )

    @patch("agent.agent.requests.post")
    def test_invalid_success_response_is_reported(self, post):
        response = Mock(ok=True)
        response.json.side_effect = ValueError("not JSON")
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "test-token",
                [],
            )

        response.json.side_effect = None
        response.json.return_value = {"message": "accepted"}
        with self.assertRaisesRegex(RuntimeError, "did not confirm"):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "test-token",
                [],
            )

    @patch("agent.agent.time.sleep")
    @patch("agent.agent.requests.post")
    def test_transient_connection_error_is_retried(self, post, sleep):
        success = Mock(ok=True)
        success.json.return_value = confirmation(0)
        post.side_effect = [requests.ConnectionError("offline"), success]

        result = send_scan_results(
            "http://127.0.0.1:8000/agent/scan-results",
            "test-token",
            [],
            attempts=2,
        )

        self.assertEqual(result["processed"], 0)
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("agent.agent.time.sleep")
    @patch("agent.agent.requests.post", side_effect=requests.Timeout("timed out"))
    def test_request_timeout_is_retried_then_reported(self, post, sleep):
        with self.assertRaises(requests.Timeout):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "test-token",
                [],
                attempts=2,
            )
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("agent.agent.time.sleep")
    @patch("agent.agent.requests.post")
    def test_server_error_retries_but_auth_and_validation_do_not(
        self,
        post,
        sleep,
    ):
        server_error = Mock(ok=False, status_code=503)
        server_error.json.return_value = {"detail": "Temporarily unavailable"}
        success = Mock(ok=True)
        success.json.return_value = confirmation(0)
        post.side_effect = [server_error, success]

        send_scan_results(
            "http://127.0.0.1:8000/agent/scan-results",
            "test-token",
            [],
            attempts=2,
        )
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1)

        post.side_effect = None
        for status_code, error_type in (
            (401, AgentAuthenticationError),
            (422, AgentValidationError),
        ):
            response = Mock(ok=False, status_code=status_code)
            response.json.return_value = {"detail": "Rejected"}
            post.reset_mock()
            post.return_value = response
            with self.subTest(status_code=status_code):
                with self.assertRaises(error_type):
                    send_scan_results(
                        "http://127.0.0.1:8000/agent/scan-results",
                        "test-token",
                        [],
                        attempts=3,
                    )
            post.assert_called_once()

        post.reset_mock()
        persistent_server_error = Mock(ok=False, status_code=503)
        persistent_server_error.json.return_value = {"detail": "Unavailable"}
        post.return_value = persistent_server_error
        with self.assertRaises(AgentServerError):
            send_scan_results(
                "http://127.0.0.1:8000/agent/scan-results",
                "test-token",
                [],
                attempts=2,
                retry_delay_seconds=0,
            )
        self.assertEqual(post.call_count, 2)

    @patch("agent.agent.subprocess.run")
    def test_ping_latency_is_null_when_windows_reports_less_than_one_ms(
        self,
        run_ping,
    ):
        run_ping.return_value = Mock(
            returncode=0,
            stdout="Reply from 192.168.1.2: time<1ms",
            stderr="",
        )
        result = ping_device("192.168.1.2")
        self.assertEqual(result["status"], "Online")
        self.assertIsNone(result["latency_ms"])


if __name__ == "__main__":
    unittest.main()
