# Harness-neutral protocol

## Purpose

HarnessX and Pi must use the same ProblemForger core/service. Their adapters translate native lifecycle events and agent tool calls into a stable, versioned protocol.

The protocol is independent from provider implementations and from the transport used to carry it.

## Protocol planes

Do not put every harness event into the authoritative graph stream.

### Command/query plane

Used by the harness/worker to interact with ProblemForger.

Initial operations should cover:

- start/create a run and return its `run_id`;
- get run metadata and current graph version by explicit `run_id`;
- query graph state or a bounded subgraph by explicit `run_id`;
- propose a graph mutation against `expected_graph_version` with explicit `run_id`;
- attach/reference evidence through a governed mutation for explicit `run_id`;
- query a mutation proposal by explicit `(run_id, proposal_id)`;
- retrieve/replay the resulting governor decision;
- read a bounded durable governance/audit timeline for a run, ordered by `journal_position`, so observers can inspect proposal receipts and non-commit outcomes without relying on optional telemetry.

All run-scoped v1 commands and queries carry `run_id` explicitly. There is no ambient/session-selected run context in the domain/application protocol; a transport may maintain connections or sessions, but it must not infer or override the target run. Missing/unknown/mismatched `run_id` is an explicit protocol error.

Run creation is durable and idempotent: `create_run(run_id, run_metadata)`
registers an empty version-zero run before any proposal is accepted. A repeat
create returns the existing registration only when the supplied metadata has the
same canonical serialization and metadata hash; otherwise it returns an explicit
`RUN_METADATA_CONFLICT` without changing the journal. Reopen/restart preserves
that registration and its `graph_version = 0` / empty-journal state. No operation
implicitly creates a run from an arbitrary ID; unknown runs return `NOT_FOUND`.

The exact wire schema is finalized in P1.

### Observation plane

Used for non-authoritative harness telemetry such as:

- run start/end;
- model call requested/completed;
- tool call requested/completed;
- token/cost/latency measurements;
- adapter diagnostics.

Observation events may be stored/exported for evaluation and UI, but they do not alter graph state or graph version.

### Durable governance/journal records

ProblemForger durably records mutation proposals and final governance decisions in the run journal.

Every completed mutation request therefore leaves durable audit history, including `REJECT`, `RETRY`, `ESCALATE`, and `CONFLICT`.

Committed graph changes are additional graph-changing domain events in the same journal.

Examples:

- mutation proposal recorded;
- mutation decision recorded;
- node committed;
- edge committed;
- evidence attached;
- entity invalidated/superseded.

Harnesses do not submit durable journal records directly; they submit commands. ProblemForger creates the corresponding audit/domain records.

See ADR 0006.

## Decisions

A mutation request can yield outcomes such as:

- `COMMIT`;
- `REJECT`;
- `RETRY`;
- `ESCALATE`;
- `CONFLICT`.

`RETRY` means that the current proposal attempt ended with a retry request. A later resubmission is a new proposal attempt with its own identity/version context and causal linkage to the prior attempt; the prior proposal is not mutated into a "retried" state.

The service must persist the final decision record before returning a completed governance outcome to the harness.

<a id="spec-protocol-proposal-recovery"></a>
<!-- spec-id: PROTOCOL.PROPOSAL-RECOVERY -->
### Proposal identity, idempotency, and recovery

Every mutation command carries a client-generated `proposal_id` that is unique within the ProblemForger run and acts as the idempotency key for transport retries.

On the first accepted submission of `(run_id, proposal_id)`, ProblemForger durably records the complete normalized mutation request together with a canonical request hash covering the mutation payload, expected graph version, and evidence content identities. Evidence references resolve to immutable versioned records, not mutable path/URL contents. The receipt retains the normalized evidence inputs required by [EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-recovery), including inline worker assertions. The durable receipt must contain enough versioned input to resume governance after process restart without consulting transient client state.

Proposal execution uses a durable processing claim.

