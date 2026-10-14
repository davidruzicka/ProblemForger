/** Public protocol v1 types and structural codec for TypeScript clients. */

export const CURRENT_PROTOCOL_SCHEMA_VERSION = 1 as const;
export const CURRENT_REQUEST_SCHEMA_VERSION = 1 as const;
export const MAX_PROTOCOL_MESSAGE_BYTES = 4 * 1024 * 1024;
export const MAX_RUN_METADATA_BYTES = 1024 * 1024;
export const MAX_NORMALIZED_REQUEST_BYTES = 1024 * 1024;
export const MAX_PROTOCOL_PAGE_SIZE = 100;
export const MAX_SAFE_JSON_INTEGER = Number.MAX_SAFE_INTEGER;

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export type Operation =
  | 'create_run'
  | 'get_run'
  | 'get_graph'
  | 'propose_mutation'
  | 'get_proposal'
  | 'get_audit_timeline';
export type GovernanceOutcome = 'COMMIT' | 'REJECT' | 'RETRY' | 'ESCALATE' | 'CONFLICT';
export type ProposalStatus = GovernanceOutcome | 'PENDING' | 'ABANDONED';

export type RunMetadata = { metadata_schema_version: 1; data: JsonObject };
export type RequestBase<O extends Operation, P> = {
  protocol_schema_version: 1;
  request_id: string;
  operation: O;
  params: P;
};

export type CreateRunRequest = RequestBase<'create_run', { run_id: string; run_metadata: RunMetadata }>;
export type GetRunRequest = RequestBase<'get_run', { run_id: string }>;
export type GetGraphRequest = RequestBase<'get_graph', {
  run_id: string;
  limit: number;
  selection?: JsonObject;
  after_cursor?: string;
}>;
export type ProposeMutationRequest = RequestBase<'propose_mutation', {
  run_id: string;
  proposal_id: string;
  request_schema_version: 1;
  expected_graph_version: number;
  operations: JsonObject[];
  evidence: JsonObject[];
}>;
export type GetProposalRequest = RequestBase<'get_proposal', { run_id: string; proposal_id: string }>;
export type GetAuditTimelineRequest = RequestBase<'get_audit_timeline', {
  run_id: string;
  limit: number;
  after_journal_position?: number;
}>;

export type ProtocolRequest =
  | CreateRunRequest
  | GetRunRequest
  | GetGraphRequest
  | ProposeMutationRequest
  | GetProposalRequest
  | GetAuditTimelineRequest;

export type RunResult = {
  run_id: string;
  run_metadata: RunMetadata;
  metadata_hash: string;
  graph_version: number;
  last_journal_position: number;
  created: boolean;
};
export type GraphResult = {
  run_id: string;
  graph_schema_version: number;
  graph_version: number;
  nodes: JsonObject[];
  edges: JsonObject[];
  next_cursor: string | null;
  has_more: boolean;
};
export type ProposalResult = {
  run_id: string;
  proposal_id: string;
  status: ProposalStatus;
  request_hash: string;
  reason_code: string | null;
  resulting_graph_version: number | null;
  journal_position: number;
};
export type PublicAuditRecord = {
  journal_position: number;
  record_type: string;
  run_id: string;
  proposal_id?: string;
  lifecycle_state?: 'PENDING' | 'ABANDONED';
  outcome?: GovernanceOutcome;
  reason_code?: string;
  graph_version?: number;
};
export type AuditTimelineResult = {
  run_id: string;
  records: PublicAuditRecord[];
  next_after_journal_position: number;
  has_more: boolean;
};
export type ErrorCode =
  | 'PROTOCOL_ERROR'
  | 'UNSUPPORTED_PROTOCOL_VERSION'
  | 'UNAUTHORIZED'
  | 'NOT_FOUND'
  | 'RUN_METADATA_CONFLICT'
  | 'IDEMPOTENCY_CONFLICT'
  | 'INVALID_LIMIT'
  | 'PAYLOAD_TOO_LARGE'
  | 'STORE_IN_USE';
export type ProtocolError = { code: ErrorCode; message: string };

