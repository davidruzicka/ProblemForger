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
