"""Provider-neutral run graph commands and bounded public queries."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4
from typing import Any, Callable, NoReturn

from problemforger.application._graph_contract import CONTRACT as GRAPH_CONTRACT
from problemforger.application.graph import GraphReplayError, query_graph, replay_graph, validate_candidate

from problemforger.application._protocol_contract import ErrorCode
from problemforger.application.protocol import (
    ProtocolRequest,
    ProtocolResponse,
    ProtocolValidationError,
    validate_request,
    validate_response,
    _validate_shape,
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
    VersionConflict,
    journal_batch_within_bounds,
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


class ProtocolApplication:
    """Apply structural graph invariants; C evidence policy remains P3 work."""

    def __init__(self, event_store: EventStore, telemetry: TelemetrySink, *,
                 authorize_run: Callable[[str, str], bool] | None = None) -> None:
        self._event_store = event_store
        self._telemetry = telemetry
        self._authorize_run = authorize_run if authorize_run is not None else lambda operation, run_id: True

    def handle(self, value: object) -> ProtocolResponse:
        """Validate, handle, and validate one request/response pair."""
        request = validate_request(value)
        try:
            if not self._authorize_run(request['operation'], request['params']['run_id']):
                raise ProtocolValidationError('run access denied', code='UNAUTHORIZED')
            result = self._dispatch(request)
            response: ProtocolResponse = {
                "protocol_schema_version": 1,
                "request_id": request["request_id"],
                "operation": request["operation"],
                "result": result,
            }
            validate_response(response, request)
        except GraphReplayError:
            response = {
                'protocol_schema_version': 1, 'request_id': request['request_id'],
                'error': {'code': 'PROTOCOL_ERROR', 'message': 'committed graph cannot be reconstructed'},
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
            self._require_run(params['run_id'])
            return query_graph(replay_graph(self._event_store, params['run_id']), params, request_id=request['request_id'])
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
        return self._finalize_mutation(request["request_id"], snapshot)

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

    def _finalize_mutation(
        self, request_id: str, snapshot: ProposalSnapshot, *, bootstrap: bool = False
    ) -> dict[str, Any]:
        expected = snapshot.normalized_request.expected_graph_version
        current = self._event_store.current_graph_version(snapshot.run_id)
        if isinstance(current, StoreError):
            self._raise_store_error(current)
        outcome = GovernanceOutcome.REJECT
        reason = _PLACEHOLDER_REJECTION
        events = ()
        if current != expected:
            outcome, reason = GovernanceOutcome.CONFLICT, 'stale_graph_version'
        elif snapshot.c_run_recovery_context is None:
            projection = replay_graph(self._event_store, str(snapshot.run_id))
            try:
                prepared = []
                for operation in snapshot.normalized_request.operations:
                    value = operation.value
                    _validate_shape(value, 'Operation', 'graph operation', GRAPH_CONTRACT)
                    prepared.append(GraphChangedEvent(
                        self._metadata(str(snapshot.run_id), request_id, 'event'),
                        str(snapshot.proposal_id), current + 1,
                        GRAPH_CONTRACT['x-operations'][value['op']]['event_type'], 1,
                        JsonDocument.from_value({k: v for k, v in value.items() if k not in ('op', 'graph_schema_version')}),
                    ))
                events = tuple(prepared)
                validate_candidate(projection, events, worker=not bootstrap)
            except (ProtocolValidationError, GraphReplayError):
                reason = 'invalid_graph_mutation'
            else:
                outcome, reason = GovernanceOutcome.COMMIT, None
        decision = MutationDecision(
            metadata=self._metadata(str(snapshot.run_id), request_id, "decision"),
            proposal_id=str(snapshot.proposal_id),
            request_hash=snapshot.request_hash,
            expected_graph_version=expected,
            resulting_graph_version=current + 1 if outcome is GovernanceOutcome.COMMIT else current,
            outcome=outcome,
            reason_code=reason,
        )
        if outcome is GovernanceOutcome.COMMIT:
            run = self._require_run(str(snapshot.run_id))
            if not journal_batch_within_bounds((decision, *events), first_position=run.last_journal_position + 1):
                outcome = GovernanceOutcome.REJECT
                decision = replace(decision, outcome=outcome, resulting_graph_version=current,
                                   reason_code='graph_batch_too_large')
        if outcome is GovernanceOutcome.COMMIT:
            appended = self._event_store.append_graph(str(snapshot.run_id), str(snapshot.proposal_id), expected, (decision,), events)
            if isinstance(appended, VersionConflict):
                return self._finalize_mutation(request_id, snapshot, bootstrap=bootstrap)
        else:
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

    def bootstrap_root(self, run_id: str, proposal_id: str, label: str) -> dict[str, Any]:
        """Trusted service-owner setup, never dispatched on the worker socket."""
        run = self._require_run(run_id)
        if self._c_run_context(run.run_metadata) is not None:
            raise ValueError('C bootstrap requires the P3 policy')
        normalized = NormalizedMutationRequest(1, 0, (JsonDocument.from_value({
            'graph_schema_version': 1, 'op': 'create_node',
            'node': {'node_id': 'root', 'kind': 'RootGoal', 'label': label, 'protected': True},
        }),), ())
        _validate_shape(normalized.operations[0].value, 'Operation', 'root', GRAPH_CONTRACT)
        existing = self._event_store.get_proposal(run_id, proposal_id)
        if not isinstance(existing, StoreError):
            if existing.request_hash != proposal_request_hash(normalized):
                raise ProtocolValidationError('bootstrap proposal content differs', code='IDEMPOTENCY_CONFLICT')
            if existing.status is not ProposalStatus.PENDING:
                return self._proposal_result(existing)
        elif existing.code is not StoreErrorCode.NOT_FOUND:
            self._raise_store_error(existing)
        if run.graph_version != 0:
            raise ValueError('bootstrap requires an empty graph')
        snapshot = self._record_receipt('bootstrap', run_id, proposal_id, normalized, proposal_request_hash(normalized), None)
        if snapshot.status is not ProposalStatus.PENDING:
            return self._proposal_result(snapshot)
        return self._finalize_mutation('bootstrap', snapshot, bootstrap=True)

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
            "resulting_graph_version": snapshot.resulting_graph_version if isinstance(terminal, MutationDecision) else None,
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