export type SuccessResponse =
  | { protocol_schema_version: 1; request_id: string; operation: 'create_run' | 'get_run'; result: RunResult }
  | { protocol_schema_version: 1; request_id: string; operation: 'get_graph'; result: GraphResult }
  | { protocol_schema_version: 1; request_id: string; operation: 'propose_mutation' | 'get_proposal'; result: ProposalResult }
  | { protocol_schema_version: 1; request_id: string; operation: 'get_audit_timeline'; result: AuditTimelineResult };
export type ErrorResponse = {
  protocol_schema_version: 1;
  request_id: string | null;
  error: ProtocolError;
};
export type ProtocolResponse = SuccessResponse | ErrorResponse;

const operations = new Set<Operation>([
  'create_run', 'get_run', 'get_graph', 'propose_mutation', 'get_proposal', 'get_audit_timeline',
]);
const outcomes = new Set<GovernanceOutcome>(['COMMIT', 'REJECT', 'RETRY', 'ESCALATE', 'CONFLICT']);
const statuses = new Set<ProposalStatus>([...outcomes, 'PENDING', 'ABANDONED']);
const errorCodes = new Set<ErrorCode>([
  'PROTOCOL_ERROR', 'UNSUPPORTED_PROTOCOL_VERSION', 'UNAUTHORIZED', 'NOT_FOUND',
  'RUN_METADATA_CONFLICT', 'IDEMPOTENCY_CONFLICT', 'INVALID_LIMIT', 'PAYLOAD_TOO_LARGE', 'STORE_IN_USE',
]);

function fail(message: string): never {
  throw new TypeError(message);
}

function object(value: unknown, name: string): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return fail(`${name} must be an object`);
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return fail(`${name} must be a plain object`);
  return value as Record<string, unknown>;
}

function exactFields(value: Record<string, unknown>, required: string[], optional: string[] = [], name = 'object'): void {
  const allowed = new Set([...required, ...optional]);
  const missing = required.filter((key) => !Object.hasOwn(value, key));
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (missing.length || unknown.length) return fail(`${name} fields do not match protocol schema`);
}

function identifier(value: unknown, name: string): asserts value is string {
  if (typeof value !== 'string' || !value.trim()) return fail(`${name} must be a non-empty string`);
  identifierUnicode(value, name);
}

function integer(value: unknown, name: string, minimum = 0, maximum = MAX_SAFE_JSON_INTEGER): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
    return fail(`${name} must be a JSON safe integer from ${minimum} through ${maximum}`);
  }
}

function jsonValue(value: unknown, active = new Set<object>()): asserts value is JsonValue {
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'string') {
    identifierUnicode(value, 'JSON string');
    return;
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return fail('JSON values cannot contain non-finite numbers');
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) return fail('JSON integers must be safe integers');
    return;
  }
  if (Array.isArray(value)) {
    if (active.has(value)) return fail('JSON values cannot be cyclic');
    active.add(value);
    for (const item of value) jsonValue(item, active);
    active.delete(value);
    return;
  }
  if (typeof value === 'object') {
    const record = object(value, 'JSON value');
    if (active.has(record)) return fail('JSON values cannot be cyclic');
    active.add(record);
    for (const [key, item] of Object.entries(record)) {
      identifierUnicode(key, 'JSON object key');
      jsonValue(item, active);
    }
    active.delete(record);
    return;
  }
  return fail('value is not JSON serializable');
}

function identifierUnicode(value: string, name: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return fail(`${name} must be valid UTF-8`);
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return fail(`${name} must be valid UTF-8`);
    }
  }
}

function jsonObject(value: unknown, name: string): asserts value is JsonObject {
  const record = object(value, name);
  jsonValue(record);
}

function metadata(value: unknown): asserts value is RunMetadata {
  const runMetadata = object(value, 'run_metadata');
  exactFields(runMetadata, ['metadata_schema_version', 'data'], [], 'run_metadata');
  integer(runMetadata.metadata_schema_version, 'metadata_schema_version', 1);
  if (runMetadata.metadata_schema_version !== 1) return fail('unsupported metadata_schema_version');
  jsonObject(runMetadata.data, 'run_metadata.data');
  if (byteLength(canonicalJson(runMetadata as JsonValue)) > MAX_RUN_METADATA_BYTES) return fail('run_metadata exceeds 1 MiB');
}

function byteLength(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}

function canonicalJson(value: JsonValue): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key]!)}`).join(',')}}`;
  }
  return JSON.stringify(value) as string;
}

