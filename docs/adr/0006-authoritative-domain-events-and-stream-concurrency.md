# ADR 0006: Persist governance audit and graph events in a run-scoped journal

- Status: Accepted
- Date: 2026-09-18
- Practical P1 amendment: 2026-09-21

## Context

The bootstrap design listed graph mutations, model calls, tool calls, and
harness lifecycle events together. If all of these increment graph version or
are required for replay, authoritative state becomes coupled to harness
implementation details.

The first audit separated committed graph events from optional telemetry, but
that left a second problem: non-commit governance outcomes such as `REJECT`,
`RETRY`, `ESCALATE`, and `CONFLICT` would not be durably recorded. A restart
could therefore erase mutation/audit history and invalidate evaluation
metrics.

The initial PoC does not need several workers processing one store at once.
Adding leases, fencing epochs, and a second clock domain before that need is
measured would make the first implementation harder to operate without
improving the practical experiment.

## Decision

Each normal ProblemForger service run owns one append-only **durable run
journal** persisted through a durability-capable `EventStore`. Ephemeral
providers such as `MemoryEventStore` are restricted to explicit tests and do
not satisfy this runtime guarantee.

The journal contains:

1. **governance audit records**
   - proposal receipt;
   - final governance decision and reason metadata;
   - these records are durable but do not change graph state;

2. **graph-changing domain events**
   - committed node/edge/evidence/lifecycle changes;
   - these records reconstruct the ProblemGraph.

Every durable journal record receives a monotonic per-run `journal_position`.

Each successfully committed graph mutation batch advances the monotonic
`graph_version` exactly once. All graph-changing domain events emitted by that
atomic mutation share the same resulting `graph_version`; `journal_position`
provides their total order within the journal.

Harness/model/tool lifecycle observations remain a separate optional telemetry
plane. They may reference journal records but are not required for graph replay
or governance audit.

### Durability of outcomes

A governance outcome is not considered externally completed until its final
decision record is durably appended.

- For `COMMIT`, the `MutationDecision(COMMIT)` audit record and all
  graph-changing events produced by that proposal are appended atomically.
- For `REJECT`, `RETRY`, and `ESCALATE`, the final decision audit record is
  durably appended without advancing `graph_version`.
- For `CONFLICT`, an optimistic graph append may first return
  `VersionConflict`; the application must then durably append
  `MutationDecision(CONFLICT)` before returning `CONFLICT` to the caller. If
  that audit append fails, the service returns a persistence/service failure
  instead of claiming a completed conflict outcome.

Proposal receipt is also durable. Each proposal has a client-generated
`proposal_id` unique within the run and a canonical request hash. Recording
that identity is atomic: the same `proposal_id` cannot create two proposal
receipts or two commits.

If the process terminates after a proposal is recorded but before a final
decision is persisted, replay exposes an incomplete proposal rather than
erasing it. The durable receipt stores the complete normalized request, not
only its hash, so recovery does not depend on transient client state.

### Practical P1 execution and recovery

P1 starts exactly one service owner for a durable store. The owner holds the
store lock for its lifetime and serializes proposal evaluation and final
append operations. This is an operational simplification, not a claim that
parallel workers are impossible.

After a crash, the operating-system/store lock releases with the process. On
restart, an incomplete receipt remains `PENDING` and can be resumed by a
resubmission with the same `proposal_id` and request hash. A completed proposal
replays its recorded outcome; a different request hash is an idempotency
conflict. If the stored request cannot be resumed because a required
schema/policy/runtime is unavailable or invalid, the service records
`ABANDONED` with an explicit reason. `ABANDONED` is operational status, not a
governance outcome, and never changes graph state.

The initial P1 contract deliberately has no `claim_ttl`, `owner_id`,
`claim_epoch`, lease renewal, or persisted lease clock. Parallel processing
claims may be introduced later only with measured justification and an
amended protocol/ADR. This avoids building a distributed recovery mechanism
for a single-owner local PoC.

A transport retry with the same proposal ID/request hash reuses that existing
attempt. A completed proposal replays its already-durable outcome rather than
executing again.

### Concurrency

Graph-changing commits use optimistic comparison against
`expected_graph_version`. If the current graph version is `v`, one successful
atomic mutation batch produces `new_graph_version = v + 1`, regardless of how
many graph-changing events the mutation emits. Serialized proposal processing
does not remove this check: it still protects callers that prepared a
mutation against an older graph view.

The canonical finalization and graph-append signatures are owned by the
[EventStore port](../modules.md#spec-modules-eventstore-port), while their
atomic recovery and graph-version preconditions are defined by the [protocol
contract](../protocol.md#spec-protocol-proposal-recovery). This ADR records the
architectural invariants and rationale without redeclaring the API.

A successful `append_graph` atomically verifies the proposal identity and
expected graph version before appending its audit and graph records, assigns
the same `new_graph_version` to every graph-changing event in that batch, and
makes that version addressable only after the complete batch is durable.

Non-terminal audit records can be appended independently and do not participate
in graph-version comparison. Proposal terminal records are tied to the stored
`(run_id, proposal_id)` receipt and the serialized service operation, so a
second terminal state cannot be appended for the same proposal.

There is no required global order across independent run journals.

## Consequences

- Graph replay is independent of harness telemetry completeness.
- Every returned governance outcome survives restart.
- P6 blocked/retry/escalation/conflict metrics can be computed from durable data.
- Tool/model observations cannot accidentally create graph-version conflicts.
- `journal_position` and `graph_version` are distinct concepts and must not be
  conflated.
- `graph_version` identifies committed graph states / atomic mutation batches,
  not individual graph events; no partial intermediate version of a committed
  mutation is addressable.
- In-memory, SQLite, and future stores share the same semantic journal
  contract; only durability-capable providers are valid for normal service
  execution and restart guarantees.
- The first PoC is easy to reason about and operate because one service owner
  serializes evaluation and recovery.
- Parallel workers, leases, and fencing are explicitly deferred rather than
  silently implied. If measurements show that serialization is a bottleneck,
  that future change requires a new contract and regression suite.
