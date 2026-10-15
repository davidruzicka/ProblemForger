# ADR 0012: Problem identity and run ownership

- Status: Proposed
- Date: 2026-10-15
- Related: [ADR 0011](0011-claude-code-plugin-harness.md), [issue #37](https://github.com/davidruzicka/ProblemForger/issues/37), [P2 issue #3](https://github.com/davidruzicka/ProblemForger/issues/3)

## Context

A candidate long-term direction, conditional on examination results, is to make the product-level Problem the unit users research, decompose, plan, and coordinate across multiple projects or resources. Agents, executions, and harness sessions would be replaceable mechanisms rather than the user's primary unit of work.

The current v1 protocol defines `run_id` as the durable run/journal scope. It defines no product-level Problem identity or cross-run operations and makes no one-to-one Problem/run mapping claim. This ADR is proposed to prevent P2's graph schema from accidentally deciding that relationship before representative scenarios are reviewed.

## Decision to make

Before P2 freezes its graph schema, decide whether a product-level Problem is needed and, if so, define its minimal relationship to:

- project/resource scopes;
- one or more run-scoped graphs and graph versions;
- research, implementation, and verification phases;
- execution attempts and replaceable harness sessions;
- durable journals, evidence, and any cross-run queries or mutations.

Use representative scenarios, including one Problem spanning at least two repositories/resources, research followed by implementation, and a replaced harness session. Keep the model minimal; do not define a universal ontology.

## Constraints while unresolved

- This proposal does not approve a product pivot; examination results determine whether to proceed.
- Keep the v1 protocol and P6 HarnessX pilot unchanged.
- Keep P2 run-scoped until an accepted decision exists; do not add `problem_id`, cross-run operations, or multi-project persistence by implication.
- If the direction is rejected, retain the run-scoped model and document the no-go rationale.

## Acceptance criteria

Issue #37 records a go/no-go decision, alternatives, ownership boundaries, and consequences. If the direction is a go, replace this proposal with an accepted ADR before P2 schema freeze. If it is a no-go, close the design gate without adding product-level identity to v1.