function hash(value: unknown, prefix: string, name: string): asserts value is string {
  identifier(value, name);
  const digest = value.startsWith(prefix) ? value.slice(prefix.length) : '';
  if (!/^[0-9a-f]{64}$/.test(digest)) return fail(`${name} must use its versioned SHA-256 format`);
}

export function validateRequest(value: unknown): asserts value is ProtocolRequest {
  jsonValue(value);
  const request = object(value, 'request');
  exactFields(request, ['protocol_schema_version', 'request_id', 'operation', 'params'], [], 'request');
  integer(request.protocol_schema_version, 'protocol_schema_version', 1);
  if (request.protocol_schema_version !== CURRENT_PROTOCOL_SCHEMA_VERSION) return fail('unsupported protocol_schema_version');
  identifier(request.request_id, 'request_id');
  if (typeof request.operation !== 'string' || !operations.has(request.operation as Operation)) return fail('unknown operation');
  const params = object(request.params, 'params');
  const operation = request.operation as Operation;

  if (operation === 'create_run') {
    exactFields(params, ['run_id', 'run_metadata'], [], 'create_run params');
    identifier(params.run_id, 'run_id');
    metadata(params.run_metadata);
  } else if (operation === 'get_run') {
    exactFields(params, ['run_id'], [], 'get_run params');
    identifier(params.run_id, 'run_id');
  } else if (operation === 'get_graph') {
    exactFields(params, ['run_id', 'limit'], ['selection', 'after_cursor'], 'get_graph params');
    identifier(params.run_id, 'run_id');
    integer(params.limit, 'limit', 1, MAX_PROTOCOL_PAGE_SIZE);
    if (Object.hasOwn(params, 'selection')) jsonObject(params.selection, 'selection');
    if (Object.hasOwn(params, 'after_cursor')) identifier(params.after_cursor, 'after_cursor');
  } else if (operation === 'propose_mutation') {
    exactFields(params, [
      'run_id', 'proposal_id', 'request_schema_version', 'expected_graph_version', 'operations', 'evidence',
    ], [], 'propose_mutation params');
    identifier(params.run_id, 'run_id');
    identifier(params.proposal_id, 'proposal_id');
    integer(params.request_schema_version, 'request_schema_version', 1);
    if (params.request_schema_version !== CURRENT_REQUEST_SCHEMA_VERSION) return fail('unsupported request_schema_version');
    integer(params.expected_graph_version, 'expected_graph_version');
    if (!Array.isArray(params.operations) || !Array.isArray(params.evidence)) return fail('operations and evidence must be arrays');
    for (const item of [...params.operations, ...params.evidence]) jsonObject(item, 'operation/evidence item');
    const normalizedRequest = {
      request_schema_version: params.request_schema_version,
      expected_graph_version: params.expected_graph_version,
      operations: params.operations,
      evidence: params.evidence,
    };
    if (byteLength(canonicalJson(normalizedRequest as JsonValue)) > MAX_NORMALIZED_REQUEST_BYTES) return fail('normalized mutation request exceeds 1 MiB');
  } else if (operation === 'get_proposal') {
    exactFields(params, ['run_id', 'proposal_id'], [], 'get_proposal params');
    identifier(params.run_id, 'run_id');
    identifier(params.proposal_id, 'proposal_id');
  } else {
    exactFields(params, ['run_id', 'limit'], ['after_journal_position'], 'get_audit_timeline params');
    identifier(params.run_id, 'run_id');
    integer(params.limit, 'limit', 1, MAX_PROTOCOL_PAGE_SIZE);
    if (Object.hasOwn(params, 'after_journal_position')) integer(params.after_journal_position, 'after_journal_position');
  }
}

function validateRunResult(value: unknown, name: string): void {
  const result = object(value, name);
  exactFields(result, ['run_id', 'run_metadata', 'metadata_hash', 'graph_version', 'last_journal_position', 'created'], [], name);
  identifier(result.run_id, 'run_id');
  metadata(result.run_metadata);
  hash(result.metadata_hash, 'sha256:problemforger-run-metadata-v1:', 'metadata_hash');
  integer(result.graph_version, 'graph_version');
  integer(result.last_journal_position, 'last_journal_position');
  if (typeof result.created !== 'boolean') return fail('created must be a boolean');
}

