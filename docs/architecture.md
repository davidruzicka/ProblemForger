# Architecture

## Boundaries

```text
Agent harness (HarnessX / Pi / ...)
            |
       thin adapter
            |
   versioned service protocol
            |
    ProblemForger process
            |
  +---------+------------------------------+
  |                                        |
  | application API                       | observation API
  |                                        |
  v                                        v
ProblemGraph -> Governor -> domain events   TelemetrySink
     ^             |
     |             +-- evidence / verifier ports
     |
     +-- EventStore port
```

The worker/harness may propose changes. It does not own authoritative graph state.

ProblemForger runs as a separate local process/service for the PoC. HarnessX and Pi use thin clients/adapters against the same service contract. This preserves a symmetric integration boundary even though HarnessX and the core are both Python.

## Two event planes

ProblemForger explicitly separates:

### Authoritative domain events

Domain events reconstruct the ProblemGraph and increment the graph stream version. Examples include committed node/edge changes, invalidations, and accepted evidence attachments.

They are persisted through `EventStore`.

### Observation/telemetry events

Harness lifecycle events, model calls, tool calls, token/cost measurements, and adapter diagnostics are useful for evaluation and UI, but they do **not** define authoritative graph state and do not increment graph version.

They flow through `TelemetrySink` and may reference domain events through correlation/causation identifiers.

A domain event may also be mirrored to telemetry for observability, but telemetry must never become required for graph replay.

See ADR 0006.

## Layers

### Domain/core

Contains:

- graph domain types;
- graph mutation semantics;
- entity lifecycle and provenance;
- governance policy interfaces;
- authoritative domain event definitions;
- pure replay/projection logic.

It must not depend on SQLite, PostgreSQL, a specific model API, HarnessX, Pi, a UI framework, or provider-specific settings.

The core also does **not** own model inference in the initial PoC. Model execution remains a harness responsibility. Later routing asks the harness to select a model; it does not move inference into the core.

### Application API

The application layer exposes harness-neutral commands and queries such as:

- create/start a ProblemForger run;
- query graph state or a bounded subgraph;
- propose a graph mutation against an expected graph version;
- attach/reference evidence;
- retrieve governor decisions and current graph version.

The initial agent interaction uses this explicit API/tool surface rather than automatic full-graph prompt injection. This avoids introducing a context-selection subsystem before the graph/governance hypotheses have been tested.

See ADR 0008.

### Ports

Introduce a port only when there is a real replaceable policy or infrastructure boundary.

Initial ports:

- `EventStore`;
- `TelemetrySink`;
- deterministic `Clock` / ID source only where tests or replay require injection.

Later phases may introduce:

- `Verifier`;
- `Calibrator`;
- `ModelSuitabilityEstimator`;
- `ArtifactStore` if artifacts cannot remain external references;
- `SnapshotStore` if replay performance demonstrates a need.

Do not add `ModelProvider` or `ContextSelector` to the initial core. The harness already owns model execution, and the initial PoC uses explicit graph queries instead of automatic context selection.

### Modules/adapters

Concrete implementations of ports include:

- event store: memory, SQLite, later PostgreSQL;
- telemetry: null/recording/JSONL or another sink;
- verifier: later LLM judge or learned model;
- calibration/routing: later experimental modules.

Harness integrations are adapters to the service protocol, not provider modules inside the core.

Provider-specific configuration belongs to the provider module.

### Composition root and configuration

A typed loader maps a capability + provider name to validated provider configuration and an explicit factory/registry entry.

Example:

```yaml
schema_version: 1

modules:
  event_store:
    provider: sqlite
    config:
      path: .problemforger/events.db

  telemetry:
    provider: jsonl
    config:
      path: .problemforger/telemetry.jsonl
```

Core code receives implementations of ports, never raw provider configuration.

Provider lookup is explicit. The PoC does not dynamically import arbitrary classes from configuration strings.

## Event sourcing

The authoritative graph stream is run-scoped. Current graph state is a projection:

```text
G_v = fold(domain_events[0:v])
```

A mutation is committed with optimistic compare-and-append semantics:

```text
append(expected_version=v, events=[...])
    -> new_version
    OR VersionConflict
```

One accepted mutation may emit multiple domain events, which must be appended atomically. Observation/telemetry events do not participate in `v`.

There is no requirement for a global event order across runs.

Snapshots may be added later as a derived optimization but may not become the source of truth.

See ADR 0006.

## Graph governor

The governor evaluates proposed mutations using:

1. schema and deterministic graph invariants;
2. relevant deterministic or externally observed evidence;
3. later, learned/LLM verification when necessary;
4. policy and uncertainty.

Possible outcomes are:

- commit;
- reject;
- retry;
- escalate;
- conflict when the proposal is based on a stale graph version.

For the initial ablation:

- configuration **B** exposes the explicit graph API with only schema/version/invariant checks required for a valid graph;
- configuration **C** uses the same API and prompt surface but adds deterministic governance/evidence policy.

This makes B→C the cleanest early estimate of governance contribution.

## Harness adapters

Adapters:

- register or expose ProblemForger graph tools/commands to the worker;
- normalize relevant harness observations into telemetry;
- translate governor outcomes into harness actions;
- declare capabilities.

Candidate capabilities include:

- can block tool call;
- can inject context;
- can replace model;
- can pause/resume;
- can render native status UI.

Adapters must not contain graph/governance policy.

HarnessX currently exposes composable processors/event middleware and model/harness separation. Pi exposes TypeScript extensions with lifecycle/tool interception and custom TUI support. Exact capabilities are re-audited at their pinned revisions when P4/P5 begin.

## Runtime language

- ProblemForger core/service: Python 3.12+.
- HarnessX adapter: Python client/processor.
- Pi adapter: TypeScript extension/client.

The transport is intentionally left for a bounded P1 decision. Changing transport must not change the domain/application protocol.

See ADR 0009.

## UI

UI consumes observation events and graph projections and is outside the correctness path. Native harness UI may expose compact status. A later web observer may provide full provenance and timeline inspection.
