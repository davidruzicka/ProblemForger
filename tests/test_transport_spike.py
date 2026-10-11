from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from spikes.transport import transport_spike as spike


class TransportSpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="pf-transport-test-")
        cls.http_process, cls.http_ready, _ = spike._start("http", cls.temporary.name)
        cls.unix_process, cls.unix_ready, _ = spike._start("unix", cls.temporary.name)
        cls.http = spike.HttpClient(cls.http_ready["host"], cls.http_ready["port"])
        cls.unix = spike.UnixClient(cls.unix_ready["socket"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.http.close()
        cls.unix.close()
        cls.http_process.terminate()
        cls.unix_process.terminate()
        cls.http_process.wait(timeout=5)
        cls.unix_process.wait(timeout=5)
        cls.temporary.cleanup()

    def test_versioned_echo_works_over_both_transports(self) -> None:
        request = spike._request("echo-1", "echo", {"payload": {"value": "ok"}})
        for client in (self.http, self.unix):
            events, response = client.call(request)
            self.assertEqual(events, [])
            self.assertEqual(response["protocol_version"], 1)
            self.assertEqual(response["request_id"], "echo-1")
            self.assertEqual(response["result"], {"payload": {"value": "ok"}})

    def test_observations_stream_before_final_response(self) -> None:
        request = spike._request("stream-1", "stream_observations", {"count": 2})
        for client in (self.http, self.unix):
            events, response = client.call(request)
            self.assertEqual([event["event"]["sequence"] for event in events], [0, 1])
            self.assertEqual(response["result"], {"event_count": 2})

    def test_worker_capability_rejects_admin_and_store_methods(self) -> None:
        for method in ("admin.evidence_ingest", "admin.policy.update", "journal.append", "store.owner.acquire", "credentials.read"):
            for client in (self.http, self.unix):
                _, response = client.call(spike._request(method, method, {}))
                self.assertEqual(response["error"]["code"], "METHOD_NOT_FOUND")

    def test_unsupported_protocol_version_and_invalid_params_are_explicit(self) -> None:
        unsupported = spike._request("bad-version", "echo", {"payload": "x"})
        unsupported["protocol_version"] = 2
        _, response = self.unix.call(unsupported)
        self.assertEqual(response["error"]["code"], "UNSUPPORTED_VERSION")
        invalid = spike._request("bad-params", "stream_observations", {"count": True})
        _, response = self.http.call(invalid)
        self.assertEqual(response["error"]["code"], "INVALID_PARAMS")

    def test_unknown_fields_and_invalid_json_are_rejected(self) -> None:
        request = spike._request("extra", "echo", {"payload": "x"})
        request["unexpected"] = True
        _, response = self.unix.call(request)
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")
        parsed, error = spike._decode_request(b"{not-json}")
        self.assertIsNone(parsed)
        self.assertEqual(error["error"]["code"], "INVALID_JSON")
        parsed, error = spike._decode_request(b"NaN")
        self.assertIsNone(parsed)
        self.assertEqual(error["error"]["code"], "INVALID_JSON")

    def test_http_rejects_oversized_content_length_without_reading_body(self) -> None:
        connection = http.client.HTTPConnection(self.http_ready["host"], self.http_ready["port"], timeout=2)
        connection.putrequest("POST", "/v1/request")
        connection.putheader("Content-Length", str(spike.MAX_MESSAGE_BYTES + 1))
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 413)
        self.assertEqual(json.loads(response.read())["error"]["code"], "PAYLOAD_TOO_LARGE")
        connection.close()

    def test_jsonl_rejects_oversized_frames_and_missing_newline(self) -> None:
        oversized = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        oversized.connect(self.unix_ready["socket"])
        oversized.sendall(b"x" * (spike.MAX_MESSAGE_BYTES + 1) + b"\n")
        line = oversized.makefile("rb").readline(1024)
        self.assertEqual(json.loads(line)["error"]["code"], "PAYLOAD_TOO_LARGE")
        oversized.close()

        incomplete = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        incomplete.connect(self.unix_ready["socket"])
        incomplete.sendall(b"not-json")
        incomplete.shutdown(socket.SHUT_WR)
        line = incomplete.makefile("rb").readline(1024)
        self.assertEqual(json.loads(line)["error"]["code"], "INVALID_FRAME")
        incomplete.close()

    def test_clients_reject_non_positive_timeouts_and_oversized_requests(self) -> None:
        with self.assertRaises(ValueError):
            spike.HttpClient("127.0.0.1", 1, timeout=0)
        with self.assertRaises(ValueError):
            spike.UnixClient("/unused", timeout=0)
        request = spike._request("large", "echo", {"payload": "x" * spike.MAX_MESSAGE_BYTES})
        with self.assertRaises(ValueError):
            self.http.call(request)
        with self.assertRaises(ValueError):
            self.unix.call(request)

    def test_process_failure_is_reported_as_connection_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pf-transport-failure-") as directory:
            for transport in ("http", "unix"):
                process, ready, _ = spike._start(transport, directory)
                process.terminate()
                process.wait(timeout=5)
                if transport == "http":
                    client = spike.HttpClient(ready["host"], ready["port"], timeout=0.2)
                    try:
                        with self.assertRaises(OSError):
                            client.call(spike._request("after-exit", "echo", {"payload": "x"}))
                    finally:
                        client.close()
                else:
                    with self.assertRaises(FileNotFoundError):
                        spike.UnixClient(ready["socket"], timeout=0.2)

    def test_percentile_and_benchmark_report(self) -> None:
        self.assertEqual(spike._percentile([4.0, 1.0, 3.0, 2.0], 0.95), 3.0)
        with self.assertRaises(ValueError):
            spike._percentile([], 0.5)
        report = spike.benchmark(iterations=500, large_iterations=30)
        self.assertEqual(set(report["transports"]), {"http", "unix"})
        self.assertIn("startup_ms", report["transports"]["http"])
        self.assertIn("64KiB_json_encode_decode_ms", report["transports"]["unix"])
        print("TRANSPORT_BENCHMARK", json.dumps(report, sort_keys=True))

    def test_typescript_client_runs_against_both_candidates(self) -> None:
        version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
        numbers = tuple(int(part) for part in version.lstrip("v").split(".")[:2])
        if numbers < (22, 6):
            self.skipTest("the dependency-free TypeScript smoke client needs Node.js 22.6+ type stripping")
        client = Path(__file__).resolve().parents[1] / "spikes/transport/client.ts"
        targets = (
            ("http", f"http://{self.http_ready['host']}:{self.http_ready['port']}"),
            ("unix", self.unix_ready["socket"]),
        )
        for transport, target in targets:
            for method in ("echo", "stream_observations"):
                result = subprocess.run(
                    ["node", "--experimental-strip-types", str(client), transport, target, "32", method],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_unix_permission_and_capability_demo(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("Unix-domain socket permission proof requires Linux")
        demo = Path(__file__).resolve().parents[1] / "spikes/transport/security_demo.py"
        if os.geteuid() == 0:
            command = [sys.executable, str(demo)]
        else:
            sudo = shutil.which("sudo")
            if sudo is None:
                self.skipTest("run the permission proof as root or with passwordless sudo")
            command = [sudo, "-n", sys.executable, str(demo)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        print("TRANSPORT_SECURITY_DEMO", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
