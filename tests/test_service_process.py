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


def expected_node(
    node_id: str,
    kind: str,
    label: str,
    protected: bool,
    proposal_id: str,
    journal_position: int,
    graph_version: int,
    lifecycle: str = "active",
) -> dict:
    return {
        "node_id": node_id,
        "kind": kind,
        "label": label,
        "lifecycle": lifecycle,
        "evidence_refs": [],
        "created_by": {
            "proposal_id": proposal_id,
            "journal_position": journal_position,
            "graph_version": graph_version,
        },
        "protected": protected,
    }


def expected_edge(
    edge_id: str,
    kind: str,
    source_id: str,
    target_id: str,
    proposal_id: str,
    journal_position: int,
    graph_version: int,
) -> dict:
    return {
        "edge_id": edge_id,
        "kind": kind,
        "source_id": source_id,
        "target_id": target_id,
        "lifecycle": "active",
        "evidence_refs": [],
        "created_by": {
            "proposal_id": proposal_id,
            "journal_position": journal_position,
            "graph_version": graph_version,
        },
    }


# Fixed before the service is invoked. The second graph reuses every entity ID
# while giving each entity different observable state.
RECOVERY_ORACLE = {
    "primary-run": {
        "graph_version": 3,
        "nodes": [
            expected_node("root", "RootGoal", "Primary objective", True, "setup-primary-root", 3, 1),
            expected_node("requirement", "Requirement", "Record the source", False, "populate-primary", 6, 2),
            expected_node("task-a", "Task", "Collect source", False, "populate-primary", 7, 2, "superseded"),
            expected_node("task-b", "Task", "Validate source", False, "populate-primary", 8, 2),
            expected_node("artifact", "Artifact", "Validation report", False, "populate-primary", 9, 2),
        ],
        "edges": [
            expected_edge("requirement-origin", "derived_from", "requirement", "root", "populate-primary", 10, 2),
            expected_edge("task-a-origin", "derived_from", "task-a", "requirement", "populate-primary", 11, 2),
            expected_edge("task-b-origin", "derived_from", "task-b", "requirement", "populate-primary", 12, 2),
            expected_edge("task-b-depends-a", "depends_on", "task-b", "task-a", "populate-primary", 13, 2),
            expected_edge("task-b-produces-report", "produces", "task-b", "artifact", "populate-primary", 14, 2),
            expected_edge("report-origin", "derived_from", "artifact", "task-b", "populate-primary", 15, 2),
        ],
    },
    "counterexample-run": {
        "graph_version": 2,
        "nodes": [
            expected_node("root", "RootGoal", "Control objective", True, "setup-counterexample-root", 3, 1),
            expected_node("requirement", "Requirement", "Control requirement", False, "populate-counterexample", 6, 2),
            expected_node("task-a", "Task", "Control collection", False, "populate-counterexample", 7, 2),
            expected_node("task-b", "Task", "Control validation", False, "populate-counterexample", 8, 2),
            expected_node("artifact", "Artifact", "Control report", False, "populate-counterexample", 9, 2),
        ],
        "edges": [
            expected_edge("requirement-origin", "derived_from", "requirement", "root", "populate-counterexample", 10, 2),
            expected_edge("task-a-origin", "derived_from", "task-a", "requirement", "populate-counterexample", 11, 2),
            expected_edge("task-b-origin", "derived_from", "task-b", "requirement", "populate-counterexample", 12, 2),
            expected_edge("task-b-depends-a", "depends_on", "task-b", "task-a", "populate-counterexample", 13, 2),
            expected_edge("task-b-produces-report", "produces", "task-b", "artifact", "populate-counterexample", 14, 2),
            expected_edge("report-origin", "derived_from", "artifact", "task-b", "populate-counterexample", 15, 2),
        ],
    },
}


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
        self.assertEqual(replay["result"]["reason_code"], "invalid_graph_mutation")

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

    def test_graph_commits_queries_and_restart_agree_between_clients(self) -> None:
        seed = r'''import sys
from problemforger.application.service import ProtocolApplication
from problemforger.modules.persistence import SqliteEventStore
from problemforger.modules.telemetry import NullTelemetrySink
from problemforger.ports.event_store import RunMetadata
with SqliteEventStore(sys.argv[1]) as store:
    store.create_run('smoke-run', RunMetadata.from_value({}))
    ProtocolApplication(store, NullTelemetrySink()).bootstrap_root('smoke-run', 'setup-root', 'Goal')
'''
        subprocess.run([sys.executable, '-c', seed, str(self.database)], cwd=ROOT, env=self.environment, check=True)
        self.start_service()
        operations = [
            {'graph_schema_version': 1, 'op': 'create_node', 'node': {'node_id': 'task', 'kind': 'Task', 'label': 'Work', 'protected': False}},
            {'graph_schema_version': 1, 'op': 'create_edge', 'edge': {'edge_id': 'origin', 'kind': 'derived_from', 'source_id': 'task', 'target_id': 'root'}},
        ]
        mutation = request('propose_mutation', {'run_id': 'smoke-run', 'proposal_id': 'graph-change',
            'request_schema_version': 1, 'expected_graph_version': 1, 'operations': operations, 'evidence': []}, 'graph-write')
        committed = self.client().call(mutation)['result']
        self.assertEqual(committed['status'], 'COMMIT')
        source = (
            "import { callService } from './clients/typescript/service_client.ts';"
            "const requests = JSON.parse(process.argv[1]); const results = [];"
            "for (const request of requests) results.push(await callService(process.argv[2], request));"
            "process.stdout.write(JSON.stringify(results));"
        )
        query = request('get_graph', {'run_id': 'smoke-run', 'limit': 1}, 'page-one')
        first = self.client().call(query)['result']
        continued = request('get_graph', {'run_id': 'smoke-run', 'limit': 100, 'after_cursor': first['next_cursor']}, 'page-two')
        responses = subprocess.run(['node', '--input-type=module', '-e', source,
            json.dumps([mutation, continued]), str(self.socket_path)], cwd=ROOT, env=self.environment,
            check=True, capture_output=True, text=True, timeout=10)
        replay, page = json.loads(responses.stdout)
        self.assertEqual(replay['result'], committed)
        self.assertEqual([node['node_id'] for node in page['result']['nodes']], ['task'])
        self.assertEqual([edge['edge_id'] for edge in page['result']['edges']], ['origin'])
        self.stop_service()
        self.start_service()
        self.assertEqual(self.client().call(mutation)['result'], committed)
        self.assertEqual(self.client().call(continued)['result'], page['result'])

    def test_public_recovery_history_and_run_isolation_match_fixed_oracle(self) -> None:
        seed = r'''import sys
from problemforger.application.service import ProtocolApplication
from problemforger.modules.persistence import SqliteEventStore
from problemforger.modules.telemetry import NullTelemetrySink
from problemforger.ports.event_store import RunMetadata
with SqliteEventStore(sys.argv[1]) as store:
    application = ProtocolApplication(store, NullTelemetrySink())
    for run_id, proposal_id, label in (
        ("primary-run", "setup-primary-root", "Primary objective"),
        ("counterexample-run", "setup-counterexample-root", "Control objective"),
    ):
        store.create_run(run_id, RunMetadata.from_value({}))
        application.bootstrap_root(run_id, proposal_id, label)
'''
        subprocess.run(
            [sys.executable, "-c", seed, str(self.database)],
            cwd=ROOT,
            env=self.environment,
            check=True,
        )

        operations = [
            {"graph_schema_version": 1, "op": "create_node", "node": {
                "node_id": "requirement", "kind": "Requirement", "label": "Record the source", "protected": False}},
            {"graph_schema_version": 1, "op": "create_node", "node": {
                "node_id": "task-a", "kind": "Task", "label": "Collect source", "protected": False}},
            {"graph_schema_version": 1, "op": "create_node", "node": {
                "node_id": "task-b", "kind": "Task", "label": "Validate source", "protected": False}},
            {"graph_schema_version": 1, "op": "create_node", "node": {
                "node_id": "artifact", "kind": "Artifact", "label": "Validation report", "protected": False}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "requirement-origin", "kind": "derived_from", "source_id": "requirement", "target_id": "root"}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "task-a-origin", "kind": "derived_from", "source_id": "task-a", "target_id": "requirement"}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "task-b-origin", "kind": "derived_from", "source_id": "task-b", "target_id": "requirement"}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "task-b-depends-a", "kind": "depends_on", "source_id": "task-b", "target_id": "task-a"}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "task-b-produces-report", "kind": "produces", "source_id": "task-b", "target_id": "artifact"}},
            {"graph_schema_version": 1, "op": "create_edge", "edge": {
                "edge_id": "report-origin", "kind": "derived_from", "source_id": "artifact", "target_id": "task-b"}},
        ]
        counterexample_operations = json.loads(json.dumps(operations))
        counterexample_labels = {
            "requirement": "Control requirement",
            "task-a": "Control collection",
            "task-b": "Control validation",
            "artifact": "Control report",
        }
        for operation in counterexample_operations[:4]:
            node = operation["node"]
            node["label"] = counterexample_labels[node["node_id"]]

        self.start_service()
        client = self.client()
        private_claim = "private-proposal-metadata-must-not-be-returned"
        committed = {}
        for run_id, proposal_id, graph_operations in (
            ("primary-run", "populate-primary", operations),
            ("counterexample-run", "populate-counterexample", counterexample_operations),
        ):
            response = client.call(request(
                "propose_mutation",
                {
                    "run_id": run_id,
                    "proposal_id": proposal_id,
                    "request_schema_version": 1,
                    "expected_graph_version": 1,
                    "operations": graph_operations,
                    "evidence": [{"source": "private", "claim": private_claim}],
                },
                f"populate-{run_id}",
            ))
            self.assertEqual(response["result"]["status"], "COMMIT")
            self.assertEqual(response["result"]["resulting_graph_version"], 2)
            committed[run_id] = response["result"]

        lifecycle = client.call(request(
            "propose_mutation",
            {
                "run_id": "primary-run",
                "proposal_id": "supersede-primary-task",
                "request_schema_version": 1,
                "expected_graph_version": 2,
                "operations": [{
                    "graph_schema_version": 1,
                    "op": "change_lifecycle",
                    "entity_kind": "node",
                    "entity_id": "task-a",
                    "lifecycle": "superseded",
                    "reason": "A later collection task replaced it",
                }],
                "evidence": [],
            },
            "supersede-primary-task",
        ))
        self.assertEqual(lifecycle["result"]["status"], "COMMIT")
        self.assertEqual(lifecycle["result"]["resulting_graph_version"], 3)

        def read_public_graph(request_prefix: str) -> dict:
            results = {}
            for run_id in RECOVERY_ORACLE:
                results[run_id] = client.call(request(
                    "get_graph",
                    {"run_id": run_id, "limit": 100},
                    f"{request_prefix}-{run_id}",
                ))["result"]
                self.assertFalse(results[run_id]["has_more"])
            return results

        before_restart = read_public_graph("before-restart")
        self.stop_service()
        self.start_service()
        client = self.client()
        after_restart = read_public_graph("after-restart")

        def facts(graph: dict) -> dict:
            value = {
                "run_id": graph["run_id"],
                "graph_schema_version": graph["graph_schema_version"],
                "graph_version": graph["graph_version"],
                "nodes": {},
                "edges": {},
            }
            for collection, identifier in (("nodes", "node_id"), ("edges", "edge_id")):
                for entity in graph[collection]:
                    normalized = json.loads(json.dumps(entity))
                    record_id = normalized["created_by"].pop("record_id")
                    self.assertTrue(record_id)
                    value[collection][normalized[identifier]] = normalized
            return value

        for run_id, expected in RECOVERY_ORACLE.items():
            self.assertEqual(before_restart[run_id], after_restart[run_id])
            actual = facts(after_restart[run_id])
            self.assertEqual(actual["run_id"], run_id)
            self.assertEqual(actual["graph_schema_version"], 1)
            self.assertEqual(actual["graph_version"], expected["graph_version"])
            self.assertEqual(
                actual["nodes"],
                {node["node_id"]: node for node in expected["nodes"]},
            )
            self.assertEqual(
                actual["edges"],
                {edge["edge_id"]: edge for edge in expected["edges"]},
            )

        primary = facts(after_restart["primary-run"])
        counterexample = facts(after_restart["counterexample-run"])
        self.assertNotEqual(primary["nodes"], counterexample["nodes"])
        self.assertEqual(primary["nodes"]["task-a"]["lifecycle"], "superseded")
        self.assertEqual(counterexample["nodes"]["task-a"]["lifecycle"], "active")
        self.assertEqual(primary["edges"]["task-b-depends-a"]["lifecycle"], "active")
        self.assertEqual(counterexample["edges"]["task-b-depends-a"]["lifecycle"], "active")

        audit = client.call(request(
            "get_audit_timeline",
            {"run_id": "primary-run", "limit": 100},
            "read-primary-audit",
        ))["result"]
        self.assertNotIn(private_claim, json.dumps((committed, lifecycle, before_restart, after_restart, audit)))

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
