# Harness-neutral protocol

## Purpose

HarnessX and Pi must use the same ProblemForger core/service. Their adapters translate native lifecycle events and agent tool calls into a stable, versioned protocol.

The protocol is independent from provider implementations and from the transport used to carry it.

## Protocol planes

Do not put every harness event into the authoritative graph stream.

### Command/query plane

Used by the harness/worker to interact with ProblemForger.

Initial operations should cover:

- start/create a run;
- get run metadata and current graph version;
- query graph state or a bounded subgraph;
- propose a graph mutation against `expected_version`;
- attach/reference evidence through a governed mutation;
- retrieve the resulting governor decision.

The exact wire schema is finalized in P1.

### Observation plane

Used for non-authoritative harness telemetry such as:

- run start/end;
- model call requested/completed;
- tool call requested/completed;
- token/cost/latency measurements;
- adapter diagnostics.

Observation events may be stored/exported for evaluation and UI, but they do not alter graph state or graph version.

### Authoritative domain events

Committed graph changes are emitted by ProblemForger itself after successful governance and `EventStore` append.

Examples:

- node committed;
- edge committed;
- evidence attached;
- entity invalidated/superseded.

Harnesses do not submit authoritative domain events directly.

See ADR 0006.

## Decisions

A mutation request can yield outcomes such as:

- `COMMIT`;
- `REJECT`;
- `RETRY`;
- `ESCALATE`;
- `CONFLICT`.

Harness-specific actions such as blocking a tool call are adapter behavior derived from these decisions; they are not themselves graph semantics.

## Harness capabilities

An adapter declares capabilities independently from normalized events, for example:

- `can_block_tool_call`;
- `can_inject_context`;
- `can_replace_model`;
- `can_pause`;
- `can_resume`;
- `can_render_native_ui`.

This prevents the protocol from collapsing to the least-capable harness.

## Initial graph tool surface

For the first A/B/C ablation, adapters should expose the same ProblemForger graph interaction surface in B and C.

Conceptually:

```text
get_graph(...)
propose_mutation(expected_version, operations, evidence_refs)
```

The exact tool names are harness-specific and are not part of the domain protocol.

Configuration B commits proposals after schema/version/core-invariant checks only.

Configuration C uses the same tool/API/prompt surface but additionally applies deterministic governance/evidence policy.

This design minimizes B→C confounding.

## Service boundary

ProblemForger runs as a separate local process/service during the PoC.

Reasons:

- Pi is TypeScript while the core is Python;
- HarnessX is Python, but using the same process boundary keeps the two integrations structurally comparable;
- the core can evolve independently from harness runtime dependencies;
- observer/UI clients can later consume the same public boundary.

See ADR 0009.

## Transport

P1 must choose and document the smallest local transport satisfying:

- practical Python and TypeScript clients;
- request/response commands and queries;
- versioned typed messages;
- cancellation/timeouts;
- bounded payloads;
- clear process lifecycle and error semantics;
- future observation streaming without changing domain contracts.

Candidates may include local HTTP or a framed/line-oriented RPC protocol. The choice must be captured in an ADR after a small implementation spike.

Transport is replaceable; protocol semantics are not transport-specific.

## Versioning

At minimum distinguish:

- protocol schema version;
- domain event schema version;
- module configuration schema version.

Backward-compatibility policy is intentionally narrow during early PoC development: migrations may be breaking before the first public release, but stored event streams used for experiments must remain replayable by the code/version that produced them and carry enough version metadata to identify that code path.
