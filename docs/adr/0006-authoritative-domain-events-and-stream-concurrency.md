# ADR 0006: Persist governance audit and graph events in a run-scoped journal

- Status: Accepted
- Date: 2026-09-18

## Context

The bootstrap design listed graph mutations, model calls, tool calls, and harness lifecycle events together. If all of these increment graph version or are required for replay, authoritative state becomes coupled to harness implementation details.

The first audit separated committed graph events from optional telemetry, but that left a second problem: non-commit governance outcomes such as `REJECT`, `RETRY`, `ESCALATE`, and `CONFLICT` would not be durably recorded. A restart could therefore erase mutation/audit history and invalidate evaluation metrics.

Parallel workers also need a clear conflict model.

## Decision

Each normal ProblemForger service run owns one append-only **durable run journal** persisted through a durability-capable `EventStore`. Ephemeral providers such as `MemoryEventStore` are restricted to explicit tests and do not satisfy this runtime guarantee.

The journal contains:

1. **governance audit records**
   - proposal receipt;
   - final governance decision and reason metadata;
   - these records are durable but do not change graph state;

2. **graph-changing domain events**
   - committed node/edge/evidence/lifecycle changes;
   - these records reconstruct the ProblemGraph.

Every durable journal record receives a monotonic per-run `journal_position`.

Each successfully committed graph mutation batch advances the monotonic `graph_version` exactly once. All graph-changing domain events emitted by that atomic mutation share the same resulting `graph_version`; `journal_position` provides their total order within the journal.

Harness/model/tool lifecycle observations remain a separate optional telemetry plane. They may reference journal records but are not required for graph replay or governance audit.

### Durability of outcomes

A governance outcome is not considered externally completed until its final decision record is durably appended.

- For `COMMIT`, the `MutationDecision(COMMIT)` audit record and all graph-changing events produced by that proposal are appended atomically.
- For `REJECT`, `RETRY`, and `ESCALATE`, the final decision audit record is durably appended without advancing `graph_version`.
- For `CONFLICT`, an optimistic graph append may first return `VersionConflict`; the application must then durably append `MutationDecision(CONFLICT)` before returning `CONFLICT` to the caller. If that audit append fails, the service returns a persistence/service failure instead of claiming a completed conflict outcome.

Proposal receipt is also durable. Each proposal has a client-generated `proposal_id` unique within the run and a canonical request hash. Recording that identity is atomic: the same `proposal_id` cannot create two proposal receipts or two commits.

If the process terminates after a proposal is recorded but before a final decision is persisted, replay exposes an incomplete proposal rather than erasing it. The durable receipt stores the complete normalized request, not only its hash, so recovery does not depend on transient client state.

Incomplete proposals are processed under a durable lease/claim with `owner_id`, monotonic `claim_epoch`, and finite expiry.

P1 permits one live EventStore provider instance per durable store. All concurrent workers using that store share the instance and its lease clock. Opening another instance must fail before it can initialize a clock or access journal state; a crash must release ownership without manual lock-file deletion. This deliberately excludes concurrent service owners instead of introducing distributed clock coordination into the PoC.

Lease deadlines use a restart-stable time domain rather than persisted process-monotonic timestamps. The operational ownership and clock algorithms have one normative home: [STORE-OWNER and LEASE-CLOCK](../protocol.md#spec-protocol-store-owner). Concurrent provider instances require an amendment to this ADR and a coherent shared-time contract before they are supported.

A new worker may atomically claim an unclaimed/expired proposal and increments the epoch. Final decision append or graph commit must atomically validate both the current claim epoch and an unexpired lease (`lease_expires_at_ms > lease_now_ms`); a stale or expired worker receives `STALE_CLAIM` and cannot append a decision or mutate graph state. Renewal cannot revive an expired claim.

If safe resumption is impossible because the producing schema/policy/runtime is unavailable or the durable request is invalid, the current claimant may append terminal operational status `ABANDONED` with a reason. This is not a governance outcome and never changes graph state.

A transport retry with the same proposal ID/request hash reuses that existing attempt; a retry with the same ID but different request hash is rejected as an idempotency conflict. A completed proposal replays its already-durable outcome rather than executing again.

### Concurrency

Graph-changing commits use optimistic comparison against `expected_graph_version`. If the current graph version is `v`, one successful atomic mutation batch produces `new_graph_version = v + 1`, regardless of how many graph-changing events the mutation emits.

The canonical claim, finalization, and graph-append signatures are owned by the
[EventStore port](../modules.md#spec-modules-eventstore-port), while their
atomic recovery and fencing preconditions are defined by the [protocol
contract](../protocol.md#spec-protocol-proposal-recovery). This ADR records the
architectural invariants and rationale without redeclaring the API.

A successful `append_graph` atomically verifies the current, unexpired claim before appending its audit and graph records, assigns the same `new_graph_version` to every graph-changing event in that batch, and makes that version addressable only after the complete batch is durable.

Non-terminal audit records can be appended independently and do not participate in graph-version comparison. Proposal terminal records are different: they require the current, unexpired claim and its epoch, including non-commit decisions and `ABANDONED`, so a stale or expired worker cannot create a second terminal state.

There is no required global order across independent run journals.

## Consequences

- Graph replay is independent of harness telemetry completeness.
- Every returned governance outcome survives restart.
- P6 blocked/retry/escalation/conflict metrics can be computed from durable data.
- Tool/model observations cannot accidentally create graph-version conflicts.
- `journal_position` and `graph_version` are distinct concepts and must not be conflated.
- `graph_version` identifies committed graph states / atomic mutation batches, not individual graph events; no partial intermediate version of a committed mutation is addressable.
- In-memory, SQLite, and future stores share the same semantic journal/concurrency contract; only durability-capable providers are valid for normal service execution and restart guarantees.
- Future parallel workers can detect stale graph proposals and stale proposal-processing claims; durable lease expiry remains finite across service/provider restart.
- The PoC may serialize actual governance execution internally while retaining the optimistic graph-write contract.
- Store ownership is distinct from a proposal processing claim: one provider may host multiple workers, but no second provider may independently advance the same store's lease clock.
