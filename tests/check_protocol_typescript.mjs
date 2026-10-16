import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  MAX_PROTOCOL_MESSAGE_BYTES,
  decodeRequest,
  decodeResponse,
  encodeRequest,
  encodeResponse,
} from '../clients/typescript/protocol.ts';

const fixture = JSON.parse(await readFile(process.argv[2], 'utf8'));

for (const { label, message } of fixture.requests) {
  assert.deepEqual(decodeRequest(encodeRequest(message)), message, `${label} request`);
}
for (const { label, message } of fixture.responses) {
  const request = fixture.requests.find(({ message: candidate }) => candidate.request_id === message.request_id)?.message;
  assert.deepEqual(decodeResponse(encodeResponse(message, request), request), message, `${label} response`);
}
for (const { label, message } of fixture.invalid_requests) {
  assert.throws(() => encodeRequest(message), undefined, `${label} request`);
}
for (const { label, message } of fixture.invalid_responses) {
  assert.throws(() => encodeResponse(message), undefined, `${label} response`);
}

const textEncoder = new TextEncoder();
const getRunRequest = fixture.requests.find(({ label }) => label === 'get_run').message;
const encodedGetRunRequest = textEncoder.encode(JSON.stringify(getRunRequest));
assert.deepEqual(decodeRequest(encodedGetRunRequest), getRunRequest, 'UTF-8 byte request frame');

function withUtf8Bom(frame) {
  const prefixed = new Uint8Array(frame.byteLength + 3);
  prefixed.set([0xef, 0xbb, 0xbf]);
  prefixed.set(frame, 3);
  return prefixed;
}

assert.throws(
  () => decodeRequest(withUtf8Bom(encodedGetRunRequest)),
  undefined,
  'request frame rejects a UTF-8 BOM',
);
const protocolErrorResponse = {
  protocol_schema_version: 1,
  request_id: 'req',
  error: { code: 'PROTOCOL_ERROR', message: 'invalid request' },
};
assert.throws(
  () => decodeResponse(withUtf8Bom(textEncoder.encode(JSON.stringify(protocolErrorResponse)))),
  undefined,
  'response frame rejects a UTF-8 BOM',
);

const oversizedFrame = new Uint8Array(MAX_PROTOCOL_MESSAGE_BYTES + 1).fill(0xff);
assert.throws(
  () => decodeRequest(oversizedFrame),
  /message exceeds 4 MiB/,
  'oversized request byte frame is rejected before UTF-8 decoding',
);
assert.throws(
  () => decodeResponse(oversizedFrame),
  /message exceeds 4 MiB/,
  'oversized response byte frame is rejected before UTF-8 decoding',
);

const createRun = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
createRun.params.run_metadata.data.large = 'é'.repeat(512 * 1024);
assert.throws(() => encodeRequest(createRun), undefined, 'run metadata over 1 MiB');

const mutation = structuredClone(fixture.requests.find(({ label }) => label === 'propose_mutation').message);
mutation.params.operations = [{ payload: 'x'.repeat(1024 * 1024) }];
assert.throws(() => encodeRequest(mutation), undefined, 'normalized mutation over 1 MiB');

const unsafeIntegerRequest = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
unsafeIntegerRequest.params.run_metadata.data.nested = { value: 9007199254740993 };
assert.throws(() => encodeRequest(unsafeIntegerRequest), undefined, 'unsafe integer in nested metadata');
const safeIntegerRequest = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
safeIntegerRequest.params.run_metadata.data.value = Number.MAX_SAFE_INTEGER;
assert.doesNotThrow(() => encodeRequest(safeIntegerRequest), 'maximum safe JSON integer');
assert.throws(
  () => decodeRequest('{"protocol_schema_version":1,"request_id":"req","operation":"create_run","params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"value":9007199254740993}}}}'),
  undefined,
  'unsafe integer in decoded metadata',
);
const exponentialValues = Array.from({ length: 95_000 }, () => ({ x: 1e-7 }));
const exponentialMetadata = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
exponentialMetadata.params.run_metadata.data.items = exponentialValues;
assert.throws(() => encodeRequest(exponentialMetadata), undefined, 'metadata size matches durable canonical JSON');
const exponentialMutation = structuredClone(fixture.requests.find(({ label }) => label === 'propose_mutation').message);
exponentialMutation.params.operations = exponentialValues;
exponentialMutation.params.evidence = [];
assert.doesNotThrow(() => encodeRequest(exponentialMutation), 'mutation size uses shared exponential number formatting');