<a id="spec-protocol-store-owner"></a>
<!-- spec-id: PROTOCOL.STORE-OWNER -->
#### STORE-OWNER

P1 permits exactly one live EventStore provider instance per durable store, shared by all workers using that store. The provider must acquire exclusive ownership **before initializing the lease clock**, loading journal state, or accepting operations. A competing open fails explicitly with `STORE_IN_USE`; this is a service startup error, not a governance decision or a proposal claim.

Ownership must cover same-process duplicate instances as well as separate processes and path aliases for the same store. Hold it for the provider lifetime and release it only after in-flight operations/connections are closed. A process crash releases ownership automatically; a persisted boolean, PID file, or lease-clock deadline alone is not an ownership lock. The SQLite implementation must document its canonical store/lock identity and supported local-filesystem assumptions, reject unsupported storage, and prevent replacing/unlinking its live store or lock identity. Internal connections are allowed only under the owning provider and its shared clock. A forked child cannot operate an inherited provider; it must open normally and obtain ownership after the old owner closes.

Concurrent workers still use atomic proposal claims, fencing epochs, and graph-version checks. Multiple live providers for one store are out of scope under ADR 0006; independent stores may be opened concurrently. Required P1 tests include racing process opens, same-process duplicate opens, path aliases, graceful close, crash release, and reopening with an active proposal lease.

<a id="spec-protocol-lease-clock"></a>
<!-- spec-id: PROTOCOL.LEASE-CLOCK -->
#### LEASE-CLOCK

Lease expiry uses a **restart-stable lease-time domain**, never a process-local monotonic timestamp persisted directly:

- the durable EventStore persists a per-store `lease_clock_floor_ms`;
- the durable EventStore persists a per-store `lease_clock_floor_ms` and `lease_clock_generation`;
- after acquiring store ownership, provider/service open atomically increments `lease_clock_generation`, samples UTC Unix time in milliseconds, and sets `lease_clock_anchor_ms = max(persisted lease_clock_floor_ms, sampled_utc_ms)`; it also captures a process-local monotonic anchor;
- during that provider instance, compute `lease_now_ms = lease_clock_anchor_ms + elapsed_monotonic_ms`; later wall-clock jumps do not move lease time backward or forward;
- every claim/renew/expiry transaction atomically advances persisted `lease_clock_floor_ms` to at least the transaction's `lease_now_ms`;
- persisted `lease_expires_at_ms` is expressed in this lease-time domain as `lease_now_ms + claim_ttl_ms`;
- claim and renewal accept `claim_ttl_ms`, never a caller-supplied deadline; the owning EventStore samples its own lease clock and computes the deadline inside the same atomic transaction that validates/updates the claim and advances the persisted floor. Renewal is accepted only while the matching claim is still active and unexpired;
- TTL is a positive integer number of milliseconds validated against typed service configuration; invalid TTLs or deadline overflow fail without changing claim or floor state. The provider must not use caller/process timestamps as its clock source;
- after restart, the new anchor starts at least at the persisted floor and advances from a fresh monotonic anchor. Every claim records the provider `lease_clock_generation`; a claim from an earlier generation is treated as expired/inactive immediately, cannot be renewed or finalized, and must be reclaimed under a new epoch. This conservative recovery rule prevents a backward wall-clock jump plus repeated restarts from reviving a dead claim indefinitely;
- a wall clock that is ahead of the persisted floor may move the restart anchor forward and make an old lease expire sooner; claim-epoch fencing still prevents the superseded owner from finalizing, while the expiry check independently prevents a current-but-expired owner from finalizing.

Every active claim also has an `owner_id` unique to the service/worker incarnation and a monotonically increasing `claim_epoch`. The service assigns or authenticates that owner identity at the application boundary; a worker cannot choose an arbitrary identity to impersonate another claimant, and a `PENDING` response does not disclose the active owner's identity.

