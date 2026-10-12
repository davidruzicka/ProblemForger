# ADR 0010: Use a Unix-domain socket for the local service transport

- Status: Accepted
- Date: 2026-10-11

[ADR 0011](0011-claude-code-plugin-harness.md) replaces the Pi target with
Claude Code. Its MCP bridge uses this worker socket; the transport decision
and the spike evidence below remain in force.

## Context

ADR 0009 requires HarnessX and Pi to use the same local Python service boundary,
but leaves the transport open. Issue #19 calls for a bounded comparison of
Python and TypeScript clients, bounded versioned messages, observation streaming,
failure behavior, local overhead, and the local evidence-trust boundary.

The spike compares HTTP/1.1 with JSON and Server-Sent Events on loopback against
JSON Lines over a Unix-domain stream socket. Both implement the same versioned
request/response envelope and worker method allowlist. A Python and TypeScript
client exercise both candidates.

## Decision

For the initial Linux deployment, use a Unix-domain stream socket carrying
UTF-8 JSON Lines for the local worker service. Keep application request,
response, and observation types independent of the transport. Use a versioned
envelope and cap each encoded request and response frame at 4 MiB.

Deploy the service under its own unprivileged UID. Place the worker socket in a
service-owned directory whose group permissions grant access to the worker
group; keep the journal, ownership lock, policy, and producer credentials in a
private service directory. Expose only worker methods through this socket.
Trusted evidence ingestion and administrative operations remain outside the
worker capability.

Client deadlines stop waiting for a response; they do not imply rollback of a
sent mutation. A future mutation retry must use the same `(run_id, proposal_id)`
and request hash so the durable receipt can resolve an uncertain outcome. A
supervisor owns process startup and shutdown, detects early process failure, and
removes stale socket paths only after confirming the old service has stopped.
Observation events are JSONL frames followed by a final response frame.

## Evidence

GitHub Actions run #212 on Ubuntu 24.04, with Python 3.12.3 and TCP_NODELAY
enabled on both HTTP peers, measured warm echo round trips and JSON cost as
follows:

| Measurement | HTTP loopback | JSONL over Unix socket |
| --- | ---: | ---: |
| Startup (ms) | 63.814 | 63.346 |
| 256-byte round trip p50 / p95 (ms) | 0.208 / 0.227 | 0.076 / 0.111 |
| 64-KiB round trip p50 / p95 (ms) | 0.756 / 0.774 | 0.723 / 0.793 |
| 64-KiB JSON encode/decode (ms) | 0.253 | 0.254 |

The run passed all 299 Python tests with 92% total coverage, including Python
and TypeScript client paths, streaming, invalid and oversized messages, timeout
configuration, process failure, and the Linux permission demonstration. That
demonstration ran the service as UID 65534 and the worker as UID 65533; the
worker could use the worker socket but could not reach the admin path, invoke
admin/store methods, or read or change four protected sentinel files.

The benchmark is a single shared CI runner observation, not an application
latency or throughput claim. Startup and JSON costs are effectively the same;
Unix sockets were faster in the small-request sample, while large-request p95
was 0.019 ms slower. Both candidates remain technically viable.

## Alternatives considered

### HTTP/1.1 with JSON and Server-Sent Events

HTTP has familiar Python and TypeScript clients and a natural event-streaming
format. It is a credible option if a later observer or remote client needs an
HTTP endpoint. On loopback, however, the server cannot identify the worker
process from the connection. A production local HTTP deployment would need a
separate worker-only capability and caller-to-run authorization mechanism.
The spike did not implement or measure that additional mechanism.

### JSON Lines over a Unix-domain socket

This requires a small framing/client implementation, but supports both Python
and TypeScript with standard libraries, streams observation frames, and uses
filesystem permissions to grant local socket access. The Linux demonstration
verified this with separate service and worker UIDs while keeping service state
inaccessible to the worker.

## Consequences

- The initial worker boundary gets a local OS-enforced socket capability and
  avoids adding a caller token to the prototype.
- The wire format and application contract remain transport-neutral; a later
  HTTP adapter can reuse them if remote clients become necessary.
- macOS supports the socket APIs, but this spike has only been exercised in
  Linux CI. Windows has OS-level `AF_UNIX` support, while Python's asyncio
  Unix-socket server APIs are Unix-only and Node uses named pipes for Windows
  IPC. Windows support is deferred; it would need a platform adapter plus a
  Windows ACL isolation design. The POSIX UID/group permission proof does not
  establish that boundary.
- Remote deployment requires a separate transport and security decision.
- The demonstration does not claim isolation from a worker with unrestricted
  host privileges. Production authentication/TLS, remote deployment, and the
  full graph API remain out of scope.
