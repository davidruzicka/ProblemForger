/** Public protocol v1 types and structural codec for TypeScript clients. */

import { createHash } from 'node:crypto';
import { protocolContract } from './protocol_contract.ts';

export const CURRENT_PROTOCOL_SCHEMA_VERSION = protocolContract['x-contract-version'];
export const CURRENT_REQUEST_SCHEMA_VERSION = protocolContract.$defs.RequestVersion.const;
export const MAX_PROTOCOL_MESSAGE_BYTES = protocolContract['x-frame-max-bytes'];
export const MAX_RUN_METADATA_BYTES = protocolContract.$defs.RunMetadata['x-max-canonical-bytes'];
export const MAX_NORMALIZED_REQUEST_BYTES = protocolContract.$defs.ProposeMutationParams['x-max-canonical-bytes'];
export const MAX_PROTOCOL_PAGE_SIZE = protocolContract['x-page-max-records'];
export const MAX_SAFE_JSON_INTEGER = protocolContract.$defs.SafeInteger.maximum;

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export type Operation = keyof typeof protocolContract['x-operations'];
export type ProposalStatus = keyof typeof protocolContract['x-proposal-states'];
export type GovernanceOutcome = typeof protocolContract.$defs.AuditRecord.properties.outcome.enum[number];
export type AuditRecordType = typeof protocolContract.$defs.AuditRecord.properties.record_type.enum[number];

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
  record_type: AuditRecordType;
  run_id: string;
  proposal_id?: string;
  lifecycle_state?: typeof protocolContract.$defs.AuditRecord.properties.lifecycle_state.enum[number];
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
export type ErrorCode = typeof protocolContract.$defs.Error.properties.code.enum[number];
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

type Shape = {
  $ref?: string;
  type?: string | readonly string[];
  const?: JsonValue;
  enum?: readonly JsonValue[];
  minimum?: number;
  maximum?: number;
  pattern?: string;
  'x-max-utf8-bytes'?: number;
  properties?: Readonly<Record<string, Shape>>;
  required?: readonly string[];
  additionalProperties?: boolean;
  items?: Shape;
  maxItems?: number;
  allOf?: readonly Shape[];
  oneOf?: readonly Shape[];
  if?: Shape;
  then?: Shape;
  'x-error-code'?: string;
  'x-const-error-code'?: string;
  'x-max-canonical-bytes'?: number;
  'x-size-fields'?: readonly string[];
  'x-size-canonicalization'?: 'run-metadata-json-v2' | 'ecmascript-json-v1';
  'x-version-position'?: readonly string[];
};
const definitions = protocolContract.$defs as unknown as Readonly<Record<string, Shape>>;

function fail(message: string): never {
  throw new TypeError(message);
}

function withJsonRecursionGuard<T>(operation: () => T): T {
  try {
    return operation();
  } catch (error) {
    if (error instanceof RangeError) return fail('message exceeds supported JSON nesting');
    throw error;
  }
}

function object(value: unknown, name: string): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return fail(`${name} must be an object`);
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return fail(`${name} must be a plain object`);
  return value as Record<string, unknown>;
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