const identifierLimitRequest = structuredClone(getRunRequest);
identifierLimitRequest.request_id = 'é'.repeat(128);
assert.doesNotThrow(() => encodeRequest(identifierLimitRequest), 'identifier permits 256 UTF-8 bytes');
identifierLimitRequest.request_id = 'é'.repeat(129);
assert.throws(() => encodeRequest(identifierLimitRequest), undefined, 'identifier rejects over 256 UTF-8 bytes');

for (const integerForm of ['1.0', '1e0']) {
  const request = `{"protocol_schema_version":1,"request_id":"req","operation":"get_graph","params":{"run_id":"run-1","limit":${integerForm}}}`;
  assert.equal(decodeRequest(request).params.limit, 1, `integral JSON form ${integerForm}`);
}

const invalidUnicodeRequest = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
invalidUnicodeRequest.params.run_metadata.data.value = '\ud800';
assert.throws(() => encodeRequest(invalidUnicodeRequest), undefined, 'lone surrogate in nested metadata value');
delete invalidUnicodeRequest.params.run_metadata.data.value;
invalidUnicodeRequest.params.run_metadata.data['key\ud800'] = 'value';
assert.throws(() => encodeRequest(invalidUnicodeRequest), undefined, 'lone surrogate in nested metadata key');
assert.throws(
  () => decodeRequest('{"protocol_schema_version":1,"request_id":"req","operation":"create_run","params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"value":"\\ud800"}}}}'),
  undefined,
  'lone surrogate in decoded metadata',
);
assert.throws(
  () => decodeRequest('{"protocol_schema_version":1,"request_id":"req","operation":"create_run","params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"\\ud800":"value"}}}}'),
  undefined,
  'lone surrogate in decoded metadata key',
);

const graphResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_graph').message);
graphResponse.result.nodes = [{ value: 9007199254740993 }];
assert.throws(() => encodeResponse(graphResponse), undefined, 'unsafe integer in response JSON');

for (const duplicate of [
  '{"protocol_schema_version":1,"request_id":"first","request_id":"second","operation":"get_run","params":{"run_id":"run-1"}}',
  '{"protocol_schema_version":1,"request_id":"req","operation":"propose_mutation","params":{"run_id":"run-1","proposal_id":"p","request_schema_version":1,"expected_graph_version":0,"operations":[{"op":"one","op":"two"}],"evidence":[]}}',
  '{"protocol_schema_version":1,"request_id":"req","operation":"get_run","params":{"run_id":"run-1","\\u0072un_id":"run-2"}}',
]) {
  assert.throws(() => decodeRequest(duplicate), undefined, `duplicate JSON key: ${duplicate}`);
}

const auditResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_audit_timeline').message);
auditResponse.result.next_after_journal_position = 99;
assert.throws(() => encodeResponse(auditResponse), undefined, 'audit cursor must equal final record position');

const boundedGraphRequest = structuredClone(fixture.requests.find(({ label }) => label === 'get_graph').message);
boundedGraphRequest.params.limit = 1;
const boundedGraphResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_graph').message);
const firstGraphNode = boundedGraphResponse.result.nodes[0];
boundedGraphResponse.result.nodes = [firstGraphNode, { ...firstGraphNode, id: 'goal-2' }];
assert.throws(() => encodeResponse(boundedGraphResponse, boundedGraphRequest), undefined, 'graph response must respect requested limit');
assert.throws(
  () => decodeResponse(JSON.stringify(boundedGraphResponse), boundedGraphRequest),
  undefined,
  'decoded graph response must respect requested limit',
);
boundedGraphRequest.params.limit = 2;
assert.deepEqual(
  decodeResponse(encodeResponse(boundedGraphResponse, boundedGraphRequest), boundedGraphRequest),
  boundedGraphResponse,
  'graph response at the requested limit is accepted',
);

