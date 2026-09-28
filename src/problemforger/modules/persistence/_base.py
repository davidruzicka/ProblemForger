"""Shared EventStore semantics for provider implementations."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import RLock
from problemforger.core.journal import (
    CommittedMutationBatch,
    GovernanceOutcome,
    GraphChangedEvent,
    JournalEntry,
    JsonDocument,
    MutationDecision,
    NormalizedMutationRequest,
    ProposalAbandoned,
    ProposalId,
    ProposalReceipt,
    ProposalStatus,
    RecordId,
    RequestHash,
    RunId,
    VersionConflict,
    deserialize_entry,
    proposal_request_hash,
    proposal_status,
    serialize_entry,
)
from problemforger.ports.event_store import (
    AppendResult,
    CreateRunResult,
    CreateRunStatus,
    JournalPage,
    ProposalSnapshot,
    RecordProposalResult,
    RecordProposalStatus,
    RunMetadata,
    RunSnapshot,
    StoreDurability,
    StoreError,
    StoreErrorCode,
)


DEFAULT_MAX_JOURNAL_PAGE_SIZE = 100
MAX_RUN_METADATA_BYTES = 1_048_576
MAX_JOURNAL_RECORD_BYTES = 1_048_576
MAX_APPEND_BATCH_BYTES = 4_194_304
MAX_JOURNAL_PAGE_BYTES = 4_194_304
_HASH_PREFIX = "sha256:problemforger-request-v1:"


@dataclass(slots=True)
class _RunState:
    metadata: RunMetadata
    metadata_hash: str
    graph_version: int = 0
    entries: list[JournalEntry] = field(default_factory=list)

    @property
    def last_journal_position(self) -> int:
        return len(self.entries)

    def copy_for_write(self) -> _RunState:
        return _RunState(
            metadata=self.metadata,
            metadata_hash=self.metadata_hash,
            graph_version=self.graph_version,
            entries=list(self.entries),
        )


@dataclass(frozen=True, slots=True)
class _ProposalParts:
    receipt: ProposalReceipt
    receipt_position: int
    terminal: MutationDecision | ProposalAbandoned | None
    terminal_position: int
    terminal_last_position: int


def _valid_identifier(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _valid_integer(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _record_id(record: object) -> str | None:
    metadata = getattr(record, "metadata", None)
    record_id = getattr(metadata, "record_id", None)
    return record_id if isinstance(record_id, str) else None


class EventStoreState:
    """Thread-safe behavioral contract; providers persist each accepted transition."""

    def __init__(
        self,
        *,
        durability: StoreDurability,
        max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE,
    ) -> None:
        if (
            not _valid_integer(max_journal_page_size, minimum=1)
            or max_journal_page_size > DEFAULT_MAX_JOURNAL_PAGE_SIZE
        ):
            raise ValueError(
                "max_journal_page_size must be a positive integer no greater than "
                f"{DEFAULT_MAX_JOURNAL_PAGE_SIZE}"
            )
        self._durability = durability
        self._max_journal_page_size = max_journal_page_size
        self._runs: dict[str, _RunState] = {}
        self._lock = RLock()
        self._closed = False

    @property
    def durability(self) -> StoreDurability:
        return self._durability

    def _ensure_usable(self) -> None:
        if self._closed:
            raise RuntimeError("EventStore is closed")

    def _persist_transition(
        self, run_id: str, previous: _RunState | None, current: _RunState
    ) -> None:
        """Persist a complete validated run transition; memory provider is a no-op."""

    def _save(self, run_id: str, candidate: _RunState) -> None:
        previous = self._runs.get(run_id)
        try:
            self._persist_transition(run_id, previous, candidate)
            self._runs[run_id] = candidate
        except BaseException:
            self._recover_after_persist_error(run_id)
            raise

    def _recover_after_persist_error(self, run_id: str) -> None:
        """Fail closed unless a provider can reconcile an ambiguous write."""
        self._closed = True

    @staticmethod
    def _error(code: StoreErrorCode, detail: str = "") -> StoreError:
        return StoreError(code=code, detail=detail)

    @staticmethod
    def _snapshot(run_id: str, run: _RunState) -> RunSnapshot:
        return RunSnapshot(
            run_id=RunId(run_id),
            run_metadata=run.metadata,
            metadata_hash=run.metadata_hash,
            graph_version=run.graph_version,
            last_journal_position=run.last_journal_position,
        )

    def create_run(self, run_id: str, run_metadata: RunMetadata) -> CreateRunResult:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id) or not isinstance(run_metadata, RunMetadata):
                return CreateRunResult(CreateRunStatus.INVALID_REQUEST)
            if len(run_metadata.canonical_json.encode("utf-8")) > MAX_RUN_METADATA_BYTES:
                return CreateRunResult(CreateRunStatus.INVALID_REQUEST)
            metadata_hash = run_metadata.metadata_hash
            existing = self._runs.get(run_id)
            if existing is not None:
                if existing.metadata_hash == metadata_hash:
                    return CreateRunResult(
                        CreateRunStatus.EXISTING,
                        metadata_hash=metadata_hash,
                        run=self._snapshot(run_id, existing),
                    )
                return CreateRunResult(
                    CreateRunStatus.RUN_METADATA_CONFLICT,
                    metadata_hash=metadata_hash,
                    existing_metadata_hash=existing.metadata_hash,
                )
            run = _RunState(run_metadata, metadata_hash)
            self._save(run_id, run)
            return CreateRunResult(
                CreateRunStatus.CREATED,
                metadata_hash=metadata_hash,
                run=self._snapshot(run_id, run),
            )

    def get_run(self, run_id: str) -> RunSnapshot | StoreError:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id):
                return self._error(StoreErrorCode.INVALID_REQUEST, "run_id is required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            return self._snapshot(run_id, run)

    def get_proposal(
        self, run_id: str, proposal_id: str
    ) -> ProposalSnapshot | StoreError:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id) or not _valid_identifier(proposal_id):
                return self._error(StoreErrorCode.INVALID_REQUEST, "run_id and proposal_id are required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            parts = self._proposal_parts(run, proposal_id)
            if parts is None:
                return self._error(StoreErrorCode.NOT_FOUND, "proposal does not exist")
            return self._snapshot_proposal(run_id, run, proposal_id, parts)

    def record_proposal(
        self,
        run_id: str,
        proposal_id: str,
        request_hash: str,
        normalized_request: NormalizedMutationRequest,
        receipt_record: ProposalReceipt,
    ) -> RecordProposalResult:
        with self._lock:
            self._ensure_usable()
            run = self._runs.get(run_id) if _valid_identifier(run_id) else None
            if run is None:
                status = (
                    RecordProposalStatus.NOT_FOUND
                    if _valid_identifier(run_id)
                    else RecordProposalStatus.INVALID_PROPOSAL
                )
                return RecordProposalResult(status, supplied_request_hash=_as_hash(request_hash))
            if not self._valid_receipt_arguments(
                run_id, proposal_id, request_hash, normalized_request, receipt_record
            ):
                return RecordProposalResult(
                    RecordProposalStatus.INVALID_PROPOSAL,
                    supplied_request_hash=_as_hash(request_hash),
                )
            parts = self._proposal_parts(run, proposal_id)
            if parts is not None:
                receipt = parts.receipt
                if receipt.request_hash != request_hash:
                    return RecordProposalResult(
                        RecordProposalStatus.IDEMPOTENCY_CONFLICT,
                        proposal=self._snapshot_proposal(run_id, run, proposal_id, parts),
                        stored_request_hash=receipt.request_hash,
                        supplied_request_hash=RequestHash(request_hash),
                    )
                return RecordProposalResult(
                    RecordProposalStatus.EXISTING,
                    proposal=self._snapshot_proposal(run_id, run, proposal_id, parts),
                    stored_request_hash=receipt.request_hash,
                    supplied_request_hash=RequestHash(request_hash),
                )
            if not self._records_within_bounds(
                (receipt_record,), first_position=run.last_journal_position + 1
            ):
                return RecordProposalResult(
                    RecordProposalStatus.INVALID_PROPOSAL,
                    supplied_request_hash=RequestHash(request_hash),
                )
            candidate = run.copy_for_write()
            if self._has_record_id(candidate, receipt_record.metadata.record_id):
                return RecordProposalResult(
                    RecordProposalStatus.INVALID_PROPOSAL,
                    supplied_request_hash=RequestHash(request_hash),
                )
            self._append(candidate, receipt_record)
            self._save(run_id, candidate)
            parts = self._proposal_parts(candidate, proposal_id)
            assert parts is not None
            return RecordProposalResult(
                RecordProposalStatus.CREATED,
                proposal=self._snapshot_proposal(run_id, candidate, proposal_id, parts),
                supplied_request_hash=RequestHash(request_hash),
            )

    def append_audit(
        self,
        run_id: str,
        records: tuple[MutationDecision | ProposalAbandoned, ...],
        proposal_id: str | None = None,
    ) -> AppendResult | StoreError:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id):
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "run_id is required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            try:
                batch = tuple(records)
            except TypeError:
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "records must be a sequence")
            if not batch or any(
                not isinstance(record, (MutationDecision, ProposalAbandoned)) for record in batch
            ):
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "unsupported or empty audit batch")
            if not _valid_identifier(proposal_id):
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "terminal proposal_id is required")
            if len(batch) != 1:
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "P1 allows one terminal record per batch")
            record = batch[0]
            if record.metadata.run_id != run_id or record.proposal_id != proposal_id:
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "terminal record identity mismatch")
            if isinstance(record, MutationDecision) and record.outcome is GovernanceOutcome.COMMIT:
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "COMMIT must use append_graph")
            candidate = run.copy_for_write()
            parts = self._proposal_parts(candidate, proposal_id)
            if parts is None:
                return self._error(StoreErrorCode.NOT_FOUND, "proposal does not exist")
            receipt = parts.receipt
            terminal = parts.terminal
            terminal_position = parts.terminal_position
            if getattr(record, "request_hash", None) != receipt.request_hash:
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "request_hash does not match receipt")
            if terminal is not None:
                if isinstance(terminal, MutationDecision) and terminal.outcome is GovernanceOutcome.COMMIT:
                    entries = self._committed_entries(candidate, terminal_position, proposal_id)
                    return AppendResult(
                        parts.terminal_last_position,
                        entries,
                        replayed=True,
                        new_graph_version=terminal.resulting_graph_version,
                    )
                if isinstance(terminal, type(record)):
                    start = terminal_position - 1
                    entry = candidate.entries[start]
                    result_version = (
                        terminal.resulting_graph_version
                        if isinstance(terminal, MutationDecision)
                        else self._graph_version_at(candidate, terminal_position - 1)
                    )
                    return AppendResult(
                        terminal_position,
                        (entry,),
                        replayed=True,
                        new_graph_version=result_version,
                    )
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "proposal already has another terminal record")
            if isinstance(record, MutationDecision):
                if record.expected_graph_version != receipt.request.expected_graph_version:
                    return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "expected_graph_version does not match receipt")
                if record.outcome is GovernanceOutcome.CONFLICT:
                    if run.graph_version == receipt.request.expected_graph_version:
                        return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "CONFLICT requires a changed graph version")
                    record = replace(record, resulting_graph_version=run.graph_version)
                elif run.graph_version != receipt.request.expected_graph_version:
                    record = self._as_conflict(record, receipt, run.graph_version)
            if self._has_record_id(candidate, record.metadata.record_id):
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "record_id already exists")
            if not self._records_within_bounds(
                (record,), first_position=candidate.last_journal_position + 1
            ):
                return self._error(StoreErrorCode.INVALID_AUDIT_BATCH, "audit record exceeds the storage size limit")
            entry = self._append(candidate, record)
            self._save(run_id, candidate)
            new_graph_version = (
                record.resulting_graph_version
                if isinstance(record, MutationDecision)
                else run.graph_version
            )
            return AppendResult(
                entry.journal_position,
                (entry,),
                new_graph_version=new_graph_version,
            )

    def append_graph(
        self,
        run_id: str,
        proposal_id: str,
        expected_graph_version: int,
        audit_records: tuple[MutationDecision, ...],
        graph_events: tuple[GraphChangedEvent, ...],
    ) -> AppendResult | VersionConflict | StoreError:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "run_id is required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            try:
                decisions = tuple(audit_records)
                events = tuple(graph_events)
            except TypeError:
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "records must be sequences")
            if (
                not _valid_identifier(proposal_id)
                or not _valid_integer(expected_graph_version, minimum=0)
                or len(decisions) != 1
                or len(events) == 0
                or any(not isinstance(item, MutationDecision) for item in decisions)
                or any(not isinstance(item, GraphChangedEvent) for item in events)
            ):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "malformed graph batch")
            decision = decisions[0]
            if decision.outcome is not GovernanceOutcome.COMMIT:
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "exactly one COMMIT is required")
            if decision.metadata.run_id != run_id or decision.proposal_id != proposal_id:
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "COMMIT identity mismatch")
            if any(
                event.metadata.run_id != run_id or event.proposal_id != proposal_id
                for event in events
            ):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "graph event identity mismatch")
            candidate = run.copy_for_write()
            parts = self._proposal_parts(candidate, proposal_id)
            if parts is None:
                return self._error(StoreErrorCode.NOT_FOUND, "proposal does not exist")
            receipt = parts.receipt
            terminal = parts.terminal
            terminal_position = parts.terminal_position
            if decision.request_hash != receipt.request_hash:
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "request_hash does not match receipt")
            if expected_graph_version != receipt.request.expected_graph_version:
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "expected_graph_version does not match receipt")
            if (
                decision.expected_graph_version != expected_graph_version
                or decision.resulting_graph_version != expected_graph_version + 1
            ):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "COMMIT versions do not match the supplied version")
            try:
                CommittedMutationBatch(decision, events)
            except (TypeError, ValueError):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "graph events are not bound to COMMIT")
            if terminal is not None:
                if isinstance(terminal, MutationDecision) and terminal.outcome is GovernanceOutcome.COMMIT:
                    entries = self._committed_entries(candidate, terminal_position, proposal_id)
                    return AppendResult(
                        terminal_position + len(entries) - 1,
                        entries,
                        replayed=True,
                        new_graph_version=terminal.resulting_graph_version,
                    )
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "proposal already has another terminal record")
            if expected_graph_version != run.graph_version:
                return VersionConflict(expected_graph_version, run.graph_version)
            all_records = (decision, *events)
            record_ids = [_record_id(record) for record in all_records]
            if any(not _valid_identifier(record_id) for record_id in record_ids):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "record_id is required")
            if len(set(record_ids)) != len(record_ids) or any(
                self._has_record_id(candidate, record_id) for record_id in record_ids
            ):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "record_id already exists")
            if not self._records_within_bounds(
                all_records, first_position=candidate.last_journal_position + 1
            ):
                return self._error(StoreErrorCode.INVALID_GRAPH_BATCH, "graph batch exceeds the storage size limit")
            entries = tuple(self._append(candidate, record) for record in all_records)
            candidate.graph_version = decision.resulting_graph_version
            self._save(run_id, candidate)
            return AppendResult(
                entries[-1].journal_position,
                entries,
                new_graph_version=candidate.graph_version,
            )

    def read_journal(
        self,
        run_id: str,
        *,
        limit: int,
        after_journal_position: int | None = None,
    ) -> JournalPage | StoreError:
        with self._lock:
            self._ensure_usable()
            if (
                not _valid_integer(limit, minimum=1)
                or limit > self._max_journal_page_size
                or (after_journal_position is not None and not _valid_integer(after_journal_position, minimum=0))
            ):
                return self._error(StoreErrorCode.INVALID_LIMIT, "limit or cursor is outside the configured bounds")
            if not _valid_identifier(run_id):
                return self._error(StoreErrorCode.INVALID_REQUEST, "run_id is required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            cursor = 0 if after_journal_position is None else after_journal_position
            page_entries: list[JournalEntry] = []
            page_bytes = 0
            for entry in run.entries[cursor : cursor + limit]:
                entry_bytes = len(serialize_entry(entry).encode("utf-8"))
                if page_entries and page_bytes + entry_bytes > MAX_JOURNAL_PAGE_BYTES:
                    break
                page_entries.append(entry)
                page_bytes += entry_bytes
            page = tuple(page_entries)
            next_position = page[-1].journal_position if page else cursor
            return JournalPage(page, next_position, next_position < run.last_journal_position)

    def current_graph_version(self, run_id: str) -> int | StoreError:
        with self._lock:
            self._ensure_usable()
            if not _valid_identifier(run_id):
                return self._error(StoreErrorCode.INVALID_REQUEST, "run_id is required")
            run = self._runs.get(run_id)
            if run is None:
                return self._error(StoreErrorCode.NOT_FOUND, "run does not exist")
            return run.graph_version

    def close(self) -> None:
        with self._lock:
            self._closed = True

    @staticmethod
    def _valid_receipt_arguments(
        run_id: str,
        proposal_id: str,
        request_hash: str,
        normalized_request: NormalizedMutationRequest,
        receipt_record: ProposalReceipt,
    ) -> bool:
        if (
            not _valid_identifier(proposal_id)
            or not isinstance(normalized_request, NormalizedMutationRequest)
            or not isinstance(receipt_record, ProposalReceipt)
            or not isinstance(request_hash, str)
        ):
            return False
        try:
            calculated_hash = proposal_request_hash(normalized_request)
        except (TypeError, ValueError):
            return False
        return (
            request_hash == calculated_hash
            and receipt_record.request_hash == calculated_hash
            and receipt_record.request == normalized_request
            and receipt_record.proposal_id == proposal_id
            and receipt_record.metadata.run_id == run_id
            and request_hash.startswith(_HASH_PREFIX)
        )

    @staticmethod
    def _proposal_parts(
        run: _RunState, proposal_id: str
    ) -> _ProposalParts | None:
        receipt: ProposalReceipt | None = None
        receipt_position = 0
        terminal: MutationDecision | ProposalAbandoned | None = None
        terminal_position = 0
        for entry in run.entries:
            record = entry.record
            if isinstance(record, ProposalReceipt) and record.proposal_id == proposal_id:
                receipt, receipt_position = record, entry.journal_position
            elif isinstance(record, (MutationDecision, ProposalAbandoned)) and record.proposal_id == proposal_id:
                terminal, terminal_position = record, entry.journal_position
        if receipt is None:
            return None
        terminal_last_position = terminal_position
        if isinstance(terminal, MutationDecision) and terminal.outcome is GovernanceOutcome.COMMIT:
            committed = EventStoreState._committed_entries(run, terminal_position, proposal_id)
            terminal_last_position = committed[-1].journal_position
        return _ProposalParts(
            receipt,
            receipt_position,
            terminal,
            terminal_position,
            terminal_last_position,
        )

    @classmethod
    def _snapshot_proposal(
        cls,
        run_id: str,
        run: _RunState,
        proposal_id: str,
        parts: _ProposalParts,
    ) -> ProposalSnapshot:
        receipt = parts.receipt
        terminal = parts.terminal
        terminal_position = parts.terminal_position
        result_version = None
        last_position = parts.receipt_position
        if terminal is not None:
            result_version = (
                terminal.resulting_graph_version
                if isinstance(terminal, MutationDecision)
                else cls._graph_version_at(run, terminal_position - 1)
            )
            last_position = parts.terminal_last_position
        return ProposalSnapshot(
            run_id=RunId(run_id),
            proposal_id=ProposalId(proposal_id),
            request_hash=receipt.request_hash,
            normalized_request=receipt.request,
            status=proposal_status(receipt, terminal),
            terminal_record=terminal,
            resulting_graph_version=result_version,
            last_journal_position=last_position,
        )

    @staticmethod
    def _graph_version_at(run: _RunState, position: int) -> int:
        graph_version = 0
        for entry in run.entries:
            if entry.journal_position > position:
                break
            if isinstance(entry.record, MutationDecision) and entry.record.outcome is GovernanceOutcome.COMMIT:
                graph_version = entry.record.resulting_graph_version
        return graph_version

    @staticmethod
    def _has_record_id(run: _RunState, record_id: str) -> bool:
        return any(entry.record.metadata.record_id == record_id for entry in run.entries)

    @staticmethod
    def _append(run: _RunState, record: object) -> JournalEntry:
        entry = JournalEntry(len(run.entries) + 1, record)  # type: ignore[arg-type]
        run.entries.append(entry)
        return entry

    @staticmethod
    def _records_within_bounds(records: tuple[object, ...], *, first_position: int) -> bool:
        total_bytes = 0
        for offset, record in enumerate(records):
            try:
                encoded_size = len(
                    serialize_entry(JournalEntry(first_position + offset, record)).encode("utf-8")  # type: ignore[arg-type]
                )
            except (TypeError, ValueError, UnicodeEncodeError):
                return False
            if encoded_size > MAX_JOURNAL_RECORD_BYTES:
                return False
            total_bytes += encoded_size
            if total_bytes > MAX_APPEND_BATCH_BYTES:
                return False
        return True

    @staticmethod
    def _as_conflict(
        candidate: MutationDecision, receipt: ProposalReceipt, current_graph_version: int
    ) -> MutationDecision:
        if current_graph_version == receipt.request.expected_graph_version:
            raise ValueError("a conflict requires a different current graph version")
        return replace(
            candidate,
            expected_graph_version=receipt.request.expected_graph_version,
            resulting_graph_version=current_graph_version,
            outcome=GovernanceOutcome.CONFLICT,
            reason_code="stale_graph_version",
            details=JsonDocument.from_value({}),
        )

    @staticmethod
    def _committed_entries(
        run: _RunState, terminal_position: int, proposal_id: str
    ) -> tuple[JournalEntry, ...]:
        entries = run.entries
        result = [entries[terminal_position - 1]]
        for entry in entries[terminal_position:]:
            if not isinstance(entry.record, GraphChangedEvent) or entry.record.proposal_id != proposal_id:
                break
            result.append(entry)
        return tuple(result)

    @staticmethod
    def validate_loaded_run(run_id: str, run: _RunState) -> None:
        """Fail closed if durable rows cannot be interpreted as a valid journal."""
        if run.metadata.metadata_hash != run.metadata_hash:
            raise ValueError(f"stored metadata hash mismatch for run {run_id}")
        seen_ids: set[str] = set()
        receipts: dict[str, ProposalReceipt] = {}
        terminals: set[str] = set()
        graph_version = 0
        entries = run.entries
        index = 0
        while index < len(entries):
            entry = entries[index]
            if entry.journal_position != index + 1 or entry.record.metadata.run_id != run_id:
                raise ValueError(f"invalid journal position or run binding for {run_id}")
            record = entry.record
            record_id = record.metadata.record_id
            if record_id in seen_ids:
                raise ValueError(f"duplicate record_id in run {run_id}")
            seen_ids.add(record_id)
            if isinstance(record, ProposalReceipt):
                if record.proposal_id in receipts:
                    raise ValueError(f"duplicate proposal receipt in run {run_id}")
                receipts[record.proposal_id] = record
                index += 1
                continue
            if isinstance(record, GraphChangedEvent):
                raise ValueError(f"graph event without preceding COMMIT in run {run_id}")
            receipt = receipts.get(record.proposal_id)
            if receipt is None or record.proposal_id in terminals:
                raise ValueError(f"terminal record without a pending receipt in run {run_id}")
            if record.request_hash != receipt.request_hash:
                raise ValueError(f"terminal request hash mismatch in run {run_id}")
            terminals.add(record.proposal_id)
            if isinstance(record, ProposalAbandoned):
                index += 1
                continue
            if record.expected_graph_version != receipt.request.expected_graph_version:
                raise ValueError(f"terminal expected graph version mismatch in run {run_id}")
            if record.outcome is GovernanceOutcome.COMMIT:
                if (
                    record.expected_graph_version != graph_version
                    or record.resulting_graph_version != graph_version + 1
                ):
                    raise ValueError(f"invalid graph version transition in run {run_id}")
                index += 1
                event_count = 0
                graph_batch: list[object] = [record]
                while index < len(entries) and isinstance(entries[index].record, GraphChangedEvent):
                    graph_entry = entries[index]
                    if graph_entry.journal_position != index + 1:
                        raise ValueError(f"invalid graph event position in run {run_id}")
                    event = graph_entry.record
                    if event.metadata.run_id != run_id or event.proposal_id != record.proposal_id or event.graph_version != record.resulting_graph_version:
                        raise ValueError(f"graph event does not match COMMIT in run {run_id}")
                    if event.metadata.record_id in seen_ids:
                        raise ValueError(f"duplicate record_id in run {run_id}")
                    seen_ids.add(event.metadata.record_id)
                    graph_batch.append(event)
                    event_count += 1
                    index += 1
                if event_count == 0:
                    raise ValueError(f"COMMIT without graph events in run {run_id}")
                if not EventStoreState._records_within_bounds(
                    tuple(graph_batch), first_position=entry.journal_position
                ):
                    raise ValueError(f"committed graph batch exceeds size limit in run {run_id}")
                graph_version = record.resulting_graph_version
                continue
            if record.outcome is GovernanceOutcome.CONFLICT:
                if record.resulting_graph_version != graph_version or record.expected_graph_version == graph_version:
                    raise ValueError(f"invalid CONFLICT graph version in run {run_id}")
            elif record.expected_graph_version != graph_version or record.resulting_graph_version != graph_version:
                raise ValueError(f"non-commit terminal outcome is stale in run {run_id}")
            index += 1
        if run.graph_version != graph_version or run.last_journal_position != len(entries):
            raise ValueError(f"run head does not match journal for {run_id}")


def _as_hash(value: object) -> RequestHash | None:
    return RequestHash(value) if isinstance(value, str) else None
