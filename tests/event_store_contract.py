"""Shared semantic contract for all EventStore providers."""

from datetime import datetime, timezone
import unittest

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
    ProposalStatus,
    RecordMetadata,
    VersionConflict,
    proposal_request_hash,
    serialize_entry,
)
from problemforger.ports.event_store import (
    AppendResult,
    CreateRunStatus,
    RecordProposalStatus,
    RunMetadata,
    StoreError,
    StoreErrorCode,
)
from problemforger.modules.persistence._base import (
    MAX_APPEND_BATCH_BYTES,
    MAX_JOURNAL_PAGE_BYTES,
    MAX_JOURNAL_RECORD_BYTES,
    MAX_RUN_METADATA_BYTES,
)


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def metadata(record_id: str, run_id: str = "run-1") -> RecordMetadata:
    return RecordMetadata(run_id=run_id, record_id=record_id, recorded_at=NOW)


def request(expected_version: int = 0, proposal_id: str = "proposal-1") -> NormalizedMutationRequest:
    return NormalizedMutationRequest(
        request_schema_version=1,
        expected_graph_version=expected_version,
        operations=(JsonDocument.from_value({"op": "add_node", "id": proposal_id}),),
        evidence=(JsonDocument.from_value({"content_digest": f"sha256:{proposal_id}"}),),
    )


def receipt(
    proposal_id: str = "proposal-1",
    expected_version: int = 0,
    *,
    record_id: str | None = None,
    run_id: str = "run-1",
) -> ProposalReceipt:
    normalized = request(expected_version, proposal_id)
    return ProposalReceipt(
        metadata=metadata(record_id or f"{proposal_id}-receipt", run_id),
        proposal_id=proposal_id,
        request=normalized,
    )


def decision(
    proposal_id: str = "proposal-1",
    *,
    outcome: GovernanceOutcome = GovernanceOutcome.COMMIT,
    expected_version: int = 0,
    resulting_version: int | None = None,
    record_id: str | None = None,
    run_id: str = "run-1",
    reason_code: str | None = None,
    request_hash: str | None = None,
) -> MutationDecision:
    if resulting_version is None:
        resulting_version = (
            expected_version + 1
            if outcome is GovernanceOutcome.COMMIT
            else expected_version
        )
    normalized = request(expected_version, proposal_id)
    if request_hash is None:
        request_hash = proposal_request_hash(normalized)
    if reason_code is None and outcome is not GovernanceOutcome.COMMIT:
        reason_code = "test_outcome"
    return MutationDecision(
        metadata=metadata(record_id or f"{proposal_id}-{outcome.value.lower()}", run_id),
        proposal_id=proposal_id,
        request_hash=request_hash,
        expected_graph_version=expected_version,
        resulting_graph_version=resulting_version,
        outcome=outcome,
        reason_code=reason_code,
        details=JsonDocument.from_value({"checks": ["contract"]}),
    )


def graph_event(
    proposal_id: str = "proposal-1",
    *,
    version: int = 1,
    record_id: str | None = None,
    run_id: str = "run-1",
    payload: dict[str, object] | None = None,
) -> GraphChangedEvent:
    return GraphChangedEvent(
        metadata=metadata(record_id or f"{proposal_id}-event-{version}-{record_id or 'a'}", run_id),
        proposal_id=proposal_id,
        graph_version=version,
        event_type="node.added",
        event_schema_version=1,
        payload=JsonDocument.from_value(payload or {"node_id": proposal_id}),
    )


def audit_record(
    record_id: str,
    *,
    run_id: str = "run-1",
    proposal_id: str | None = None,
    audit_type: str = "policy.observation",
    payload: dict[str, object] | None = None,
) -> NonTerminalAuditRecord:
    return NonTerminalAuditRecord(
        metadata=metadata(record_id, run_id),
        proposal_id=proposal_id,
        audit_type=audit_type,
        payload=JsonDocument.from_value(payload or {"source": "contract"}),
    )


