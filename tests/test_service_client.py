from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from problemforger.application.protocol import encode_response
from problemforger.service.client import (
    ServiceClient,
    ServiceTimeoutError,
    ServiceUnavailableError,
)


REQUEST = {
    "protocol_schema_version": 1,
    "request_id": "client-test",
    "operation": "get_run",
    "params": {"run_id": "run-1"},
}


class ServiceClientTests(unittest.TestCase):
    def test_absent_service_uses_a_distinct_unavailable_error(self) -> None:
        class MissingSocket:
            def __init__(self, *args) -> None:
                pass

            def settimeout(self, timeout) -> None:
                pass

            def connect(self, path) -> None:
                raise FileNotFoundError(2, "No such file or directory", path)

            def close(self) -> None:
                pass

        with patch("problemforger.service.client.socket.socket", MissingSocket):
            with self.assertRaises(ServiceUnavailableError):
                ServiceClient("/missing.sock").call(REQUEST)

    def test_deadline_uses_a_distinct_timeout_error(self) -> None:
        class StalledSocket:
            def __init__(self, *args) -> None:
                pass

            def settimeout(self, timeout) -> None:
                pass

            def connect(self, path) -> None:
                pass

            def sendall(self, payload) -> None:
                pass

            def recv(self, size) -> bytes:
                raise socket.timeout("timed out")

            def close(self) -> None:
                pass

        with patch("problemforger.service.client.socket.socket", StalledSocket):
            with self.assertRaises(ServiceTimeoutError):
                ServiceClient("/stalled.sock", timeout_seconds=0.01).call(REQUEST)

    def test_timeout_must_be_positive(self) -> None:
        for timeout in (0, -1, True, float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                ServiceClient("/worker.sock", timeout_seconds=timeout)

    def test_response_is_validated_against_its_request(self) -> None:
        expected = {
            "protocol_schema_version": 1,
            "request_id": "client-test",
            "error": {"code": "NOT_FOUND", "message": "run was not found"},
        }
        frame = encode_response(expected, REQUEST) + b"\n"

        class RespondingSocket:
            def __init__(self, *args) -> None:
                pass

            def settimeout(self, timeout) -> None:
                pass

            def connect(self, path) -> None:
                pass

            def sendall(self, payload) -> None:
                pass

            def recv(self, size) -> bytes:
                return frame

            def close(self) -> None:
                pass

        with patch("problemforger.service.client.socket.socket", RespondingSocket):
            response = ServiceClient("/worker.sock").call(REQUEST)
        self.assertEqual(response["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
