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
    -> CREATED {metadata_hash, graph_version=0, last_journal_position=0}
    | EXISTING {run_metadata, metadata_hash, graph_version, last_journal_position}
    | RUN_METADATA_CONFLICT {metadata_hash, existing_metadata_hash}

get_run(run_id)
    -> RUN {run_metadata, metadata_hash, graph_version, last_journal_position}
    | NOT_FOUND

get_proposal(run_id, proposal_id)
    -> PROPOSAL {request_hash, normalized_request, status,
                 terminal_outcome, resulting_graph_version, last_journal_position}
    | NOT_FOUND

record_proposal(run_id, proposal_id, request_hash, normalized_request, receipt_record)
    -> CREATED
    | EXISTING {request_hash, status, last_journal_position}
    | NOT_FOUND

append_audit(run_id, records[], proposal_id?)
    -> last_journal_position
    | INVALID_AUDIT_BATCH
    | NOT_FOUND

append_graph(run_id, proposal_id, expected_graph_version,
             audit_records[], graph_events[])
    -> {last_journal_position, new_graph_version}
    | INVALID_GRAPH_BATCH
    | VersionConflict
    | NOT_FOUND

read_journal(run_id, after_journal_position?, limit)
    -> {records, next_after_journal_position, has_more}
    | INVALID_LIMIT
    | NOT_FOUND

current_graph_version(run_id)
    -> graph_version
    | NOT_FOUND
