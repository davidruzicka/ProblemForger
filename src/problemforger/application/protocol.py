"""Versioned, transport-neutral public command/query messages."""

from __future__ import annotations

import json
import math
from typing import Any, Literal, NotRequired, TypedDict, TypeAlias, cast

from problemforger.core.journal import (
    CURRENT_PROTOCOL_SCHEMA_VERSION,
    CURRENT_REQUEST_SCHEMA_VERSION,
    GovernanceOutcome,
    JsonDocument,
    ProposalStatus,
)


MAX_PROTOCOL_MESSAGE_BYTES = 4 * 1024 * 1024
MAX_PROTOCOL_PAGE_SIZE = 100
MAX_SAFE_JSON_INTEGER = (1 << 53) - 1
MAX_RUN_METADATA_BYTES = 1024 * 1024
MAX_NORMALIZED_REQUEST_BYTES = 1024 * 1024

Operation: TypeAlias = Literal[
    "create_run",
    "get_run",
    "get_graph",
    "propose_mutation",
    "get_proposal",
    "get_audit_timeline",
]
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ProtocolValidationError(ValueError):
    """A malformed, unsupported, or oversized protocol message."""

    def __init__(self, message: str, *, code: str = "PROTOCOL_ERROR") -> None:
        super().__init__(message)
        self.code = code


class RunMetadata(TypedDict):
    metadata_schema_version: Literal[1]
    data: JsonObject


class CreateRunParams(TypedDict):
    run_id: str
    run_metadata: RunMetadata


class GetRunParams(TypedDict):
    run_id: str


class GetGraphParams(TypedDict):
    run_id: str
    limit: int
    selection: NotRequired[JsonObject]
    after_cursor: NotRequired[str]


class ProposeMutationParams(TypedDict):
    run_id: str
    proposal_id: str
    request_schema_version: Literal[1]
    expected_graph_version: int
    operations: list[JsonObject]
    evidence: list[JsonObject]


class GetProposalParams(TypedDict):
    run_id: str
    proposal_id: str


class GetAuditTimelineParams(TypedDict):
    run_id: str
    limit: int
    after_journal_position: NotRequired[int]


class CreateRunRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["create_run"]
    params: CreateRunParams


class GetRunRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_run"]
    params: GetRunParams


class GetGraphRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_graph"]
    params: GetGraphParams


class ProposeMutationRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["propose_mutation"]
    params: ProposeMutationParams


class GetProposalRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_proposal"]
    params: GetProposalParams