class EventStoreContractMixin:
    """Subclasses supply a fresh ``self.store`` and run cleanup."""

    store: object

    def make_store(self):  # pragma: no cover - implemented by provider test classes
        raise NotImplementedError

    def setUp(self) -> None:
        self.store = self.make_store()
        result = self.store.create_run("run-1", RunMetadata.from_value({"task": "contract"}))
        self.assertEqual(CreateRunStatus.CREATED, result.status)

    def tearDown(self) -> None:
        self.store.close()

    def submit(self, proposal_id: str = "proposal-1", expected: int = 0):
        normalized = request(expected, proposal_id)
        proposal_receipt = receipt(proposal_id, expected)
        result = self.store.record_proposal(
            "run-1",
            proposal_id,
            proposal_request_hash(normalized),
            normalized,
            proposal_receipt,
        )
        self.assertEqual(RecordProposalStatus.CREATED, result.status)
        return normalized, proposal_receipt

    def test_proposal_snapshot_preserves_c_run_recovery_context(self):
        context = CRunRecoveryContext(
            manifest_hash="sha256:manifest",
            effective_graph_intervention_identity="sha256:graph-intervention",
            effective_governance_policy_identity="sha256:governance-policy",
        )
        normalized = request(0, "c-proposal")
        proposal_receipt = ProposalReceipt(
            metadata("c-proposal-receipt"),
            "c-proposal",
            normalized,
            c_run_recovery_context=context,
        )
        result = self.store.record_proposal(
            "run-1",
            "c-proposal",
            proposal_request_hash(normalized),
            normalized,
            proposal_receipt,
        )
        self.assertEqual(RecordProposalStatus.CREATED, result.status)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(context, result.proposal.c_run_recovery_context)
        snapshot = self.store.get_proposal("run-1", "c-proposal")
        self.assertEqual(context, snapshot.c_run_recovery_context)
        existing = self.store.record_proposal(
            "run-1",
            "c-proposal",
            proposal_request_hash(normalized),
            normalized,
            ProposalReceipt(metadata("ignored-receipt"), "c-proposal", normalized),
        )
        self.assertEqual(RecordProposalStatus.EXISTING, existing.status)
        self.assertEqual(context, existing.proposal.c_run_recovery_context)

    def append_commit(
        self,
        proposal_id: str,
        expected: int,
        *,
        event_count: int = 1,
        record_suffix: str = "",
    ) -> AppendResult:
        proposal = self.store.get_proposal("run-1", proposal_id)
        graph_decision = decision(
            proposal_id,
            expected_version=expected,
            record_id=f"{proposal_id}-commit{record_suffix}",
            request_hash=proposal.request_hash,
        )
        events = tuple(
            graph_event(
                proposal_id,
                version=expected + 1,
                record_id=f"{proposal_id}-event-{index}{record_suffix}",
                payload={"index": index},
            )
            for index in range(event_count)
        )
        result = self.store.append_graph(
            "run-1", proposal_id, expected, (graph_decision,), events
        )
        self.assertIsInstance(result, AppendResult)
        return result

    def test_run_registration_is_idempotent_and_metadata_conflicts_are_read_only(self):
        existing = self.store.create_run("run-1", RunMetadata.from_value({"task": "contract"}))
        self.assertEqual(CreateRunStatus.EXISTING, existing.status)
        identical_retry = self.store.create_run("run-1", RunMetadata.from_value({"task": "contract"}))
        self.assertEqual(existing.metadata_hash, identical_retry.metadata_hash)

        changed = self.store.create_run("run-1", RunMetadata.from_value({"task": "different"}))
        self.assertEqual(CreateRunStatus.RUN_METADATA_CONFLICT, changed.status)
        self.assertNotEqual(changed.metadata_hash, changed.existing_metadata_hash)
        run = self.store.get_run("run-1")
        self.assertEqual(0, run.graph_version)
        self.assertEqual(0, run.last_journal_position)
        self.assertEqual({"task": "contract"}, run.run_metadata.data.value)
        self.assertTrue(run.metadata_hash.startswith("sha256:problemforger-run-metadata-v1:"))

    def test_serialized_metadata_records_batches_and_pages_are_bounded(self):
        oversized_metadata = RunMetadata.from_value({"value": "x" * MAX_RUN_METADATA_BYTES})
        invalid_run = self.store.create_run("oversized-run", oversized_metadata)
        self.assertEqual(CreateRunStatus.INVALID_REQUEST, invalid_run.status)
        self.assertEqual(StoreErrorCode.NOT_FOUND, self.store.get_run("oversized-run").code)

        oversized_request = NormalizedMutationRequest(
            request_schema_version=1,
            expected_graph_version=0,
            operations=(JsonDocument.from_value({"payload": "x" * MAX_JOURNAL_RECORD_BYTES}),),
            evidence=(),
        )
        oversized_receipt = ProposalReceipt(
            metadata("oversized-receipt"), "oversized-proposal", oversized_request
        )
        rejected_receipt = self.store.record_proposal(
            "run-1",
            "oversized-proposal",
            proposal_request_hash(oversized_request),
            oversized_request,
            oversized_receipt,
        )
        self.assertEqual(RecordProposalStatus.INVALID_PROPOSAL, rejected_receipt.status)
        self.assertEqual(0, self.store.get_run("run-1").last_journal_position)

        proposal_id = "large-batch"
        self.submit(proposal_id)
        proposal = self.store.get_proposal("run-1", proposal_id)
        commit = decision(
            proposal_id,
            request_hash=proposal.request_hash,
            record_id="large-batch-commit",
        )
        large_events = tuple(
            graph_event(
                proposal_id,
                record_id=f"large-batch-event-{index}",
                payload={"payload": "x" * 850_000},
            )
            for index in range(5)
        )
        invalid_batch = self.store.append_graph(
            "run-1", proposal_id, 0, (commit,), large_events
        )
        self.assertEqual(StoreErrorCode.INVALID_GRAPH_BATCH, invalid_batch.code)
        self.assertGreater(MAX_APPEND_BATCH_BYTES, MAX_JOURNAL_RECORD_BYTES)
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

        for index in range(5):
            page_proposal_id = f"page-{index}"
            normalized = NormalizedMutationRequest(
                request_schema_version=1,
                expected_graph_version=0,
                operations=(JsonDocument.from_value({"payload": "y" * 850_000}),),
                evidence=(),
            )
            page_receipt = ProposalReceipt(
                metadata(f"{page_proposal_id}-receipt"), page_proposal_id, normalized
            )
            result = self.store.record_proposal(
                "run-1",
                page_proposal_id,
                proposal_request_hash(normalized),
                normalized,
                page_receipt,
            )
            self.assertEqual(RecordProposalStatus.CREATED, result.status)

        first_page = self.store.read_journal("run-1", limit=100)
        self.assertEqual(5, len(first_page.records))
        page_bytes = sum(len(serialize_entry(entry).encode("utf-8")) for entry in first_page.records)
        self.assertLessEqual(page_bytes, MAX_JOURNAL_PAGE_BYTES)
        self.assertTrue(first_page.has_more)
        second_page = self.store.read_journal(
            "run-1", after_journal_position=first_page.next_after_journal_position, limit=100
        )
        self.assertEqual(1, len(second_page.records))
        self.assertFalse(second_page.has_more)

    def test_unknown_run_and_proposal_never_create_implicit_streams(self):
        normalized = request()
        proposal_receipt = receipt()
        missing_run = self.store.get_run("missing")
        self.assertEqual(StoreErrorCode.NOT_FOUND, missing_run.code)
        self.assertEqual("NOT_FOUND", missing_run.status)
        self.assertEqual(StoreErrorCode.NOT_FOUND, self.store.get_proposal("missing", "p").code)
        for proposal_id in ("", "\ud800"):
            with self.subTest(proposal_id=proposal_id):
                self.assertEqual(
                    StoreErrorCode.NOT_FOUND,
                    self.store.get_proposal("missing", proposal_id).code,
                )
        self.assertEqual(StoreErrorCode.NOT_FOUND, self.store.current_graph_version("missing").code)
        self.assertEqual(
            StoreErrorCode.NOT_FOUND,
            self.store.read_journal("missing", limit=1).code,
        )
        self.assertEqual(
            StoreErrorCode.NOT_FOUND,
            self.store.read_journal("missing", limit=0).code,
        )
        self.assertEqual(
            RecordProposalStatus.NOT_FOUND,
            self.store.record_proposal(
                "missing", "p", proposal_request_hash(normalized), normalized, proposal_receipt
            ).status,
        )
        self.assertEqual(
            StoreErrorCode.NOT_FOUND,
            self.store.append_audit(
                "missing", (decision(outcome=GovernanceOutcome.REJECT),), "proposal-1"
            ).code,
        )
        self.assertEqual(
            StoreErrorCode.NOT_FOUND,
            self.store.append_graph("missing", "p", 0, (), ()).code,
        )
        self.assertEqual(0, self.store.get_run("run-1").last_journal_position)

    def test_unknown_graph_proposal_precedes_batch_validation(self):
        event = graph_event("missing-proposal", version=1)
        commit = decision("missing-proposal")
        for audit_records, graph_events in (
            ((), ()),
            ((), (event,)),
            ((commit,), ()),
        ):
            with self.subTest(audit_records=audit_records, graph_events=graph_events):
                result = self.store.append_graph(
                    "run-1", "missing-proposal", 0, audit_records, graph_events
                )
                self.assertEqual(StoreErrorCode.NOT_FOUND, result.code)
        self.assertEqual(0, self.store.get_run("run-1").last_journal_position)

    def test_invalid_utf8_and_reused_record_ids_are_rejected_before_writes(self):
        run_metadata = RunMetadata.from_value({"task": "contract"})
        self.assertEqual(
            CreateRunStatus.INVALID_REQUEST,
            self.store.create_run("\ud800", run_metadata).status,
        )
        self.assertEqual(StoreErrorCode.INVALID_REQUEST, self.store.get_run("\ud800").code)
        self.assertEqual(
            StoreErrorCode.INVALID_REQUEST,
            self.store.get_proposal("run-1", "\ud800").code,
        )
        self.assertEqual(
            StoreErrorCode.INVALID_REQUEST,
            self.store.current_graph_version("\ud800").code,
        )

        self.submit("first")
        second_request = request(0, "second")
        reused_receipt = receipt(
            "second", record_id="first-receipt"
        )
        invalid = self.store.record_proposal(
            "run-1",
            "second",
            proposal_request_hash(second_request),
            second_request,
            reused_receipt,
        )
        self.assertEqual(RecordProposalStatus.INVALID_PROPOSAL, invalid.status)
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

        self.assertEqual(
            StoreErrorCode.INVALID_AUDIT_BATCH,
            self.store.append_audit("", (), "first").code,
        )
        self.assertEqual(
            StoreErrorCode.INVALID_AUDIT_BATCH,
            self.store.append_audit("run-1", None, "first").code,
        )
        self.assertEqual(
            StoreErrorCode.INVALID_AUDIT_BATCH,
            self.store.append_audit("run-1", ("unsupported",), "first").code,
        )

    def test_receipt_registration_is_atomic_idempotent_and_hash_bound(self):
        normalized, proposal_receipt = self.submit()
        same = self.store.record_proposal(
            "run-1",
            "proposal-1",
            proposal_request_hash(normalized),
            normalized,
            proposal_receipt,
        )
        self.assertEqual(RecordProposalStatus.EXISTING, same.status)
        self.assertEqual(1, same.proposal.last_journal_position)

        changed = request(1, "proposal-1")
        changed_receipt = receipt("proposal-1", 1, record_id="different-receipt")
        conflict = self.store.record_proposal(
            "run-1",
            "proposal-1",
            proposal_request_hash(changed),
            changed,
            changed_receipt,
        )
        self.assertEqual(RecordProposalStatus.IDEMPOTENCY_CONFLICT, conflict.status)
        self.assertEqual(proposal_request_hash(normalized), conflict.stored_request_hash)
        self.assertEqual(proposal_request_hash(changed), conflict.supplied_request_hash)

        wrong_hash = self.store.record_proposal(
            "run-1", "proposal-1", "sha256:wrong", normalized, proposal_receipt
        )
        self.assertEqual(RecordProposalStatus.INVALID_PROPOSAL, wrong_hash.status)
        wrong_identity = receipt("another-id", record_id="wrong-identity")
        invalid = self.store.record_proposal(
            "run-1", "proposal-1", proposal_request_hash(normalized), normalized, wrong_identity
        )
        self.assertEqual(RecordProposalStatus.INVALID_PROPOSAL, invalid.status)
        missing_identity = self.store.record_proposal(
            "run-1", "", proposal_request_hash(normalized), normalized, proposal_receipt
        )
        self.assertEqual(RecordProposalStatus.INVALID_PROPOSAL, missing_identity.status)
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

    def test_existing_proposal_identity_precedes_unused_receipt_size(self):
        normalized, original_receipt = self.submit()
        before = self.store.get_proposal("run-1", "proposal-1")
        oversized_request = NormalizedMutationRequest(
            request_schema_version=1,
            expected_graph_version=0,
            operations=(
                JsonDocument.from_value({"payload": "x" * MAX_JOURNAL_RECORD_BYTES}),
            ),
            evidence=(),
        )
        oversized_receipt = ProposalReceipt(
            metadata("changed-receipt"), "proposal-1", oversized_request
        )
        conflict = self.store.record_proposal(
            "run-1",
            "proposal-1",
            proposal_request_hash(oversized_request),
            oversized_request,
            oversized_receipt,
        )
        self.assertEqual(RecordProposalStatus.IDEMPOTENCY_CONFLICT, conflict.status)
        self.assertEqual(original_receipt.request_hash, conflict.stored_request_hash)
        self.assertEqual(oversized_receipt.request_hash, conflict.supplied_request_hash)
        self.assertEqual(before, conflict.proposal)

        unused_oversized_receipt = ProposalReceipt(
            metadata("x" * MAX_JOURNAL_RECORD_BYTES), "proposal-1", normalized
        )
        existing = self.store.record_proposal(
            "run-1",
            "proposal-1",
            original_receipt.request_hash,
            normalized,
            unused_oversized_receipt,
        )
        self.assertEqual(RecordProposalStatus.EXISTING, existing.status)
        self.assertEqual(before, existing.proposal)
        self.assertEqual(before, self.store.get_proposal("run-1", "proposal-1"))
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

    def test_pending_receipt_round_trips_complete_normalized_request(self):
        normalized, _ = self.submit()
        pending = self.store.get_proposal("run-1", "proposal-1")
        self.assertEqual(ProposalStatus.PENDING, pending.status)
        self.assertEqual(normalized, pending.normalized_request)
        self.assertEqual(1, pending.last_journal_position)
        self.assertIsNone(pending.terminal_outcome)
        self.assertIsNone(pending.resulting_graph_version)

    def test_commit_is_atomic_advances_one_version_and_replays_exact_metadata(self):
        self.submit("proposal-1", 0)
        first = self.append_commit("proposal-1", 0, event_count=2)
        self.assertEqual((2, 3, 4), tuple(entry.journal_position for entry in first.entries))
        self.assertEqual(1, first.new_graph_version)
        self.assertEqual(1, self.store.current_graph_version("run-1"))
        first_snapshot = self.store.get_proposal("run-1", "proposal-1")
        self.assertEqual(GovernanceOutcome.COMMIT, first_snapshot.status)
        self.assertEqual(GovernanceOutcome.COMMIT, first_snapshot.terminal_outcome)
        self.assertEqual(1, first_snapshot.resulting_graph_version)
        self.assertEqual(4, first_snapshot.last_journal_position)

        alternate_outcome = decision(
            "proposal-1",
            outcome=GovernanceOutcome.REJECT,
            record_id="proposal-1-alternate-reject",
            request_hash=first_snapshot.request_hash,
        )
        audit_replay = self.store.append_audit("run-1", (alternate_outcome,), "proposal-1")
        self.assertTrue(audit_replay.replayed)
        self.assertEqual(first.entries, audit_replay.entries)
        self.assertEqual(first.last_journal_position, audit_replay.last_journal_position)
        self.assertEqual(first.new_graph_version, audit_replay.new_graph_version)

        replay = self.append_commit("proposal-1", 0, event_count=2, record_suffix="-retry")
        self.assertTrue(replay.replayed)
        self.assertEqual(first.entries, replay.entries)
        self.submit("proposal-2", 1)
        second = self.append_commit("proposal-2", 1)
        self.assertEqual(2, second.new_graph_version)
        still_first = self.store.get_proposal("run-1", "proposal-1")
        self.assertEqual(4, still_first.last_journal_position)
        self.assertEqual(1, still_first.resulting_graph_version)
        page = self.store.read_journal("run-1", limit=100)
        self.assertEqual(tuple(range(1, 8)), tuple(entry.journal_position for entry in page.records))

    def test_non_commit_decisions_and_abandoned_status_are_terminal_and_replayable(self):
        for outcome in (GovernanceOutcome.REJECT, GovernanceOutcome.RETRY, GovernanceOutcome.ESCALATE):
            proposal_id = outcome.value.lower()
            self.submit(proposal_id, 0)
            record = decision(proposal_id, outcome=outcome, record_id=f"{proposal_id}-final")
            result = self.store.append_audit("run-1", (record,), proposal_id)
            self.assertIsInstance(result, AppendResult)
            self.assertEqual(outcome, self.store.get_proposal("run-1", proposal_id).status)
            duplicate = self.store.append_audit("run-1", (record,), proposal_id)
            self.assertTrue(duplicate.replayed)
            self.assertEqual(result.entries, duplicate.entries)
            self.assertEqual(result.last_journal_position, duplicate.last_journal_position)
            self.assertEqual(result.new_graph_version, duplicate.new_graph_version)
        self.submit("abandoned", 0)
        abandoned = ProposalAbandoned(
            metadata("abandoned-terminal"),
            "abandoned",
            proposal_request_hash(request(0, "abandoned")),
            "unsupported_recovery_schema",
        )
        result = self.store.append_audit("run-1", (abandoned,), "abandoned")
        self.assertIsInstance(result, AppendResult)
        snapshot = self.store.get_proposal("run-1", "abandoned")
        self.assertEqual(ProposalStatus.ABANDONED, snapshot.status)
        self.assertIsNone(snapshot.terminal_outcome)
        self.assertEqual(0, snapshot.resulting_graph_version)
        self.assertEqual(result.last_journal_position, snapshot.last_journal_position)
        self.assertEqual(0, self.store.current_graph_version("run-1"))
        abandoned_replay = self.store.append_audit("run-1", (abandoned,), "abandoned")
        self.assertTrue(abandoned_replay.replayed)
        self.assertEqual(result.entries, abandoned_replay.entries)
        self.assertEqual(result.new_graph_version, abandoned_replay.new_graph_version)

        self.submit("after-abandoned", 0)
        self.append_commit("after-abandoned", 0)
        historical = self.store.get_proposal("run-1", "abandoned")
        self.assertEqual(0, historical.resulting_graph_version)
        self.assertEqual(result.last_journal_position, historical.last_journal_position)

    def test_stale_non_commit_candidate_is_recorded_as_conflict_without_policy_details(self):
        self.submit("stale", 0)
        self.submit("winner", 0)
        self.append_commit("winner", 0)
        candidate = decision(
            "stale",
            outcome=GovernanceOutcome.REJECT,
            record_id="stale-candidate",
        )
        result = self.store.append_audit("run-1", (candidate,), "stale")
        self.assertIsInstance(result, AppendResult)
        persisted = result.terminal_record
        self.assertEqual(GovernanceOutcome.CONFLICT, persisted.outcome)
        self.assertEqual("stale_graph_version", persisted.reason_code)
        self.assertEqual(1, persisted.resulting_graph_version)
        self.assertEqual({}, persisted.details.value)
        snapshot = self.store.get_proposal("run-1", "stale")
        self.assertEqual(GovernanceOutcome.CONFLICT, snapshot.status)
        self.assertEqual(1, snapshot.resulting_graph_version)

    def test_graph_batch_rejects_bad_bindings_versions_and_empty_commits_without_writes(self):
        self.submit("proposal-1", 0)
        correct = decision("proposal-1", expected_version=0, request_hash=proposal_request_hash(request(0)))
        event = graph_event("proposal-1", version=1)
        malformed = (
            self.store.append_graph("run-1", "proposal-1", 0, (), (event,)),
            self.store.append_graph("run-1", "proposal-1", 0, (correct,), ()),
            self.store.append_graph("run-1", "proposal-1", 0, (correct,), (graph_event("other", version=1),)),
            self.store.append_graph("run-1", "proposal-1", 0, (correct,), (replace_event_run(event, "other-run"),)),
        )
        for result in malformed:
            self.assertEqual(StoreErrorCode.INVALID_GRAPH_BATCH, result.code)
        wrong_receipt_version = decision(
            "proposal-1", expected_version=1, resulting_version=2,
            record_id="wrong-receipt-version",
        )
        wrong_event_version = graph_event("proposal-1", version=2, record_id="wrong-version-event")
        result = self.store.append_graph("run-1", "proposal-1", 1, (wrong_receipt_version,), (wrong_event_version,))
        self.assertEqual(StoreErrorCode.INVALID_GRAPH_BATCH, result.code)
        mismatched_decision = decision(
            "proposal-1",
            expected_version=20,
            resulting_version=21,
            record_id="mismatched-decision-version",
            request_hash=proposal_request_hash(request(0)),
        )
        mismatched_event = graph_event(
            "proposal-1", version=21, record_id="mismatched-decision-event"
        )
        result = self.store.append_graph(
            "run-1", "proposal-1", 0, (mismatched_decision,), (mismatched_event,)
        )
        self.assertEqual(StoreErrorCode.INVALID_GRAPH_BATCH, result.code)
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)
        self.assertEqual(0, self.store.current_graph_version("run-1"))

        self.submit("winner", 0)
        self.append_commit("winner", 0)
        stale = self.store.append_graph("run-1", "proposal-1", 0, (correct,), (event,))
        self.assertIsInstance(stale, VersionConflict)
        self.assertEqual(0, stale.expected_graph_version)
        self.assertEqual(1, stale.actual_graph_version)
        self.assertEqual(ProposalStatus.PENDING, self.store.get_proposal("run-1", "proposal-1").status)

    def test_stale_graph_batches_are_fully_validated_before_version_conflicts(self):
        _, proposal_receipt = self.submit("proposal-1", 0)
        self.submit("winner", 0)
        self.append_commit("winner", 0)

        proposal = self.store.get_proposal("run-1", "proposal-1")
        commit = decision(
            "proposal-1",
            expected_version=0,
            record_id="stale-candidate-commit",
            request_hash=proposal.request_hash,
        )
        reused_record_id = graph_event(
            "proposal-1", version=1, record_id=proposal_receipt.metadata.record_id
        )
        oversized_event = graph_event(
            "proposal-1",
            version=1,
            record_id="oversized-stale-candidate-event",
            payload={"payload": "x" * (MAX_JOURNAL_RECORD_BYTES + 1)},
        )

        for event in (reused_record_id, oversized_event):
            result = self.store.append_graph("run-1", "proposal-1", 0, (commit,), (event,))
            self.assertIsInstance(result, StoreError)
            self.assertEqual(StoreErrorCode.INVALID_GRAPH_BATCH, result.code)

        run = self.store.get_run("run-1")
        self.assertEqual(1, run.graph_version)
        self.assertEqual(4, run.last_journal_position)
        self.assertEqual(ProposalStatus.PENDING, self.store.get_proposal("run-1", "proposal-1").status)

    def test_audit_batch_requires_terminal_identity_and_never_accepts_commit(self):
        self.submit("proposal-1", 0)
        reject = decision("proposal-1", outcome=GovernanceOutcome.REJECT, record_id="reject")
        invalid = (
            self.store.append_audit("run-1", (reject,)),
            self.store.append_audit("run-1", (decision("other", outcome=GovernanceOutcome.REJECT),), "proposal-1"),
            self.store.append_audit("run-1", (reject, reject), "proposal-1"),
            self.store.append_audit("run-1", (decision("proposal-1"),), "proposal-1"),
            self.store.append_audit("run-1", (), "proposal-1"),
        )
        for result in invalid:
            self.assertEqual(StoreErrorCode.INVALID_AUDIT_BATCH, result.code)
        wrong_hash = decision(
            "proposal-1", outcome=GovernanceOutcome.REJECT, record_id="wrong-hash",
            request_hash="sha256:problemforger-request-v1:" + "0" * 64,
        )
        self.assertEqual(
            StoreErrorCode.INVALID_AUDIT_BATCH,
            self.store.append_audit("run-1", (wrong_hash,), "proposal-1").code,
        )
        duplicate_record_id = decision(
            "proposal-1", outcome=GovernanceOutcome.REJECT,
            record_id="proposal-1-receipt",
        )
        self.assertEqual(
            StoreErrorCode.INVALID_AUDIT_BATCH,
            self.store.append_audit("run-1", (duplicate_record_id,), "proposal-1").code,
        )
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

    def test_nonterminal_audits_append_independently_without_advancing_graph_version(self):
        first = audit_record("audit-1", payload={"step": 1})
        second = audit_record("audit-2", payload={"step": 2})

        result = self.store.append_audit("run-1", (first, second))

        self.assertIsInstance(result, AppendResult)
        self.assertEqual((1, 2), tuple(entry.journal_position for entry in result.entries))
        self.assertEqual((first, second), tuple(entry.record for entry in result.entries))
        self.assertIsNone(result.terminal_record)
        self.assertFalse(result.replayed)
        self.assertEqual(0, result.new_graph_version)
        self.assertEqual(0, self.store.current_graph_version("run-1"))
        self.assertEqual(2, self.store.get_run("run-1").last_journal_position)
        page = self.store.read_journal("run-1", limit=10)
        self.assertEqual((first, second), tuple(entry.record for entry in page.records))

    def test_scoped_nonterminal_audits_bind_without_finalizing_and_are_atomic(self):
        self.submit("scoped", 0)
        first = audit_record("scoped-audit-1", proposal_id="scoped", payload={"step": 1})
        second = audit_record("scoped-audit-2", proposal_id="scoped", payload={"step": 2})

        result = self.store.append_audit("run-1", (first, second), "scoped")

        self.assertIsInstance(result, AppendResult)
        self.assertEqual((2, 3), tuple(entry.journal_position for entry in result.entries))
        self.assertEqual(0, result.new_graph_version)
        pending = self.store.get_proposal("run-1", "scoped")
        self.assertEqual(ProposalStatus.PENDING, pending.status)
        self.assertEqual(3, pending.last_journal_position)

        invalid_scope = self.store.append_audit(
            "run-1",
            (audit_record("wrong-scope", proposal_id="other"),),
            "scoped",
        )
        self.assertEqual(StoreErrorCode.INVALID_AUDIT_BATCH, invalid_scope.code)
        self.assertEqual(3, self.store.get_run("run-1").last_journal_position)

        rejected = decision(
            "scoped",
            outcome=GovernanceOutcome.REJECT,
            expected_version=0,
            record_id="scoped-reject",
        )
        self.assertIsInstance(self.store.append_audit("run-1", (rejected,), "scoped"), AppendResult)
        after_terminal = self.store.append_audit(
            "run-1",
            (audit_record("scoped-audit-after-terminal", proposal_id="scoped"),),
            "scoped",
        )
        self.assertIsInstance(after_terminal, AppendResult)
        self.assertEqual(5, self.store.get_run("run-1").last_journal_position)
        finalized = self.store.get_proposal("run-1", "scoped")
        self.assertEqual(4, finalized.last_journal_position)

    def test_nonterminal_audit_batches_reject_mixed_scope_and_terminal_records_without_writes(self):
        self.submit("scoped", 0)
        run_level = audit_record("run-level")
        scoped = audit_record("scoped-audit", proposal_id="scoped")
        terminal = decision(
            "scoped",
            outcome=GovernanceOutcome.REJECT,
            expected_version=0,
            record_id="scoped-reject",
        )
        invalid = (
            self.store.append_audit("run-1", (run_level,), "scoped"),
            self.store.append_audit("run-1", (scoped,)),
            self.store.append_audit("run-1", (scoped, terminal), "scoped"),
            self.store.append_audit("run-1", (audit_record("duplicate-a"), audit_record("duplicate-a"))),
            self.store.append_audit("run-1", (audit_record("scoped-receipt"),)),
            self.store.append_audit("run-1", (audit_record("wrong-run", run_id="other"),)),
            self.store.append_audit(
                "run-1",
                (audit_record("oversized", payload={"payload": "x" * (MAX_JOURNAL_RECORD_BYTES + 1)}),),
            ),
        )
        for result in invalid:
            self.assertEqual(StoreErrorCode.INVALID_AUDIT_BATCH, result.code)
        self.assertEqual(1, self.store.get_run("run-1").last_journal_position)

    def test_unknown_proposal_precedes_audit_batch_validation(self):
        self.submit("known-proposal", 0)
        for records in (None, ()):
            with self.subTest(records=records):
                result = self.store.append_audit("run-1", records, "missing-proposal")
                self.assertEqual(StoreErrorCode.NOT_FOUND, result.code)

        invalid_existing = self.store.append_audit("run-1", None, "known-proposal")
        self.assertEqual(StoreErrorCode.INVALID_AUDIT_BATCH, invalid_existing.code)

    def test_journal_reads_are_ordered_bounded_and_use_an_exclusive_cursor(self):
        for proposal_id in ("one", "two", "three"):
            self.submit(proposal_id, 0)
        first = self.store.read_journal("run-1", limit=2)
        self.assertEqual((1, 2), tuple(item.journal_position for item in first.records))
        self.assertEqual(2, first.next_after_journal_position)
        self.assertTrue(first.has_more)
        second = self.store.read_journal(
            "run-1", after_journal_position=first.next_after_journal_position, limit=2
        )
        self.assertEqual((3,), tuple(item.journal_position for item in second.records))
        self.assertFalse(second.has_more)
        empty = self.store.read_journal("run-1", after_journal_position=99, limit=2)
        self.assertEqual((), empty.records)
        self.assertEqual(99, empty.next_after_journal_position)
        self.assertFalse(empty.has_more)
        for limit, cursor in ((0, None), (101, None), (True, None), (1, -1), (1, True)):
            result = self.store.read_journal(
                "run-1", limit=limit, after_journal_position=cursor
            )
            self.assertEqual(StoreErrorCode.INVALID_LIMIT, result.code)

    def test_each_run_has_independent_journal_and_graph_version(self):
        self.assertEqual(
            CreateRunStatus.CREATED,
            self.store.create_run("run-2", RunMetadata.from_value({"task": "other"})).status,
        )
        normalized = request(0, "isolated")
        isolated_receipt = receipt("isolated", run_id="run-2")
        self.assertEqual(
            RecordProposalStatus.CREATED,
            self.store.record_proposal(
                "run-2", "isolated", proposal_request_hash(normalized), normalized, isolated_receipt
            ).status,
        )
        commit = decision(
            "isolated", request_hash=isolated_receipt.request_hash, run_id="run-2",
            record_id="run2-commit",
        )
        event = graph_event("isolated", version=1, run_id="run-2", record_id="run2-event")
        self.assertIsInstance(
            self.store.append_graph("run-2", "isolated", 0, (commit,), (event,)), AppendResult
        )
        self.assertEqual(1, self.store.current_graph_version("run-2"))
        self.assertEqual(0, self.store.current_graph_version("run-1"))
        self.assertEqual(3, self.store.get_run("run-2").last_journal_position)

    def test_invalid_run_metadata_and_closed_store_are_explicit(self):
        invalid = self.store.create_run("", RunMetadata.from_value({}))
        self.assertEqual(CreateRunStatus.INVALID_REQUEST, invalid.status)


def replace_event_run(event: GraphChangedEvent, run_id: str) -> GraphChangedEvent:
    return GraphChangedEvent(
        metadata=metadata(event.metadata.record_id, run_id),
        proposal_id=event.proposal_id,
        graph_version=event.graph_version,
        event_type=event.event_type,
        event_schema_version=event.event_schema_version,
        payload=event.payload,
    )