function inertJsonSnapshot(value: unknown, active = new Set<object>()): unknown {
  if (value === null || typeof value !== 'object') return value;
  if (active.has(value)) return fail('JSON values cannot be cyclic');
  active.add(value);

  if (Array.isArray(value)) {
    const snapshot: unknown[] = [];
    Object.defineProperty(snapshot, 'toJSON', { value: undefined });
    for (let index = 0; index < value.length; index += 1) {
      snapshot[index] = inertJsonSnapshot(value[index], active);
    }
    active.delete(value);
    return snapshot;
  }

  const source = object(value, 'JSON value');
  const snapshot = Object.create(null) as Record<string, unknown>;
  for (const [key, item] of Object.entries(source)) {
    snapshot[key] = inertJsonSnapshot(item, active);
  }
  active.delete(value);
  return snapshot;
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

function compareCodePoints(left: string, right: string): number {
  const leftPoints = [...left].map((character) => character.codePointAt(0)!);
  const rightPoints = [...right].map((character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(leftPoints.length, rightPoints.length); index += 1) {
    if (leftPoints[index] !== rightPoints[index]) return leftPoints[index]! - rightPoints[index]!;
  }
  return leftPoints.length - rightPoints.length;
}

function pythonCanonicalFloat(value: number): string {
  const source = value.toString().toLowerCase();
  const negative = source.startsWith('-');
  const unsigned = negative ? source.slice(1) : source;
  const [mantissa, exponentText] = unsigned.split('e');
  const exponent = exponentText === undefined ? 0 : Number.parseInt(exponentText, 10);
  const [integerPart, fractionalPart = ''] = mantissa!.split('.');
  let digits = `${integerPart}${fractionalPart}`;
  const significant = digits.replace(/^0+/, '');
  const leadingZeroes = digits.length - significant.length;
  let decimalPosition = integerPart!.length + exponent - leadingZeroes;
  digits = significant.replace(/0+$/, '');
  const scientificExponent = decimalPosition - 1;
  let rendered: string;
  if (scientificExponent < -4) {
    const exponentDigits = Math.abs(scientificExponent).toString().padStart(2, '0');
    rendered = `${digits[0]}${digits.length > 1 ? `.${digits.slice(1)}` : ''}e-${exponentDigits}`;
  } else if (decimalPosition <= 0) {
    rendered = `0.${'0'.repeat(-decimalPosition)}${digits}`;
  } else {
    rendered = `${digits.slice(0, decimalPosition)}.${digits.slice(decimalPosition)}`;
  }
  return `${negative ? '-' : ''}${rendered}`;
}

function pythonCanonicalJson(value: JsonValue): string {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value) as string;
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : pythonCanonicalFloat(value);
  if (Array.isArray(value)) return `[${value.map(pythonCanonicalJson).join(',')}]`;
  const fields = Object.keys(value).sort(compareCodePoints);
  return `{${fields.map((key) => `${JSON.stringify(key)}:${pythonCanonicalJson(value[key]!)}`).join(',')}}`;
}

function runMetadataHash(metadata: RunMetadata): string {
  const rule = protocolContract.$defs.MetadataHash['x-canonical-hash'];
  const digest = createHash(rule.algorithm)
    .update(rule.domain_separator, 'utf8')
    .update(pythonCanonicalJson(metadata), 'utf8')
    .digest('hex');
  return `${rule.prefix}${digest}`;
}

function validateShape(value: unknown, shape: Shape | string, name: string): void {
  let schema = typeof shape === 'string' ? definitions[shape]! : shape;
  if (schema.$ref !== undefined) {
    const { $ref, ...siblings } = schema;
    schema = { ...definitions[$ref.replace('#/$defs/', '')]!, ...siblings };
  }
  const kind = schema.type;
  const kinds = typeof kind === 'string' ? [kind] : kind;
  if (kinds !== undefined) {
    if (value === null && kinds.includes('null')) {
      // Nullable fields still pass through constant and enum constraints below.
    } else if (typeof value === 'number' && kinds.includes('integer')) {
      integer(value, name, schema.minimum ?? 0, schema.maximum ?? MAX_SAFE_JSON_INTEGER);
    } else if (!kinds.some((item) =>
      (item === 'object' && value !== null && typeof value === 'object' && !Array.isArray(value))
      || (item === 'array' && Array.isArray(value))
      || (item === 'string' && typeof value === 'string')
      || (item === 'boolean' && typeof value === 'boolean'))) {
      return fail(`${name} must have type ${kind}`);
    }
  }
  if (Object.hasOwn(schema, 'const') && canonicalJson(value as JsonValue) !== canonicalJson(schema.const!)) return fail(`${name} has an unsupported value`);
  if (schema.enum !== undefined && !schema.enum.includes(value as JsonValue)) return fail(`${name} has an unsupported value`);
  if (typeof value === 'string' && schema.pattern !== undefined && !new RegExp(schema.pattern).test(value)) return fail(`${name} does not match its string format`);
  if (typeof value === 'string' && schema['x-max-utf8-bytes'] !== undefined && byteLength(value) > schema['x-max-utf8-bytes']) return fail(`${name} exceeds ${schema['x-max-utf8-bytes']} UTF-8 bytes`);
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    const record = object(value, name);
    const properties = schema.properties ?? {};
    if (schema.required?.some((field) => !Object.hasOwn(record, field))) return fail(`${name} is missing required fields`);
    if (schema.additionalProperties === false && Object.keys(record).some((field) => !Object.hasOwn(properties, field))) return fail(`${name} contains unknown fields`);
    for (const [field, rule] of Object.entries(properties)) {
      if (Object.hasOwn(record, field)) validateShape(record[field], rule, `${name}.${field}`);
    }
  }
  if (Array.isArray(value)) {
    if (schema.maxItems !== undefined && value.length > schema.maxItems) return fail(`${name} exceeds its record limit`);
    if (schema.items !== undefined) for (const item of value) validateShape(item, schema.items, `${name} item`);
  }
  for (const rule of schema.allOf ?? []) validateShape(value, rule, name);
  if (schema.oneOf !== undefined) {
    let matches = 0;
    for (const rule of schema.oneOf) {
      try {
        validateShape(value, rule, name);
        matches += 1;
      } catch (error) {
        if (!(error instanceof TypeError)) throw error;
      }
    }
    if (matches !== 1) return fail(`${name} does not match exactly one allowed shape`);
  }
  if (schema.if !== undefined) {
    let matches = true;
    try { validateShape(value, schema.if, name); }
    catch (error) { if (!(error instanceof TypeError)) throw error; matches = false; }
    if (matches) validateShape(value, schema.then!, name);
  }
  if (schema['x-max-canonical-bytes'] !== undefined) {
    const record = value as Record<string, JsonValue>;
    const sized = schema['x-size-fields'] === undefined ? value : Object.fromEntries(schema['x-size-fields'].map((field) => [field, record[field]]));
    const canonicalization = schema['x-size-canonicalization'] ?? 'ecmascript-json-v1';
    const canonical = canonicalization === 'run-metadata-json-v2'
      ? pythonCanonicalJson(sized as JsonValue)
      : canonicalJson(sized as JsonValue);
    if (byteLength(canonical) > schema['x-max-canonical-bytes']) return fail(`${name} exceeds 1 MiB`);
  }
  if (schema['x-version-position'] !== undefined) {
    const [versionField, positionField] = schema['x-version-position'];
    const record = value as Record<string, number | null>;
    const version = record[versionField!];
    if (version !== undefined && version !== null && version > record[positionField!]!) return fail(`${name}.${versionField} cannot exceed ${positionField}`);
  }
}

