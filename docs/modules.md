# Ports, adapters, and configuration-driven modules

## Decision

Replaceable infrastructure and policies are modules behind stable APIs/ports. Concrete implementations are selected by typed configuration and assembled at one composition root.

SQLite and in-memory persistence are the initial `EventStore` providers. They are ordinary adapters behind the same contract; future PostgreSQL or remote implementations must not require graph-domain changes.

See ADR 0003 and ADR 0006.

## Goals

- replace infrastructure without changing domain semantics;
- keep provider-specific dependencies and configuration isolated;
- support provider-independent contract tests;
- record effective experiment configuration with secrets redacted;
- avoid coupling the core to HarnessX, Pi, SQLite, PostgreSQL, or a model vendor.

## Non-goals

The PoC does not need:

- a generic third-party plugin ecosystem;
- arbitrary Python imports/classes named in configuration;
- dynamic package discovery;
- a provider abstraction for capabilities that are not yet part of the core.

Use an explicit typed registry/factory until a real use case justifies something more dynamic.

## Initial ports

P1 should define only capabilities already required by the PoC architecture:

### EventStore

Owns persistence of authoritative run-scoped domain-event streams.

Conceptual contract:

```text
append(stream_id, expected_version, events[])
    -> new_version
    | VersionConflict

read(stream_id, after_version?)
    -> ordered domain events

current_version(stream_id)
    -> version
```

Requirements:

- compare-and-append is atomic;
- multiple events emitted by one accepted mutation are committed atomically;
- event order is stable within a run stream;
- no global ordering across runs is required;
- stored payload/schema metadata is sufficient for deterministic replay;
- append-only history is never rewritten by later invalidation.

The in-memory provider is introduced in P1. SQLite follows in P2 and must pass the same contract suite.

### TelemetrySink

Receives non-authoritative observations such as harness/model/tool events, cost/latency measurements, and diagnostics.

Telemetry:

- may reference domain events through correlation/causation IDs;
- does not increment graph version;
- is not required to reconstruct graph state;
- can be disabled without changing domain correctness.

A recording/in-memory or JSONL sink may be used initially.

### Clock / ID source

Inject only where deterministic tests or reproducibility require it. Do not introduce a general service-locator abstraction.

## Deferred ports

Introduce these only in the phase that requires them:

- `Verifier` — P7;
- `Calibrator` — P8;
- `ModelSuitabilityEstimator` — P9;
- `SnapshotStore` — only if replay cost demonstrates need;
- `ArtifactStore` — only if artifacts cannot remain stable external references.

Do not introduce `ModelProvider` in the initial core: model inference belongs to the harness. Do not introduce `ContextSelector` in P1: the first PoC uses explicit graph queries.

## Illustrative layout

```text
src/problemforger/
  core/
    graph/
    governance/
    events/
  application/
    commands/
    queries/
  ports/
    event_store.py
    telemetry.py
  modules/
    persistence/
      memory/
      sqlite/            # P2
      postgres/          # later
    telemetry/
  config/
    models.py
    registry.py
    loader.py
  service/
    ...
```

Harness clients/adapters may live in this repository or separate packages, but they consume the public service protocol rather than importing provider modules.

The final package layout may differ. Dependency direction must remain equivalent.

## Configuration model

Configuration has its own schema version.

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

Rules:

- unknown capability/provider names fail explicitly;
- provider configuration is validated before construction;
- a provider receives only its own typed config;
- provider-specific settings do not appear in domain types;
- secrets are never serialized into graph/domain events;
- effective experiment configuration can be exported with secrets redacted;
- provider creation is centralized in the composition root;
- core modules receive constructed port implementations via explicit dependency injection.

## Provider registry

Prefer a small explicit registry, conceptually:

```text
(event_store, memory) -> MemoryEventStoreConfig -> factory
(event_store, sqlite) -> SqliteEventStoreConfig -> factory
(telemetry, null)     -> NullTelemetryConfig -> factory
```

The registry itself belongs to application/configuration wiring, not domain code.

## Contract testing

Every provider of the same port runs the same behavioral contract suite.

For `EventStore`, tests must cover at least:

- empty stream/version semantics;
- ordered append/read;
- atomic multi-event append;
- stale `expected_version` conflict;
- failed append leaves stream unchanged;
- independent run streams;
- byte/semantic fidelity sufficient for deterministic replay.

Provider-specific tests may add performance/error cases but cannot replace the common contract suite.