const boundedAuditRequest = structuredClone(fixture.requests.find(({ label }) => label === 'get_audit_timeline').message);
boundedAuditRequest.params.limit = 1;
const boundedAuditResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_audit_timeline').message);
assert.throws(() => encodeResponse(boundedAuditResponse, boundedAuditRequest), undefined, 'audit response must respect requested limit');
assert.throws(
  () => decodeResponse(JSON.stringify(boundedAuditResponse), boundedAuditRequest),
  undefined,
  'decoded audit response must respect requested limit',
);
boundedAuditRequest.params.limit = 2;
assert.deepEqual(
  decodeResponse(encodeResponse(boundedAuditResponse, boundedAuditRequest), boundedAuditRequest),
  boundedAuditResponse,
  'audit response at the requested limit is accepted',
);

const emptyAuditResponse = structuredClone(auditResponse);
emptyAuditResponse.result.records = [];
emptyAuditResponse.result.next_after_journal_position = 5;
emptyAuditResponse.result.has_more = false;
const auditRequest = structuredClone(fixture.requests.find(({ label }) => label === 'get_audit_timeline').message);
auditRequest.params.after_journal_position = 4;
assert.throws(
  () => decodeResponse(JSON.stringify(emptyAuditResponse), auditRequest),
  undefined,
  'empty audit response must preserve the supplied cursor',
);

emptyAuditResponse.result.next_after_journal_position = 4;
assert.doesNotThrow(() => encodeResponse(emptyAuditResponse, auditRequest));
assert.deepEqual(
  decodeResponse(JSON.stringify(emptyAuditResponse), auditRequest),
  emptyAuditResponse,
  'empty audit response preserves a nonzero supplied cursor',
);
const emptyFromStart = structuredClone(emptyAuditResponse);
emptyFromStart.result.next_after_journal_position = 0;
const initialAuditRequest = structuredClone(auditRequest);
delete initialAuditRequest.params.after_journal_position;
assert.throws(() => encodeResponse(emptyFromStart), undefined, 'empty audit response needs request context');
assert.doesNotThrow(() => encodeResponse(emptyFromStart, initialAuditRequest));
assert.deepEqual(
  decodeResponse(JSON.stringify(emptyFromStart), initialAuditRequest),
  emptyFromStart,
  'empty audit response preserves the default zero cursor',
);
emptyAuditResponse.result.has_more = true;
assert.throws(() => encodeResponse(emptyAuditResponse, auditRequest), undefined, 'empty page cannot continue');
emptyAuditResponse.result.has_more = false;
assert.throws(
  () => encodeResponse(emptyAuditResponse, { ...auditRequest, request_id: 'another-request' }),
  undefined,
  'audit response must match request id',
);
assert.throws(
  () => encodeResponse(emptyAuditResponse, { ...auditRequest, params: { ...auditRequest.params, run_id: 'another-run' } }),
  undefined,
  'audit response must match requested run',
);
assert.throws(
  () => encodeResponse(emptyAuditResponse, {
    ...auditRequest,
    operation: 'get_run',
    params: { run_id: 'run-1' },
  }),
  undefined,
  'audit response context must be an audit request',
);

