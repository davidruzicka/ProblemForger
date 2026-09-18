# Problem graph

## Purpose

The ProblemGraph is an explicit representation of evolving problem state. It is not the harness execution graph and it is not a dump of model chain-of-thought.

The graph exists to make goals, requirements, work units, artifacts, evidence, dependencies, and provenance explicit enough to govern and inspect.

## Minimal initial node categories

Keep the initial ontology small:

- **RootGoal** — the user-level objective or protected anchor;
- **Requirement** — a constraint or condition that must remain satisfied;
- **Task** — a bounded unit of work;
- **Artifact** — code, patch, file, test result, or other produced object;
- **Evidence** — evidence relevant to a claim, entity, or proposed mutation.

Additional node types require demonstrated need.

## Edges

Edges are typed and carry provenance. Candidate examples include:

- `derived_from`;
- `depends_on`;
- `implements`;
- `produces`;
- `supported_by`;
- `conflicts_with`;
- `invalidates`;
- `supersedes`.

The exact initial edge set is finalized during P1/P2 planning.

## Agent interaction

The initial PoC does not automatically serialize the entire graph into model context.

The worker receives a small ProblemForger tool/API surface that can:

- query current graph state or a bounded neighborhood;
- propose node/edge mutations;
- attach or reference evidence;
- request the current graph version.

The worker proposes semantic changes; it never writes authoritative graph state directly.

This is intentionally simpler than introducing a separate context selector/planner subsystem before the core graph hypothesis has been measured.

See ADR 0008.

## Mutation model

A proposal identifies the authoritative graph version on which it was based.

```text
G_v
 + proposed mutation(expected_version=v)
 + evidence references
 -> governor
 -> commit / reject / retry / escalate / conflict
 -> G_(v+n) or unchanged G_v
```

A single accepted mutation may produce multiple domain events and must commit them atomically.

If `expected_version` is stale, the result is a version conflict rather than silent last-write-wins behavior.

## Separate state axes

Do not encode proposal state, entity validity, and verification confidence in one enum.

### Mutation outcome

A mutation proposal attempt can be:

- proposed;
- committed;
- rejected;
- conflicted;
- retry requested;
- escalated.

`retry requested` describes the outcome of the current proposal attempt. If the worker submits another attempt, that is a new proposal with its own identity/version context and should retain causal/provenance linkage to the earlier attempt rather than rewriting it as "retried".

A proposal that is not committed is not part of authoritative graph state, but its proposal/decision audit records remain durable in the run journal.

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

Evidence source and verification method are orthogonal and must not be compressed into a single "strength" enum.

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

See `docs/verification.md`.

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

Each ProblemForger run owns an append-only durable journal.

Every durable record advances per-run `journal_position`. Only graph-changing domain events advance `graph_version`; proposal/decision audit records do not.

The PoC may serialize governance internally, but graph-changing writes use optimistic `expected_graph_version` checks so future parallel workers cannot silently overwrite each other.

Observation/telemetry events remain outside the durable governance journal and do not increment graph version.

See ADR 0006.
