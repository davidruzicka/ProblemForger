import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { encodeRequest, decodeRequest, encodeResponse, decodeResponse } from '../clients/typescript/protocol.ts';

const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'));
for (const { label, kind, message, request, valid } of cases) {
  const encode = () => kind === 'request' ? encodeRequest(message) : encodeResponse(message, request ?? undefined);
  const decode = () => kind === 'request' ? decodeRequest(JSON.stringify(message)) : decodeResponse(JSON.stringify(message), request ?? undefined);
  if (valid) {
    assert.doesNotThrow(encode, `${label}: encode`);
    assert.deepEqual(decode(), message, `${label}: decode`);
  } else {
    assert.throws(encode, TypeError, `${label}: encode`);
    assert.throws(decode, TypeError, `${label}: decode`);
  }
}
