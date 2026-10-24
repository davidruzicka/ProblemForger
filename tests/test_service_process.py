from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from problemforger.application.protocol import encode_request
from problemforger.service.client import ServiceClient


ROOT = Path(__file__).resolve().parents[1]


def request(operation: str, params: dict, request_id: str) -> dict:
    return {
        "protocol_schema_version": 1,
        "request_id": request_id,
        "operation": operation,
        "params": params,
    }


def create_run_request(run_id: str = "smoke-run") -> dict:
    return request(
        "create_run",
        {
            "run_id": run_id,
            "run_metadata": {
                "metadata_schema_version": 1,
                "data": {"purpose": "P1 service smoke"},
            },
        },
        "create-run-request",
    )


def propose_request() -> dict:
    return request(
        "propose_mutation",
        {
            "run_id": "smoke-run",
            "proposal_id": "proposal-lost-response",
            "request_schema_version": 1,
            "expected_graph_version": 0,
            "operations": [{"op": "add_node", "node": {"id": "uncommitted"}}],
            "evidence": [{"source": "worker", "claim": "candidate"}],
        },
        "propose-request",
    )


class ServiceProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "events.sqlite3"
        self.socket_path = self.root / "worker.sock"
        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {
                            "provider": "sqlite",
                            "config": {"path": str(self.database)},
                        },
                        "telemetry": {"provider": "null", "config": {}},
                    },
                }
            ),
            encoding="utf-8",
        )
        self.process: subprocess.Popen[str] | None = None
        self.environment = os.environ.copy()
        self.environment["PYTHONPATH"] = str(ROOT / "src")

    def tearDown(self) -> None:
        self.stop_service()
        self.temporary.cleanup()

    def start_service(self) -> None:
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "problemforger.service",
                "--config",
                str(self.config_path),
                "--socket",
                str(self.socket_path),
            ],
            cwd=ROOT,
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10
        assert self.process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    self.fail(f"service exited before readiness: {stderr}")
                if selector.select(timeout=0.02):
                    ready = self.process.stdout.readline()
                    if not ready:
                        stderr = self.process.stderr.read() if self.process.stderr else ""
                        self.fail(f"service closed readiness output: {stderr}")
                    self.assertEqual(json.loads(ready).get("event"), "ready")
                    return
        self.fail("service did not become ready")

    def stop_service(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stderr:
            process.stderr.close()
        if process.stdout:
            process.stdout.close()

    def client(self) -> ServiceClient:
        return ServiceClient(str(self.socket_path), timeout_seconds=2)

    def send_without_reading(self, value: dict) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.connect(str(self.socket_path))
            connection.sendall(encode_request(value) + b"\n")
        finally:
            connection.close()

    def test_lost_response_retry_after_restart_replays_one_durable_outcome(self) -> None:
        self.start_service()
        client = self.client()
        created = client.call(create_run_request())
        self.assertIn("result", created)

        mutation = propose_request()
        self.send_without_reading(mutation)
        expected = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = client.call(
                request(
                    "get_proposal",
                    {"run_id": "smoke-run", "proposal_id": "proposal-lost-response"},
                    "poll-proposal",
                )
            )
            if "result" in status and status["result"]["status"] != "PENDING":
                expected = status
                break
            time.sleep(0.02)
        self.assertIsNotNone(expected, "service did not durably finish the proposal")
        self.stop_service()

        self.start_service()
        replay = self.client().call(mutation)
        self.assertEqual(replay["result"], expected["result"])
        timeline = self.client().call(
            request(
                "get_audit_timeline",
                {"run_id": "smoke-run", "limit": 10},
                "read-audit",
            )
        )
        self.assertEqual(
            [record["record_type"] for record in timeline["result"]["records"]],
            ["proposal_receipt", "mutation_decision"],
        )
        self.assertEqual(replay["result"]["reason_code"], "P1_GOVERNANCE_NOT_IMPLEMENTED")

    def test_crash_after_receipt_recovers_from_sqlite_without_duplicate_receipt(self) -> None:
        seed = r'''import os, sys
from datetime import datetime, timezone
from problemforger.core.journal import JsonDocument, NormalizedMutationRequest, ProposalReceipt, RecordMetadata, proposal_request_hash
from problemforger.modules.persistence import SqliteEventStore
from problemforger.ports.event_store import RunMetadata
store = SqliteEventStore(sys.argv[1])
metadata = RunMetadata(JsonDocument.from_value({"purpose": "P1 service smoke"}))
store.create_run("smoke-run", metadata)
normalized = NormalizedMutationRequest(1, 0, (JsonDocument.from_value({"op": "add_node", "node": {"id": "uncommitted"}}),), (JsonDocument.from_value({"source": "worker", "claim": "candidate"}),))
receipt = ProposalReceipt(RecordMetadata("smoke-run", "crash-receipt", datetime.now(timezone.utc)), "proposal-lost-response", normalized)
store.record_proposal("smoke-run", "proposal-lost-response", proposal_request_hash(normalized), normalized, receipt)
os._exit(23)
'''
        crashed = subprocess.run(
            [sys.executable, "-c", seed, str(self.database)],
            cwd=ROOT,
            env=self.environment,
            check=False,
        )
        self.assertEqual(crashed.returncode, 23)
        self.start_service()
        resumed = self.client().call(propose_request())
        self.assertEqual(resumed["result"]["status"], "REJECT")
        timeline = self.client().call(
            request(
                "get_audit_timeline",
                {"run_id": "smoke-run", "limit": 10},
                "read-audit",
            )
        )
        self.assertEqual(
            [record["record_type"] for record in timeline["result"]["records"]],
            ["proposal_receipt", "mutation_decision"],
        )

    def test_typescript_client_uses_the_same_worker_protocol(self) -> None:
        self.start_service()
        request_value = create_run_request("typescript-run")
        source = (
            "import { callService } from './clients/typescript/service_client.ts';"
            "const request = JSON.parse(process.argv[1]);"
            "const result = await callService(process.argv[2], request);"
            "process.stdout.write(JSON.stringify(result));"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", source, json.dumps(request_value), str(self.socket_path)],
            cwd=ROOT,
            env=self.environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        response = json.loads(result.stdout)
        self.assertEqual(response["request_id"], "create-run-request")
        self.assertEqual(response["result"]["run_id"], "typescript-run")

    def test_malformed_frame_is_distinguished_and_does_not_stop_service(self) -> None:
        self.start_service()
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        try:
            connection.connect(str(self.socket_path))
            connection.sendall(b"not-json\n")
            response = json.loads(connection.makefile("rb").readline())
        finally:
            connection.close()
        self.assertEqual(response["error"]["code"], "PROTOCOL_ERROR")
        created = self.client().call(create_run_request())
        self.assertEqual(created["result"]["run_id"], "smoke-run")

    def test_normal_service_rejects_ephemeral_memory_configuration(self) -> None:
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {"provider": "memory", "config": {}},
                        "telemetry": {"provider": "null", "config": {}},
                    },
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "problemforger.service",
                "--config",
                str(self.config_path),
                "--socket",
                str(self.socket_path),
            ],
            cwd=ROOT,
            env=self.environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("durable EventStore", result.stderr)
        self.assertFalse(self.socket_path.exists())

