"""Immutable, provider-neutral records for the authoritative run journal.

Storage providers assign journal positions and persist batches. This module
defines the values and checks that are independent of any provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, NewType, TypeAlias


RunId = NewType("RunId", str)
RecordId = NewType("RecordId", str)
ProposalId = NewType("ProposalId", str)
CorrelationId = NewType("CorrelationId", str)
CausationId = NewType("CausationId", str)
RequestHash = NewType("RequestHash", str)
JournalPosition = NewType("JournalPosition", int)
GraphVersion = NewType("GraphVersion", int)

CURRENT_RECORD_SCHEMA_VERSION = 1
CURRENT_REQUEST_SCHEMA_VERSION = 1
REQUEST_HASH_PREFIX = "sha256:problemforger-request-v1:"
_REQUEST_HASH_DOMAIN = b"problemforger.normalized-mutation-request.v1\0"


@dataclass(frozen=True, slots=True)
class VersionConflict:
    """Observed graph version differs from the proposal's expected version."""

    expected_graph_version: GraphVersion
    actual_graph_version: GraphVersion

    def __post_init__(self) -> None:
        _require_integer(self.expected_graph_version, "expected_graph_version", minimum=0)
        _require_integer(self.actual_graph_version, "actual_graph_version", minimum=0)
        if self.actual_graph_version == self.expected_graph_version:
            raise ValueError("VersionConflict requires different expected and actual versions")


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_integer(value: int, name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")


def _validate_json(value: Any, path: str = "$") -> None:
    """Reject Python values that JSON would otherwise silently coerce."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{path} must not contain a non-finite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{path} object keys must be strings")
            _validate_json(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contains a value that is not JSON serializable")


def _canonical_json(value: Any) -> str:
    _validate_json(value)
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        serialized.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ValueError("value cannot be represented as canonical UTF-8 JSON") from error
    return serialized


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(constant: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {constant}")


def _parse_json(serialized: str) -> Any:
    if not isinstance(serialized, str):
        raise TypeError("serialized JSON must be a string")
    try:
        return json.loads(
            serialized,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, UnicodeEncodeError) as error:
        raise ValueError("invalid JSON document") from error


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(f"{name} must be a JSON object")
    return value


def _require_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{name} fields do not match schema (missing={missing}, unknown={unknown})")


@dataclass(frozen=True, slots=True)
class JsonDocument:
    """A deeply immutable JSON value stored as canonical JSON text."""

    canonical_json: str

    def __post_init__(self) -> None:
        value = _parse_json(self.canonical_json)
        _validate_json(value)
        if _canonical_json(value) != self.canonical_json:
            raise ValueError("JsonDocument must contain canonical JSON")

    @classmethod
    def from_value(cls, value: Any) -> JsonDocument:
        return cls(_canonical_json(value))

    @property
    def value(self) -> Any:
        """Return a fresh mutable copy; mutating it cannot alter this value."""
        return _parse_json(self.canonical_json)


@dataclass(frozen=True, slots=True)
class RecordMetadata:
    """Common identity and provenance fields on a durable record."""

    run_id: RunId
    record_id: RecordId
    recorded_at: datetime
    record_schema_version: int = CURRENT_RECORD_SCHEMA_VERSION
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.run_id, "run_id")
        _require_identifier(self.record_id, "record_id")
        _require_integer(
            self.record_schema_version,
            "record_schema_version",
            minimum=1,
        )
        if self.record_schema_version != CURRENT_RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported record schema version: {self.record_schema_version}"
            )
        if not isinstance(self.recorded_at, datetime):
            raise TypeError("recorded_at must be a datetime")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone")
        object.__setattr__(self, "recorded_at", self.recorded_at.astimezone(timezone.utc))
        if self.correlation_id is not None:
            _require_identifier(self.correlation_id, "correlation_id")
        if self.causation_id is not None:
            _require_identifier(self.causation_id, "causation_id")


@dataclass(frozen=True, slots=True)
class NormalizedMutationRequest:
    """Complete immutable request input needed to identify and resume a proposal."""

    request_schema_version: int
    expected_graph_version: GraphVersion
    operations: tuple[JsonDocument, ...]
    evidence: tuple[JsonDocument, ...]

    def __post_init__(self) -> None:
        _require_integer(self.request_schema_version, "request_schema_version", minimum=1)
        if self.request_schema_version != CURRENT_REQUEST_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported request schema version: {self.request_schema_version}"
            )
        _require_integer(self.expected_graph_version, "expected_graph_version", minimum=0)
        operations = tuple(self.operations)
        evidence = tuple(self.evidence)
        if any(not isinstance(item, JsonDocument) for item in operations):
            raise TypeError("operations must contain JsonDocument values")
        if any(not isinstance(item, JsonDocument) for item in evidence):
            raise TypeError("evidence must contain JsonDocument values")
        for item in operations:
            _require_object(item.value, "each operation")
        for item in evidence:
            _require_object(item.value, "each evidence record")
        object.__setattr__(self, "operations", operations)
        object.__setattr__(self, "evidence", evidence)

    def to_value(self) -> dict[str, Any]:
        return {
            "request_schema_version": self.request_schema_version,
            "expected_graph_version": self.expected_graph_version,
            "operations": [item.value for item in self.operations],
            "evidence": [item.value for item in self.evidence],
        }


def proposal_request_hash(request: NormalizedMutationRequest) -> RequestHash:
    """Hash the full normalized request, including version and evidence inputs."""
    if not isinstance(request, NormalizedMutationRequest):
        raise TypeError("request must be a NormalizedMutationRequest")
    digest = hashlib.sha256(
        _REQUEST_HASH_DOMAIN + _canonical_json(request.to_value()).encode("utf-8")
    ).hexdigest()
    return RequestHash(f"{REQUEST_HASH_PREFIX}{digest}")


def _validate_request_hash(value: str) -> None:
    _require_identifier(value, "request_hash")
    if not value.startswith(REQUEST_HASH_PREFIX):
        raise ValueError("request_hash must use the supported SHA-256 request-hash version")
    digest = value[len(REQUEST_HASH_PREFIX) :]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("request_hash must contain a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CRunRecoveryContext:
    """Run metadata identities needed to verify a recovered C-run proposal."""

    manifest_hash: str
    effective_graph_intervention_identity: str
    effective_governance_policy_identity: str

    def __post_init__(self) -> None:
        for name in (
            "manifest_hash",
            "effective_graph_intervention_identity",
            "effective_governance_policy_identity",
        ):
            value = getattr(self, name)
            _require_identifier(value, name)
            if value.strip().casefold() == "none":
                raise ValueError(f"{name} must not use the NONE sentinel")


@dataclass(frozen=True, slots=True)
class ProposalReceipt:
    """The durable pending receipt; it is not a governance outcome."""

    metadata: RecordMetadata
    proposal_id: ProposalId
    request: NormalizedMutationRequest
    c_run_recovery_context: CRunRecoveryContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RecordMetadata):
            raise TypeError("metadata must be RecordMetadata")
        _require_identifier(self.proposal_id, "proposal_id")
        if not isinstance(self.request, NormalizedMutationRequest):
            raise TypeError("request must be NormalizedMutationRequest")
        if self.c_run_recovery_context is not None and not isinstance(
            self.c_run_recovery_context, CRunRecoveryContext
        ):
            raise TypeError("c_run_recovery_context must be CRunRecoveryContext or None")

    @property
    def request_hash(self) -> RequestHash:
        return proposal_request_hash(self.request)


class GovernanceOutcome(str, Enum):
    COMMIT = "COMMIT"
    REJECT = "REJECT"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"
    CONFLICT = "CONFLICT"


class ProposalStatus(str, Enum):
    """Non-outcome states exposed while recovery has no governance decision."""

    PENDING = "PENDING"
    ABANDONED = "ABANDONED"


ProposalResult: TypeAlias = ProposalStatus | GovernanceOutcome


@dataclass(frozen=True, slots=True)
class MutationDecision:
    """One durable final governance decision, distinct from proposal receipt state."""

    metadata: RecordMetadata
    proposal_id: ProposalId
    request_hash: RequestHash
    expected_graph_version: GraphVersion
    resulting_graph_version: GraphVersion
    outcome: GovernanceOutcome
    reason_code: str | None = None
    details: JsonDocument = field(default_factory=lambda: JsonDocument.from_value({}))

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RecordMetadata):
            raise TypeError("metadata must be RecordMetadata")
        _require_identifier(self.proposal_id, "proposal_id")
        _validate_request_hash(self.request_hash)
        _require_integer(self.expected_graph_version, "expected_graph_version", minimum=0)
        _require_integer(self.resulting_graph_version, "resulting_graph_version", minimum=0)
        try:
            outcome = GovernanceOutcome(self.outcome)
        except ValueError as error:
            raise ValueError(f"unsupported governance outcome: {self.outcome}") from error
        object.__setattr__(self, "outcome", outcome)
        if not isinstance(self.details, JsonDocument):
            raise TypeError("details must be a JsonDocument")
        _require_object(self.details.value, "decision details")

        if outcome is GovernanceOutcome.COMMIT:
            if self.resulting_graph_version != self.expected_graph_version + 1:
                raise ValueError("COMMIT must advance graph_version exactly once")
        elif outcome is GovernanceOutcome.CONFLICT:
            VersionConflict(self.expected_graph_version, self.resulting_graph_version)
        else:
            if self.resulting_graph_version != self.expected_graph_version:
                raise ValueError("non-commit, non-conflict outcomes do not advance graph_version")
        if outcome is not GovernanceOutcome.COMMIT:
            _require_identifier(self.reason_code or "", "reason_code")
        elif self.reason_code is not None:
            _require_identifier(self.reason_code, "reason_code")


@dataclass(frozen=True, slots=True)
class ProposalAbandoned:
    """A terminal operational recovery status, not a governance decision."""

    metadata: RecordMetadata
    proposal_id: ProposalId
    request_hash: RequestHash
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RecordMetadata):
            raise TypeError("metadata must be RecordMetadata")
        _require_identifier(self.proposal_id, "proposal_id")
        _validate_request_hash(self.request_hash)
        _require_identifier(self.reason_code, "reason_code")


def proposal_status(
    receipt: ProposalReceipt,
    terminal_record: MutationDecision | ProposalAbandoned | None = None,
) -> ProposalResult:
    """Derive recovery status from one receipt and its optional terminal record."""
    if not isinstance(receipt, ProposalReceipt):
        raise TypeError("receipt must be a ProposalReceipt")
    if terminal_record is None:
        return ProposalStatus.PENDING
    if not isinstance(terminal_record, (MutationDecision, ProposalAbandoned)):
        raise TypeError("terminal_record must be a final decision or ProposalAbandoned")
    if terminal_record.metadata.run_id != receipt.metadata.run_id:
        raise ValueError("terminal record run_id does not match the proposal receipt")
    if terminal_record.proposal_id != receipt.proposal_id:
        raise ValueError("terminal record proposal_id does not match the proposal receipt")
    if terminal_record.request_hash != receipt.request_hash:
        raise ValueError("terminal record request_hash does not match the proposal receipt")
    if (
        isinstance(terminal_record, MutationDecision)
        and terminal_record.expected_graph_version != receipt.request.expected_graph_version
    ):
        raise ValueError("terminal decision expected_graph_version does not match the receipt")
    if isinstance(terminal_record, ProposalAbandoned):
        return ProposalStatus.ABANDONED
    return terminal_record.outcome


@dataclass(frozen=True, slots=True)
class GraphChangedEvent:
    """One committed graph event; concrete graph vocabulary belongs to P2."""

    metadata: RecordMetadata
    proposal_id: ProposalId
    graph_version: GraphVersion
    event_type: str
    event_schema_version: int
    payload: JsonDocument

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RecordMetadata):
            raise TypeError("metadata must be RecordMetadata")
        _require_identifier(self.proposal_id, "proposal_id")
        _require_integer(self.graph_version, "graph_version", minimum=1)
        _require_identifier(self.event_type, "event_type")
        _require_integer(self.event_schema_version, "event_schema_version", minimum=1)
        if not isinstance(self.payload, JsonDocument):
            raise TypeError("payload must be a JsonDocument")
        _require_object(self.payload.value, "event payload")


JournalRecord: TypeAlias = (
    ProposalReceipt | MutationDecision | ProposalAbandoned | GraphChangedEvent
)


@dataclass(frozen=True, slots=True)
class CommittedMutationBatch:
    """Ordered commit decision and graph events that must persist atomically."""

    decision: MutationDecision
    graph_events: tuple[GraphChangedEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.decision, MutationDecision):
            raise TypeError("decision must be a MutationDecision")
        if self.decision.outcome is not GovernanceOutcome.COMMIT:
            raise ValueError("a committed mutation batch requires a COMMIT decision")
        events = tuple(self.graph_events)
        if not events:
            raise ValueError("a committed mutation batch must contain graph events")
        if any(not isinstance(event, GraphChangedEvent) for event in events):
            raise TypeError("graph_events must contain GraphChangedEvent values")
        for event in events:
            if event.metadata.run_id != self.decision.metadata.run_id:
                raise ValueError("commit decision and graph events must use the same run_id")
            if event.proposal_id != self.decision.proposal_id:
                raise ValueError("commit decision and graph events must use the same proposal_id")
            if event.graph_version != self.decision.resulting_graph_version:
                raise ValueError("all graph events must use the commit's resulting graph_version")
        object.__setattr__(self, "graph_events", events)

    @property
    def ordered_records(self) -> tuple[MutationDecision | GraphChangedEvent, ...]:
        return (self.decision, *self.graph_events)


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A durable record with its provider-assigned per-run journal position."""

    journal_position: JournalPosition
    record: JournalRecord

    def __post_init__(self) -> None:
        _require_integer(self.journal_position, "journal_position", minimum=1)
        if not isinstance(
            self.record,
            (ProposalReceipt, MutationDecision, ProposalAbandoned, GraphChangedEvent),
        ):
            raise TypeError("record must be a supported JournalRecord")


def _metadata_to_value(metadata: RecordMetadata) -> dict[str, Any]:
    return {
        "run_id": metadata.run_id,
        "record_id": metadata.record_id,
        "record_schema_version": metadata.record_schema_version,
        "recorded_at": metadata.recorded_at.isoformat().replace("+00:00", "Z"),
        "correlation_id": metadata.correlation_id,
        "causation_id": metadata.causation_id,
    }


def _request_to_value(request: NormalizedMutationRequest) -> dict[str, Any]:
    return request.to_value()


def _c_run_recovery_context_to_value(
    context: CRunRecoveryContext | None,
) -> dict[str, str] | None:
    if context is None:
        return None
    return {
        "manifest_hash": context.manifest_hash,
        "effective_graph_intervention_identity": context.effective_graph_intervention_identity,
        "effective_governance_policy_identity": context.effective_governance_policy_identity,
    }


def _c_run_recovery_context_from_value(value: Any) -> CRunRecoveryContext | None:
    if value is None:
        return None
    data = _require_object(value, "c_run_recovery_context")
    _require_keys(
        data,
        {
            "manifest_hash",
            "effective_graph_intervention_identity",
            "effective_governance_policy_identity",
        },
        "c_run_recovery_context",
    )
    return CRunRecoveryContext(
        manifest_hash=data["manifest_hash"],
        effective_graph_intervention_identity=data["effective_graph_intervention_identity"],
        effective_governance_policy_identity=data["effective_governance_policy_identity"],
    )


def _record_to_value(record: JournalRecord) -> dict[str, Any]:
    base = _metadata_to_value(record.metadata)
    if isinstance(record, ProposalReceipt):
        return {
            "record_type": "proposal_receipt",
            **base,
            "proposal_id": record.proposal_id,
            "request": _request_to_value(record.request),
            "request_hash": record.request_hash,
            "c_run_recovery_context": _c_run_recovery_context_to_value(
                record.c_run_recovery_context
            ),
        }
    if isinstance(record, MutationDecision):
        return {
            "record_type": "mutation_decision",
            **base,
            "proposal_id": record.proposal_id,
            "request_hash": record.request_hash,
            "expected_graph_version": record.expected_graph_version,
            "resulting_graph_version": record.resulting_graph_version,
            "outcome": record.outcome.value,
            "reason_code": record.reason_code,
            "details": record.details.value,
        }
    if isinstance(record, ProposalAbandoned):
        return {
            "record_type": "proposal_abandoned",
            **base,
            "proposal_id": record.proposal_id,
            "request_hash": record.request_hash,
            "reason_code": record.reason_code,
        }
    if isinstance(record, GraphChangedEvent):
        return {
            "record_type": "graph_changed",
            **base,
            "proposal_id": record.proposal_id,
            "graph_version": record.graph_version,
            "event_type": record.event_type,
            "event_schema_version": record.event_schema_version,
            "payload": record.payload.value,
        }
    raise TypeError(f"unsupported journal record type: {type(record).__name__}")


def serialize_entry(entry: JournalEntry) -> str:
    if not isinstance(entry, JournalEntry):
        raise TypeError("entry must be a JournalEntry")
    return _canonical_json(
        {
            "journal_position": entry.journal_position,
            "record": _record_to_value(entry.record),
        }
    )


def _metadata_from_value(value: dict[str, Any]) -> RecordMetadata:
    recorded_at = value["recorded_at"]
    if not isinstance(recorded_at, str):
        raise ValueError("recorded_at must be a timestamp string")
    try:
        timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("recorded_at must be an ISO-8601 timestamp") from error
    return RecordMetadata(
        run_id=RunId(value["run_id"]),
        record_id=RecordId(value["record_id"]),
        record_schema_version=value["record_schema_version"],
        recorded_at=timestamp,
        correlation_id=(
            None if value["correlation_id"] is None else CorrelationId(value["correlation_id"])
        ),
        causation_id=(
            None if value["causation_id"] is None else CausationId(value["causation_id"])
        ),
    )


def _request_from_value(value: Any) -> NormalizedMutationRequest:
    data = _require_object(value, "request")
    _require_keys(
        data,
        {
            "request_schema_version",
            "expected_graph_version",
            "operations",
            "evidence",
        },
        "request",
    )
    if type(data["operations"]) is not list or type(data["evidence"]) is not list:
        raise ValueError("request operations and evidence must be JSON arrays")
    return NormalizedMutationRequest(
        request_schema_version=data["request_schema_version"],
        expected_graph_version=data["expected_graph_version"],
        operations=tuple(JsonDocument.from_value(item) for item in data["operations"]),
        evidence=tuple(JsonDocument.from_value(item) for item in data["evidence"]),
    )


def _record_from_value(value: Any) -> JournalRecord:
    data = _require_object(value, "record")
    record_type = data.get("record_type")
    common = {
        "record_type",
        "run_id",
        "record_id",
        "record_schema_version",
        "recorded_at",
        "correlation_id",
        "causation_id",
    }
    fields_by_type = {
        "proposal_receipt": {
            "proposal_id",
            "request",
            "request_hash",
            "c_run_recovery_context",
        },
        "mutation_decision": {
            "proposal_id",
            "request_hash",
            "expected_graph_version",
            "resulting_graph_version",
            "outcome",
            "reason_code",
            "details",
        },
        "proposal_abandoned": {"proposal_id", "request_hash", "reason_code"},
        "graph_changed": {
            "proposal_id",
            "graph_version",
            "event_type",
            "event_schema_version",
            "payload",
        },
    }
    if not isinstance(record_type, str) or record_type not in fields_by_type:
        raise ValueError(f"unsupported record_type: {record_type}")
    _require_keys(data, common | fields_by_type[record_type], str(record_type))
    metadata = _metadata_from_value(data)

    if record_type == "proposal_receipt":
        proposal = ProposalReceipt(
            metadata=metadata,
            proposal_id=ProposalId(data["proposal_id"]),
            request=_request_from_value(data["request"]),
            c_run_recovery_context=_c_run_recovery_context_from_value(
                data["c_run_recovery_context"]
            ),
        )
        if data["request_hash"] != proposal.request_hash:
            raise ValueError("proposal receipt request_hash does not match its normalized request")
        return proposal

    if record_type == "mutation_decision":
        return MutationDecision(
            metadata=metadata,
            proposal_id=ProposalId(data["proposal_id"]),
            request_hash=RequestHash(data["request_hash"]),
            expected_graph_version=data["expected_graph_version"],
            resulting_graph_version=data["resulting_graph_version"],
            outcome=GovernanceOutcome(data["outcome"]),
            reason_code=data["reason_code"],
            details=JsonDocument.from_value(data["details"]),
        )

    if record_type == "proposal_abandoned":
        return ProposalAbandoned(
            metadata=metadata,
            proposal_id=ProposalId(data["proposal_id"]),
            request_hash=RequestHash(data["request_hash"]),
            reason_code=data["reason_code"],
        )

    return GraphChangedEvent(
        metadata=metadata,
        proposal_id=ProposalId(data["proposal_id"]),
        graph_version=data["graph_version"],
        event_type=data["event_type"],
        event_schema_version=data["event_schema_version"],
        payload=JsonDocument.from_value(data["payload"]),
    )


def deserialize_entry(serialized: str) -> JournalEntry:
    """Decode one versioned entry, rejecting duplicate or unknown fields."""
    data = _require_object(_parse_json(serialized), "journal entry")
    _require_keys(data, {"journal_position", "record"}, "journal entry")
    return JournalEntry(
        journal_position=data["journal_position"],
        record=_record_from_value(data["record"]),
    )
