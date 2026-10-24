# ADR 0012: Problem identity and run ownership

- Status: Accepted
- Proposal date: 2026-10-15
- Decision date: 2026-10-24
- Related: [ADR 0011](0011-claude-code-plugin-harness.md), [issue #37](https://github.com/davidruzicka/ProblemForger/issues/37), [P2 issue #3](https://github.com/davidruzicka/ProblemForger/issues/3)

## Context

A candidate long-term direction, conditional on examination results, is to make the product-level Problem the unit users research, decompose, plan, and coordinate across multiple projects or resources. Agents, executions, and harness sessions would be replaceable mechanisms rather than the user's primary unit of work.

The current v1 protocol defines `run_id` as the durable run/journal scope. It defines no product-level Problem identity or cross-run operations and makes no one-to-one Problem/run mapping claim. This decision defines the ownership boundary without changing that protocol or making a product pivot commitment.

Representative scenarios reviewed:

- One Problem spans at least two repositories/resources.
- Research and implementation happen in separate phases and may use separate runs.
- A harness session is replaced while the Problem's intent and run audit history remain available.

## Decision

**GO** for a minimal product-level Problem identity that can link multiple project/resource scopes and multiple phase-labelled runs. This accepts the identity and ownership direction only. It does not approve a product pivot or claim that cross-project demand has been empirically validated. The candidate direction remains subject to a separate evaluation after P6; P6 itself does not validate it.

The ownership boundary is:

- **Problem:** stable identity, user intent and intended outcomes, references to project/resource scopes, and ordered links to phase-labelled runs. The Problem is a coordinating record, not a shared mutable graph or journal.
- **Run:** its graph and `graph_version`, proposal attempts and receipts, append-only durable journal, and evidence/artifacts it produces. Run graphs remain independently versioned and auditable. Later runs may refer to immutable artifact/evidence identifiers from earlier runs; they do not mutate the earlier run.
- **Harness adapter/session:** native session lifecycle, credentials, and optional telemetry. A session is replaceable execution context, never the identity of a Problem or durable run.

Problem-level intent and intended outcomes are canonical to the Problem. A run graph's RootGoal remains a run-scoped objective; a later integration design must define explicit references to the relevant Problem outcomes without making the run graph authoritative for Problem state.

One Problem may link to multiple resources and runs. An associated run belongs to at most one Problem; unassociated v1 runs remain valid. This is a one-to-many relationship, not a one-to-one mapping. A replacement session must explicitly resume a `run_id` or start a successor run linked to the same Problem. It must not select a run through ambient session state.

## P2 and protocol boundary

- Keep the v1 protocol, its explicit `run_id`, and the P6 HarnessX pilot unchanged.
- P2 continues to implement one run-scoped graph over one run-scoped journal. Graph versions, replay, proposal outcomes, evidence, and recovery remain run-owned.
- This ADR does not add a Problem registry/API, cross-run operations, multi-project persistence, or shared graph mutations to P2. It does not require `problem_id` on graph nodes or journal events.
- Before implementing Problem persistence or cross-run reads, create a separately scoped issue that defines its API, durable association model, idempotency, consistency, recovery, and access boundaries. Do not infer those mechanisms from this ADR.
- After P6, if the direction remains justified, run a separately frozen evaluation spanning at least two repositories/resources, research followed by implementation, and a replaced harness session. Keep it separate from P6 and do not pool its results with P6.
- P10 remains the observer/debug UI. A Problem-first, goal-oriented interface remains a later decision tracked by issue #12.

## Alternatives considered

- **NO-GO; keep run as the only product-level identity.** This avoids a Problem registry and cross-run associations, but cannot represent the candidate multi-resource workflow as one user-owned Problem. The reviewed scenarios support a thin Problem identity, so this was not selected.
- **Use one shared graph and journal for the entire Problem.** This would couple graph versions, mutation conflicts, and audit ownership across resources and phases. The scenarios can be represented with links between independently owned runs, so a shared graph/journal is unnecessary.
- **Defer the decision.** This would leave P2's schema gate unresolved and block its freeze. The ownership boundary is sufficiently narrow to decide now while keeping implementation out of P2.

## Consequences

- A future implementation needs a durable Problem-to-resource/run association and a bounded cross-run read model.
- A Problem-level record and run-level journals introduce a persistence consistency and recovery boundary. The later implementation design must specify it; this ADR does not.
- Each run retains independent replay, audit, and version-conflict semantics. There is no cross-run transaction or shared graph version.
- The product direction remains a hypothesis until the separate post-P6 multi-resource evaluation supports it.
