# Architecture

## Boundaries

```text
Harness
  |
  v
Harness adapter
  |
  v
ProblemForger protocol
  |
  v
+----------------------- Core -----------------------+
|                                                     |
| ProblemGraph -> Governor -> decisions               |
|      ^             ^                                |
|      |             +-- evidence/verifier ports      |
|      |                                              |
|      +-- event store / snapshot ports               |
|                                                     |
| module/config registry supplies port implementations|
+-----------------------------------------------------+
```

The worker/harness may propose changes. It does not own authoritative graph state.

## Layers

### Domain/core

Contains:

- graph domain types;
- graph mutation semantics;
- lifecycle and provenance;
- governance policy interfaces;
- event definitions;
- pure replay/projection logic.

It must not depend on SQLite, PostgreSQL, a specific model API, HarnessX, Pi, a UI framework, or provider-specific settings.

### Ports

Stable contracts for replaceable capabilities. Likely ports include:

- `EventStore`;
- `SnapshotStore` when needed;
- `Verifier`;
- `Calibrator`;
- `ModelProvider`;
- `ModelSuitabilityEstimator`;
- `ContextSelector`;
- `TelemetrySink`;
- `ArtifactStore`;
- `Clock` / ID generation where determinism matters.

A port is introduced only when there is a real replaceable policy/infrastructure boundary.

### Modules/adapters

Concrete implementations of ports:

- event store: memory, SQLite, later PostgreSQL;
- verifier: deterministic composition, LLM judge, learned model;
- telemetry: JSONL, OpenTelemetry or another sink;
- harness integration: HarnessX, Pi.

Provider-specific configuration belongs to the provider module.

### Configuration/module loader

A typed loader maps a capability + provider name to a validated provider configuration and factory.

Example:

```yaml
modules:
  event_store:
    provider: sqlite
    config:
      path: .problemforger/events.db

  telemetry:
    provider: jsonl
    config:
      path: .problemforger/events.jsonl
```

Core code receives an implementation of a port, never raw provider configuration.

## Event sourcing

The event log is authoritative. Current graph state is a projection.

```text
G_t = fold(events[0:t])
```

This provides:

- replay;
- provenance;
- time travel;
- graph diffs;
- reproducible training examples;
- later invalidation without rewriting history.

Snapshots may be added as an optimization but may not become the source of truth.

## Graph governor

The governor evaluates proposed mutations using:

1. schema and deterministic graph invariants;
2. deterministic/external evidence;
3. learned or LLM verification when necessary;
4. policy and uncertainty.

Possible decisions:

- commit;
- reject;
- retry;
- escalate.

## Harness adapters

Adapters normalize harness-specific lifecycle/events into ProblemForger concepts and translate decisions back.

Adapters should declare capabilities such as:

- can block tool call;
- can inject context;
- can replace model;
- can pause/resume;
- can render native status UI.

The core must not assume the least-common-denominator behavior of every harness.

## UI

UI consumes events/projections and is outside the correctness path. Native harness UI may expose a compact status. A later web observer may provide full provenance and timeline inspection.