function validateGraphResult(value: unknown, limit?: number): void {
  const result = object(value, 'get_graph result');
  exactFields(result, ['run_id', 'graph_schema_version', 'graph_version', 'nodes', 'edges', 'next_cursor', 'has_more'], [], 'get_graph result');
  identifier(result.run_id, 'run_id');
  integer(result.graph_schema_version, 'graph_schema_version', 1);
  integer(result.graph_version, 'graph_version');
  if (!Array.isArray(result.nodes) || !Array.isArray(result.edges)) return fail('nodes and edges must be arrays');
  const recordCount = result.nodes.length + result.edges.length;
  if (recordCount > MAX_PROTOCOL_PAGE_SIZE) return fail('graph result exceeds the 100-record page limit');
  if (limit !== undefined && recordCount > limit) return fail('graph result exceeds the requested limit');
  for (const item of [...result.nodes, ...result.edges]) jsonObject(item, 'graph record');
  if (result.next_cursor !== null) identifier(result.next_cursor, 'next_cursor');
  if (typeof result.has_more !== 'boolean') return fail('has_more must be a boolean');
  if (result.has_more && result.next_cursor === null) return fail('graph continuation requires next_cursor');
}

function validateProposalResult(value: unknown, expectedGraphVersion?: number): void {
  const result = object(value, 'proposal result');
  exactFields(result, ['run_id', 'proposal_id', 'status', 'request_hash', 'reason_code', 'resulting_graph_version', 'journal_position'], [], 'proposal result');
  identifier(result.run_id, 'run_id');
  identifier(result.proposal_id, 'proposal_id');
  if (typeof result.status !== 'string' || !statuses.has(result.status as ProposalStatus)) return fail('unsupported proposal status');
  hash(result.request_hash, 'sha256:problemforger-request-v1:', 'request_hash');
  const reason = result.reason_code;
  const resultingVersion = result.resulting_graph_version;
  integer(result.journal_position, 'journal_position', 1);
  if (reason !== null) identifier(reason, 'reason_code');
  if (resultingVersion !== null) integer(resultingVersion, 'resulting_graph_version');
  if (result.status === 'PENDING' && (reason !== null || resultingVersion !== null)) return fail('PENDING cannot contain terminal outcome fields');
  if (result.status === 'ABANDONED' && (reason === null || resultingVersion !== null)) return fail('ABANDONED requires a reason and no graph version');
  if (result.status === 'COMMIT') {
    if (resultingVersion === null) return fail('COMMIT requires a graph version');
    if (expectedGraphVersion !== undefined && resultingVersion !== expectedGraphVersion + 1) {
      return fail('COMMIT must advance graph_version exactly once');
    }
  } else if (result.status !== 'PENDING' && result.status !== 'ABANDONED') {
    if (reason === null || resultingVersion === null) return fail('non-COMMIT terminal outcomes require a reason and graph version');
    if (expectedGraphVersion !== undefined) {
      if (result.status === 'CONFLICT' && resultingVersion === expectedGraphVersion) {
        return fail('CONFLICT requires a graph version different from expected_graph_version');
      }
      if (result.status !== 'CONFLICT' && resultingVersion !== expectedGraphVersion) {
        return fail('non-commit outcomes must preserve expected_graph_version');
      }
    }
  }
}