export function validateRequest(value: unknown): asserts value is ProtocolRequest {
  withJsonRecursionGuard(() => validateRequestValue(value));
}

function validateRequestValue(value: unknown): asserts value is ProtocolRequest {
  jsonValue(value);
  validateShape(value, 'Request', 'request');
  const request = value as ProtocolRequest;
  validateShape(request.params, protocolContract['x-operations'][request.operation].params, 'params');
}

function validateGraphResult(result: GraphResult, limit?: number): void {
  const recordCount = result.nodes.length + result.edges.length;
  if (recordCount > MAX_PROTOCOL_PAGE_SIZE) return fail('graph result exceeds the 100-record page limit');
  if (limit !== undefined && recordCount > limit) return fail('graph result exceeds the requested limit');
}

function validateProposalResult(result: ProposalResult, expectedGraphVersion?: number): void {
  const version = result.resulting_graph_version;
  if (expectedGraphVersion === undefined || version === null) return;
  const effect = protocolContract['x-proposal-states'][result.status].graph_effect;
  if (effect === 'advance' && version !== expectedGraphVersion + 1) return fail('COMMIT must advance graph_version exactly once');
  if (effect === 'preserve' && version !== expectedGraphVersion) return fail('non-commit outcomes must preserve expected_graph_version');
  if (effect === 'differ' && version === expectedGraphVersion) return fail('CONFLICT requires a graph version different from expected_graph_version');
}

