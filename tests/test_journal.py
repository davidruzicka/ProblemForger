"""Provider-neutral durable journal value contract tests."""

from datetime import datetime, timedelta, timezone
from dataclasses import replace
import json
import unittest

from problemforger.core.journal import (
    CommittedMutationBatch,
    CRunRecoveryContext,
    GovernanceOutcome,
    GraphChangedEvent,
    JournalEntry,
    JsonDocument,
    MutationDecision,
    NormalizedMutationRequest,
    ProposalAbandoned,
    ProposalReceipt,
    ProposalStatus,
    RecordMetadata,
    deserialize_entry,
    proposal_request_hash,
    proposal_status,
    serialize_entry,
    VersionConflict,
)


UTC = timezone.utc
RECORDED_AT = datetime(2026, 9, 27, 6, 0, tzinfo=UTC)


def metadata(record_id="record-1", *, recorded_at=RECORDED_AT, schema_version=1):
    return RecordMetadata(
        run_id="run-1",
        record_id=record_id,
        recorded_at=recorded_at,
        record_schema_version=schema_version,
        correlation_id="correlation-1",
        causation_id="cause-1",
    )


def request(*, expected_version=0, operation_id="node-1", evidence_digest="sha256:aaa"):
    return NormalizedMutationRequest(
        request_schema_version=1,
        expected_graph_version=expected_version,
        operations=(JsonDocument.from_value({"operation": "add", "id": operation_id}),),
        evidence=(JsonDocument.from_value({"content_digest": evidence_digest}),),
    )


def receipt(
    *,
    record_id="record-1",
    proposal_id="proposal-1",
    normalized_request=None,
    c_run_recovery_context=None,
):
    return ProposalReceipt(
        metadata=metadata(record_id),
        proposal_id=proposal_id,
        request=normalized_request or request(),
        c_run_recovery_context=c_run_recovery_context,
    )


def decision(
    *,
    record_id="decision-1",
    outcome=GovernanceOutcome.COMMIT,
    expected_version=0,
    resulting_version=1,
    proposal_id="proposal-1",
    reason_code=None,
):
    normalized_request = request(expected_version=expected_version)
    return MutationDecision(
        metadata=metadata(record_id),
        proposal_id=proposal_id,
        request_hash=proposal_request_hash(normalized_request),
        expected_graph_version=expected_version,
        resulting_graph_version=resulting_version,
        outcome=outcome,
        reason_code=reason_code,
        details=JsonDocument.from_value({"checks": []}),
    )


def graph_event(*, record_id="event-1", proposal_id="proposal-1", version=1):
    return GraphChangedEvent(
        metadata=metadata(record_id),
        proposal_id=proposal_id,
        graph_version=version,
        event_type="node.added",
        event_schema_version=1,
        payload=JsonDocument.from_value({"node_id": "node-1"}),
    )


