"""Provider-neutral observation envelope and sink contract tests."""

from datetime import datetime, timezone
import unittest

from event_store_contract import decision, receipt, request
from problemforger.core.journal import (
    GovernanceOutcome,
    JsonDocument,
    proposal_request_hash,
)
from problemforger.modules.persistence import MemoryEventStore
from problemforger.modules.telemetry import NullTelemetrySink, RecordingTelemetrySink
from problemforger.ports.event_store import (
    AppendResult,
    RecordProposalStatus,
    RunMetadata,
)
from problemforger.ports import TelemetryObservation


def observation(*, journal_position=None):
    return TelemetryObservation.from_value(
        {
            "observation_schema_version": 1,
            "run_id": "run-1",
            "proposal_id": "proposal-1",
            "journal_position": journal_position,
            "correlation_id": "request-1",
            "causation_id": "proposal-1",
            "event_type": "model.response",
            "observed_at": "2026-10-10T17:00:00Z",
            "attributes": {
                "provider": "example",
                "model": "model-1",
                "input_tokens": 12,
                "output_tokens": 7,
                "cost_usd": 0.003,
                "latency_ms": 42,
                "apiKey": "secret-key",
                "tokenValue": "secret-token",
                "accessTokenValue": "secret-access-token",
                "access_token_value": "secret-snake-token",
                "nested": {
                    "accessToken": "secret-token",
                    "password": "secret-password",
                    "authorization": "Bearer secret",
                    "token": "secret-token",
                    "items": [{"private_key": "secret-private"}, {"input_tokens": 99}],
                },
            },
        }
    )