function validateAuditResult(result: AuditTimelineResult, afterJournalPosition?: number, limit?: number): void {
  if (limit !== undefined && result.records.length > limit) return fail('audit records exceed the requested limit');
  let previousPosition = afterJournalPosition ?? 0;
  // Records of one proposal must form a sequence a durable journal can produce.
  const terminals = new Map<string, PublicAuditRecord>();
  const seenProposals = new Set<string>();
  const proposalsWithEvents = new Set<string>();
  let maxVersion = 0;
  let previous: PublicAuditRecord | undefined;
  for (const record of result.records) {
    if (record.run_id !== result.run_id) return fail('audit record run_id does not match response run_id');
    if (record.journal_position <= previousPosition) return fail('audit records must be ordered by journal_position');
    previousPosition = record.journal_position;
    const proposalId = record.proposal_id;
    if (previous?.outcome === 'COMMIT' && (record.record_type !== 'graph_changed' || proposalId !== previous.proposal_id)) {
      return fail('a COMMIT decision must be followed by its graph_changed records');
    }
    if (record.graph_version !== undefined) {
      if (record.graph_version < maxVersion) return fail('audit graph_version cannot decrease');
      if (record.outcome === 'COMMIT' && record.graph_version === maxVersion) return fail('each COMMIT must advance graph_version');
      maxVersion = record.graph_version;
    }
    if (record.record_type === 'proposal_receipt' && seenProposals.has(proposalId!)) {
      return fail("proposal_receipt must precede the proposal's other records");
    }
    if (record.record_type === 'mutation_decision' || record.record_type === 'proposal_abandoned') {
      if (terminals.has(proposalId!)) return fail('a proposal has at most one terminal record');
      if (proposalsWithEvents.has(proposalId!)) return fail('graph_changed records must follow their COMMIT decision');
      terminals.set(proposalId!, record);
    }
    if (record.record_type === 'graph_changed') {
      const terminal = terminals.get(proposalId!);
      if (terminal !== undefined && terminal.outcome !== 'COMMIT') return fail('graph_changed requires a COMMIT decision');
      if (previous === undefined && afterJournalPosition === 0) return fail('graph_changed cannot start the journal');
      if (previous !== undefined && (
        previous.proposal_id !== proposalId
        || (previous.record_type !== 'mutation_decision' && previous.record_type !== 'graph_changed')
        || previous.graph_version !== record.graph_version
      )) return fail('graph_changed records must directly follow their COMMIT decision at its graph_version');
      proposalsWithEvents.add(proposalId!);
    }
    if (proposalId !== undefined) seenProposals.add(proposalId);
    previous = record;
  }
  if (previous?.outcome === 'COMMIT' && !result.has_more) return fail('a complete audit page cannot end with a COMMIT decision');
  if (result.records.length === 0 && afterJournalPosition === undefined) return fail('validating an empty audit page requires its request cursor');
  if (result.next_after_journal_position !== previousPosition) return fail('audit cursor must equal the final record or supplied empty-page cursor');
}

export function validateResponse(value: unknown, request?: ProtocolRequest): asserts value is ProtocolResponse {
  withJsonRecursionGuard(() => validateResponseValue(value, request));
}

function validateResponseValue(value: unknown, request?: ProtocolRequest): asserts value is ProtocolResponse {
  jsonValue(value);
  const response = object(value, 'response');
  const isError = Object.hasOwn(response, 'error');
  validateShape(response, isError ? 'ErrorResponse' : 'SuccessResponse', 'response');
  const operation = response.operation as Operation;
  const result = isError ? undefined : object(response.result, 'response result');
  if (result !== undefined) {
    validateShape(result, protocolContract['x-operations'][operation].result, `${operation} result`);
    if (operation === 'create_run' || operation === 'get_run') {
      const runResult = result as unknown as RunResult;
      if (runMetadataHash(runResult.run_metadata) !== runResult.metadata_hash) {
        return fail('metadata_hash does not match run_metadata');
      }
    }
  }
  let afterJournalPosition: number | undefined;
  let requestedLimit: number | undefined;
  let expectedGraphVersion: number | undefined;
  if (request !== undefined) {
    validateRequest(request);
    if (response.request_id !== request.request_id) return fail('response request_id does not match request');
    if (result !== undefined) {
      if (operation !== request.operation) return fail('response operation does not match request');
      const params = request.params as unknown as Record<string, JsonValue>;
      if (result.run_id !== params.run_id) return fail('response run_id does not match request');
      if (Object.hasOwn(params, 'proposal_id') && result.proposal_id !== params.proposal_id) return fail('response proposal_id does not match request');
      if (operation === 'create_run' && canonicalJson(result.run_metadata as JsonValue) !== canonicalJson(params.run_metadata!)) return fail('create_run response run_metadata does not match request');
      if (operation === 'propose_mutation') expectedGraphVersion = params.expected_graph_version as number;
      if (operation === 'get_audit_timeline') afterJournalPosition = (params.after_journal_position as number | undefined) ?? 0;
      requestedLimit = params.limit as number | undefined;
    }
  }
  if (result !== undefined) {
    const success = response as unknown as SuccessResponse;
    if (success.operation === 'get_graph') validateGraphResult(success.result, requestedLimit);
    else if (success.operation === 'propose_mutation' || success.operation === 'get_proposal') validateProposalResult(success.result, expectedGraphVersion);
    else if (success.operation === 'get_audit_timeline') validateAuditResult(success.result, afterJournalPosition, requestedLimit);
  }
}