```

Requirements:

- persist run registration before accepting proposals; `create_run` is idempotent only when the supplied run metadata has the same canonical serialization and metadata hash as the existing registration; a mismatch returns `RUN_METADATA_CONFLICT` without changing the journal, reopening preserves the registration and version-zero state, and every operation against an unknown run returns `NOT_FOUND` rather than creating an implicit empty stream;
- canonicalize and hash `run_metadata` under a versioned metadata schema before comparing idempotent retries; return the stored hash so callers can audit that they addressed the intended run;
- enforce the [proposal identity/recovery contract](protocol.md#spec-protocol-proposal-recovery), including atomic receipt uniqueness and serialized recovery;
- obey [STORE-OWNER](protocol.md#spec-protocol-store-owner); service startup refuses a second owner before state access;
- `append_audit` requires `run_id`; terminal records require the matching `proposal_id`, while non-terminal run records may omit it. `INVALID_AUDIT_BATCH` reports invalid arguments/record binding, multiple terminal records, or a forbidden `COMMIT`; enforce [terminal append binding](protocol.md#terminal-append-binding) atomically. `COMMIT` is exclusive to `append_graph`;
- `get_proposal` returns one consistent read snapshot of the durable normalized request, lifecycle status, and terminal outcome (nullable until terminal). Resulting graph version and last journal position belong to the recorded terminal response when final, not the run's subsequently advanced head. Before finalization, return the proposal's latest recorded position and no terminal resulting version. Recovery reads grant no mutation authority. Bound stored request/response sizes under the service payload limits and use immutable references for larger evidence. Internal recovery data is not automatically exposed by worker-facing queries;
- reject malformed `append_graph` batches with `INVALID_GRAPH_BATCH` under [graph append binding](protocol.md#graph-append-binding), without partial writes;
- atomically require `append_graph`'s supplied `expected_graph_version` to equal both the proposal receipt's recorded `expected_graph_version` and the current run `graph_version`; a receipt-binding mismatch returns `INVALID_GRAPH_BATCH`, while a bound value stale against the current run returns `VersionConflict`, with no writes in either case;
- assign monotonic per-run `journal_position` to every durable record;
- require an explicit positive `limit` for `read_journal`; `after_journal_position` is an exclusive cursor, records are returned in ascending position order, and `next_after_journal_position` plus `has_more` make continuation explicit. Providers must enforce a finite configured maximum and must not return an unbounded journal response;
- atomically compare graph version and append the final decision plus graph events as one complete mutation batch under ADR 0006;
- audit-only writes never advance graph version; all graph events in a committed batch share one new version;
- persist each returned governance outcome before completing its response;
- preserve record ordering, append-only history, and versioned payload fidelity for replay/audit, with no required global order across runs;
- retain normalized evidence according to [EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-recovery);
- serialize proposal evaluation within the owning service process. A restart changes incomplete receipts back to recoverable `PENDING` state; a client resubmission with the same proposal ID replays a final outcome or resumes the normalized request. Add claims, leases, or parallel workers only after a measured requirement and a new contract decision.

Both providers are introduced in P1. `MemoryEventStore` exists for fast unit/contract tests and explicit ephemeral test harnesses only; it must not be used by the normal ProblemForger service. The composition root must reject an ephemeral EventStore for a normal service profile. SQLite is the first durable provider and must preserve the journal across close/reopen and process restart. Proposal processing is serialized by the service owner; multi-worker claims are deferred.

### TelemetrySink

Receives non-authoritative observations such as harness/model/tool events, cost/latency measurements, and diagnostics.

Telemetry:

- may reference durable journal records through correlation/causation IDs;
- does not increment graph version;
- is not required to reconstruct graph state or governance decisions;
- can be disabled without changing domain correctness or auditability.

A recording/in-memory or JSONL sink may be used initially.

### Service clock / ID source

Inject only where deterministic tests or reproducibility require it. The initial service needs only two small capabilities:

- a service clock for request deadlines and telemetry;
- an ID source for run/proposal/journal identifiers.

The initial service does not persist a lease clock or expose claim TTLs. Domain code does not implement a provider-specific clock algorithm. Claims, leases, and fencing are deferred until a measured parallel-worker requirement exists.

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
- idempotent `create_run` with identical canonical metadata returning `EXISTING`, and mismatched metadata returning `RUN_METADATA_CONFLICT` without journal mutation;
- atomic proposal receipt and proposal-ID idempotency;
- duplicate same-ID/same-hash recovery without duplicate receipt/commit;
- consistent proposal snapshots and exact terminal replay metadata after later proposals advance the run;
- missing/duplicate COMMIT, other terminal outcomes, empty graph events, or mismatched record identities rejected as `INVALID_GRAPH_BATCH` without journal, proposal, or graph changes;
- duplicate same-ID/different-hash idempotency conflict;
- restart recovery of an incomplete receipt under exclusive service ownership, with no duplicate final outcome;
- missing proposal identity rejected before a terminal or graph append;
- terminal `ABANDONED` recovery status without graph mutation, if recovery cannot resume the stored request;
- monotonic `journal_position` across audit and graph records;
- audit-only append leaves `graph_version` unchanged;
- bounded ordered journal read with an exclusive cursor, finite limit, and explicit continuation metadata;
- atomic decision + multi-graph-event commit with exactly one new graph version for the whole batch;
- stale `expected_graph_version` conflict leaves graph events uncommitted;
- supplied graph version differing from the proposal receipt is rejected as `INVALID_GRAPH_BATCH`; matching the receipt but not the current run returns `VersionConflict`; both leave journal, proposal, and graph unchanged;
- a conflict/reject/retry/escalate decision remains queryable for the lifetime represented by the provider;
- failed append leaves the journal/graph projection in the specified state;
- independent run journals;
- byte/semantic fidelity sufficient for deterministic replay and governance audit.

Durable providers additionally run a durability contract suite covering close/reopen and process-restart survival of the full journal, including non-commit decisions and graph history. Test the ownership/open/crash cases from [STORE-OWNER](protocol.md#spec-protocol-store-owner) and restart recovery of incomplete receipts. Lease-clock, claim-fencing, and parallel-worker tests are deferred until that capability is introduced. Reopen durability tests do not apply to the ephemeral memory provider.

`MemoryEventStore` does **not** claim that durability contract and must be clearly marked `ephemeral`. SQLite must pass both semantic and durability suites.

Provider-specific tests may add performance/error cases but cannot replace the applicable common suites.
