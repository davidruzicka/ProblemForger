# P1.6 local transport spike

Status: bounded comparison in progress. This spike does not add a production
service or graph API. It compares two standard-library paths around the same
versioned echo/observation contract:

1. HTTP/1.1 with JSON over `127.0.0.1`; observations use Server-Sent Events.
2. JSON Lines over a Unix-domain stream socket; observations use event frames.

Both paths have Python and TypeScript clients, reject unknown worker methods,
and cap each encoded request/response message at 4 MiB. The cap matches the
current EventStore atomic-batch bound; larger evidence belongs in immutable
references. HTTP requires `Content-Length`; chunked request bodies are rejected.

## Contract checks

| Criterion | HTTP loopback | JSONL over Unix socket |
| --- | --- | --- |
| Versioned request/response | JSON envelope with `protocol_version: 1` | Same envelope, one newline-delimited frame |
| Python client | `http.client` | `socket` |
| TypeScript client | built-in `fetch` | built-in `node:net` |
| Observation stream | SSE event blocks | JSONL event frames before the final response |
| Timeout | Python socket timeout; TypeScript `AbortSignal.timeout` | Python socket timeout; TypeScript client deadline |
| Cancellation | Client stops waiting; a sent mutation remains outcome-unknown until retried with its same proposal ID | Same; closing the local socket stops the client wait but does not roll back a sent mutation |
| Process failure | Connection refusal/reset | Missing socket or connection reset |
| Local access control | Loopback has no filesystem ACL; a caller capability would be required | Socket path permissions can grant the worker group access while keeping service files private |

HTTP's loopback bind does not identify the worker process. A real HTTP service
would still need a worker-only capability for caller-to-run authorization; the
spike intentionally does not add or pass such a credential. The Unix socket
path supplies an OS-checked local capability in the selected deployment model.

The spike has no mutation method, EventStore, policy configuration, or producer
credentials. It is not a substitute for the P1 application protocol. A timeout
after sending a future mutation must use the same `(run_id, proposal_id)` and
request hash so the durable receipt resolves an uncertain outcome; client
cancellation never means mutation rollback. See
[`PROPOSAL-RECOVERY`](../../docs/protocol.md#spec-protocol-proposal-recovery).

The Unix service refuses an existing socket path rather than unlinking it
blindly. An owner-aware supervisor must confirm the old service is stopped
before removing a stale path after a forced kill.

## Trust-boundary demonstration

`security_demo.py` runs a non-root service as UID 65534 and a worker as UID
65533. The worker group receives access to only the worker socket (mode `0660`);
the socket directory is `0710`; service data and four sentinel files are
`0700`/`0600`. The worker sends evidence-ingest, policy-update, journal,
ownership-lock, and credential requests; each must return `METHOD_NOT_FOUND`.
It then attempts direct reads and writes and a connection to a private admin
path; OS permissions deny all attempts and the sentinel bytes must remain
unchanged.

Run on Linux as root, or through the test suite with passwordless `sudo`:

```sh
sudo -n python3 spikes/transport/security_demo.py
```

This demonstrates the transport capability plus a separate service UID and
worker UID. A worker with unrestricted host/root privileges remains outside the
threat model. Production authentication/TLS and remote deployment are out of
scope.

## Reproduction

Python 3.12+ is required. The no-dependency TypeScript client uses Node.js
22.6+ type stripping; the repository's normal Node checks retain their existing
Node 18+ requirement.

```sh
python3 -m unittest discover -s tests -p 'test_transport_spike.py' -v
python3 -m spikes.transport.transport_spike bench --iterations 500 --large-iterations 30
```

The benchmark reports server startup, warm p50/p95 round trips for 256-byte
and 64-KiB payloads, and JSON encode/decode time for the 64-KiB payload. It
prints Python and platform details. These are loopback/Unix-socket echo
measurements on one runner, not application latency or a production capacity
claim. Results are informational; tests assert correctness, not a performance
threshold.

Manual TypeScript smoke checks against running servers:

```sh
python3 -m spikes.transport.transport_spike serve-http --port 8765
node --experimental-strip-types spikes/transport/client.ts http http://127.0.0.1:8765 256 echo
```

```sh
python3 -m spikes.transport.transport_spike serve-unix --socket /tmp/pf-worker.sock --socket-mode 660
node --experimental-strip-types spikes/transport/client.ts unix /tmp/pf-worker.sock 256 stream_observations
```

The Python tests exercise both clients and streams. The CI test prints the
measured table; copy those exact results into the transport decision record
before accepting an ADR. HTTP and UDS JSONL remain technically viable; the
security and measured-latency evidence should drive the final choice.