const createRunResponse = structuredClone(fixture.responses.find(({ label }) => label === 'create_run').message);
const createRunRequest = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
const canonicalCreateRunRequest = structuredClone(createRunRequest);
canonicalCreateRunRequest.params.run_metadata.data = { second: 2, first: { enabled: true }, integral_float: 1.0 };
const canonicalCreateRunResponse = structuredClone(createRunResponse);
canonicalCreateRunResponse.result.run_metadata.data = { first: { enabled: true }, second: 2, integral_float: 1 };
canonicalCreateRunResponse.result.metadata_hash = 'sha256:problemforger-run-metadata-v2:99abf52f8ca513df30af599f5c82178bc909c65ef992f27675b5ed1769eed3ec';
assert.deepEqual(
  decodeResponse(encodeResponse(canonicalCreateRunResponse, canonicalCreateRunRequest), canonicalCreateRunRequest),
  canonicalCreateRunResponse,
  'create_run response accepts canonically equal metadata with reordered keys',
);

const legacyMetadataResponseJson = '{"protocol_schema_version":1,"request_id":"legacy-run","operation":"get_run","result":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"integral":1.0}},"metadata_hash":"sha256:problemforger-run-metadata-v1:a7c1e9ebc8fc5b623960ac6944f198d4666d33d6aa671e8354f928fc6c579996","graph_version":0,"last_journal_position":0,"created":false}}';
const legacyMetadataResponse = decodeResponse(legacyMetadataResponseJson);
assert.equal(legacyMetadataResponse.result.run_metadata.data.integral, 1);
for (const schemaVersionToken of ['1.0', '1e0']) {
  const legacySchemaVersionJson = legacyMetadataResponseJson.replace(
    '"metadata_schema_version":1,',
    `"metadata_schema_version":${schemaVersionToken},`,
  );
  const decodedLegacySchemaVersion = decodeResponse(legacySchemaVersionJson);
  assert.equal(decodedLegacySchemaVersion.result.run_metadata.metadata_schema_version, 1);
  assert.equal(decodedLegacySchemaVersion.result.metadata_hash, legacyMetadataResponse.result.metadata_hash);
  assert.deepEqual(
    decodeResponse(encodeResponse(decodedLegacySchemaVersion)),
    decodedLegacySchemaVersion,
    `legacy metadata hash normalizes schema version ${schemaVersionToken}`,
  );
}
const reencodedLegacyMetadata = encodeResponse(legacyMetadataResponse);
assert.match(reencodedLegacyMetadata, /"integral":1\.0/);
assert.deepEqual(decodeResponse(reencodedLegacyMetadata), legacyMetadataResponse);
assert.throws(
  () => decodeResponse(legacyMetadataResponseJson.replace('"integral":1.0', '"integral":2')),
  undefined,
  'legacy metadata hash remains bound to the original value',
);

for (const [label, enabled] of [['different metadata value', false], ['boolean and number metadata differ', 1]]) {
  const invalid = structuredClone(canonicalCreateRunResponse);
  invalid.result.run_metadata.data.first.enabled = enabled;
  assert.throws(() => encodeResponse(invalid, canonicalCreateRunRequest), undefined, label);
  assert.throws(() => decodeResponse(JSON.stringify(invalid), canonicalCreateRunRequest), undefined, `decoded ${label}`);
}

for (const field of ['graph_version', 'last_journal_position']) {
  const invalid = structuredClone(createRunResponse);
  invalid.result[field] = 1;
  assert.throws(() => encodeResponse(invalid), undefined, `new run has zero ${field}`);
  assert.throws(() => decodeResponse(JSON.stringify(invalid)), undefined, `decoded new run has zero ${field}`);
}

const getRunResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_run').message);
const invalidRunVersionPair = structuredClone(getRunResponse);
invalidRunVersionPair.result.graph_version = invalidRunVersionPair.result.last_journal_position + 1;
assert.throws(
  () => encodeResponse(invalidRunVersionPair, getRunRequest),
  undefined,
  'run graph version cannot exceed its journal position',
);
assert.throws(
  () => decodeResponse(JSON.stringify(invalidRunVersionPair), getRunRequest),
  undefined,
  'decoded run graph version cannot exceed its journal position',
);

