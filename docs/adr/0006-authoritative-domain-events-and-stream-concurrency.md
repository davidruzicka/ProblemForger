# ADR 0006: Separate authoritative domain events from observations and use optimistic run-scoped streams

- Status: Accepted
- Date: 2026-09-18

## Context

The bootstrap design listed graph mutations, model calls, tool calls, and harness lifecycle events together. If all of these increment graph version or are required for replay, authoritative state becomes coupled to harness implementation details.

Parallel workers also need a clear conflict model.

## Decision

Each ProblemForger run owns one authoritative domain-event stream.

Only committed domain changes appear in that stream and increment its monotonically increasing graph version.

Harness/model/tool lifecycle information is observation telemetry. It may reference domain events but is not required to reconstruct the graph.

The EventStore contract uses optimistic compare-and-append:

```text
append(stream_id, expected_version, events[])
  -> new_version
  OR VersionConflict
```

All events emitted for one accepted mutation are appended atomically.

There is no required global order across independent run streams.

## Consequences

- Graph replay is independent of harness telemetry completeness.
- Tool/model events cannot accidentally create graph-version conflicts.
- In-memory, SQLite, and future stores share the same concurrency contract.
- Future parallel workers can detect stale proposals.
- The PoC may serialize actual commits internally while retaining the optimistic API.