function rejectDuplicateKeys(text: string): void {
  let offset = 0;
  const whitespace = () => {
    while (offset < text.length && /[ \t\n\r]/.test(text[offset]!)) offset += 1;
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
    } else if (character === '{') {
      offset += 1;
      whitespace();
      const keys = new Set<string>();
      if (text[offset] === '}') {
        offset += 1;
      } else while (offset < text.length) {
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
          break;
        }
        if (text[offset] !== ',') return fail('message is not valid JSON');
        offset += 1;
      }
      if (text[offset - 1] !== '}') return fail('message is not valid JSON');
    } else if (character === '[') {
      offset += 1;
      whitespace();
      if (text[offset] === ']') {
        offset += 1;
      } else while (offset < text.length) {
        parseValue();
        whitespace();
        if (text[offset] === ']') {
          offset += 1;
          break;
        }
        if (text[offset] !== ',') return fail('message is not valid JSON');
        offset += 1;
      }
      if (text[offset - 1] !== ']') return fail('message is not valid JSON');
    } else if (text.startsWith('true', offset)) {
      offset += 4;
    } else if (text.startsWith('false', offset)) {
      offset += 5;
    } else if (text.startsWith('null', offset)) {
      offset += 4;
    } else {
      const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(offset));
      if (match === null) return fail('message is not valid JSON');
      offset += match[0].length;
    }
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
  try {
    rejectDuplicateKeys(text);
    return JSON.parse(text) as unknown;
  } catch (error) {
    if (error instanceof SyntaxError) return fail('message is not valid JSON');
    throw error;
  }
}

function encodeJson(value: unknown): string {
  const encoded = JSON.stringify(value);
  if (byteLength(encoded) > MAX_PROTOCOL_MESSAGE_BYTES) return fail('message exceeds 4 MiB');
  return encoded;
}

export function encodeRequest(value: ProtocolRequest): string {
  return withJsonRecursionGuard(() => {
    const snapshot = inertJsonSnapshot(value);
    validateRequest(snapshot);
    return encodeJson(snapshot);
  });
}

export function decodeRequest(serialized: string | Uint8Array): ProtocolRequest {
  return withJsonRecursionGuard(() => {
    const value = decodeJson(serialized);
    validateRequest(value);
    return value;
  });
}

export function encodeResponse(value: ProtocolResponse, request?: ProtocolRequest): string {
  return withJsonRecursionGuard(() => encodeResponseJson(value, request));
}

function encodeResponseJson(value: ProtocolResponse, request?: ProtocolRequest): string {
  const snapshot = inertJsonSnapshot(value) as ProtocolResponse;
  const requestSnapshot = request === undefined
    ? undefined
    : inertJsonSnapshot(request) as ProtocolRequest;
  validateResponse(snapshot, requestSnapshot);
  return encodeJson(snapshot);
}

export function decodeResponse(serialized: string | Uint8Array, request?: ProtocolRequest): ProtocolResponse {
  return withJsonRecursionGuard(() => {
    const value = decodeJson(serialized);
    validateResponse(value, request);
    return value;
  });
}