const createdByGetRun = structuredClone(getRunResponse);
Object.assign(createdByGetRun.result, { created: true, graph_version: 0, last_journal_position: 0 });
assert.throws(
  () => encodeResponse(createdByGetRun, getRunRequest),
  undefined,
  'get_run response cannot claim it created the run',
);
assert.throws(
  () => decodeResponse(JSON.stringify(createdByGetRun), getRunRequest),
  undefined,
  'decoded get_run response cannot claim it created the run',
);

assert.throws(
  () => encodeResponse(createRunResponse, { ...createRunRequest, request_id: 'another-request' }),
  undefined,
  'create_run response must match request id',
);
assert.throws(
  () => encodeResponse(createRunResponse, { ...createRunRequest, operation: 'get_run', params: { run_id: 'run-1' } }),
  undefined,
  'create_run response must match request operation',
);
assert.throws(
  () => encodeResponse(createRunResponse, { ...createRunRequest, params: { ...createRunRequest.params, run_id: 'another-run' } }),
  undefined,
  'create_run response must match request run id',
);
const proposalResponse = structuredClone(fixture.responses.find(({ label }) => label === 'propose_mutation_pending').message);
const proposalRequest = structuredClone(fixture.requests.find(({ label }) => label === 'propose_mutation').message);
assert.throws(
  () => encodeResponse(proposalResponse, { ...proposalRequest, params: { ...proposalRequest.params, proposal_id: 'another-proposal' } }),
  undefined,
  'proposal response must match request proposal id',
);
proposalRequest.params.expected_graph_version = 2;
const commitResponse = structuredClone(fixture.responses.find(({ label }) => label === 'get_proposal_commit').message);
commitResponse.request_id = proposalRequest.request_id;
commitResponse.operation = 'propose_mutation';
commitResponse.result.proposal_id = proposalRequest.params.proposal_id;

for (const [label, status, reasonCode, resultingVersion] of [
  ['commit advances more than once', 'COMMIT', null, 4],
  ['reject advances graph', 'REJECT', 'POLICY_REJECTED', 3],
  ['conflict has no version mismatch', 'CONFLICT', 'VERSION_CONFLICT', 2],
]) {
  const invalid = structuredClone(commitResponse);
  Object.assign(invalid.result, { status, reason_code: reasonCode, resulting_graph_version: resultingVersion });
  assert.throws(() => encodeResponse(invalid, proposalRequest), undefined, label);
  assert.throws(() => decodeResponse(JSON.stringify(invalid), proposalRequest), undefined, `decoded ${label}`);
}

for (const [status, reasonCode, resultingVersion] of [
  ['COMMIT', null, 3],
  ['REJECT', 'POLICY_REJECTED', 2],
  ['RETRY', 'RETRY_REQUESTED', 2],
  ['ESCALATE', 'ESCALATION_REQUIRED', 2],
  ['CONFLICT', 'VERSION_CONFLICT', 3],
]) {
  const valid = structuredClone(commitResponse);
  Object.assign(valid.result, { status, reason_code: reasonCode, resulting_graph_version: resultingVersion });
  assert.deepEqual(decodeResponse(encodeResponse(valid, proposalRequest), proposalRequest), valid, `${status} version relationship`);
}

const committedWithReason = structuredClone(commitResponse);
committedWithReason.result.reason_code = 'all_checks_passed';
assert.deepEqual(
  decodeResponse(encodeResponse(committedWithReason, proposalRequest), proposalRequest),
  committedWithReason,
  'committed proposal accepts an optional reason code',
);
const errorResponse = structuredClone(fixture.responses.find(({ label }) => label === 'unknown_run').message);
assert.throws(
  () => encodeResponse(errorResponse, { ...createRunRequest, request_id: 'another-request' }),
  undefined,
  'error response must match request id',
);

const beforeCursorResponse = structuredClone(auditResponse);
beforeCursorResponse.result.records[0].journal_position = 1;
beforeCursorResponse.result.next_after_journal_position = 2;
assert.throws(
  () => encodeResponse(beforeCursorResponse, { ...auditRequest, params: { ...auditRequest.params, after_journal_position: 1 } }),
  undefined,
  'audit records must be after the supplied cursor',
);
