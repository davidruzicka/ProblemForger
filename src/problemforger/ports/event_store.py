"""Provider-neutral EventStore operations and result values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeAlias

from problemforger.core.journal import (
    CRunRecoveryContext,
    GovernanceOutcome,
    GraphChangedEvent,
    JournalEntry,
    JsonDocument,
    MutationDecision,
    NormalizedMutationRequest,
    ProposalAbandoned,
    ProposalId,
    ProposalReceipt,
    ProposalResult,
    RequestHash,
    RunId,
    VersionConflict,
)


class StoreDurability(str, Enum):
    EPHEMERAL = "ephemeral"
    DURABLE = "durable"


class StoreErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_AUDIT_BATCH = "INVALID_AUDIT_BATCH"
    INVALID_GRAPH_BATCH = "INVALID_GRAPH_BATCH"
    INVALID_LIMIT = "INVALID_LIMIT"


@dataclass(frozen=True, slots=True)
class StoreError:
    code: StoreErrorCode
    detail: str = ""

    @property
    def status(self) -> str:
        return self.code.value


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Versioned, canonical JSON metadata associated with one run."""

    data: JsonDocument
    metadata_schema_version: int = 1

    def __post_init__(self) -> None:
        if (
            isinstance(self.metadata_schema_version, bool)
            or not isinstance(self.metadata_schema_version, int)
            or self.metadata_schema_version != 1
        ):
            raise ValueError("unsupported run metadata schema version")
        if not isinstance(self.data, JsonDocument) or not isinstance(self.data.value, dict):
            raise TypeError("run metadata must be a JSON object")

    @classmethod
    def from_value(cls, value: object) -> RunMetadata:
        return cls(JsonDocument.from_value(value))

    def to_value(self) -> dict[str, object]:
        return {
            "metadata_schema_version": self.metadata_schema_version,
            "data": self.data.value,
        }

    @property
    def canonical_json(self) -> str:
        return JsonDocument.from_value(self.to_value()).canonical_json

    @property
    def metadata_hash(self) -> str:
        from hashlib import sha256

        digest = sha256(
            b"problemforger.run-metadata.v1\0" + self.canonical_json.encode("utf-8")
        ).hexdigest()
        return f"sha256:problemforger-run-metadata-v1:{digest}"


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run_id: RunId
    run_metadata: RunMetadata
    metadata_hash: str
    graph_version: int
    last_journal_position: int


class CreateRunStatus(str, Enum):
    CREATED = "CREATED"
    EXISTING = "EXISTING"
    RUN_METADATA_CONFLICT = "RUN_METADATA_CONFLICT"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True, slots=True)
class CreateRunResult:
    status: CreateRunStatus
    metadata_hash: str | None = None
    existing_metadata_hash: str | None = None
    run: RunSnapshot | None = None


@dataclass(frozen=True, slots=True)
class ProposalSnapshot:
    run_id: RunId
    proposal_id: ProposalId
    request_hash: RequestHash
    normalized_request: NormalizedMutationRequest
    status: ProposalResult
    terminal_record: MutationDecision | ProposalAbandoned | None
    resulting_graph_version: int | None
    last_journal_position: int
    c_run_recovery_context: CRunRecoveryContext | None = None

    @property
    def terminal_outcome(self) -> GovernanceOutcome | None:
        if isinstance(self.terminal_record, MutationDecision):
            return self.terminal_record.outcome
        return None


class RecordProposalStatus(str, Enum):
    CREATED = "CREATED"
    EXISTING = "EXISTING"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"


@dataclass(frozen=True, slots=True)
class RecordProposalResult:
    status: RecordProposalStatus
    proposal: ProposalSnapshot | None = None
    stored_request_hash: RequestHash | None = None
    supplied_request_hash: RequestHash | None = None


@dataclass(frozen=True, slots=True)
class AppendResult:
    last_journal_position: int
    entries: tuple[JournalEntry, ...]
    replayed: bool = False
    new_graph_version: int | None = None

    @property
    def terminal_record(self) -> MutationDecision | ProposalAbandoned | None:
        for entry in reversed(self.entries):
            if isinstance(entry.record, (MutationDecision, ProposalAbandoned)):
                return entry.record
        return None


@dataclass(frozen=True, slots=True)
class JournalPage:
    records: tuple[JournalEntry, ...]
    next_after_journal_position: int
    has_more: bool


StoreOperationResult: TypeAlias = StoreError
AppendGraphResult: TypeAlias = AppendResult | VersionConflict | StoreError


class EventStore(Protocol):
    """The run-scoped authoritative journal port."""

    @property
    def durability(self) -> StoreDurability: ...

    def create_run(self, run_id: str, run_metadata: RunMetadata) -> CreateRunResult: ...

    def get_run(self, run_id: str) -> RunSnapshot | StoreError: ...

    def get_proposal(
        self, run_id: str, proposal_id: str
    ) -> ProposalSnapshot | StoreError: ...

    def record_proposal(
        self,
        run_id: str,
        proposal_id: str,
        request_hash: str,
        normalized_request: NormalizedMutationRequest,
        receipt_record: ProposalReceipt,
    ) -> RecordProposalResult: ...

    def append_audit(
        self,
        run_id: str,
        records: tuple[MutationDecision | ProposalAbandoned, ...],
        proposal_id: str | None = None,
    ) -> AppendResult | StoreError: ...

    def append_graph(
        self,
        run_id: str,
        proposal_id: str,
        expected_graph_version: int,
        audit_records: tuple[MutationDecision, ...],
        graph_events: tuple[GraphChangedEvent, ...],
    ) -> AppendGraphResult: ...

    def read_journal(
        self,
        run_id: str,
        *,
        limit: int,
        after_journal_position: int | None = None,
    ) -> JournalPage | StoreError: ...

    def current_graph_version(self, run_id: str) -> int | StoreError: ...

    def close(self) -> None: ...
