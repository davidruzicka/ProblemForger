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

<a id="spec-modules-eventstore-port"></a>
<!-- spec-id: MODULES.EVENTSTORE-PORT -->
### EventStore

Owns persistence of each run's durable journal: governance audit records plus graph-changing domain events.

The EventStore port owns the operation signatures and return statuses. The
protocol defines the atomic preconditions and recovery semantics that every
provider must implement.

Conceptual port contract:

```text
create_run(run_id, run_metadata)
    -> CREATED {graph_version=0, last_journal_position=0}
    | EXISTING {run_metadata, graph_version, last_journal_position}

get_run(run_id)
    -> RUN {run_metadata, graph_version, last_journal_position}
    | NOT_FOUND

record_proposal(stream_id, proposal_id, request_hash, normalized_request, receipt_record)
    -> CREATED
    | EXISTING {request_hash, status, last_journal_position}

claim_proposal(stream_id, proposal_id, owner_id, claim_ttl_ms)
    -> CLAIMED {claim_epoch}
    | PENDING {claim_epoch, lease_expires_at_ms}
    | FINAL
    | ABANDONED

renew_claim(stream_id, proposal_id, owner_id, expected_claim_epoch, claim_ttl_ms)
    -> RENEWED
    | STALE_CLAIM

append_audit(stream_id, records[], proposal_id?, expected_owner_id?, expected_claim_epoch?)
    -> last_journal_position
    | STALE_CLAIM

append_graph(stream_id, proposal_id, expected_owner_id, expected_claim_epoch,
             expected_graph_version, audit_records[], graph_events[])
    -> {last_journal_position, new_graph_version}
    | VersionConflict
    | STALE_CLAIM

read_journal(stream_id, after_journal_position?)
    -> ordered durable records

current_graph_version(stream_id)
    -> graph_version
```

Requirements:

- persist run registration before accepting proposals; `create_run` is idempotent, reopening preserves the registration and version-zero state, and every operation against an unknown run returns `NOT_FOUND` rather than creating an implicit empty stream;
- enforce the [proposal identity/recovery contract](protocol.md#spec-protocol-proposal-recovery), including atomic receipt uniqueness and fenced terminalization;
- obey [STORE-OWNER and LEASE-CLOCK](protocol.md#spec-protocol-store-owner); service startup refuses a second owner before state access;
- treat an expired claim as inactive even before another worker reclaims it; renewal, terminalization, and graph append must reject it atomically with `STALE_CLAIM`;
- generic audit append without both expected owner and claim epoch cannot create proposal terminal records;
- terminal audit and graph appends must atomically match both the service-assigned claim owner and claim epoch; a claim epoch alone is not sufficient authority;
- assign monotonic per-run `journal_position` to every durable record;
- atomically compare graph version and append the final decision plus graph events as one complete mutation batch under ADR 0006;
- audit-only writes never advance graph version; all graph events in a committed batch share one new version;
- persist each returned governance outcome before completing its response;
- preserve record ordering, append-only history, and versioned payload fidelity for replay/audit, with no required global order across runs;
- retain normalized evidence according to [EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-recovery).

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

Inject only where deterministic tests or reproducibility require it. Lease handling needs two explicit clock capabilities:

- UTC Unix time for the restart anchor;
- monotonic elapsed time for progress within one provider/service instance.

The owning provider combines these sources using [LEASE-CLOCK](protocol.md#spec-protocol-lease-clock). Domain code does not implement or persist a separate clock algorithm.

Do not introduce a general service-locator abstraction.

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
- crash-after-receipt recovery using a new claim epoch;
- concurrent recovery claim where only one worker owns the current epoch;
- stale-worker finalization/graph append rejected with no partial writes;
- current-but-expired-worker finalization/graph append and expired-claim renewal rejected before reclaim, with no partial writes;
- missing/null proposal identity or fencing epoch rejected before a graph append;
- claim/renewal deadlines computed from provider time plus validated TTL, independent of caller time, with invalid TTL/overflow leaving claim and floor unchanged;
- terminal `ABANDONED` recovery status without graph mutation;
- monotonic `journal_position` across audit and graph records;
- audit-only append leaves `graph_version` unchanged;
- ordered journal read;
- atomic decision + multi-graph-event commit with exactly one new graph version for the whole batch;
- stale `expected_graph_version` conflict leaves graph events uncommitted;
- a conflict/reject/retry/escalate decision remains queryable for the lifetime represented by the provider;
- failed append leaves the journal/graph projection in the specified state;
- independent run journals;
- byte/semantic fidelity sufficient for deterministic replay and governance audit.

Durable providers additionally run a durability contract suite covering close/reopen and process-restart survival of the full journal, including non-commit decisions and graph history. Test the ownership/open/crash cases from [STORE-OWNER](protocol.md#spec-protocol-store-owner), active-lease recovery, and forward/backward UTC jumps on reopen under [LEASE-CLOCK](protocol.md#spec-protocol-lease-clock). A forward restart anchor may legitimately expire a lease sooner; a backward jump must not leave it busy indefinitely. Reopen durability tests do not apply to the ephemeral memory provider.

`MemoryEventStore` does **not** claim that durability contract and must be clearly marked `ephemeral`. SQLite must pass both semantic and durability suites.

Provider-specific tests may add performance/error cases but cannot replace the applicable common suites.
