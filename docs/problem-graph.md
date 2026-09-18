# Problem graph

## Purpose

The ProblemGraph is an explicit representation of the evolving problem state. It is not the harness execution graph and it is not a dump of the model's chain of thought.

## Minimal initial node categories

The initial ontology should remain small:

- **RootGoal** — the user-level objective or immutable anchor;
- **Requirement** — a constraint or condition that must remain satisfied;
- **Task** — a bounded unit of work;
- **Artifact** — code, patch, file, test, result, or other produced object;
- **Evidence** — evidence relevant to a claim or transition.

Additional types require demonstrated need.

## Edges

Edges are typed and carry provenance. Candidate examples include:

- `derived_from`;
- `depends_on`;
- `implements`;
- `produces`;
- `verified_by`;
- `conflicts_with`;
- `invalidates`.

The exact initial edge set is a P1/P2 planning decision.

## Mutation model

The worker proposes mutations; it does not directly change authoritative state.

A mutation must identify the graph version it was based on. The governor validates it before commit.

```text
G_t
 + proposed mutation(base_version=t)
 + evidence
 -> governor
 -> commit/reject/retry/escalate
 -> G_(t+1) or unchanged G_t
```

## Lifecycle

Do not collapse all "success" into one state.

The initial model must be able to represent at least:

- proposed;
- accepted/committed;
- locally verified;
- externally verified;
- invalidated later.

A later observation may invalidate an earlier accepted claim without rewriting the historical event.

## Evidence classes

Evidence strength/source must be explicit. At minimum distinguish:

- **asserted** — produced by an agent/model;
- **learned verification** — produced by a learned verifier/judge;
- **observed** — external observed behavior;
- **deterministic** — mechanically verified property.

These classes are not interchangeable.

## Anchors and drift

Root goals and selected requirements may be anchors. Derived nodes must retain provenance back to them.

Potential drift signals include:

- unresolved provenance;
- repeated reversals/reopening;
- mutation rate;
- graph cycles where disallowed;
- disagreement between verifiers;
- confidence decay;
- later invalidation frequency.

Drift metrics are hypotheses until evaluated.

## Concurrency

Parallel mutation support must use graph versions/conflict detection. The first implementation may serialize commits, but the event model must not assume silent last-write-wins behavior.