function validateAuditResult(value: unknown, afterJournalPosition?: number, limit?: number): void {
  const result = object(value, 'audit timeline result');
  exactFields(result, ['run_id', 'records', 'next_after_journal_position', 'has_more'], [], 'audit timeline result');
  identifier(result.run_id, 'run_id');
  if (!Array.isArray(result.records) || result.records.length > MAX_PROTOCOL_PAGE_SIZE) return fail('audit records must fit the 100-record page limit');
  if (limit !== undefined && result.records.length > limit) return fail('audit records exceed the requested limit');
  let previousPosition = afterJournalPosition ?? 0;
  for (const value of result.records) {
    const record = object(value, 'audit record');
    exactFields(record, ['journal_position', 'record_type', 'run_id'], ['proposal_id', 'lifecycle_state', 'outcome', 'reason_code', 'graph_version'], 'audit record');
    integer(record.journal_position, 'journal_position', 1);
    if (record.journal_position <= previousPosition) return fail('audit records must be ordered by journal_position');
    previousPosition = record.journal_position;
    identifier(record.record_type, 'record_type');
    identifier(record.run_id, 'run_id');
    if (record.run_id !== result.run_id) return fail('audit record run_id does not match response run_id');
    if (Object.hasOwn(record, 'proposal_id')) identifier(record.proposal_id, 'proposal_id');
    if (Object.hasOwn(record, 'lifecycle_state') && record.lifecycle_state !== 'PENDING' && record.lifecycle_state !== 'ABANDONED') return fail('unsupported audit lifecycle_state');
    if (Object.hasOwn(record, 'outcome') && (typeof record.outcome !== 'string' || !outcomes.has(record.outcome as GovernanceOutcome))) return fail('unsupported audit outcome');
    if (Object.hasOwn(record, 'reason_code')) identifier(record.reason_code, 'reason_code');
    if (Object.hasOwn(record, 'graph_version')) integer(record.graph_version, 'graph_version');
  }
  integer(result.next_after_journal_position, 'next_after_journal_position');
  if (typeof result.has_more !== 'boolean') return fail('has_more must be a boolean');
  if (result.records.length > 0) {
    if (result.next_after_journal_position !== previousPosition) return fail('next_after_journal_position must equal the last returned record');
  } else {
    if (afterJournalPosition === undefined) return fail('validating an empty audit page requires its request cursor');
    const expectedPosition = afterJournalPosition;
    if (result.next_after_journal_position !== expectedPosition) return fail('empty audit page must preserve its supplied cursor');
    if (result.has_more) return fail('empty audit page cannot have more records');
  }
}

export function validateResponse(value: unknown, request?: ProtocolRequest): asserts value is ProtocolResponse {
  jsonValue(value);
  const response = object(value, 'response');
  integer(response.protocol_schema_version, 'protocol_schema_version', 1);
  if (response.protocol_schema_version !== CURRENT_PROTOCOL_SCHEMA_VERSION) return fail('unsupported protocol_schema_version');
  let afterJournalPosition: number | undefined;
  let requestedLimit: number | undefined;
  let expectedGraphVersion: number | undefined;
  if (request !== undefined) {
    validateRequest(request);
    if (response.request_id !== request.request_id) return fail('response request_id does not match request');
    if (!Object.hasOwn(response, 'error')) {
      if (response.operation !== request.operation) return fail('response operation does not match request');
      const params = request.params as unknown as Record<string, unknown>;
      const result = object(response.result, 'response result');
      if (result.run_id !== params.run_id) return fail('response run_id does not match request');
      if (Object.hasOwn(params, 'proposal_id') && result.proposal_id !== params.proposal_id) return fail('response proposal_id does not match request');
      if (request.operation === 'propose_mutation') {
        expectedGraphVersion = request.params.expected_graph_version;
      } else if (request.operation === 'get_audit_timeline') {
        afterJournalPosition = request.params.after_journal_position ?? 0;
        requestedLimit = request.params.limit;
      } else if (request.operation === 'get_graph') {
        requestedLimit = request.params.limit;
      }
    }
  }
  if (Object.hasOwn(response, 'error')) {
    exactFields(response, ['protocol_schema_version', 'request_id', 'error'], [], 'error response');
    const error = object(response.error, 'error');
    exactFields(error, ['code', 'message'], [], 'error');
    if (typeof error.code !== 'string' || !errorCodes.has(error.code as ErrorCode)) return fail('unsupported protocol error code');
    if (response.request_id !== null) identifier(response.request_id, 'request_id');
    if (response.request_id === null && !['PROTOCOL_ERROR', 'UNSUPPORTED_PROTOCOL_VERSION', 'PAYLOAD_TOO_LARGE', 'STORE_IN_USE'].includes(error.code as string)) return fail('this error requires a request_id');
    if (error.code === 'STORE_IN_USE' && response.request_id !== null) return fail('STORE_IN_USE is a startup error and has no request_id');
    identifier(error.message, 'error.message');
    return;
  }
  exactFields(response, ['protocol_schema_version', 'request_id', 'operation', 'result'], [], 'success response');
  identifier(response.request_id, 'request_id');
  if (typeof response.operation !== 'string' || !operations.has(response.operation as Operation)) return fail('unknown response operation');
  const operation = response.operation as Operation;
  if (operation === 'create_run' || operation === 'get_run') validateRunResult(response.result, `${operation} result`);
  else if (operation === 'get_graph') validateGraphResult(response.result, requestedLimit);
  else if (operation === 'propose_mutation' || operation === 'get_proposal') validateProposalResult(response.result, expectedGraphVersion);
  else {
    validateAuditResult(response.result, afterJournalPosition, requestedLimit);
  }
}

