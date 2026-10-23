# Local service smoke test

The P1 service is a separate Python process with one SQLite EventStore owner.
Workers use the closed v1 protocol over JSON Lines on a Unix-domain stream
socket. The worker API contains only run registration, graph/proposal queries,
mutation proposals, proposal status, and public audit timeline reads. There is
no worker-facing administration or trusted evidence-ingestion operation.

P1 does not implement a graph governor. The service returns a durable `REJECT`
for each otherwise valid proposal with reason code
`P1_GOVERNANCE_NOT_IMPLEMENTED`; stale expected graph versions are durably
recorded as `CONFLICT`. Neither outcome changes the graph version. Receipts
retain the submitted normalized operations and evidence. Public proposal and
audit responses expose status and record metadata, not that private content.

## Start locally

From the repository root, install the package and create the private local
state directory:

```sh
python3 -m pip install -e .
mkdir -p .local .run
chmod 700 .local .run
```

The redacted example uses SQLite and disables optional telemetry:

```sh
python3 -m problemforger.service \
  --config examples/service-config.json \
  --socket .run/worker.sock
```

The process prints one JSON readiness line after it owns the SQLite store and
creates the socket. The default socket mode is `0600`. A supervisor can pass
`--socket-mode 0660` when the socket directory is service-owned, has the worker
group as its group, grants that group execute but not write access, and has no
group/world write permission. The socket inherits that directory group.
Existing socket paths are never removed automatically; the supervisor must
confirm the prior process stopped before removing a stale socket.

Use Ctrl-C or send `SIGTERM` for graceful shutdown. The service closes active
connections and providers, then removes only the socket inode it created.

## Python worker call

```python
from problemforger.service.client import ServiceClient

client = ServiceClient(".run/worker.sock", timeout_seconds=5)
response = client.call({
    "protocol_schema_version": 1,
    "request_id": "register-example",
    "operation": "create_run",
    "params": {
        "run_id": "example-run",
        "run_metadata": {
            "metadata_schema_version": 1,
            "data": {"purpose": "local smoke test"},
        },
    },
})
```

The TypeScript counterpart is `clients/typescript/service_client.ts`; it uses
the same generated protocol codec and operation contract. Both clients report
service unavailability separately from deadline expiry. A timed-out mutation
may already have a durable receipt, so retry it with the same `run_id`,
`proposal_id`, and normalized request content.

## Verify

Run the repository checks in [Specification ownership and checks](specification-checks.md#run-checks).
The service process tests cover Python and TypeScript clients, a lost response
followed by restart and same-ID replay, restart recovery from a SQLite receipt
left by an abruptly terminated process, memory-store rejection in the normal
profile, and durable audit with telemetry disabled. They require Linux Unix
sockets and Node.js 22.6 or newer.

On Linux, run the privilege-boundary demonstration as root (or through
passwordless `sudo`) to start separate service and worker UIDs:

```sh
python3 -m unittest tests.test_service_security -v
```

It checks that a worker can use the socket's worker methods, that an
administrative operation is rejected by the closed protocol, and that the
worker cannot access the private database, lock, configuration, policy, or
credential files.
