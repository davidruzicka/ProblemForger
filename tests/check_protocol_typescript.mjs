import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { decodeRequest, decodeResponse, encodeRequest, encodeResponse } from '../clients/typescript/protocol.ts';

const fixture = JSON.parse(await readFile(process.argv[2], 'utf8'));

for (const { label, message } of fixture.requests) {
  assert.deepEqual(decodeRequest(encodeRequest(message)), message, `${label} request`);
}
for (const { label, message } of fixture.responses) {
  assert.deepEqual(decodeResponse(encodeResponse(message)), message, `${label} response`);
}
for (const { label, message } of fixture.invalid_requests) {
  assert.throws(() => encodeRequest(message), undefined, `${label} request`);
}
for (const { label, message } of fixture.invalid_responses) {
  assert.throws(() => encodeResponse(message), undefined, `${label} response`);
}

const createRun = structuredClone(fixture.requests.find(({ label }) => label === 'create_run').message);
createRun.params.run_metadata.data.large = 'é'.repeat(512 * 1024);
assert.throws(() => encodeRequest(createRun), undefined, 'run metadata over 1 MiB');

const mutation = structuredClone(fixture.requests.find(({ label }) => label === 'propose_mutation').message);
mutation.params.operations = [{ payload: 'x'.repeat(1024 * 1024) }];
assert.throws(() => encodeRequest(mutation), undefined, 'normalized mutation over 1 MiB');

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

const beforeCursorResponse = structuredClone(auditResponse);
beforeCursorResponse.result.records[0].journal_position = 1;
beforeCursorResponse.result.next_after_journal_position = 2;
assert.throws(
  () => encodeResponse(beforeCursorResponse, { ...auditRequest, params: { ...auditRequest.params, after_journal_position: 1 } }),
  undefined,
  'audit records must be after the supplied cursor',
);
