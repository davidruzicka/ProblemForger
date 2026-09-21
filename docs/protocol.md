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

Proposal execution is owned by the service and serialized for the initial P1
PoC. The durable receipt is the recovery point; it is not a worker lease.

<a id="spec-protocol-store-owner"></a>
<!-- spec-id: PROTOCOL.STORE-OWNER -->
#### STORE-OWNER

P1 permits exactly one live EventStore provider instance per durable store. The provider must acquire exclusive ownership **before loading journal state or accepting operations**. A competing open fails explicitly with `STORE_IN_USE`; this is a service startup error, not a governance decision or a proposal claim.

Ownership must cover same-process duplicate instances as well as separate processes and path aliases for the same store. Hold it for the provider lifetime and release it only after in-flight operations/connections are closed. A process crash releases ownership automatically; a persisted boolean or PID file alone is not an ownership lock. The SQLite implementation must document its canonical store/lock identity and supported local-filesystem assumptions, reject unsupported storage, and prevent replacing/unlinking its live store or lock identity. Internal connections are allowed only under the owning provider. A forked child cannot operate an inherited provider; it must open normally and obtain ownership after the old owner closes.

Proposal evaluation and finalization are serialized by the owning service. Multiple live providers for one store are out of scope under ADR 0006; independent stores may be opened concurrently. Required P1 tests include racing process opens, same-process duplicate opens, path aliases, graceful close, crash release, and reopening with an incomplete receipt.

<a id="spec-protocol-parallel-claims"></a>
<!-- spec-id: PROTOCOL.PARALLEL-CLAIMS -->
#### Deferred parallel proposal claims

The initial P1 service has one exclusive durable-store owner and serializes
proposal evaluation and finalization. It therefore does not expose
`claim_ttl`, `owner_id`, `claim_epoch`, renewal, lease expiry, or a persisted
lease clock. A second provider cannot open the same store, and a second worker
does not race to finalize a proposal.

On restart, the store owner reconstructs incomplete receipts as recoverable
`PENDING` proposals. A resubmission with the same `(run_id, proposal_id)` and
canonical request hash resumes that stored request; a completed proposal is
replayed. A request with a different hash is an idempotency conflict. If the
request cannot be resumed safely, the service records `ABANDONED` with an
explicit operational reason.

Parallel claims are a deferred extension, not an implicit provider
requirement. Adding them requires a measured throughput/recovery need, a new
protocol/ADR decision, and dedicated concurrency tests. The operation
signatures remain owned by the [EventStore port](modules.md#spec-modules-eventstore-port);
provider summaries must not invent a claim API before that extension exists.

#### Terminal append binding

`run_id` is required for every audit batch, including non-terminal-only batches.

A batch containing terminal `REJECT`, `RETRY`, `ESCALATE`, `CONFLICT`, or
`ABANDONED` requires non-null `run_id` and `proposal_id`. The terminal record
must explicitly reference the supplied `(run_id, proposal_id)`. Reject
missing/null arguments, mismatched terminal record identity, or more than one
terminal record (including duplicates for the same proposal) with
`INVALID_AUDIT_BATCH` before writing any record.
Non-terminal records may accompany one terminal record, but validation applies
to the complete batch: rejection of the entire batch leaves the journal and
proposal state unchanged.

Resolve authority from the owning service and the stored receipt for the
supplied `(run_id, proposal_id)`, not from caller-supplied worker metadata. In
one transaction, validate the complete batch and require that the proposal has
no existing terminal outcome. An unknown run/proposal returns `NOT_FOUND`; an
already-finalized proposal is replayed or rejected without a second write. On
success, atomically append the records and finalize the proposal state.

`COMMIT` is forbidden in `append_audit` and returns `INVALID_AUDIT_BATCH`; its
decision and graph events are persisted exclusively through `append_graph`, with
the same proposal binding and single-terminal checks plus the graph-version
check. Non-terminal-only audit batches require no proposal and never advance
`graph_version`; non-commit terminal appends also leave it unchanged.

`VersionConflict` does not complete the proposal by itself. The serialized
service must durably append the corresponding `CONFLICT` record before returning
that outcome; if persistence fails, return a persistence/service failure
instead, as required by ADR 0006.

#### Graph append binding

`append_graph` requires non-null run/proposal identity and expected graph
version. Its audit records contain exactly one `COMMIT`
bound to the supplied `(run_id, proposal_id)` and no other terminal outcome,
including `ABANDONED`. Its graph events contain at least one event, all bound
to that same run/proposal. An empty mutation is not a graph-version advance.
Accompanying non-terminal audit records must reference the supplied run;
if proposal-scoped, they must reference the same proposal. Run-level audit
records may omit proposal identity. The same accompanying-record binding
applies to terminal `append_audit` batches.

Validate the whole graph batch before any write. Missing/null required fields,
invalid structure, mismatched identities, absent/duplicate `COMMIT`, another
terminal outcome, or empty graph events return `INVALID_GRAPH_BATCH`, leaving
journal, proposal state, and graph unchanged. The EventStore validates structure
and binding; it does not rerun governance policy. In the same transaction, the
supplied `expected_graph_version` must equal the proposal receipt's recorded
`expected_graph_version`; a mismatch is `INVALID_GRAPH_BATCH` with no writes.
The bound value must then equal the current run `graph_version`; otherwise return
`VersionConflict` with no writes. Success atomically appends the complete batch,
finalizes the proposal, and increments graph version exactly once. Any failed
check leaves the whole batch unwritten.

#### Proposal recovery responses

Subsequent submissions follow these rules:

- same `proposal_id` + same canonical request hash + final decision already durable → return/replay the recorded final outcome and recorded resulting graph/journal metadata; do not re-run governance or mutate the graph;
- same `proposal_id` + same canonical request hash + proposal is incomplete → return `PENDING` while the owning service resumes the durable normalized request; do not create a second proposal attempt;
- same `proposal_id` + different canonical request hash → return `IDEMPOTENCY_CONFLICT`; do not evaluate or mutate;
- unknown `proposal_id` → treat as a new proposal submission.

If an incomplete proposal cannot be safely resumed because its required schema/policy/runtime version is unavailable or its durable input is invalid, the owning service may append terminal operational status `ABANDONED` with a reason code. `ABANDONED` is **not** a governance decision and never changes graph state. Reusing that proposal ID replays the terminal abandoned status; a semantic retry requires a new proposal ID.

The command/query plane exposes a proposal-status query keyed by `(run_id, proposal_id)` returning `NOT_FOUND`, `PENDING`, `ABANDONED`, or the durable final governance outcome plus relevant `journal_position` / graph-version metadata. The internal EventStore `get_proposal` provides a consistent durable snapshot for recovery. Public status responses omit internal normalized recovery inputs. Final replay returns the original recorded result metadata even after the run advances.

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

For the first P6-AC whole-system comparison, the C adapter exposes the frozen
ProblemForger graph interaction and governance surface while A exposes neither.
If a later B/C diagnostic is run, B and C must expose the same graph interaction
surface and differ only in governance activation.

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
