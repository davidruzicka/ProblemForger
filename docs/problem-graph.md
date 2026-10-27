<a id="spec-graph-model"></a>
<!-- spec-id: GRAPH.MODEL -->
# Problem graph

## Purpose

The problem graph explicitly represents evolving problem state. It is neither the harness execution graph nor a dump of model chain-of-thought.

The graph exists to make goals, requirements, work units, artifacts, evidence, dependencies, and provenance explicit enough to govern and inspect.

## Minimal initial node categories

Keep the initial ontology small:

- **RootGoal**: the run-scoped objective or protected anchor;
- **Requirement**: a constraint or condition that must remain satisfied;
- **Task**: a bounded unit of work;
- **Artifact**: code, patch, file, test result, or other produced object;
- **Evidence**: evidence relevant to a claim, entity, or proposed mutation.

Additional node types require demonstrated need.

## Edges

Edges are typed and carry provenance. The initial kinds are:

- `derived_from`;
- `depends_on`;
- `implements`;
- `produces`;
- `supported_by`;
- `conflicts_with`;
- `invalidates`;
- `supersedes`.

The graph-v1 edge set is exactly the eight names above. Edges describe relationships;
creating an `invalidates` or `supersedes` edge does not itself change lifecycle.
Lifecycle changes are explicit operations below.

## Agent interaction

The initial PoC does not automatically serialize the entire graph into model context.

The worker receives a small ProblemForger tool/API surface that can:

- query current graph state or a bounded neighborhood;
- propose node/edge mutations;
- attach or reference evidence;
- request the current graph version.

The worker proposes semantic changes; it never writes authoritative graph state directly.

A separate context selector or planner subsystem is deferred until the core graph hypothesis has been measured.

See ADR 0008.

## Mutation model

A proposal identifies the authoritative graph version on which it was based.

```text
G_v
 + proposed mutation(expected_version=v)
 + evidence references
 -> governor
 -> commit / reject / retry / escalate / conflict
 -> G_(v+1) or unchanged G_v
```

A single accepted mutation may produce multiple domain events and must commit them atomically.

If `expected_version` is stale, the result is a version conflict rather than silent last-write-wins behavior.

## Separate state axes

Do not encode proposal state, entity validity, and verification confidence in one enum.

### Proposal receipt / pending state

Receiving a proposal is not a governance outcome.

The durable journal records a proposal receipt with its proposal identity, expected graph version, operations/evidence references, provenance, and a pending/no-final-decision status until a terminal governance decision is recorded.

A crash may therefore leave a durably recorded proposal with no final decision; this is an incomplete attempt, not a completed outcome.

### Mutation outcome

A completed mutation proposal attempt has exactly one final governance outcome:

- committed;
- rejected;
- conflicted;
- retry requested;
- escalated.

`retry requested` describes the final outcome of the current proposal attempt. If the worker submits another attempt, that is a new proposal with its own identity/version context and should retain causal/provenance linkage to the earlier attempt rather than rewriting it as "retried".

A proposal that is not committed is not part of authoritative graph state, but its proposal receipt and final decision records remain durable in the run journal.

### Entity lifecycle

A committed graph entity is initially active and may later become:

- superseded;
- invalidated.

The PoC should avoid destructive deletion of historical entities. Later evidence invalidates/supersedes them through new domain events.

### Verification state

Verification is derived from attached evidence and policy; it is not the entity lifecycle.

Useful derived UI/status terms may include:

- unverified;
- locally supported;
- externally supported;
- disputed.

These are projections over evidence, not historical states that overwrite prior truth.

See ADR 0007.

## Evidence model

Evidence origin and verification method are orthogonal and must not be compressed into a single "strength" enum.

At minimum an evidence record should be able to represent:

### Origin

Examples:

- worker/model;
- harness/tool/environment;
- independent verifier;
- human;
- benchmark/evaluator.

### Method

Examples:

- assertion;
- deterministic check;
- observed outcome;
- learned judge;
- human review.

### Subject and result

Evidence must identify what claim/entity/mutation it supports or contradicts and preserve enough result/provenance metadata to audit the decision.

A passing test is strong evidence for the behavior that test covers; it is not automatically proof that the root goal is fully satisfied.