class GetAuditTimelineRequest(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_audit_timeline"]
    params: GetAuditTimelineParams


ProtocolRequest: TypeAlias = (
    CreateRunRequest
    | GetRunRequest
    | GetGraphRequest
    | ProposeMutationRequest
    | GetProposalRequest
    | GetAuditTimelineRequest
)


class RunResult(TypedDict):
    run_id: str
    run_metadata: RunMetadata
    metadata_hash: str
    graph_version: int
    last_journal_position: int
    created: bool


class GraphResult(TypedDict):
    run_id: str
    graph_schema_version: int
    graph_version: int
    nodes: list[JsonObject]
    edges: list[JsonObject]
    next_cursor: str | None
    has_more: bool


class ProposalResult(TypedDict):
    run_id: str
    proposal_id: str
    status: Literal[
        "PENDING", "ABANDONED", "COMMIT", "REJECT", "RETRY", "ESCALATE", "CONFLICT"
    ]
    request_hash: str
    reason_code: str | None
    resulting_graph_version: int | None
    journal_position: int


class PublicAuditRecord(TypedDict):
    journal_position: int
    record_type: str
    run_id: str
    proposal_id: NotRequired[str]
    lifecycle_state: NotRequired[Literal["PENDING", "ABANDONED"]]
    outcome: NotRequired[Literal["COMMIT", "REJECT", "RETRY", "ESCALATE", "CONFLICT"]]
    reason_code: NotRequired[str]
    graph_version: NotRequired[int]


class AuditTimelineResult(TypedDict):
    run_id: str
    records: list[PublicAuditRecord]
    next_after_journal_position: int
    has_more: bool


class ProtocolError(TypedDict):
    code: Literal[
        "PROTOCOL_ERROR",
        "UNSUPPORTED_PROTOCOL_VERSION",
        "UNAUTHORIZED",
        "NOT_FOUND",
        "RUN_METADATA_CONFLICT",
        "IDEMPOTENCY_CONFLICT",
        "INVALID_LIMIT",
        "PAYLOAD_TOO_LARGE",
        "STORE_IN_USE",
    ]
    message: str


class CreateRunResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["create_run"]
    result: RunResult


class GetRunResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_run"]
    result: RunResult


class GetGraphResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_graph"]
    result: GraphResult


class ProposeMutationResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["propose_mutation"]
    result: ProposalResult


class GetProposalResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_proposal"]
    result: ProposalResult


class GetAuditTimelineResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str
    operation: Literal["get_audit_timeline"]
    result: AuditTimelineResult


class ErrorResponse(TypedDict):
    protocol_schema_version: Literal[1]
    request_id: str | None
    error: ProtocolError


SuccessResponse: TypeAlias = (
    CreateRunResponse
    | GetRunResponse
    | GetGraphResponse
    | ProposeMutationResponse
    | GetProposalResponse
    | GetAuditTimelineResponse
)
ProtocolResponse: TypeAlias = SuccessResponse | ErrorResponse

_OPERATIONS = frozenset(
    {"create_run", "get_run", "get_graph", "propose_mutation", "get_proposal", "get_audit_timeline"}
)
_OUTCOMES = frozenset(outcome.value for outcome in GovernanceOutcome)
_STATUSES = _OUTCOMES | frozenset(status.value for status in ProposalStatus)
_ERROR_CODES = frozenset(
    {
        "PROTOCOL_ERROR",
        "UNSUPPORTED_PROTOCOL_VERSION",
        "UNAUTHORIZED",
        "NOT_FOUND",
        "RUN_METADATA_CONFLICT",
        "IDEMPOTENCY_CONFLICT",
        "INVALID_LIMIT",
        "PAYLOAD_TOO_LARGE",
        "STORE_IN_USE",
    }
)
_HASH_PREFIXES = {
    "metadata_hash": "sha256:problemforger-run-metadata-v1:",
    "request_hash": "sha256:problemforger-request-v1:",
}


def _object(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ProtocolValidationError(f"{name} must be a JSON object")
    return value


def _json_tree(value: Any, name: str) -> None:
    try:
        JsonDocument.from_value(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise ProtocolValidationError(f"{name} must contain only JSON values") from error

    def check_numbers(item: Any) -> None:
        if type(item) is int and abs(item) > MAX_SAFE_JSON_INTEGER:
            raise ProtocolValidationError("JSON integers must be safe integers")
        if type(item) is float and item.is_integer() and abs(item) > MAX_SAFE_JSON_INTEGER:
            raise ProtocolValidationError("JSON integers must be safe integers")
        if type(item) is list:
            for child in item:
                check_numbers(child)
        elif type(item) is dict:
            for child in item.values():
                check_numbers(child)

    check_numbers(value)


def _fields(
    value: dict[str, Any], required: set[str], optional: set[str] = frozenset(), name: str = "object"
) -> None:
    actual = set(value)
    missing = required - actual
    unknown = actual - required - optional
    if missing or unknown:
        raise ProtocolValidationError(
            f"{name} fields do not match protocol schema (missing={sorted(missing)}, unknown={sorted(unknown)})"
        )


def _identifier(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolValidationError(f"{name} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProtocolValidationError(f"{name} must be valid UTF-8") from error


def _integer(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_SAFE_JSON_INTEGER,
    error_code: str = "PROTOCOL_ERROR",
) -> None:
    integer_value = value
    if type(value) is float and value.is_integer():
        integer_value = int(value)
    if type(integer_value) is not int or not minimum <= integer_value <= maximum:
        raise ProtocolValidationError(
            f"{name} must be a JSON safe integer from {minimum} through {maximum}",
            code=error_code,
        )


def _boolean(value: Any, name: str) -> None:
    if type(value) is not bool:
        raise ProtocolValidationError(f"{name} must be a boolean")


def _ecmascript_number(value: float) -> str:
    """Return the compact ECMAScript JSON spelling for a finite Python float."""
    if not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if value == 0:
        return "0"

    number = repr(abs(value)).lower()
    if "e" in number:
        coefficient, exponent_text = number.split("e", 1)
        exponent = int(exponent_text)
    else:
        coefficient = number
        exponent = 0
    integer_part, _, fractional_part = coefficient.partition(".")
    digits = integer_part + fractional_part
    leading_zeroes = len(digits) - len(digits.lstrip("0"))
    digits = digits[leading_zeroes:].rstrip("0")
    decimal_position = len(integer_part) + exponent - leading_zeroes

    if decimal_position > 0 and decimal_position <= 21:
        if decimal_position >= len(digits):
            rendered = digits + ("0" * (decimal_position - len(digits)))
        else:
            rendered = f"{digits[:decimal_position]}.{digits[decimal_position:]}"
    elif decimal_position <= 0 and decimal_position > -6:
        rendered = f"0.{('0' * -decimal_position)}{digits}"
    else:
        scientific_exponent = decimal_position - 1
        mantissa = digits[0] + (f".{digits[1:]}" if len(digits) > 1 else "")
        exponent_sign = "+" if scientific_exponent >= 0 else ""
        rendered = f"{mantissa}e{exponent_sign}{scientific_exponent}"

    return f"-{rendered}" if value < 0 else rendered


def _protocol_json_size(value: Any) -> int:
    """Count compact UTF-8 JSON bytes using the TypeScript codec's number form."""
    if value is None:
        return 4
    if type(value) is bool:
        return 4 if value else 5
    if isinstance(value, str):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if type(value) is int:
        return len(str(value))
    if type(value) is float:
        return len(_ecmascript_number(value))
    if type(value) is list:
        return 2 + max(len(value) - 1, 0) + sum(_protocol_json_size(item) for item in value)
    if type(value) is dict:
        return (
            2
            + max(len(value) - 1, 0)
            + sum(
                _protocol_json_size(key) + 1 + _protocol_json_size(item)
                for key, item in value.items()
            )
        )
    raise TypeError("value is not JSON serializable")


def _metadata(value: Any) -> dict[str, Any]:
    metadata = _object(value, "run_metadata")
    _fields(metadata, {"metadata_schema_version", "data"}, name="run_metadata")
    _integer(metadata["metadata_schema_version"], "metadata_schema_version", minimum=1)
    if metadata["metadata_schema_version"] != 1:
        raise ProtocolValidationError("unsupported metadata_schema_version", code="PROTOCOL_ERROR")
    _object(metadata["data"], "run_metadata.data")
    if _protocol_json_size(metadata) > MAX_RUN_METADATA_BYTES:
        raise ProtocolValidationError("run_metadata exceeds 1 MiB", code="PAYLOAD_TOO_LARGE")
    return metadata


def _hash(value: Any, name: str) -> None:
    _identifier(value, name)
    prefix = _HASH_PREFIXES[name]
    digest = value[len(prefix) :] if value.startswith(prefix) else ""
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ProtocolValidationError(f"{name} must use its versioned SHA-256 format")


def validate_request(value: Any) -> ProtocolRequest:
    """Validate a decoded request's closed v1 shape and bounded scalar fields."""
    request = _object(value, "request")
    _json_tree(request, "request")
    _fields(
        request,
        {"protocol_schema_version", "request_id", "operation", "params"},
        name="request",
    )
    _integer(request["protocol_schema_version"], "protocol_schema_version", minimum=1)
    if request["protocol_schema_version"] != CURRENT_PROTOCOL_SCHEMA_VERSION:
        raise ProtocolValidationError(
            "unsupported protocol_schema_version", code="UNSUPPORTED_PROTOCOL_VERSION"
        )
    _identifier(request["request_id"], "request_id")
    operation = request["operation"]
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise ProtocolValidationError(f"unknown operation: {operation!r}")
    params = _object(request["params"], "params")

    if operation == "create_run":
        _fields(params, {"run_id", "run_metadata"}, name="create_run params")
        _identifier(params["run_id"], "run_id")
        _metadata(params["run_metadata"])
    elif operation == "get_run":
        _fields(params, {"run_id"}, name="get_run params")
        _identifier(params["run_id"], "run_id")
    elif operation == "get_graph":
        _fields(
            params,
            {"run_id", "limit"},
            {"selection", "after_cursor"},
            "get_graph params",
        )
        _identifier(params["run_id"], "run_id")
        _integer(params["limit"], "limit", minimum=1, maximum=MAX_PROTOCOL_PAGE_SIZE)
        if "selection" in params:
            _object(params["selection"], "selection")
        if "after_cursor" in params:
            _identifier(params["after_cursor"], "after_cursor")
    elif operation == "propose_mutation":
        _fields(
            params,
            {
                "run_id",
                "proposal_id",
                "request_schema_version",
                "expected_graph_version",
                "operations",
                "evidence",
            },
            name="propose_mutation params",
        )
        _identifier(params["run_id"], "run_id")
        _identifier(params["proposal_id"], "proposal_id")
        _integer(params["request_schema_version"], "request_schema_version", minimum=1)
        _integer(params["expected_graph_version"], "expected_graph_version")
        if params["request_schema_version"] != CURRENT_REQUEST_SCHEMA_VERSION:
            raise ProtocolValidationError("unsupported request_schema_version")
        operations = params["operations"]
        evidence = params["evidence"]
        if type(operations) is not list or type(evidence) is not list:
            raise ProtocolValidationError("operations and evidence must be arrays")
        if any(type(item) is not dict for item in (*operations, *evidence)):
            raise ProtocolValidationError("each operation and evidence item must be a JSON object")
        normalized_value = {
            "request_schema_version": params["request_schema_version"],
            "expected_graph_version": params["expected_graph_version"],
            "operations": operations,
            "evidence": evidence,
        }
        if _protocol_json_size(normalized_value) > MAX_NORMALIZED_REQUEST_BYTES:
            raise ProtocolValidationError("normalized mutation request exceeds 1 MiB", code="PAYLOAD_TOO_LARGE")
    elif operation == "get_proposal":
        _fields(params, {"run_id", "proposal_id"}, name="get_proposal params")
        _identifier(params["run_id"], "run_id")
        _identifier(params["proposal_id"], "proposal_id")
    else:
        if "limit" not in params:
            raise ProtocolValidationError(
                "get_audit_timeline requires limit", code="INVALID_LIMIT"
            )
        _integer(
            params["limit"],
            "limit",
            minimum=1,
            maximum=MAX_PROTOCOL_PAGE_SIZE,
            error_code="INVALID_LIMIT",
        )
        _fields(
            params,
            {"run_id", "limit"},
            {"after_journal_position"},
            "get_audit_timeline params",
        )
        _identifier(params["run_id"], "run_id")
        if "after_journal_position" in params:
            _integer(params["after_journal_position"], "after_journal_position")

    return cast(ProtocolRequest, request)


def _validate_run_result(value: Any, name: str) -> None:
    result = _object(value, name)
    _fields(
        result,
        {"run_id", "run_metadata", "metadata_hash", "graph_version", "last_journal_position", "created"},
        name=name,
    )
    _identifier(result["run_id"], "run_id")
    _metadata(result["run_metadata"])
    _hash(result["metadata_hash"], "metadata_hash")
    _integer(result["graph_version"], "graph_version")
    _integer(result["last_journal_position"], "last_journal_position")
    _boolean(result["created"], "created")


def _validate_graph_result(value: Any, limit: int | None = None) -> None:
    result = _object(value, "get_graph result")
    _fields(
        result,
        {"run_id", "graph_schema_version", "graph_version", "nodes", "edges", "next_cursor", "has_more"},
        name="get_graph result",
    )
    _identifier(result["run_id"], "run_id")
    _integer(result["graph_schema_version"], "graph_schema_version", minimum=1)
    _integer(result["graph_version"], "graph_version")
    if type(result["nodes"]) is not list or type(result["edges"]) is not list:
        raise ProtocolValidationError("nodes and edges must be arrays")
    record_count = len(result["nodes"]) + len(result["edges"])
    if record_count > MAX_PROTOCOL_PAGE_SIZE:
        raise ProtocolValidationError("graph result exceeds the 100-record page limit", code="INVALID_LIMIT")
    if limit is not None and record_count > limit:
        raise ProtocolValidationError("graph result exceeds the requested limit", code="INVALID_LIMIT")
    for node in result["nodes"]:
        _object(node, "graph node")
    for edge in result["edges"]:
        _object(edge, "graph edge")
    cursor = result["next_cursor"]
    if cursor is not None:
        _identifier(cursor, "next_cursor")
    _boolean(result["has_more"], "has_more")
    if result["has_more"] and cursor is None:
        raise ProtocolValidationError("graph continuation requires next_cursor")


def _validate_proposal_result(value: Any) -> None:
    result = _object(value, "proposal result")
    _fields(
        result,
        {
            "run_id",
            "proposal_id",
            "status",
            "request_hash",
            "reason_code",
            "resulting_graph_version",
            "journal_position",
        },
        name="proposal result",
    )
    _identifier(result["run_id"], "run_id")
    _identifier(result["proposal_id"], "proposal_id")
    status = result["status"]
    if not isinstance(status, str) or status not in _STATUSES:
        raise ProtocolValidationError("unsupported proposal status")
    _hash(result["request_hash"], "request_hash")
    reason = result["reason_code"]
    resulting_version = result["resulting_graph_version"]
    _integer(result["journal_position"], "journal_position", minimum=1)
    if reason is not None:
        _identifier(reason, "reason_code")
    if resulting_version is not None:
        _integer(resulting_version, "resulting_graph_version")
    if status == ProposalStatus.PENDING.value:
        if reason is not None or resulting_version is not None:
            raise ProtocolValidationError("PENDING cannot contain terminal outcome fields")
    elif status == ProposalStatus.ABANDONED.value:
        if reason is None or resulting_version is not None:
            raise ProtocolValidationError("ABANDONED requires a reason and no graph version")
    elif status == GovernanceOutcome.COMMIT.value:
        if reason is not None or resulting_version is None:
            raise ProtocolValidationError("COMMIT requires a graph version and no reason")
    elif reason is None or resulting_version is None:
        raise ProtocolValidationError("non-COMMIT terminal outcomes require a reason and graph version")


def _validate_audit_record(value: Any, expected_run_id: str, previous_position: int) -> int:
    record = _object(value, "audit record")
    _fields(
        record,
        {"journal_position", "record_type", "run_id"},
        {"proposal_id", "lifecycle_state", "outcome", "reason_code", "graph_version"},
        "audit record",
    )
    position = record["journal_position"]
    _integer(position, "journal_position", minimum=1)
    if position <= previous_position:
        raise ProtocolValidationError("audit records must be ordered by journal_position")
    _identifier(record["record_type"], "record_type")
    _identifier(record["run_id"], "run_id")
    if record["run_id"] != expected_run_id:
        raise ProtocolValidationError("audit record run_id does not match response run_id")
    if "proposal_id" in record:
        _identifier(record["proposal_id"], "proposal_id")
    if "lifecycle_state" in record:
        lifecycle_state = record["lifecycle_state"]
        if not isinstance(lifecycle_state, str) or lifecycle_state not in {
            ProposalStatus.PENDING.value,
            ProposalStatus.ABANDONED.value,
        }:
            raise ProtocolValidationError("unsupported audit lifecycle_state")
    if "outcome" in record:
        outcome = record["outcome"]
        if not isinstance(outcome, str) or outcome not in _OUTCOMES:
            raise ProtocolValidationError("unsupported audit outcome")
    if "reason_code" in record:
        _identifier(record["reason_code"], "reason_code")
    if "graph_version" in record:
        _integer(record["graph_version"], "graph_version")
    return position


def _validate_audit_result(
    value: Any, after_journal_position: int | None = None, limit: int | None = None
) -> None:
    result = _object(value, "audit timeline result")
    _fields(
        result,
        {"run_id", "records", "next_after_journal_position", "has_more"},
        name="audit timeline result",
    )
    _identifier(result["run_id"], "run_id")
    records = result["records"]
    if type(records) is not list or len(records) > MAX_PROTOCOL_PAGE_SIZE:
        raise ProtocolValidationError("audit records must fit the 100-record page limit", code="INVALID_LIMIT")
    if limit is not None and len(records) > limit:
        raise ProtocolValidationError("audit records exceed the requested limit", code="INVALID_LIMIT")
    if after_journal_position is not None:
        _integer(after_journal_position, "after_journal_position")
    previous_position = after_journal_position or 0
    for record in records:
        previous_position = _validate_audit_record(record, result["run_id"], previous_position)
    next_position = result["next_after_journal_position"]
    _integer(next_position, "next_after_journal_position")
    _boolean(result["has_more"], "has_more")
    if records:
        if next_position != previous_position:
            raise ProtocolValidationError(
                "next_after_journal_position must equal the last returned record"
            )
    else:
        if after_journal_position is None:
            raise ProtocolValidationError(
                "validating an empty audit page requires its request cursor"
            )
        expected_position = after_journal_position
        if next_position != expected_position:
            raise ProtocolValidationError(
                "empty audit page must preserve its supplied cursor"
            )
        if result["has_more"]:
            raise ProtocolValidationError("empty audit page cannot have more records")


def validate_response(
    value: Any, request: ProtocolRequest | None = None
) -> ProtocolResponse:
    """Validate success/error envelopes and the public operation result shape."""
    response = _object(value, "response")
    _json_tree(response, "response")
    after_journal_position = None
    requested_limit = None
    if request is not None:
        validate_request(request)
        if response.get("request_id") != request["request_id"]:
            raise ProtocolValidationError("response request_id does not match request")
        if "error" not in response:
            if response.get("operation") != request["operation"]:
                raise ProtocolValidationError("response operation does not match request")
            params = _object(request["params"], "request params")
            result = _object(response.get("result"), "response result")
            if result.get("run_id") != params["run_id"]:
                raise ProtocolValidationError("response run_id does not match request")
            if "proposal_id" in params and result.get("proposal_id") != params["proposal_id"]:
                raise ProtocolValidationError("response proposal_id does not match request")
            if request["operation"] == "get_audit_timeline":
                after_journal_position = params.get("after_journal_position", 0)
                requested_limit = params["limit"]
            elif request["operation"] == "get_graph":
                requested_limit = params["limit"]
    _integer(response.get("protocol_schema_version"), "protocol_schema_version", minimum=1)
    if response["protocol_schema_version"] != CURRENT_PROTOCOL_SCHEMA_VERSION:
        raise ProtocolValidationError(
            "unsupported protocol_schema_version", code="UNSUPPORTED_PROTOCOL_VERSION"
        )
    if "error" in response:
        _fields(response, {"protocol_schema_version", "request_id", "error"}, name="error response")
        request_id = response["request_id"]
        error = _object(response["error"], "error")
        _fields(error, {"code", "message"}, name="error")
        if not isinstance(error["code"], str) or error["code"] not in _ERROR_CODES:
            raise ProtocolValidationError("unsupported protocol error code")
        if request_id is not None:
            _identifier(request_id, "request_id")
        elif error["code"] not in {
            "PROTOCOL_ERROR",
            "UNSUPPORTED_PROTOCOL_VERSION",
            "PAYLOAD_TOO_LARGE",
            "STORE_IN_USE",
        }:
            raise ProtocolValidationError("this error requires a request_id")
        if error["code"] == "STORE_IN_USE" and request_id is not None:
            raise ProtocolValidationError("STORE_IN_USE is a startup error and has no request_id")
        _identifier(error["message"], "error.message")
        return cast(ProtocolResponse, response)

    _fields(response, {"protocol_schema_version", "request_id", "operation", "result"}, name="success response")
    _identifier(response["request_id"], "request_id")
    operation = response["operation"]
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise ProtocolValidationError("unknown response operation")
    result = response["result"]
    if operation in {"create_run", "get_run"}:
        _validate_run_result(result, f"{operation} result")
    elif operation == "get_graph":
        _validate_graph_result(result, requested_limit)
    elif operation in {"propose_mutation", "get_proposal"}:
        _validate_proposal_result(result)
    else:
        _validate_audit_result(result, after_journal_position, requested_limit)
    return cast(ProtocolResponse, response)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ProtocolValidationError(f"non-finite JSON number is forbidden: {value}")


def _parse_protocol_float(value: str) -> float | int:
    number = float(value)
    if number.is_integer() and abs(number) <= MAX_SAFE_JSON_INTEGER:
        return int(number)
    return number


def _encode(value: Any, validator: Any) -> bytes:
    validator(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
        raise ProtocolValidationError("message is not valid UTF-8 JSON") from error
    if len(encoded) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ProtocolValidationError("message exceeds 4 MiB", code="PAYLOAD_TOO_LARGE")
    return encoded


def _decode(payload: str | bytes, validator: Any) -> Any:
    if isinstance(payload, bytes):
        encoded = payload
    elif isinstance(payload, str):
        try:
            encoded = payload.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ProtocolValidationError("message is not valid UTF-8") from error
    else:
        raise ProtocolValidationError("message must be str or bytes")
    if len(encoded) > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ProtocolValidationError("message exceeds 4 MiB", code="PAYLOAD_TOO_LARGE")
    try:
        value = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
            parse_float=_parse_protocol_float,
        )
    except ProtocolValidationError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ProtocolValidationError("message is not valid UTF-8 JSON") from error
    return validator(value)


def encode_request(value: ProtocolRequest) -> bytes:
    """Validate and serialize one v1 request as compact UTF-8 JSON."""
    return _encode(value, validate_request)


def decode_request(payload: str | bytes) -> ProtocolRequest:
    """Decode one v1 request, rejecting duplicate keys and invalid JSON."""
    return cast(ProtocolRequest, _decode(payload, validate_request))


def encode_response(
    value: ProtocolResponse, request: ProtocolRequest | None = None
) -> bytes:
    """Validate and serialize one v1 response as compact UTF-8 JSON."""
    return _encode(value, lambda response: validate_response(response, request))


def decode_response(
    payload: str | bytes, request: ProtocolRequest | None = None
) -> ProtocolResponse:
    """Decode a response; pass its request to validate an empty audit page cursor."""
    return cast(
        ProtocolResponse,
        _decode(payload, lambda response: validate_response(response, request)),
    )
