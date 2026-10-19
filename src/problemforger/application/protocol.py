"""Versioned, transport-neutral public command/query messages."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, NotRequired, TypedDict, TypeAlias, cast

from problemforger.application._protocol_contract import (
    CONTRACT, AuditLifecycleState, AuditOutcome, AuditRecordType, ErrorCode, Operation, ProposalState,
)
from problemforger.core.journal import (
    CURRENT_PROTOCOL_SCHEMA_VERSION,
    CURRENT_REQUEST_SCHEMA_VERSION,
    JsonDocument,
    canonical_json_with_safe_integer_normalization,
    ecmascript_json_number,
    ecmascript_json_size,
    validate_json_safe_integers,
)
from problemforger.ports.event_store import RunMetadata as StoreRunMetadata


MAX_PROTOCOL_MESSAGE_BYTES = CONTRACT["x-frame-max-bytes"]
MAX_PROTOCOL_PAGE_SIZE = CONTRACT["x-page-max-records"]
MAX_SAFE_JSON_INTEGER = CONTRACT["$defs"]["SafeInteger"]["maximum"]
MAX_RUN_METADATA_BYTES = CONTRACT["$defs"]["RunMetadata"]["x-max-canonical-bytes"]
MAX_NORMALIZED_REQUEST_BYTES = CONTRACT["$defs"]["ProposeMutationParams"]["x-max-canonical-bytes"]

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
    status: ProposalState
    request_hash: str
    reason_code: str | None
    resulting_graph_version: int | None
    journal_position: int


class PublicAuditRecord(TypedDict):
    journal_position: int
    record_type: AuditRecordType
    run_id: str
    proposal_id: NotRequired[str]
    lifecycle_state: NotRequired[AuditLifecycleState]
    outcome: NotRequired[AuditOutcome]
    reason_code: NotRequired[str]
    graph_version: NotRequired[int]


class AuditTimelineResult(TypedDict):
    run_id: str
    records: list[PublicAuditRecord]
    next_after_journal_position: int
    has_more: bool


class ProtocolError(TypedDict):
    code: ErrorCode
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

def _object(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ProtocolValidationError(f"{name} must be a JSON object")
    return value


def _json_tree(value: Any, name: str) -> None:
    try:
        JsonDocument.from_value(value)
    except (TypeError, ValueError, RecursionError) as error:
        raise ProtocolValidationError(f"{name} must contain only JSON values") from error

    try:
        validate_json_safe_integers(value)
    except ValueError as error:
        raise ProtocolValidationError(str(error)) from error


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


def _validate_shape(value: Any, schema: str | dict[str, Any], name: str) -> None:
    """Evaluate only the schema keywords used by the embedded v1 contract."""
    if isinstance(schema, str):
        schema = CONTRACT["$defs"][schema]
    if "$ref" in schema:
        target = CONTRACT["$defs"][schema["$ref"].removeprefix("#/$defs/")]
        schema = {**target, **{key: item for key, item in schema.items() if key != "$ref"}}
    code = schema.get("x-error-code", "PROTOCOL_ERROR")
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if kind is not None:
        if value is None and "null" in kinds:
            pass
        elif "integer" in kinds and type(value) in (int, float):
            _integer(
                value, name, minimum=schema.get("minimum", 0),
                maximum=schema.get("maximum", MAX_SAFE_JSON_INTEGER), error_code=code,
            )
        elif not any(
            (item == "object" and type(value) is dict)
            or (item == "array" and type(value) is list)
            or (item == "string" and type(value) is str)
            or (item == "boolean" and type(value) is bool)
            for item in kinds
        ):
            raise ProtocolValidationError(f"{name} must have type {kind}", code=code)
    if "const" in schema and _canonical_json_value(value) != _canonical_json_value(schema["const"]):
        raise ProtocolValidationError(
            f"{name} has an unsupported value", code=schema.get("x-const-error-code", code)
        )
    if "enum" in schema and value not in schema["enum"]:
        raise ProtocolValidationError(f"{name} has an unsupported value", code=code)
    if type(value) is str and "pattern" in schema and re.search(schema["pattern"], value) is None:
        raise ProtocolValidationError(f"{name} does not match its string format", code=code)
    if type(value) is str and "x-max-utf8-bytes" in schema:
        maximum = schema["x-max-utf8-bytes"]
        if len(value.encode("utf-8")) > maximum:
            raise ProtocolValidationError(f"{name} exceeds {maximum} UTF-8 bytes", code=code)
    if type(value) is dict:
        properties = schema.get("properties", {})
        for field in schema.get("required", []):
            if field not in value:
                raise ProtocolValidationError(
                    f"{name} requires {field}", code=properties[field].get("x-error-code", code)
                )
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            raise ProtocolValidationError(f"{name} contains unknown fields", code=code)
        for field, rule in properties.items():
            if field in value:
                _validate_shape(value[field], rule, f"{name}.{field}")
    if type(value) is list:
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ProtocolValidationError(f"{name} exceeds its record limit", code=code)
        if "items" in schema:
            for item in value:
                _validate_shape(item, schema["items"], f"{name} item")
    for rule in schema.get("allOf", []):
        _validate_shape(value, rule, name)
    if "oneOf" in schema:
        matches = 0
        for rule in schema["oneOf"]:
            try:
                _validate_shape(value, rule, name)
            except ProtocolValidationError:
                continue
            matches += 1
        if matches != 1:
            raise ProtocolValidationError(f"{name} does not match exactly one allowed shape", code=code)
    if "if" in schema:
        try:
            _validate_shape(value, schema["if"], name)
        except ProtocolValidationError:
            pass
        else:
            _validate_shape(value, schema["then"], name)
    if "x-max-canonical-bytes" in schema:
        sized = (
            {field: value[field] for field in schema["x-size-fields"]}
            if "x-size-fields" in schema else value
        )
        canonicalization = schema.get("x-size-canonicalization", "ecmascript-json-v1")
        if canonicalization == "run-metadata-json-v2":
            encoded_size = len(
                canonical_json_with_safe_integer_normalization(sized).encode("utf-8")
            )
        elif canonicalization == "ecmascript-json-v1":
            encoded_size = ecmascript_json_size(sized)
        else:  # pragma: no cover - generated contract validation prevents this
            raise RuntimeError(f"unsupported size canonicalization: {canonicalization}")
        if encoded_size > schema["x-max-canonical-bytes"]:
            raise ProtocolValidationError(f"{name} exceeds 1 MiB", code="PAYLOAD_TOO_LARGE")
    if "x-version-position" in schema:
        version_field, position_field = schema["x-version-position"]
        version = value.get(version_field)
        if version is not None and version > value[position_field]:
            raise ProtocolValidationError(f"{name}.{version_field} cannot exceed {position_field}")


def _canonical_json_value(value: Any) -> Any:
    """Build a type-safe, key-order-independent comparison form for JSON values."""
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is str:
        return ("string", value)
    if type(value) is int:
        return ("number", str(value))
    if type(value) is float:
        return ("number", ecmascript_json_number(value))
    if type(value) is list:
        return ("array", tuple(_canonical_json_value(item) for item in value))
    if type(value) is dict:
        return (
            "object",
            tuple((key, _canonical_json_value(value[key])) for key in sorted(value)),
        )
    raise TypeError("value is not JSON serializable")


def _run_metadata_hash(run_metadata: dict[str, Any]) -> str:
    return StoreRunMetadata(JsonDocument.from_value(run_metadata["data"])).metadata_hash


def validate_request(value: Any) -> ProtocolRequest:
    """Validate a request against the shared closed v1 contract."""
    _json_tree(value, "request")
    _validate_shape(value, "Request", "request")
    _validate_shape(value["params"], CONTRACT["x-operations"][value["operation"]]["params"], "params")
    return cast(ProtocolRequest, value)


def _validate_graph_result(result: dict[str, Any], limit: int | None) -> None:
    record_count = len(result["nodes"]) + len(result["edges"])
    if record_count > MAX_PROTOCOL_PAGE_SIZE:
        raise ProtocolValidationError("graph result exceeds the 100-record page limit", code="INVALID_LIMIT")
    if limit is not None and record_count > limit:
        raise ProtocolValidationError("graph result exceeds the requested limit", code="INVALID_LIMIT")


def _validate_proposal_result(result: dict[str, Any], expected_graph_version: int | None) -> None:
    resulting_version = result["resulting_graph_version"]
    if expected_graph_version is None or resulting_version is None:
        return
    effect = CONTRACT["x-proposal-states"][result["status"]]["graph_effect"]
    if effect == "advance" and resulting_version != expected_graph_version + 1:
        raise ProtocolValidationError("COMMIT must advance graph_version exactly once")
    if effect == "preserve" and resulting_version != expected_graph_version:
        raise ProtocolValidationError("non-commit outcomes must preserve expected_graph_version")
    if effect == "differ" and resulting_version == expected_graph_version:
        raise ProtocolValidationError("CONFLICT requires a graph version different from expected_graph_version")


def _validate_audit_result(result: dict[str, Any], after_journal_position: int | None, limit: int | None) -> None:
    records = result["records"]
    if limit is not None and len(records) > limit:
        raise ProtocolValidationError("audit records exceed the requested limit", code="INVALID_LIMIT")
    previous_position = after_journal_position or 0
    # Records of one proposal must form a sequence a durable journal can produce.
    terminals: dict[str, dict[str, Any]] = {}
    seen_proposals: set[str] = set()
    proposals_with_events: set[str] = set()
    max_version = 0
    previous: dict[str, Any] | None = None
    for record in records:
        if record["run_id"] != result["run_id"]:
            raise ProtocolValidationError("audit record run_id does not match response run_id")
        position = record["journal_position"]
        if position <= previous_position:
            raise ProtocolValidationError("audit records must be ordered by journal_position")
        previous_position = position
        proposal_id = record.get("proposal_id")
        record_type = record["record_type"]
        if previous is not None and previous.get("outcome") == "COMMIT" and (
            record_type != "graph_changed" or proposal_id != previous["proposal_id"]
        ):
            raise ProtocolValidationError("a COMMIT decision must be followed by its graph_changed records")
        if "graph_version" in record:
            if record["graph_version"] < max_version:
                raise ProtocolValidationError("audit graph_version cannot decrease")
            if record.get("outcome") == "COMMIT" and record["graph_version"] == max_version:
                raise ProtocolValidationError("each COMMIT must advance graph_version")
            max_version = record["graph_version"]
        if record_type == "proposal_receipt" and proposal_id in seen_proposals:
            raise ProtocolValidationError("proposal_receipt must precede the proposal's other records")
        if record_type in {"mutation_decision", "proposal_abandoned"}:
            if proposal_id in terminals:
                raise ProtocolValidationError("a proposal has at most one terminal record")
            if proposal_id in proposals_with_events:
                raise ProtocolValidationError("graph_changed records must follow their COMMIT decision")
            terminals[proposal_id] = record
        if record_type == "graph_changed":
            terminal = terminals.get(proposal_id)
            if terminal is not None and terminal.get("outcome") != "COMMIT":
                raise ProtocolValidationError("graph_changed requires a COMMIT decision")
            if previous is None and after_journal_position == 0:
                raise ProtocolValidationError("graph_changed cannot start the journal")
            if previous is not None and (
                previous.get("proposal_id") != proposal_id
                or previous["record_type"] not in {"mutation_decision", "graph_changed"}
                or previous["graph_version"] != record["graph_version"]
            ):
                raise ProtocolValidationError(
                    "graph_changed records must directly follow their COMMIT decision at its graph_version"
                )
            proposals_with_events.add(proposal_id)
        if proposal_id is not None:
            seen_proposals.add(proposal_id)
        previous = record
    if previous is not None and previous.get("outcome") == "COMMIT" and not result["has_more"]:
        raise ProtocolValidationError("a complete audit page cannot end with a COMMIT decision")
    if not records and after_journal_position is None:
        raise ProtocolValidationError("validating an empty audit page requires its request cursor")
    if result["next_after_journal_position"] != previous_position:
        raise ProtocolValidationError("audit cursor must equal the final record or supplied empty-page cursor")


def validate_response(value: Any, request: ProtocolRequest | None = None) -> ProtocolResponse:
    """Validate shared shapes, then enforce request and projection invariants."""
    response = _object(value, "response")
    _json_tree(response, "response")
    is_error = "error" in response
    _validate_shape(response, "ErrorResponse" if is_error else "SuccessResponse", "response")
    if not is_error:
        operation = response["operation"]
        result = response["result"]
        _validate_shape(result, CONTRACT["x-operations"][operation]["result"], f"{operation} result")
        if operation in {"create_run", "get_run"}:
            if _run_metadata_hash(result["run_metadata"]) != result["metadata_hash"]:
                raise ProtocolValidationError("metadata_hash does not match run_metadata")
    after_journal_position = None
    requested_limit = None
    expected_graph_version = None
    if request is not None:
        validate_request(request)
        if response["request_id"] != request["request_id"]:
            raise ProtocolValidationError("response request_id does not match request")
        if not is_error:
            if operation != request["operation"]:
                raise ProtocolValidationError("response operation does not match request")
            params = request["params"]
            if result["run_id"] != params["run_id"]:
                raise ProtocolValidationError("response run_id does not match request")
            if "proposal_id" in params and result["proposal_id"] != params["proposal_id"]:
                raise ProtocolValidationError("response proposal_id does not match request")
            if operation == "create_run" and _canonical_json_value(
                result["run_metadata"]
            ) != _canonical_json_value(params["run_metadata"]):
                raise ProtocolValidationError("create_run response run_metadata does not match request")
            if operation == "propose_mutation":
                expected_graph_version = params["expected_graph_version"]
            if operation == "get_audit_timeline":
                after_journal_position = params.get("after_journal_position", 0)
            requested_limit = params.get("limit")
    if not is_error:
        if operation == "get_graph":
            _validate_graph_result(result, requested_limit)
        elif operation in {"propose_mutation", "get_proposal"}:
            _validate_proposal_result(result, expected_graph_version)
        elif operation == "get_audit_timeline":
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


def _parse_protocol_float(value: str) -> float:
    return float(value)


def _normalize_decoded_numbers(value: Any) -> Any:
    if type(value) is float:
        if value.is_integer() and abs(value) <= MAX_SAFE_JSON_INTEGER:
            return int(value)
        return value
    if type(value) is list:
        return [_normalize_decoded_numbers(item) for item in value]
    if type(value) is dict:
        return {key: _normalize_decoded_numbers(item) for key, item in value.items()}
    return value


def _encode(value: Any, validator: Any) -> bytes:
    try:
        validator(value)
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except ProtocolValidationError:
        raise
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
    try:
        value = _normalize_decoded_numbers(value)
        return validator(value)
    except RecursionError as error:
        raise ProtocolValidationError("message exceeds supported JSON nesting") from error


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