- claim TTL and renewal cadence are versioned typed service configuration and use the injected UTC + monotonic clock pair so behavior is testable/reproducible;
- the claimant renews the lease while evaluating;
- an expired claim is no longer active even if no reclaim has occurred; renewal of an expired claim fails `STALE_CLAIM` and cannot extend it;
- an unclaimed proposal or a proposal whose claim lease has expired may be atomically claimed/reclaimed, incrementing `claim_epoch`;
- every proposal terminalization/finalization operation, including non-commit decisions and `ABANDONED`, carries the claimant's expected owner identity and `claim_epoch`; every graph append requires `proposal_id`, `expected_owner_id`, and `expected_claim_epoch`, with no unfenced overload or default. Missing fields fail validation before any write. Run creation creates empty version-zero state; any initial graph content is committed through the same fenced proposal path;
- the EventStore/application boundary atomically rejects a finalization or graph append unless both expected owner identity and claim epoch match the active claim and `lease_expires_at_ms > lease_now_ms`; this active-claim check occurs before any final decision or graph mutation, and failure returns `STALE_CLAIM`;
- governance evaluation before final append must not perform non-idempotent external side effects; any future side-effecting integration requires its own idempotency contract.

The operation signatures are owned by the [EventStore port](modules.md#spec-modules-eventstore-port).
This section defines their atomic lease, fencing, recovery, and graph-version
preconditions; provider summaries must not copy this algorithm.

#### Proposal recovery responses

Subsequent submissions follow these rules:

- same `proposal_id` + same canonical request hash + final decision already durable → return/replay the recorded final outcome and recorded resulting graph/journal metadata; do not re-run governance or mutate the graph;
- same `proposal_id` + same canonical request hash + proposal has an active, unexpired processing claim according to the restart-stable lease clock → return `PENDING` with current recovery metadata; do not create a second proposal attempt;
- same `proposal_id` + same canonical request hash + proposal is incomplete and unclaimed/claim-expired → a mutation resubmission must attempt to atomically acquire a new recovery claim; the winner resumes governance from the durable normalized request under the new epoch, while a loser observes the new active claim and returns `PENDING`;
- same `proposal_id` + different canonical request hash → return `IDEMPOTENCY_CONFLICT`; do not evaluate or mutate;
- unknown `proposal_id` → treat as a new proposal submission.

If an incomplete proposal cannot be safely resumed because its required schema/policy/runtime version is unavailable or its durable input is invalid, the current valid claimant may append terminal operational status `ABANDONED` with a reason code. `ABANDONED` is **not** a governance decision and never changes graph state. Reusing that proposal ID replays the terminal abandoned status; a semantic retry requires a new proposal ID.

The command/query plane exposes a proposal-status query keyed by `(run_id, proposal_id)` returning `NOT_FOUND`, `PENDING`/claim metadata, `ABANDONED`, or the durable final governance outcome plus relevant `journal_position` / graph-version metadata.

A client retry caused by timeout, cancellation, connection loss, or a lost response reuses the **same** `proposal_id`. This is distinct from the governance outcome `RETRY`: if the governor requests a semantic retry, the worker creates a **new** proposal with a new `proposal_id` and a causation/provenance link to the prior attempt.

The uniqueness/idempotency claim must be enforced atomically by the durable EventStore/application boundary so concurrent duplicate submissions cannot both commit.

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
get_graph(run_id, ...)
get_proposal(run_id, proposal_id)
get_audit_timeline(run_id, after_journal_position?, limit?)
propose_mutation(run_id, proposal_id, expected_graph_version, operations, evidence_refs)
```

The exact tool names are harness-specific and are not part of the domain protocol. Their run-scoped semantics are not: every graph/proposal operation resolves against the explicit `run_id` supplied by the caller.

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

The local service boundary must also enforce [EVIDENCE-TRUST](verification.md#spec-verification-evidence-trust). The transport spike must show that worker tools cannot use trusted evidence-ingestion/admin operations or modify the durable store and policy configuration. Choosing a separate process alone does not establish that protection. Production authentication/TLS and remote deployment remain out of scope.

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
