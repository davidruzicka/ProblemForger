"""Provider-neutral P1 command/query handling over the public protocol."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, NoReturn

from problemforger.application._protocol_contract import ErrorCode
from problemforger.application.protocol import (
    ProtocolRequest,
    ProtocolResponse,
    ProtocolValidationError,
    validate_request,
    validate_response,
)
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
    proposal_request_hash,
)
from problemforger.ports.event_store import (
    CreateRunStatus,
    EventStore,
    ProposalSnapshot,
    RecordProposalStatus,
    RunMetadata,
    StoreError,
    StoreErrorCode,
)
from problemforger.ports.telemetry import TelemetryObservation, TelemetrySink


_PLACEHOLDER_REJECTION = "P1_GOVERNANCE_NOT_IMPLEMENTED"
_GRAPH_SCHEMA_VERSION = 1


class ProtocolApplication:
    """Implement protocol wiring while leaving graph semantics to P2/P3."""

    def __init__(self, event_store: EventStore, telemetry: TelemetrySink) -> None:
        self._event_store = event_store
        self._telemetry = telemetry

    def handle(self, value: object) -> ProtocolResponse:
        """Validate, handle, and validate one request/response pair."""
        request = validate_request(value)
        try:
            result = self._dispatch(request)
            response: ProtocolResponse = {
                "protocol_schema_version": 1,
                "request_id": request["request_id"],
                "operation": request["operation"],
                "result": result,
            }
        except ProtocolValidationError as error:
            response = {
                "protocol_schema_version": 1,
                "request_id": request["request_id"],
                "error": {"code": error.code, "message": str(error)},
            }
        checked = validate_response(response, request)
        self._observe(request, checked)
        return checked

    def _dispatch(self, request: ProtocolRequest) -> dict[str, Any]:
        operation = request["operation"]
        params = request["params"]
        if operation == "create_run":
            return self._create_run(request["request_id"], params["run_id"], params["run_metadata"])
        if operation == "get_run":
            return self._run_result(self._require_run(params["run_id"]), created=False)
        if operation == "get_graph":
            run = self._require_run(params["run_id"])
            return {
                "run_id": params["run_id"],
                "graph_schema_version": _GRAPH_SCHEMA_VERSION,
                "graph_version": run.graph_version,
                "nodes": [],
                "edges": [],
                "next_cursor": None,
                "has_more": False,
            }
        if operation == "propose_mutation":
            return self._propose_mutation(request)
        if operation == "get_proposal":
            snapshot = self._event_store.get_proposal(
                params["run_id"], params["proposal_id"]
            )
            if isinstance(snapshot, StoreError):
                self._raise_store_error(snapshot)
            return self._proposal_result(snapshot)
        if operation == "get_audit_timeline":
            page = self._event_store.read_journal(
                params["run_id"],
                limit=params["limit"],
                after_journal_position=params.get("after_journal_position"),
            )
            if isinstance(page, StoreError):
                self._raise_store_error(page)
            return {
                "run_id": params["run_id"],
                "records": [self._public_record(entry) for entry in page.records],
                "next_after_journal_position": page.next_after_journal_position,
                "has_more": page.has_more,
            }
        raise AssertionError(f"validated operation was not dispatched: {operation}")

    def _create_run(
        self, request_id: str, run_id: str, metadata_value: dict[str, Any]
    ) -> dict[str, Any]:
        metadata = RunMetadata(
            data=JsonDocument.from_value(metadata_value["data"]),
            metadata_schema_version=metadata_value["metadata_schema_version"],
        )
        self._c_run_context(metadata)
        created = self._event_store.create_run(run_id, metadata)
        if created.status is CreateRunStatus.RUN_METADATA_CONFLICT:
            raise ProtocolValidationError(
                "run_id is already registered with different run_metadata",
                code="RUN_METADATA_CONFLICT",
            )
        if created.status is CreateRunStatus.INVALID_REQUEST or created.run is None:
            raise ProtocolValidationError("EventStore rejected run registration")
        return self._run_result(created.run, created=created.status is CreateRunStatus.CREATED)

    def _propose_mutation(self, request: ProtocolRequest) -> dict[str, Any]:
        params = request["params"]
        run_id = params["run_id"]
        proposal_id = params["proposal_id"]
        run = self._require_run(run_id)
        normalized = NormalizedMutationRequest(
            request_schema_version=params["request_schema_version"],
            expected_graph_version=params["expected_graph_version"],
            operations=tuple(JsonDocument.from_value(item) for item in params["operations"]),
            evidence=tuple(JsonDocument.from_value(item) for item in params["evidence"]),
        )
        request_hash = proposal_request_hash(normalized)
        existing = self._event_store.get_proposal(run_id, proposal_id)
        if isinstance(existing, StoreError):
            if existing.code is not StoreErrorCode.NOT_FOUND:
                self._raise_store_error(existing)
            context = self._c_run_context(run.run_metadata)
            snapshot = self._record_receipt(
                request["request_id"], run_id, proposal_id, normalized, request_hash, context
            )
        else:
            if existing.request_hash != request_hash:
                raise ProtocolValidationError(
                    "proposal_id is already bound to different request content",
                    code="IDEMPOTENCY_CONFLICT",
                )
            if existing.status is not ProposalStatus.PENDING:
                return self._proposal_result(existing)
            try:
                context = self._c_run_context(run.run_metadata)
            except ProtocolValidationError:
                return self._abandon_pending(
                    request["request_id"], existing, "c_run_identity_missing"
                )
            if existing.c_run_recovery_context != context:
                return self._abandon_pending(
                    request["request_id"], existing, "c_run_identity_mismatch"
                )
            snapshot = existing

        if snapshot.status is not ProposalStatus.PENDING:
            return self._proposal_result(snapshot)
        return self._finalize_placeholder(request["request_id"], snapshot)

    def _record_receipt(
        self,
        request_id: str,
        run_id: str,
        proposal_id: str,
        normalized: NormalizedMutationRequest,
        request_hash: str,
        context: CRunRecoveryContext | None,
    ) -> ProposalSnapshot:
        receipt = ProposalReceipt(
            metadata=self._metadata(run_id, request_id, "receipt"),
            proposal_id=proposal_id,
            request=normalized,
            c_run_recovery_context=context,
        )
        recorded = self._event_store.record_proposal(
            run_id, proposal_id, request_hash, normalized, receipt
        )
        if recorded.status is RecordProposalStatus.IDEMPOTENCY_CONFLICT:
            raise ProtocolValidationError(
                "proposal_id is already bound to different request content",
                code="IDEMPOTENCY_CONFLICT",
            )
        if recorded.status is RecordProposalStatus.NOT_FOUND:
            raise ProtocolValidationError("run does not exist", code="NOT_FOUND")
        if recorded.status is RecordProposalStatus.INVALID_PROPOSAL or recorded.proposal is None:
            raise ProtocolValidationError("EventStore rejected proposal receipt")
        return recorded.proposal

    def _finalize_placeholder(
        self, request_id: str, snapshot: ProposalSnapshot
    ) -> dict[str, Any]:
        expected = snapshot.normalized_request.expected_graph_version
        current = self._event_store.current_graph_version(snapshot.run_id)
        if isinstance(current, StoreError):
            self._raise_store_error(current)
        outcome = (
            GovernanceOutcome.CONFLICT
            if current != expected
            else GovernanceOutcome.REJECT
        )
        decision = MutationDecision(
            metadata=self._metadata(str(snapshot.run_id), request_id, "decision"),
            proposal_id=str(snapshot.proposal_id),
            request_hash=snapshot.request_hash,
            expected_graph_version=expected,
            resulting_graph_version=current,
            outcome=outcome,
            reason_code=(
                "stale_graph_version"
                if outcome is GovernanceOutcome.CONFLICT
                else _PLACEHOLDER_REJECTION
            ),
        )
        appended = self._event_store.append_audit(
            str(snapshot.run_id), (decision,), str(snapshot.proposal_id)
        )
        if isinstance(appended, StoreError):
            self._raise_store_error(appended)
        finalized = self._event_store.get_proposal(
            str(snapshot.run_id), str(snapshot.proposal_id)
        )
        if isinstance(finalized, StoreError):
            self._raise_store_error(finalized)
        return self._proposal_result(finalized)

    def _abandon_pending(
        self, request_id: str, snapshot: ProposalSnapshot, reason_code: str
    ) -> dict[str, Any]:
        abandoned = ProposalAbandoned(
            metadata=self._metadata(str(snapshot.run_id), request_id, "abandoned"),
            proposal_id=str(snapshot.proposal_id),
            request_hash=snapshot.request_hash,
            reason_code=reason_code,
        )
        appended = self._event_store.append_audit(
            str(snapshot.run_id), (abandoned,), str(snapshot.proposal_id)
        )
        if isinstance(appended, StoreError):
            self._raise_store_error(appended)
        finalized = self._event_store.get_proposal(
            str(snapshot.run_id), str(snapshot.proposal_id)
        )
        if isinstance(finalized, StoreError):
            self._raise_store_error(finalized)
        return self._proposal_result(finalized)

    def _c_run_context(self, metadata: RunMetadata) -> CRunRecoveryContext | None:
        data = metadata.data.value
        if data.get("configuration") != "C":
            return None
        fields = (
            "manifest_hash",
            "effective_graph_intervention_identity",
            "effective_governance_policy_identity",
        )
        values = {name: data.get(name) for name in fields}
        if any(
            not isinstance(value, str)
            or not value.strip()
            or value.strip().casefold() == "none"
            for value in values.values()
        ):
            raise ProtocolValidationError(
                "C run metadata requires non-empty manifest and effective policy identities"
            )
        try:
            return CRunRecoveryContext(**values)
        except (TypeError, ValueError) as error:
            raise ProtocolValidationError(
                "C run metadata identities are invalid"
            ) from error

    def _require_run(self, run_id: str):
        run = self._event_store.get_run(run_id)
        if isinstance(run, StoreError):
            self._raise_store_error(run)
        return run

    @staticmethod
    def _run_result(run, *, created: bool) -> dict[str, Any]:
        return {
            "run_id": str(run.run_id),
            "run_metadata": run.run_metadata.to_value(),
            "metadata_hash": run.metadata_hash,
            "graph_version": run.graph_version,
            "last_journal_position": run.last_journal_position,
            "created": created,
        }

    @staticmethod
    def _proposal_result(snapshot: ProposalSnapshot) -> dict[str, Any]:
        terminal = snapshot.terminal_record
        reason_code = (
            terminal.reason_code
            if isinstance(terminal, (MutationDecision, ProposalAbandoned))
            else None
        )
        return {
            "run_id": str(snapshot.run_id),
            "proposal_id": str(snapshot.proposal_id),
            "status": snapshot.status.value,
            "request_hash": str(snapshot.request_hash),
            "reason_code": reason_code,
            "resulting_graph_version": snapshot.resulting_graph_version,
            "journal_position": snapshot.last_journal_position,
        }

    @staticmethod
    def _public_record(entry) -> dict[str, Any]:
        record = entry.record
        value: dict[str, Any] = {
            "journal_position": entry.journal_position,
            "record_type": "",
            "run_id": str(record.metadata.run_id),
        }
        if isinstance(record, ProposalReceipt):
            value.update(
                record_type="proposal_receipt",
                proposal_id=str(record.proposal_id),
                lifecycle_state="PENDING",
            )
        elif isinstance(record, NonTerminalAuditRecord):
            value["record_type"] = "non_terminal_audit"
            if record.proposal_id is not None:
                value["proposal_id"] = str(record.proposal_id)
        elif isinstance(record, MutationDecision):
            value.update(
                record_type="mutation_decision",
                proposal_id=str(record.proposal_id),
                outcome=record.outcome.value,
                graph_version=record.resulting_graph_version,
            )
            if record.reason_code is not None:
                value["reason_code"] = record.reason_code
        elif isinstance(record, ProposalAbandoned):
            value.update(
                record_type="proposal_abandoned",
                proposal_id=str(record.proposal_id),
                lifecycle_state="ABANDONED",
                reason_code=record.reason_code,
            )
        elif isinstance(record, GraphChangedEvent):
            value.update(
                record_type="graph_changed",
                proposal_id=str(record.proposal_id),
                graph_version=record.graph_version,
            )
        else:
            raise TypeError(f"unsupported journal record: {type(record).__name__}")
        return value

    @staticmethod
    def _metadata(run_id: str, request_id: str, kind: str) -> RecordMetadata:
        return RecordMetadata(
            run_id=run_id,
            record_id=f"{kind}-{uuid4().hex}",
            recorded_at=datetime.now(timezone.utc),
            correlation_id=request_id,
        )

    @staticmethod
    def _raise_store_error(error: StoreError) -> NoReturn:
        mapping: dict[StoreErrorCode, ErrorCode] = {
            StoreErrorCode.NOT_FOUND: "NOT_FOUND",
            StoreErrorCode.INVALID_LIMIT: "INVALID_LIMIT",
            StoreErrorCode.INVALID_REQUEST: "PROTOCOL_ERROR",
        }
        code = mapping.get(error.code)
        if code is None:
            raise RuntimeError(
                f"EventStore rejected a service-owned operation: {error.code.value}"
            )
        raise ProtocolValidationError(error.detail or error.code.value, code=code)

    def _observe(self, request: ProtocolRequest, response: ProtocolResponse) -> None:
        run_id = request["params"]["run_id"]
        attrs = {"operation": request["operation"]}
        if "error" in response:
            attrs["status"] = response["error"]["code"]
        else:
            attrs["status"] = "completed"
        proposal_id = request["params"].get("proposal_id")
        try:
            self._telemetry.emit(
                TelemetryObservation(
                    run_id=run_id,
                    event_type="protocol.request",
                    observed_at=datetime.now(timezone.utc),
                    attributes=JsonDocument.from_value(attrs),
                    proposal_id=proposal_id,
                )
            )
        except Exception:
            # Telemetry is optional and cannot invalidate a durable response.
            return
