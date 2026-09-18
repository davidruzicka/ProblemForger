# Ports, adapters, and configuration-driven modules

## Decision

Replaceable infrastructure and policies are modules behind stable APIs/ports. Concrete implementations are selected by typed configuration and assembled at one composition root.

SQLite and in-memory persistence are the initial `EventStore` providers behind the same port, but they have different durability capabilities. `MemoryEventStore` is explicitly ephemeral/test-only; SQLite is the first durable service provider. Future PostgreSQL or remote implementations must not require graph-domain changes.

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

Owns persistence of each run's durable journal: governance audit records plus graph-changing domain events.

Conceptual contract:

```text
record_proposal(stream_id, proposal_id, request_hash, receipt_record)
    -> CREATED
    | EXISTING {request_hash, status, last_journal_position}

append_audit(stream_id, records[])
    -> last_journal_position

append_graph(stream_id, expected_graph_version, audit_records[], graph_events[])
    -> {last_journal_position, new_graph_version}
    | VersionConflict

read_journal(stream_id, after_journal_position?)
    -> ordered durable records

current_graph_version(stream_id)
    -> graph_version
```

Requirements:

- `proposal_id` is unique within a run and claimed atomically with its canonical request hash;
- duplicate same-ID/same-hash submissions resolve to the existing proposal state/outcome, never a second mutation;
- duplicate same-ID/different-hash submissions are detectable as idempotency conflicts;
- every durable record has a monotonic per-run `journal_position`;
- every graph-changing event carries a `graph_version`, but one atomic committed mutation batch advances the version only once;
- all graph events in the same mutation batch share the same resulting `graph_version`;
- audit-only records never advance `graph_version`;
- graph compare-and-append is atomic;
- a successful `COMMIT` persists its final decision audit record and all graph-changing events atomically, with one new graph version assigned to the complete batch;
- `REJECT`, `RETRY`, `ESCALATE`, and returned `CONFLICT` outcomes are durably recorded before the service response completes;
- proposal receipt is durable, so crashes can leave an explicit incomplete proposal rather than erasing history;
- journal order is stable within a run;
- no global ordering across runs is required;
- stored payload/schema metadata is sufficient for deterministic graph replay and governance audit;
- append-only history is never rewritten by later invalidation.

Both providers are introduced in P1. `MemoryEventStore` exists for fast unit/contract tests and explicit ephemeral test harnesses only; it must not be used by the normal ProblemForger service where ADR 0006 promises restart durability. The composition root must reject an ephemeral EventStore for a normal service profile. SQLite is the first durable provider and must preserve the journal across close/reopen and process restart.

### TelemetrySink

Receives non-authoritative observations such as harness/model/tool events, cost/latency measurements, and diagnostics.

Telemetry:

- may reference durable journal records through correlation/causation IDs;
- does not increment graph version;
- is not required to reconstruct graph state or governance decisions;
- can be disabled without changing domain correctness or auditability.

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
      memory/            # ephemeral/test-only
      sqlite/            # first durable provider, P1
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

For `EventStore`, all providers run a common semantic contract suite covering at least:

- empty journal/`graph_version` semantics;
- atomic proposal-ID claim;
- duplicate same-ID/same-hash recovery without duplicate receipt/commit;
- duplicate same-ID/different-hash idempotency conflict;
- monotonic `journal_position` across audit and graph records;
- audit-only append leaves `graph_version` unchanged;
- ordered journal read;
- atomic decision + multi-graph-event commit with exactly one new graph version for the whole batch;
- stale `expected_graph_version` conflict leaves graph events uncommitted;
- a conflict/reject/retry/escalate decision remains queryable for the lifetime represented by the provider;
- failed append leaves the journal/graph projection in the specified state;
- independent run journals;
- byte/semantic fidelity sufficient for deterministic replay and governance audit.

Durable providers additionally run a durability contract suite covering close/reopen and process-restart survival of the full journal, including non-commit decisions and graph history.

`MemoryEventStore` does **not** claim that durability contract and must be clearly marked `ephemeral`. SQLite must pass both semantic and durability suites.

Provider-specific tests may add performance/error cases but cannot replace the applicable common suites.
