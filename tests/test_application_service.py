"""P1 command/query behavior over the provider-neutral EventStore port."""

from datetime import datetime, timezone
import unittest

from problemforger.application.service import ProtocolApplication
from problemforger.core.journal import (
    CRunRecoveryContext,
    GovernanceOutcome,
    GraphChangedEvent,
    JsonDocument,
    MutationDecision,
    NonTerminalAuditRecord,
    NormalizedMutationRequest,
    ProposalAbandoned,
    ProposalReceipt,
    RecordMetadata,
    proposal_request_hash,
)
from problemforger.modules.persistence import MemoryEventStore
from problemforger.modules.telemetry import RecordingTelemetrySink
from problemforger.ports.event_store import RecordProposalStatus, RunMetadata


NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def message(operation: str, params: dict, request_id: str = "request-1") -> dict:
    return {
        "protocol_schema_version": 1,
        "request_id": request_id,
        "operation": operation,
        "params": params,
    }


def run_metadata(data: dict | None = None) -> dict:
    return {"metadata_schema_version": 1, "data": data or {"purpose": "P1 smoke"}}


def proposal(
    proposal_id: str = "proposal-1",
    *,
    run_id: str = "run-1",
    expected_graph_version: int = 0,
    evidence: list[dict] | None = None,
) -> dict:
    return message(
        "propose_mutation",
        {
            "run_id": run_id,
            "proposal_id": proposal_id,
            "request_schema_version": 1,
            "expected_graph_version": expected_graph_version,
            "operations": [{"op": "add_node", "node": {"id": "node-1"}}],
            "evidence": evidence or [],
        },
    )


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryEventStore()
        self.telemetry = RecordingTelemetrySink()
        self.application = ProtocolApplication(self.store, self.telemetry)

    def tearDown(self) -> None:
        self.store.close()
        self.telemetry.close()

    def create_run(self, *, run_id: str = "run-1", metadata: dict | None = None) -> dict:
        return self.application.handle(
            message(
                "create_run",
                {"run_id": run_id, "run_metadata": metadata or run_metadata()},
            )
        )

    def _normalized(self, request: dict) -> NormalizedMutationRequest:
        params = request["params"]
        return NormalizedMutationRequest(
            request_schema_version=params["request_schema_version"],
            expected_graph_version=params["expected_graph_version"],
            operations=tuple(JsonDocument.from_value(item) for item in params["operations"]),
            evidence=tuple(JsonDocument.from_value(item) for item in params["evidence"]),
        )

    def _seed_receipt(self, request: dict, *, c_context=None) -> NormalizedMutationRequest:
        params = request["params"]
        normalized = self._normalized(request)
        receipt = ProposalReceipt(
            metadata=RecordMetadata(
                params["run_id"],
                f"{params['proposal_id']}-receipt",
                NOW,
            ),
            proposal_id=params["proposal_id"],
            request=normalized,
            c_run_recovery_context=c_context,
        )
        result = self.store.record_proposal(
            params["run_id"],
            params["proposal_id"],
            proposal_request_hash(normalized),
            normalized,
            receipt,
        )
        self.assertEqual(RecordProposalStatus.CREATED, result.status)
        return normalized

    def _seed_commit(self, *, run_id: str = "run-1", proposal_id: str = "seed") -> None:
        request = proposal(proposal_id, run_id=run_id)
        normalized = self._seed_receipt(request)
        request_hash = proposal_request_hash(normalized)
        decision = MutationDecision(
            metadata=RecordMetadata(run_id, f"{proposal_id}-decision", NOW),
            proposal_id=proposal_id,
            request_hash=request_hash,
            expected_graph_version=0,
            resulting_graph_version=1,
            outcome=GovernanceOutcome.COMMIT,
        )
        event = GraphChangedEvent(
            metadata=RecordMetadata(run_id, f"{proposal_id}-event", NOW),
            proposal_id=proposal_id,
            graph_version=1,
            event_type="node.added",
            event_schema_version=1,
            payload=JsonDocument.from_value({"node_id": "seed-node"}),
        )
        self.store.append_graph(run_id, proposal_id, 0, (decision,), (event,))

    def test_run_registration_is_idempotent_and_queries_are_explicitly_scoped(self) -> None:
        created = self.create_run()
        self.assertTrue(created["result"]["created"])
        self.assertEqual(0, created["result"]["graph_version"])
        self.assertEqual(0, created["result"]["last_journal_position"])

        repeated = self.create_run()
        self.assertFalse(repeated["result"]["created"])
        self.assertEqual(created["result"]["metadata_hash"], repeated["result"]["metadata_hash"])

        run = self.application.handle(message("get_run", {"run_id": "run-1"}))
        self.assertEqual(created["result"]["metadata_hash"], run["result"]["metadata_hash"])
        graph = self.application.handle(message("get_graph", {"run_id": "run-1", "limit": 10}))
        self.assertEqual(
            {"run_id": "run-1", "graph_schema_version": 1, "graph_version": 0,
             "nodes": [], "edges": [], "next_cursor": None, "has_more": False},
            graph["result"],
        )

        mismatch = self.create_run(metadata=run_metadata({"purpose": "different"}))
        self.assertEqual("RUN_METADATA_CONFLICT", mismatch["error"]["code"])
        unknown = self.application.handle(message("get_run", {"run_id": "missing"}))
        self.assertEqual("NOT_FOUND", unknown["error"]["code"])

    def test_rejected_mutation_is_durable_and_replay_is_idempotent(self) -> None:
        self.create_run()
        evidence = [{
            "evidence_id": "evidence-1",
            "content_digest": "sha256:immutable-content",
            "worker_claims": {"origin": "independent_verifier", "method": "deterministic_check"},
        }]
        request = proposal(evidence=evidence)
        result = self.application.handle(request)
        self.assertEqual("REJECT", result["result"]["status"])
        self.assertEqual("invalid_graph_mutation", result["result"]["reason_code"])
        self.assertEqual(0, result["result"]["resulting_graph_version"])

        stored = self.store.get_proposal("run-1", "proposal-1")
        self.assertEqual(evidence[0], stored.normalized_request.evidence[0].value)
        self.assertEqual(result["result"]["request_hash"], stored.request_hash)

        replay = self.application.handle(message("propose_mutation", request["params"], "request-2"))
        self.assertEqual(result["result"], replay["result"])
        timeline = self.application.handle(
            message("get_audit_timeline", {"run_id": "run-1", "limit": 10})
        )["result"]
        self.assertEqual(["proposal_receipt", "mutation_decision"], [item["record_type"] for item in timeline["records"]])
        self.assertEqual([1, 2], [item["journal_position"] for item in timeline["records"]])
        self.assertEqual("REJECT", timeline["records"][1]["outcome"])

        changed = proposal(evidence=[{"content_digest": "sha256:changed"}])
        changed["params"]["proposal_id"] = "proposal-1"
        conflict = self.application.handle(changed)
        self.assertEqual("IDEMPOTENCY_CONFLICT", conflict["error"]["code"])
        self.assertEqual(2, self.store.get_run("run-1").last_journal_position)

    def test_get_proposal_returns_status_without_evidence_or_operations(self) -> None:
        self.create_run()
        response = self.application.handle(proposal())
        status = self.application.handle(
            message(
                "get_proposal",
                {"run_id": "run-1", "proposal_id": "proposal-1"},
                request_id="read-proposal",
            )
        )
        self.assertEqual(status["result"], response["result"])
        self.assertNotIn("operations", status["result"])
        self.assertNotIn("evidence", status["result"])

    def test_proposal_poll_and_replay_match_result_across_distinct_envelopes(self) -> None:
        self.create_run()
        mutation = proposal()
        mutation["request_id"] = "propose-request"
        self.application.handle(mutation)

        expected = self.application.handle(
            message(
                "get_proposal",
                {"run_id": "run-1", "proposal_id": "proposal-1"},
                request_id="poll-proposal",
            )
        )
        replay = self.application.handle(mutation)

        self.assertEqual("get_proposal", expected["operation"])
        self.assertEqual("poll-proposal", expected["request_id"])
        self.assertEqual("propose_mutation", replay["operation"])
        self.assertEqual("propose-request", replay["request_id"])
        self.assertNotEqual(replay, expected)
        self.assertEqual(replay["result"], expected["result"])

    def test_pending_receipt_resumes_to_one_durable_outcome(self) -> None:
        self.create_run()
        request = proposal()
        self._seed_receipt(request)

        result = self.application.handle(request)
        self.assertEqual("REJECT", result["result"]["status"])
        replay = self.application.handle(message("propose_mutation", request["params"], "request-2"))
        self.assertEqual(result["result"], replay["result"])
        self.assertEqual(2, self.store.get_run("run-1").last_journal_position)

    def test_stale_version_records_conflict_and_never_advances_graph(self) -> None:
        self.create_run()
        self._seed_commit()

        result = self.application.handle(proposal(expected_graph_version=0, proposal_id="stale"))
        self.assertEqual("CONFLICT", result["result"]["status"])
        self.assertEqual("stale_graph_version", result["result"]["reason_code"])
        self.assertEqual(1, result["result"]["resulting_graph_version"])
        self.assertEqual(1, self.store.get_run("run-1").graph_version)

        timeline = self.application.handle(
            message("get_audit_timeline", {"run_id": "run-1", "limit": 100})
        )["result"]["records"]
        conflict = next(item for item in timeline if item.get("outcome") == "CONFLICT")
        self.assertEqual(1, conflict["graph_version"])

    def test_c_run_identity_is_required_and_bound_to_recovery_receipt(self) -> None:
        incomplete = self.create_run(metadata=run_metadata({"configuration": "C"}))
        self.assertEqual("PROTOCOL_ERROR", incomplete["error"]["code"])

        data = {
            "configuration": "C",
            "manifest_hash": "sha256:manifest",
            "effective_graph_intervention_identity": "sha256:graph-intervention",
            "effective_governance_policy_identity": "sha256:governance-policy",
        }
        self.create_run(metadata=run_metadata(data))
        result = self.application.handle(proposal())
        self.assertEqual("REJECT", result["result"]["status"])
        snapshot = self.store.get_proposal("run-1", "proposal-1")
        self.assertEqual(
            CRunRecoveryContext(
                manifest_hash=data["manifest_hash"],
                effective_graph_intervention_identity=data["effective_graph_intervention_identity"],
                effective_governance_policy_identity=data["effective_governance_policy_identity"],
            ),
            snapshot.c_run_recovery_context,
        )

    def test_audit_projection_preserves_record_kinds_and_exclusive_pagination(self) -> None:
        self.create_run()
        independent = NonTerminalAuditRecord(
            RecordMetadata("run-1", "independent-audit", NOW),
            "smoke.marker",
            JsonDocument.from_value({"value": "fixture"}),
        )
        self.store.append_audit("run-1", (independent,))

        abandoned_request = proposal("abandoned")
        abandoned_normalized = self._seed_receipt(abandoned_request)
        abandoned = ProposalAbandoned(
            RecordMetadata("run-1", "abandoned-terminal", NOW),
            "abandoned",
            proposal_request_hash(abandoned_normalized),
            "recovery_not_possible",
        )
        self.store.append_audit("run-1", (abandoned,), "abandoned")

        self._seed_commit(proposal_id="committed")
        first = self.application.handle(
            message("get_audit_timeline", {"run_id": "run-1", "limit": 2})
        )["result"]
        self.assertEqual(["non_terminal_audit", "proposal_receipt"], [r["record_type"] for r in first["records"]])
        self.assertTrue(first["has_more"])
        second = self.application.handle(
            message(
                "get_audit_timeline",
                {"run_id": "run-1", "limit": 100, "after_journal_position": first["next_after_journal_position"]},
            )
        )["result"]
        self.assertEqual(
            ["proposal_abandoned", "proposal_receipt", "mutation_decision", "graph_changed"],
            [r["record_type"] for r in second["records"]],
        )
        self.assertEqual("ABANDONED", second["records"][0]["lifecycle_state"])
        self.assertEqual(1, second["records"][-1]["graph_version"])
        self.assertFalse(second["has_more"])

    def test_optional_telemetry_failure_does_not_change_authoritative_result(self) -> None:
        class BrokenTelemetry:
            def emit(self, _observation) -> None:
                raise RuntimeError("telemetry unavailable")

        app = ProtocolApplication(self.store, BrokenTelemetry())
        result = app.handle(message("create_run", {"run_id": "run-broken-telemetry", "run_metadata": run_metadata()}))
        self.assertTrue(result["result"]["created"])
        self.assertEqual(0, self.store.get_run("run-broken-telemetry").graph_version)


if __name__ == "__main__":
    unittest.main()
