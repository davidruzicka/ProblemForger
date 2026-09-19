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
ProblemGraph -> Governor -> durable journal   TelemetrySink
     ^             |              |
     |             |              +-- graph-changing domain events
     |             +-- proposal/decision audit records
     |
     +-- EventStore port
```

The worker/harness may propose changes. It does not own authoritative graph state. Local enforcement follows [STORE-OWNER](protocol.md#store-owner) and [EVIDENCE-TRUST](verification.md#evidence-trust); a separate process alone is not a security boundary.

ProblemForger runs as a separate local process/service for the PoC. HarnessX and Pi use thin clients/adapters against the same service contract. This preserves a symmetric integration boundary even though HarnessX and the core are both Python.

## Durable journal and observation plane

ProblemForger separates durable governance/audit history from optional harness telemetry.

### Durable run journal

Every run has one append-only journal persisted through `EventStore`.

The journal contains two classes of durable records:

- **governance audit records** — proposal receipt plus final governance outcomes such as `COMMIT`, `REJECT`, `RETRY`, `ESCALATE`, or `CONFLICT`; these are required for auditability and evaluation but do not change graph state;
- **graph-changing domain events** — committed node/edge/evidence/lifecycle changes that reconstruct the ProblemGraph.

Every journal record has a monotonic `journal_position`. Each successfully committed graph mutation batch advances `graph_version` exactly once; all graph-changing events in that batch carry the same resulting graph version.

A governance outcome is not returned to the harness as completed until its durable decision record has been appended. Proposal receipts persist the normalized/versioned request needed for recovery. If a process fails after recording a proposal but before recording a final outcome, the journal exposes an incomplete proposal rather than silently losing it. Incomplete work is resumed under a finite processing lease with monotonic claim-epoch fencing; finalization also requires the matching claim to remain unexpired, so stale or expired workers cannot finalize even before a newer claim exists.

### Observation/telemetry events

Harness lifecycle events, model calls, tool calls, token/cost measurements, and adapter diagnostics are useful for evaluation and UI, but are not the governance audit log and are not required for graph replay.

They flow through `TelemetrySink` and may reference durable journal records through correlation/causation identifiers.

Telemetry may be disabled without losing authoritative graph state or governance outcomes.

See ADR 0006.

## Layers

### Domain/core

Contains:

- graph domain types;
- graph mutation semantics;
- entity lifecycle and provenance;
- governance policy interfaces;
- durable governance audit-record and graph-domain-event definitions;
- pure replay/projection logic.

It must not depend on SQLite, PostgreSQL, a specific model API, HarnessX, Pi, a UI framework, or provider-specific settings.

The core also does **not** own model inference in the initial PoC. Model execution remains a harness responsibility. Later routing asks the harness to select a model; it does not move inference into the core.

### Application API

The application layer exposes harness-neutral commands and queries such as:

- create/start a ProblemForger run;
- query run metadata and graph state or a bounded subgraph using explicit `run_id`;
- propose a graph mutation against an expected graph version using explicit `run_id`;
- attach/reference evidence;
- query proposal status/outcome by `(run_id, proposal_id)`;
- retrieve a bounded read-only governance/audit timeline derived from durable journal audit records, ordered by `journal_position`;
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

- event store: memory (ephemeral/test-only), SQLite (durable), later PostgreSQL;
- telemetry: null/recording/JSONL or another sink;
- verifier: later LLM judge or learned model;
- calibration/routing: later experimental modules.

Harness integrations are adapters to the service protocol, not provider modules inside the core.

Harness-specific **raw trajectory archives** used for experiment reproducibility are also adapter/evaluation concerns, not core concerns. HarnessX and Pi may have different native trajectory schemas. Those raw artifacts remain external/content-addressed and are never written into the authoritative ProblemForger journal. Core domain types, `EventStore`, and graph replay must not depend on harness-native trajectory formats. Adapters may separately emit harness-neutral normalized observations through `TelemetrySink`.

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

## Event sourcing and audit persistence

The run journal is ordered by `journal_position`. `graph_version` identifies complete committed graph states, not individual events. Current graph state is the projection of complete mutation batches through version `v`:

```text
G_v = fold(complete mutation batches with graph_version <= v)
```

If a mutation based on `G_v` emits multiple graph events, every event in that atomic batch is tagged `graph_version = v + 1`; there is no addressable state containing only a prefix of that batch.

Graph-changing commits use optimistic compare-and-append against `graph_version`:

```text
append_graph(stream_id, proposal_id, expected_claim_epoch,
             expected_graph_version=v, audit_records=[...], graph_events=[...])
    -> {last_journal_position, new_graph_version}
    OR VersionConflict
    OR STALE_CLAIM
```

Audit-only records can be appended without advancing `graph_version`.

For a successful commit, the final `MutationDecision(COMMIT)` audit record and all graph-changing events from that proposal must be durable as one atomic batch. The batch advances `graph_version` once, from `v` to `v + 1`.

For non-commit outcomes, the final decision record is appended durably before the service returns that outcome. Proposal finalization atomically validates the current processing-claim epoch and an unexpired lease so restart/concurrent recovery cannot create two terminal decisions or allow a paused worker to finalize after expiry. If an optimistic graph append reports a version conflict, the application must append `MutationDecision(CONFLICT)` before returning `CONFLICT`; failure to persist that decision is a service/persistence failure, not a completed governance outcome.

There is no required global order across independent runs.

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

UI/observer clients are outside the correctness path and consume three read-only views:

- optional normalized observation/telemetry events for model/tool/runtime activity;
- graph projections for authoritative graph state;
- a durable governance/audit timeline projection exposed through the application API from run-journal audit records.

The audit timeline remains available even when telemetry is disabled and includes proposal receipts plus non-commit outcomes such as `REJECT`, `RETRY`, `ESCALATE`, and `CONFLICT`. Observers must use the service/application read API rather than access `EventStore` directly.

Native harness UI may expose compact status. A later web observer may combine graph state, durable governance provenance, and optional telemetry for full timeline inspection.