function rejectDuplicateKeys(text: string): void {
  let offset = 0;
  const whitespace = () => {
    while (offset < text.length && /\s/.test(text[offset]!)) offset += 1;
  };
  const parseString = (): string => {
    const start = offset;
    offset += 1;
    while (offset < text.length) {
      const character = text[offset]!;
      offset += 1;
      if (character === '"') return JSON.parse(text.slice(start, offset)) as string;
      if (character === '\\') offset += 1;
    }
    return fail('message is not valid JSON');
  };
  const parseValue = (): void => {
    whitespace();
    const character = text[offset];
    if (character === '"') {
      parseString();
      return;
    }
    if (character === '{') {
      offset += 1;
      whitespace();
      const keys = new Set<string>();
      if (text[offset] === '}') {
        offset += 1;
        return;
      }
      while (offset < text.length) {
        whitespace();
        if (text[offset] !== '"') return fail('message is not valid JSON');
        const key = parseString();
        if (keys.has(key)) return fail(`duplicate JSON key: ${key}`);
        keys.add(key);
        whitespace();
        if (text[offset] !== ':') return fail('message is not valid JSON');
        offset += 1;
        parseValue();
        whitespace();
        if (text[offset] === '}') {
          offset += 1;
          return;
        }
        if (text[offset] !== ',') return fail('message is not valid JSON');
        offset += 1;
      }
      return fail('message is not valid JSON');
    }
    if (character === '[') {
      offset += 1;
      whitespace();
      if (text[offset] === ']') {
        offset += 1;
        return;
      }
      while (offset < text.length) {
        parseValue();
        whitespace();
        if (text[offset] === ']') {
          offset += 1;
          return;
        }
        if (text[offset] !== ',') return fail('message is not valid JSON');
        offset += 1;
      }
      return fail('message is not valid JSON');
    }
    const start = offset;
    while (offset < text.length && !/[\s,\]}]/.test(text[offset]!)) offset += 1;
    if (offset === start) return fail('message is not valid JSON');
  };

  parseValue();
  whitespace();
  if (offset !== text.length) return fail('message is not valid JSON');
}

function decodeJson(serialized: string | Uint8Array): unknown {
  let text: string;
  if (typeof serialized === 'string') {
    text = serialized;
  } else {
    if (serialized.byteLength > MAX_PROTOCOL_MESSAGE_BYTES) return fail('message exceeds 4 MiB');
    if (serialized[0] === 0xef && serialized[1] === 0xbb && serialized[2] === 0xbf) {
      return fail('message cannot start with a UTF-8 BOM');
    }
    text = new TextDecoder('utf-8', { fatal: true }).decode(serialized);
  }
  if (byteLength(text) > MAX_PROTOCOL_MESSAGE_BYTES) return fail('message exceeds 4 MiB');
  rejectDuplicateKeys(text);
  return JSON.parse(text) as unknown;
}

function encodeJson(value: unknown): string {
  const encoded = JSON.stringify(value);
  if (byteLength(encoded) > MAX_PROTOCOL_MESSAGE_BYTES) return fail('message exceeds 4 MiB');
  return encoded;
}

export function encodeRequest(value: ProtocolRequest): string {
  validateRequest(value);
  return encodeJson(value);
}

export function decodeRequest(serialized: string | Uint8Array): ProtocolRequest {
  const value = decodeJson(serialized);
  validateRequest(value);
  return value;
}

export function encodeResponse(value: ProtocolResponse, request?: ProtocolRequest): string {
  validateResponse(value, request);
  return encodeJson(value);
}

export function decodeResponse(serialized: string | Uint8Array, request?: ProtocolRequest): ProtocolResponse {
  const value = decodeJson(serialized);
  validateResponse(value, request);
  return value;
}