class TelemetryObservationTests(unittest.TestCase):
    def test_v1_envelope_round_trips_and_redacts_sensitive_attributes(self):
        item = observation(journal_position=2)
        value = item.to_value()

        self.assertEqual(1, value["observation_schema_version"])
        self.assertEqual("run-1", value["run_id"])
        self.assertEqual("proposal-1", value["proposal_id"])
        self.assertEqual(2, value["journal_position"])
        self.assertEqual("2026-10-10T17:00:00Z", value["observed_at"])
        self.assertNotIn("graph_version", value)
        self.assertEqual(12, value["attributes"]["input_tokens"])
        self.assertEqual(7, value["attributes"]["output_tokens"])
        self.assertEqual("<redacted>", value["attributes"]["apiKey"])
        self.assertEqual("<redacted>", value["attributes"]["tokenValue"])
        self.assertEqual("<redacted>", value["attributes"]["accessTokenValue"])
        self.assertEqual("<redacted>", value["attributes"]["access_token_value"])
        self.assertEqual("<redacted>", value["attributes"]["nested"]["accessToken"])
        self.assertEqual("<redacted>", value["attributes"]["nested"]["password"])
        self.assertEqual("<redacted>", value["attributes"]["nested"]["token"])
        self.assertEqual("<redacted>", value["attributes"]["nested"]["items"][0]["private_key"])
        self.assertEqual(99, value["attributes"]["nested"]["items"][1]["input_tokens"])
        self.assertEqual(value, TelemetryObservation.from_value(value).to_value())

    def test_standard_attributes_enforce_documented_types_and_ranges(self):
        for name, invalid in (
            ("input_tokens", -1),
            ("output_tokens", True),
            ("provider", ""),
            ("model", " "),
            ("status", 1),
            ("tool_name", 42),
            ("adapter_name", None),
            ("diagnostic_code", []),
            ("cost_usd", True),
            ("cost_usd", -0.01),
            ("latency_ms", False),
            ("latency_ms", -1),
        ):
            value = observation().to_value()
            value["attributes"][name] = invalid
            with self.subTest(name=name, value=invalid), self.assertRaises(
                (TypeError, ValueError)
            ):
                TelemetryObservation.from_value(value)

    def test_envelope_rejects_unknown_or_unsupported_shapes(self):
        value = observation().to_value()
        for changed in (
            {**value, "observation_schema_version": 2},
            {**value, "observation_schema_version": True},
            {key: item for key, item in value.items() if key != "event_type"},
            {**value, "unexpected": True},
            {**value, "journal_position": True},
            {**value, "journal_position": 0},
            {**value, "observed_at": "2026-10-10T17:00:00+01:00"},
            {**value, "observed_at": "2026-99-99T17:00:00Z"},
            {**value, "observed_at": None},
            {**value, "observed_at": "short"},
            {**value, "event_type": ""},
            {**value, "run_id": ""},
            {**value, "run_id": 1},
            {**value, "proposal_id": ""},
            {**value, "causation_id": ""},
            {**value, "correlation_id": ""},
            {**value, "journal_position": "2"},
            {**value, "attributes": []},
        ):
            with self.subTest(value=changed), self.assertRaises((TypeError, ValueError)):
                TelemetryObservation.from_value(changed)
        with self.assertRaises(TypeError):
            TelemetryObservation.from_value([])
        non_string_field = dict(value)
        non_string_field[1] = "invalid"
        with self.assertRaises(TypeError):
            TelemetryObservation.from_value(non_string_field)
        invalid_utf8 = dict(value, run_id="\ud800")
        with self.assertRaises(ValueError):
            TelemetryObservation.from_value(invalid_utf8)

    def test_direct_observation_requires_timezone_and_immutable_json_attributes(self):
        with self.assertRaises(ValueError):
            TelemetryObservation(run_id="run-1", event_type="test", observed_at=datetime(2026, 1, 1))
        with self.assertRaises(TypeError):
            TelemetryObservation(
                run_id="run-1",
                event_type="test",
                observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                attributes={},
            )
        with self.assertRaises(TypeError):
            TelemetryObservation(
                run_id="run-1",
                event_type="test",
                observed_at="2026-01-01T00:00:00Z",
            )
        with self.assertRaises(ValueError):
            TelemetryObservation(
                run_id="run-1",
                event_type="test",
                observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                attributes=JsonDocument.from_value([]),
            )

    def test_recording_sink_retains_only_typed_observations(self):
        item = observation()
        sink = RecordingTelemetrySink(max_observations=1)
        sink.emit(item)
        self.assertEqual((item,), sink.observations)
        with self.assertRaises(TypeError):
            sink.emit({"kind": "untyped"})
        with self.assertRaises(TypeError):
            NullTelemetrySink().emit({"kind": "untyped"})
        with self.assertRaises(OverflowError):
            sink.emit(item)

    def test_telemetry_emission_does_not_change_event_store_state(self):
        store = MemoryEventStore()
        try:
            store.create_run("run-1", RunMetadata.from_value({}))
            before_run = store.get_run("run-1")
            before_page = store.read_journal("run-1", limit=10)
            sink = RecordingTelemetrySink()
            sink.emit(observation())
            self.assertEqual(before_run, store.get_run("run-1"))
            self.assertEqual(before_page, store.read_journal("run-1", limit=10))
            self.assertEqual(0, store.current_graph_version("run-1"))
        finally:
            store.close()

    def test_null_telemetry_does_not_hide_or_replace_durable_governance_audit(self):
        store = MemoryEventStore()
        try:
            store.create_run("run-1", RunMetadata.from_value({}))
            normalized = request(0, "proposal-1")
            request_hash = proposal_request_hash(normalized)
            self.assertEqual(
                RecordProposalStatus.CREATED,
                store.record_proposal(
                    "run-1",
                    "proposal-1",
                    request_hash,
                    normalized,
                    receipt("proposal-1"),
                ).status,
            )
            rejected = decision(
                "proposal-1",
                outcome=GovernanceOutcome.REJECT,
                request_hash=request_hash,
            )
            appended = store.append_audit("run-1", (rejected,), "proposal-1")
            self.assertIsInstance(appended, AppendResult)
            before_page = store.read_journal("run-1", limit=10)

            self.assertIsNone(NullTelemetrySink().emit(observation(journal_position=2)))

            self.assertEqual(before_page, store.read_journal("run-1", limit=10))
            self.assertEqual(0, store.current_graph_version("run-1"))
            self.assertEqual(
                GovernanceOutcome.REJECT,
                store.get_proposal("run-1", "proposal-1").status,
            )
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()

