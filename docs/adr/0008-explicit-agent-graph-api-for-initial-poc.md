# ADR 0008: Use an explicit agent-facing graph API before automatic context selection

- Status: Accepted
- Date: 2026-09-18

## Context

An explicit graph is only useful to the worker if the worker can create/query it. The bootstrap architecture did not specify how semantic graph state enters execution.

Automatically injecting selected graph context would introduce an additional ContextSelector subsystem and confound the first graph/governance experiment.

## Decision

The initial PoC exposes a small harness-neutral graph command/query API.

Harness adapters register thin agent tools that map to operations such as:

- query graph/run state;
- query a bounded subgraph;
- propose a versioned mutation;
- attach/reference evidence through a governed mutation.

The worker remains responsible for decomposition in the initial PoC.

Configuration B and C expose the same graph API and minimal graph-use instructions.

- B applies schema/version/core graph invariants but otherwise accepts valid proposals.
- C adds deterministic governance/evidence policy.

Automatic graph-to-context selection is deferred to a later separately evaluated subsystem.

## Consequences

- The graph intervention is concrete and testable.
- B→C isolates governance more cleanly.
- A→B still includes a tool/prompt intervention and must be interpreted accordingly.
- A future planner/context selector can be added as its own ablation rather than hidden inside the initial graph implementation.