class JournalValueTests(unittest.TestCase):
    def test_json_document_copies_nested_input_and_returns_fresh_values(self):
        source = {"nested": [{"value": 1}]}
        document = JsonDocument.from_value(source)
        source["nested"][0]["value"] = 2
        returned = document.value
        returned["nested"][0]["value"] = 3

        self.assertEqual({"nested": [{"value": 1}]}, document.value)
        self.assertEqual('{"nested":[{"value":1}]}', document.canonical_json)

    def test_json_document_rejects_non_json_and_noncanonical_payloads(self):
        for invalid in (
            {1: "integer key"},
            {"not_finite": float("nan")},
            object(),
        ):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    JsonDocument.from_value(invalid)

        with self.assertRaises(ValueError):
            JsonDocument('{"b":2, "a":1}')
        with self.assertRaises(ValueError):
            JsonDocument.from_value("\ud800")
        with self.assertRaises(ValueError):
            JsonDocument("NaN")
        with self.assertRaises(ValueError):
            JsonDocument('{"same":1,"same":2}')
        with self.assertRaises(ValueError):
            JsonDocument("{")
        with self.assertRaises(TypeError):
            JsonDocument(None)

    def test_normalized_request_hash_covers_version_operations_and_evidence(self):
        original = request()
        reordered = NormalizedMutationRequest(
            request_schema_version=1,
            expected_graph_version=0,
            operations=(JsonDocument.from_value({"id": "node-1", "operation": "add"}),),
            evidence=(JsonDocument.from_value({"content_digest": "sha256:aaa"}),),
        )

        digest = proposal_request_hash(original)
        self.assertEqual(digest, proposal_request_hash(reordered))
        self.assertTrue(digest.startswith("sha256:problemforger-request-v1:"))
        self.assertNotEqual(digest, proposal_request_hash(request(expected_version=1)))
        self.assertNotEqual(digest, proposal_request_hash(request(operation_id="node-2")))
        self.assertNotEqual(digest, proposal_request_hash(request(evidence_digest="sha256:bbb")))
        self.assertEqual(
            "sha256:problemforger-request-v1:b6436732b766f8135a89d8cf2e54e05d3db31f59829a914f413dc93f92bd9f17",
            digest,
        )

    def test_normalized_request_hash_preserves_array_order_and_utf8_vector(self):
        operations = (
            JsonDocument.from_value({"operation": "add", "id": "node-1"}),
            JsonDocument.from_value({"operation": "remove", "id": "node-2"}),
        )
        evidence = (
            JsonDocument.from_value({"content_digest": "sha256:first"}),
            JsonDocument.from_value({"content_digest": "sha256:second"}),
        )
        original = NormalizedMutationRequest(1, 0, operations, evidence)

        self.assertNotEqual(
            proposal_request_hash(original),
            proposal_request_hash(replace(original, operations=tuple(reversed(operations)))),
        )
        self.assertNotEqual(
            proposal_request_hash(original),
            proposal_request_hash(replace(original, evidence=tuple(reversed(evidence)))),
        )

        unicode_request = NormalizedMutationRequest(
            1,
            0,
            (JsonDocument.from_value({"label": "café"}),),
            (JsonDocument.from_value({"label": "雪"}),),
        )
        self.assertEqual(
            "sha256:problemforger-request-v1:e11bb58d6a38ffa29f184dbb1d9e4c393aed6f413109f68925cf5e0e30922959",
            proposal_request_hash(unicode_request),
        )

    def test_c_run_recovery_context_round_trips_without_changing_request_hash(self):
        context = CRunRecoveryContext(
            manifest_hash="sha256:manifest-1",
            effective_graph_intervention_identity="graph-intervention-v3",
            effective_governance_policy_identity="governance-policy-v2",
        )
        c_receipt = receipt(c_run_recovery_context=context)
        serialized = serialize_entry(JournalEntry(1, c_receipt))
        decoded = deserialize_entry(serialized)
        envelope = json.loads(serialized)

        self.assertEqual(c_receipt, decoded.record)
        self.assertEqual(
            context.manifest_hash,
            envelope["record"]["c_run_recovery_context"]["manifest_hash"],
        )
        self.assertEqual(receipt().request_hash, c_receipt.request_hash)

        changed_context = CRunRecoveryContext(
            manifest_hash="sha256:manifest-2",
            effective_graph_intervention_identity="graph-intervention-v3",
            effective_governance_policy_identity="governance-policy-v2",
        )
        self.assertEqual(
            c_receipt.request_hash,
            receipt(c_run_recovery_context=changed_context).request_hash,
        )

    def test_c_run_recovery_context_requires_all_three_non_none_identities(self):
        for values in (
            ("", "graph-intervention-v3", "governance-policy-v2"),
            ("sha256:manifest-1", " ", "governance-policy-v2"),
            ("sha256:manifest-1", None, "governance-policy-v2"),
            ("sha256:manifest-1", "graph-intervention-v3", "NONE"),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    CRunRecoveryContext(*values)

        with self.assertRaises(TypeError):
            CRunRecoveryContext("sha256:manifest-1", "graph-intervention-v3")

        with self.assertRaises(TypeError):
            receipt(c_run_recovery_context={"manifest_hash": "sha256:manifest-1"})

        # An absent context is the representation for a non-C run. Whether a
        # C run may omit it depends on run metadata and is enforced by service code.
        self.assertIsNone(receipt().c_run_recovery_context)

    def test_journal_entry_round_trip_keeps_record_and_stream_versions_distinct(self):
        entry = JournalEntry(journal_position=1, record=receipt())

        serialized = serialize_entry(entry)
        decoded = deserialize_entry(serialized)
        envelope = json.loads(serialized)

        self.assertEqual(1, envelope["journal_position"])
        self.assertEqual(1, envelope["record"]["record_schema_version"])
        self.assertEqual(1, envelope["record"]["request"]["request_schema_version"])
        self.assertEqual(0, envelope["record"]["request"]["expected_graph_version"])
        self.assertIsNone(envelope["record"]["c_run_recovery_context"])
        self.assertEqual(entry, decoded)
        request_hash = envelope["record"]["request_hash"]
        self.assertTrue(request_hash.startswith("sha256:problemforger-request-v1:"))
        self.assertEqual(64, len(request_hash.rsplit(":", 1)[1]))

    def test_final_decision_round_trip_preserves_normalized_audit_details(self):
        normalized_request = request()
        final_decision = MutationDecision(
            metadata=metadata("decision-with-details"),
            proposal_id="proposal-1",
            request_hash=proposal_request_hash(normalized_request),
            expected_graph_version=0,
            resulting_graph_version=1,
            outcome=GovernanceOutcome.COMMIT,
            details=JsonDocument.from_value(
                {
                    "check_results": [{"check_id": "tests", "result": "pass"}],
                    "checker_versions": {"test_runner": "3.2.1"},
                    "policy_versions": {"governance": "sha256:policy-v4"},
                }
            ),
        )

        decoded = deserialize_entry(serialize_entry(JournalEntry(2, final_decision)))

        self.assertEqual(final_decision, decoded.record)
        self.assertEqual(
            "sha256:policy-v4",
            decoded.record.details.value["policy_versions"]["governance"],
        )

    def test_record_timestamp_is_normalized_to_utc_and_must_be_aware(self):
        offset = timezone(timedelta(hours=2))
        value = metadata(recorded_at=datetime(2026, 9, 27, 8, 0, tzinfo=offset))
        self.assertEqual(RECORDED_AT, value.recorded_at)

        with self.assertRaises(ValueError):
            metadata(recorded_at=datetime(2026, 9, 27, 6, 0))

    def test_identifiers_must_be_utf8_encodable_on_construction_and_decode(self):
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            RecordMetadata("\ud800", "record-1", RECORDED_AT)

        wire = json.loads(serialize_entry(JournalEntry(1, receipt())))
        wire["record"]["run_id"] = "\ud800"
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            deserialize_entry(json.dumps(wire, ensure_ascii=True))

    def test_receipt_hash_is_recomputed_and_checked_on_decode(self):
        serialized = serialize_entry(JournalEntry(1, receipt()))
        changed_hash = serialized.replace("sha256:problemforger-request-v1:", "sha256:problemforger-request-v2:")

        with self.assertRaises(ValueError):
            deserialize_entry(changed_hash)

    def test_incomplete_receipt_stays_pending_and_terminal_status_is_bound(self):
        pending_receipt = receipt()
        self.assertEqual(ProposalStatus.PENDING, proposal_status(pending_receipt))
        self.assertEqual(ProposalStatus.PENDING, proposal_status(pending_receipt))

        rejected = decision(
            outcome=GovernanceOutcome.REJECT,
            expected_version=0,
            resulting_version=0,
            reason_code="policy_rejected",
        )
        self.assertEqual(GovernanceOutcome.REJECT, proposal_status(pending_receipt, rejected))

        abandoned = ProposalAbandoned(
            metadata=metadata("abandoned-2"),
            proposal_id="proposal-1",
            request_hash=pending_receipt.request_hash,
            reason_code="required_schema_unavailable",
        )
        self.assertEqual(ProposalStatus.ABANDONED, proposal_status(pending_receipt, abandoned))

        with self.assertRaises(ValueError):
            proposal_status(pending_receipt, decision(proposal_id="other-proposal"))
        with self.assertRaises(TypeError):
            proposal_status(pending_receipt, graph_event())
        with self.assertRaises(TypeError):
            proposal_status(object())
        other_run = replace(metadata("other-run"), run_id="other-run")
        with self.assertRaises(ValueError):
            proposal_status(pending_receipt, replace(rejected, metadata=other_run))
        different_request_decision = replace(
            rejected,
            request_hash=proposal_request_hash(request(evidence_digest="sha256:changed")),
        )
        with self.assertRaises(ValueError):
            proposal_status(pending_receipt, different_request_decision)
        different_expected_version = replace(
            rejected,
            expected_graph_version=1,
            resulting_graph_version=1,
        )
        with self.assertRaises(ValueError):
            proposal_status(pending_receipt, different_expected_version)

    def test_provider_neutral_envelope_examples_keep_position_and_graph_versions_separate(self):
        empty_journal = ()
        graph_version = 0
        last_journal_position = 0
        self.assertEqual((), empty_journal)
        self.assertEqual((0, 0), (graph_version, last_journal_position))

        pending_rejection = receipt(
            record_id="receipt-reject",
            proposal_id="proposal-reject",
        )
        first_record = JournalEntry(1, pending_rejection)
        self.assertEqual(ProposalStatus.PENDING, proposal_status(first_record.record))
        self.assertEqual(0, first_record.record.request.expected_graph_version)

        rejected = decision(
            record_id="decision-reject",
            outcome=GovernanceOutcome.REJECT,
            expected_version=0,
            resulting_version=0,
            proposal_id="proposal-reject",
            reason_code="policy_rejected",
        )
        audit_entry = JournalEntry(2, rejected)
        self.assertEqual(2, audit_entry.journal_position)
        self.assertEqual(0, audit_entry.record.resulting_graph_version)
        self.assertEqual(GovernanceOutcome.REJECT, proposal_status(pending_rejection, rejected))

        pending_commit = receipt(
            record_id="receipt-commit",
            proposal_id="proposal-commit",
        )
        commit_receipt_entry = JournalEntry(3, pending_commit)
        committed = CommittedMutationBatch(
            decision=decision(record_id="decision-commit", proposal_id="proposal-commit"),
            graph_events=(
                graph_event(record_id="event-1", proposal_id="proposal-commit"),
                graph_event(record_id="event-2", proposal_id="proposal-commit"),
            ),
        )
        commit_records = committed.ordered_records
        commit_entries = tuple(
            JournalEntry(position, record)
            for position, record in enumerate(commit_records, start=4)
        )
        self.assertEqual([4, 5, 6], [entry.journal_position for entry in commit_entries])
        self.assertEqual(1, committed.decision.resulting_graph_version)
        self.assertEqual([1, 1], [event.graph_version for event in committed.graph_events])
        self.assertEqual(
            GovernanceOutcome.COMMIT,
            proposal_status(pending_commit, committed.decision),
        )

        pending_conflict = receipt(
            record_id="receipt-conflict",
            proposal_id="proposal-conflict",
        )
        conflict_receipt_entry = JournalEntry(7, pending_conflict)
        stale_decision = decision(
            record_id="decision-conflict",
            outcome=GovernanceOutcome.CONFLICT,
            expected_version=0,
            resulting_version=1,
            proposal_id="proposal-conflict",
            reason_code="stale_graph_version",
        )
        conflict_entry = JournalEntry(8, stale_decision)
        self.assertEqual(
            GovernanceOutcome.CONFLICT,
            proposal_status(pending_conflict, stale_decision),
        )
        self.assertEqual(0, stale_decision.expected_graph_version)
        self.assertEqual(1, stale_decision.resulting_graph_version)

        pending_abandonment = receipt(
            record_id="receipt-abandoned",
            proposal_id="proposal-abandoned",
            normalized_request=request(expected_version=1),
        )
        abandoned_receipt_entry = JournalEntry(9, pending_abandonment)
        abandoned = ProposalAbandoned(
            metadata=metadata("abandoned-1"),
            proposal_id=pending_abandonment.proposal_id,
            request_hash=pending_abandonment.request_hash,
            reason_code="required_policy_version_unavailable",
        )
        abandoned_entry = JournalEntry(10, abandoned)
        self.assertEqual(ProposalStatus.ABANDONED, proposal_status(pending_abandonment, abandoned))
        self.assertNotIsInstance(abandoned, GraphChangedEvent)

        example_journal = (
            first_record,
            audit_entry,
            commit_receipt_entry,
            *commit_entries,
            conflict_receipt_entry,
            conflict_entry,
            abandoned_receipt_entry,
            abandoned_entry,
        )
        self.assertEqual(list(range(1, 11)), [entry.journal_position for entry in example_journal])

    def test_version_conflict_carries_different_nonnegative_versions(self):
        self.assertEqual(0, VersionConflict(1, 0).actual_graph_version)
        with self.assertRaises(ValueError):
            VersionConflict(0, 0)
        with self.assertRaises(ValueError):
            VersionConflict(-1, 0)
        with self.assertRaises(ValueError):
            VersionConflict(True, 0)

    def test_rejects_duplicate_json_keys_unknown_records_and_invalid_positions(self):
        with self.assertRaises(ValueError):
            deserialize_entry('{"journal_position":1,"journal_position":2,"record":{}}')
        with self.assertRaises(ValueError):
            deserialize_entry('{"journal_position":1,"record":{"record_type":"unknown"}}')
        with self.assertRaises(ValueError):
            JournalEntry(journal_position=0, record=receipt())
        with self.assertRaises(ValueError):
            JournalEntry(journal_position=True, record=receipt())
        for invalid in (
            "not-json",
            '{"journal_position":1,"record":{}} trailing',
            "[1,2]",
            "NaN",
        ):
            with self.subTest(serialized=invalid):
                with self.assertRaises(ValueError):
                    deserialize_entry(invalid)
        with self.assertRaises(TypeError):
            serialize_entry(object())
        with self.assertRaises(TypeError):
            JournalEntry(1, object())

    def test_value_objects_reject_unsupported_schema_and_invalid_field_types(self):
        for build in (
            lambda: RecordMetadata(" ", "record", RECORDED_AT),
            lambda: RecordMetadata("run", "record", RECORDED_AT, record_schema_version=2),
            lambda: RecordMetadata("run", "record", "not-a-date"),
            lambda: RecordMetadata("run", "record", RECORDED_AT, correlation_id=" "),
            lambda: RecordMetadata("run", "record", RECORDED_AT, causation_id=" "),
            lambda: NormalizedMutationRequest(2, 0, (), ()),
            lambda: NormalizedMutationRequest(1, True, (), ()),
            lambda: NormalizedMutationRequest(1, 0, ({},), ()),
            lambda: NormalizedMutationRequest(1, 0, (JsonDocument.from_value([]),), ()),
            lambda: proposal_request_hash(object()),
        ):
            with self.subTest(build=build):
                with self.assertRaises((TypeError, ValueError)):
                    build()

    def test_deserializer_rejects_unknown_fields_and_invalid_request_shapes(self):
        entry = json.loads(serialize_entry(JournalEntry(1, receipt())))

        missing = json.loads(json.dumps(entry))
        del missing["record"]["record_id"]
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(missing))

        unknown = json.loads(json.dumps(entry))
        unknown["record"]["unexpected"] = True
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(unknown))

        unsupported = json.loads(json.dumps(entry))
        unsupported["record"]["record_schema_version"] = 2
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(unsupported))

        bad_timestamp = json.loads(json.dumps(entry))
        bad_timestamp["record"]["recorded_at"] = "not-a-timestamp"
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(bad_timestamp))

        bad_request = json.loads(json.dumps(entry))
        bad_request["record"]["request"]["operations"] = "not-an-array"
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(bad_request))

        bad_request = json.loads(json.dumps(entry))
        bad_request["record"]["request"]["extra"] = True
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(bad_request))

        bad_request = json.loads(json.dumps(entry))
        bad_request["record"]["request"]["expected_graph_version"] = True
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(bad_request))

        bad_context = json.loads(json.dumps(entry))
        bad_context["record"]["c_run_recovery_context"] = {
            "manifest_hash": "sha256:manifest-1",
            "effective_graph_intervention_identity": "graph-intervention-v3",
        }
        with self.assertRaises(ValueError):
            deserialize_entry(json.dumps(bad_context))

    def test_audit_outcomes_do_not_conflate_abandoned_with_governance_decision(self):
        for outcome, expected, resulting, reason in (
            (GovernanceOutcome.REJECT, 0, 0, "policy_rejected"),
            (GovernanceOutcome.RETRY, 0, 0, "missing_evidence"),
            (GovernanceOutcome.ESCALATE, 0, 0, "human_review"),
            (GovernanceOutcome.CONFLICT, 0, 1, "stale_graph_version"),
        ):
            record = decision(
                outcome=outcome,
                expected_version=expected,
                resulting_version=resulting,
                reason_code=reason,
            )
            self.assertEqual(outcome, deserialize_entry(serialize_entry(JournalEntry(2, record))).record.outcome)

        abandoned = ProposalAbandoned(
            metadata=metadata("abandoned-1"),
            proposal_id="proposal-1",
            request_hash=receipt().request_hash,
            reason_code="required_policy_version_unavailable",
        )
        self.assertEqual(
            abandoned,
            deserialize_entry(serialize_entry(JournalEntry(3, abandoned))).record,
        )
        with self.assertRaises(ValueError):
            GovernanceOutcome("ABANDONED")

    def test_mutation_decision_enforces_graph_version_semantics(self):
        with self.assertRaises(ValueError):
            decision(resulting_version=0)
        with self.assertRaises(ValueError):
            decision(outcome=GovernanceOutcome.REJECT, resulting_version=1, reason_code="rejected")
        with self.assertRaises(ValueError):
            decision(outcome=GovernanceOutcome.CONFLICT, resulting_version=0, reason_code="stale")
        # A caller may be ahead of the run's current version; any mismatch
        # conflicts and records the actual current version.
        future_version_conflict = decision(
            outcome=GovernanceOutcome.CONFLICT,
            expected_version=1,
            resulting_version=0,
            reason_code="version_mismatch",
        )
        self.assertEqual(0, future_version_conflict.resulting_graph_version)
        with self.assertRaisesRegex(ValueError, "reason_code"):
            decision(
                outcome=GovernanceOutcome.REJECT,
                resulting_version=0,
                reason_code=None,
            )

    def test_committed_batch_is_ordered_and_uses_one_new_graph_version(self):
        second = graph_event(record_id="event-2")
        batch = CommittedMutationBatch(
            decision=decision(),
            graph_events=(graph_event(), second),
        )

        self.assertEqual((batch.decision, graph_event(), second), batch.ordered_records)
        self.assertEqual(1, batch.decision.resulting_graph_version)
        self.assertEqual({1}, {event.graph_version for event in batch.graph_events})

    def test_committed_batch_rejects_partial_or_mismatched_batches(self):
        with self.assertRaises(ValueError):
            CommittedMutationBatch(decision=decision(), graph_events=())
        with self.assertRaises(ValueError):
            CommittedMutationBatch(
                decision=decision(),
                graph_events=(graph_event(version=2),),
            )
        with self.assertRaises(ValueError):
            CommittedMutationBatch(
                decision=decision(),
                graph_events=(graph_event(proposal_id="another-proposal"),),
            )
        rejected = decision(
            outcome=GovernanceOutcome.REJECT,
            expected_version=1,
            resulting_version=1,
            reason_code="policy_rejected",
        )
        with self.assertRaisesRegex(ValueError, "requires a COMMIT decision"):
            CommittedMutationBatch(
                decision=rejected,
                graph_events=(graph_event(version=1),),
            )

    def test_graph_event_schema_version_and_payload_are_validated(self):
        event = graph_event()
        self.assertEqual(event, deserialize_entry(serialize_entry(JournalEntry(1, event))).record)

        with self.assertRaisesRegex(ValueError, "unsupported graph event schema version"):
            replace(event, event_schema_version=2)

        wire = json.loads(serialize_entry(JournalEntry(1, event)))
        wire["record"]["event_schema_version"] = 999
        with self.assertRaisesRegex(ValueError, "unsupported graph event schema version"):
            deserialize_entry(json.dumps(wire))

        with self.assertRaises(ValueError):
            GraphChangedEvent(
                metadata=metadata(),
                proposal_id="proposal-1",
                graph_version=0,
                event_type="node.added",
                event_schema_version=1,
                payload=JsonDocument.from_value({}),
            )


if __name__ == "__main__":
    unittest.main()