The normative trust, immutable-subject binding, and recovery rules are [EVIDENCE-TRUST through EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-trust). Evidence metadata describes provenance; worker-controlled metadata cannot establish trusted provenance.

## Anchors and drift

Root goals and selected requirements may be protected anchors. Derived nodes must retain provenance back to them.

Potential drift signals include:

- unresolved provenance;
- repeated reversals/reopening;
- mutation rate;
- graph cycles where disallowed;
- verifier disagreement;
- confidence decay;
- later invalidation frequency.

These are research hypotheses until evaluated.

## Versioning and concurrency

The [EventStore port](modules.md#spec-modules-eventstore-port), [protocol
contract](protocol.md#spec-protocol-proposal-recovery), and ADR 0006 own journal,
lease, and append algorithms. The graph-level invariants are: a committed
mutation advances `graph_version` once as a complete batch; stale
`expected_graph_version` values conflict rather than overwrite; and telemetry
remains outside authoritative graph state. The graph projection must therefore
never expose a prefix of an atomic mutation batch.

## Concrete graph-v1 contract

[contracts/graph-v1.json](../contracts/graph-v1.json) owns the closed field
shapes, node/edge kinds, operation-to-event mapping, and lifecycle transition
table. [Fixtures](../tests/fixtures/graph-v1.json) contain valid/invalid shapes
and every lifecycle state pair. These are domain payloads inside the existing
v1 protocol, not a replacement transport or journal format. The replay
implementation validates committed events and candidate mutations against this
contract; worker queries expose bounded public projections.

The graph belongs to one explicit `run_id`. Node IDs and edge IDs have separate
run-local namespaces; an edge endpoint always identifies a node in that run.
IDs use the protocol's existing identifier rules. They cannot be reused after
invalidation or supersession. No `problem_id` is introduced. Accepted
[ADR 0012](adr/0012-problem-identity-and-run-ownership.md) owns the future
Problem/run relationship. A Problem's intended outcomes are not stored or
made authoritative by this run graph.

### Entities and provenance

A node input contains `node_id`, `kind`, `label`, and `protected`. An edge input
contains `edge_id`, `kind`, `source_id`, and `target_id`. Their meanings and
endpoints are immutable. Labels are nonblank UTF-8 text, bounded at 4096 bytes.
There is no arbitrary attributes bag in graph-v1. Artifact bytes and raw
checker outputs remain outside graph entities; an Artifact label alone does
not identify checked bytes or satisfy an evidence requirement.

A committed entity starts with `lifecycle=active` and an empty `evidence_refs`
list. Its public projection adds `created_by`: `proposal_id`, `record_id`,
`journal_position`, and `graph_version` copied from its creating journal event.
The enclosing graph response supplies `run_id`. These fields are service-derived;
workers cannot supply them. Later attachment/lifecycle provenance remains in
the corresponding durable events; creation provenance is never overwritten.
The projection retains inactive entities and their incident edges. Invalidation
does not recursively mutate dependencies or imply that an incident edge still
provides valid support. P3 owns admissibility and downstream policy.

RootGoal nodes must be protected. A Requirement may also be a protected anchor;
other node kinds must have `protected=false`. Protected creation and changes
require an explicitly authorized service/operator path. P2's worker path must
reject creating a RootGoal or any protected node, changing its lifecycle, or
attaching evidence to it until P3 defines the authorized meta-operation.
A worker cannot remove protection through a new node with a reused ID. This
contract does not add an operator transport or choose a bootstrap mechanism;
service integration must define how trusted initial anchors are registered
without widening worker authority.

A fresh graph has version zero and empty node/edge collections; no RootGoal
is invented from a harness session. Nonempty committed graph state must contain
exactly one RootGoal. Every other node must have a directed `derived_from` path
to that RootGoal when the complete batch is considered. This structural path
retains provenance; it is not proof of semantic relevance. Retained inactive
nodes/edges may establish historical provenance. No additional acyclicity or
semantic edge-kind restrictions are imposed in P2.

### Operations and graph events

Each operation carries `graph_schema_version=1` and its `op` discriminator.
Its other fields are defined by the JSON contract:

| Operation | Fields beyond version/op | Graph event type |
| --- | --- | --- |
| `create_node` | `node` | `node_created` |
| `create_edge` | `edge` | `edge_created` |
| `attach_evidence` | `entity_kind`, `entity_id`, `evidence` | `evidence_attached` |
| `change_lifecycle` | `entity_kind`, `entity_id`, `lifecycle`, `reason` | `lifecycle_changed` |

`entity_kind` is `node` or `edge`. Creating a node/edge with an existing ID is
invalid even when its content is identical. To revise meaning, create a new
entity and explicitly supersede the old one. A newly created edge requires
both endpoints to exist and be active at that point in operation order.
Self-edges are allowed; semantic usefulness is a governance concern.
Attachments and lifecycle changes require an existing active target. Evidence
references contain immutable `evidence_id` and `content_digest` (a `sha256:`
prefix and 64 lowercase hexadecimal digits). A duplicate evidence ID on the
same target is invalid, including one supplied with a different digest.
A digest is not a trust attestation. Registration, producer identity,
subject binding, and admissibility are owned by
[EVIDENCE-TRUST through EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-trust).
P2 may retain asserted references; it cannot label them trusted.

The lifecycle table permits only `active → superseded` and
`active → invalidated`, with a nonblank bounded `reason`. Inactive states are
terminal; repeating a transition, reactivation, and destructive deletion are
invalid. A protocol retry replays the original proposal outcome instead of
applying its operations twice. Evidence-derived verification is separate
from lifecycle; attaching evidence never changes lifecycle automatically.

A successful operation emits exactly one corresponding graph event, in input
order. Its `event_schema_version` is 1; its payload is the operation's fields
with `op` and `graph_schema_version` removed. The Event definition describes
only this nested event triplet; journal envelope/proposal/version fields remain
owned by [MODULES.EVENTSTORE-PORT](modules.md#spec-modules-eventstore-port).
`created_by` is derived from that envelope, not duplicated in the payload.
All events share the single resulting graph version of the committed batch.

### Batch validation and replay

Prepare a private candidate state from the caller's expected committed version.
Validate operation shapes, then apply them sequentially to that candidate.
Later operations may reference entities created earlier in the same batch;
forward references are invalid. Final RootGoal/provenance checks inspect the
complete candidate, so a node and its `derived_from` edge may be created in
one batch. A batch must contain at least one operation. Any invalid operation
or final graph invariant discards the entire candidate and emits no graph
events. The application still retains the receipt and final outcome under
[PROPOSAL-RECOVERY](protocol.md#spec-protocol-proposal-recovery).
P3 owns outcome/reason mapping; this schema does not mint governance outcomes
or override stale-version/recovery precedence.

Replay consumes only complete committed batches in journal order, applying
the same structural rules without re-running evidence producers or governor
policy. Audit-only records cannot affect the projection. Neither a failed
candidate nor a partial event prefix becomes a queryable graph version.
The [EventStore contract](modules.md#spec-modules-eventstore-port) owns atomic
append, version assignment, optimistic conflict detection, and durability.

Unknown operation/kind/field/version is invalid input. Replay of an unsupported
event type/version or structurally invalid committed batch fails explicitly;
it must never skip that event and return a plausible partial graph. P1's opaque
test payloads are not graph-v1 histories. There is no silent conversion of
legacy/unknown payloads. Introducing another graph payload meaning requires
an explicit version/reader decision under the EventStore schema rules.

### Protocol compatibility and verification boundary

The protocol envelope remains v1. Its `operations` and graph-result entity
objects are currently opaque JSON; the new domain shapes fit those existing
slots. The wire codec remains structural and must not import graph policy.
The service integration in issue #43 supplies graph queries, selection,
pagination, and domain error handling over replay from #42. Wire clients
continue to carry opaque graph payloads; schema-only issue #41 changed no
client or service behavior.

The graph-contract tests reuse the existing finite-schema interpreter. Lifecycle vectors
check the finite table; they do not prove runtime transition enforcement.
Replay tests must cover duplicate IDs, missing/inactive targets, same-batch
references, whole-batch rollback, provenance paths, protected worker operations,
unsupported event histories, and provider/restart equivalence. Service tests
must prove authorization, redaction, bounds, and durable outcomes. None of
these graph-contract fixtures replaces the P3 evidence/governance tests or freezes
`graph-intervention-v1`.


## Replay implementation

`problemforger.application.graph.replay_graph(store, run_id, page_size=100)`
uses only the EventStore port. It captures the run's committed graph version
and last journal position, then reads that prefix in bounded pages. It groups
contiguous graph events into batches by version and proposal. Pages may split
a mutation. Replay returns an immutable `GraphProjection` after validating the
complete captured prefix and excludes appends after that boundary. It sorts
nodes and edges by their run-local IDs; `to_value()` returns detached JSON data.

After each batch, replay checks the graph-v1 structure and final provenance.
It preserves historical entities, evidence references, and creation provenance.
Authorization, evidence producers, and governor policy are not re-run.
Unknown or malformed events, truncated or gapped journals, records from another
run, and unsupported batch versions raise `GraphReplayError`. Missing or
unreadable runs and journal pages also fail explicitly. These failures return
no partial state. The EventStore provider must commit atomically and report
committed run boundaries accurately.

The existing `python3 -m scripts.generate_protocol_contract` command embeds
the graph contract, so replay needs no contract file I/O at runtime. The
service uses this projection for queries and private mutation candidates.
Observers continue to use the service API.

## Service integration

`get_graph` accepts an omitted or empty `selection` for the whole graph, or
`{"node_id": "..."}` for that node, its incident edges, and their endpoints.
Historical inactive entities remain visible. Unknown selection fields, malformed
IDs, and malformed cursors return `PROTOCOL_ERROR`; an absent selected node
returns `NOT_FOUND`. The wire codecs keep selection opaque.

Pages order all nodes by ID, then all edges by ID, using Unicode code-point
order. `limit` bounds their combined count under the existing 1–100 contract.
Continuation cursors bind run ID, canonical selection, and graph version; they
are not authorization capabilities. A graph change invalidates continuation,
so callers restart without a cursor. Audit-only appends preserve continuation.
An invalid or mismatched cursor fails explicitly instead of mixing versions.
A completed page returns `next_cursor=null` and `has_more=false`.
Pages also stop before the encoded 4 MiB response limit, including the envelope
and continuation metadata. A byte-limited page may contain fewer entities than
requested; its cursor resumes at the next entity without skipping it.

Each entity's compact UTF-8 JSON projection, including evidence references and
creation provenance, is capped at 1 MiB by candidate validation. New creation
provenance reserves the largest wire-safe journal-position width before the
provider assigns its actual position. Attachments that exceed this bound reject
the whole proposal with `invalid_graph_mutation`; evidence is never truncated.
An oversized entity in an older journal returns explicit `PAYLOAD_TOO_LARGE`
when queried. The socket boundary also returns encoding errors as protocol
errors instead of closing a valid request without a response.

For non-C runs, structurally valid proposals commit through `append_graph`.
Invalid shapes, operation order, protection, or complete graph invariants
produce durable `REJECT` with `invalid_graph_mutation`. Stale versions produce
durable `CONFLICT` before structural evaluation. These are P2 structural
outcomes, not P3 evidence-policy judgments. Configuration C retains
`P1_GOVERNANCE_NOT_IMPLEMENTED` rejection until P3 supplies its policy.
Evidence references remain assertions and do not establish trusted provenance.
Before committing, the application checks the expanded decision/event batch
against the shared serialized journal record and append limits. An oversized
batch produces durable `REJECT` with `graph_batch_too_large`, preserving the
graph version; same-ID retries replay that rejection after restart. This check
uses the same provider-neutral serialization and bounds as both stores.

Trusted service-owner setup calls
`ProtocolApplication.bootstrap_root(run_id, proposal_id, label)` for a registered
version-zero non-C run. It commits one protected `RootGoal` with ID `root` via
the same durable receipt/atomic commit path. Reusing its proposal ID and label
replays the result; changed content conflicts. It adds no worker operation,
transport, or worker-controlled metadata switch. The operator runs setup in
the exclusive store-owner process before serving workers, or with the service
stopped, and retains the proposal ID for recovery. Workers cannot bootstrap
an empty graph; attempts to create or modify anchors are rejected.

The initial Unix socket is one OS-authorized worker capability for all runs
in that service instance. Separate trust domains use separate service/store/
socket instances. Embedders can supply an `authorize_run(operation, run_id)`
callback; the application checks it before any store access, including existing
run-registration retries and metadata comparisons. This callback does not add
a worker token or a new transport. Administrative bootstrap remains outside
the worker capability.
