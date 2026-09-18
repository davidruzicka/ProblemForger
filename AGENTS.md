# AGENTS.md

## Purpose

This repository is a research prototype. Preserve experimental validity before implementation speed.

## Language

All code, comments, documentation, issue content, pull-request content, commit messages, and repository communication must be in English.

## Authority order

When sources conflict, use this order:

1. accepted ADRs;
2. domain specifications in `docs/`;
3. `PLAN.md`;
4. the current GitHub issue;
5. implementation;
6. comments and discussion.

Do not silently override a higher-authority source. If an implementation need conflicts with an ADR or specification, stop and propose an ADR/specification change first.

## Architectural invariants

- ProblemForger core is harness-neutral.
- ProblemForger core/application logic runs behind the same separate local service boundary for HarnessX and Pi.
- Harness adapters contain translation/integration logic only, never domain policy.
- The worker model is not the authority for graph state.
- Authoritative graph state is reconstructable from append-only **domain events**.
- Harness/model/tool observations are telemetry and must not be required for graph replay or increment graph version.
- Each run has its own optimistic authoritative event stream; stale writes fail explicitly rather than silently overwriting.
- Mutation outcome, entity lifecycle, and evidence-derived verification status are separate concepts.
- Evidence origin and verification method are separate metadata; no single evidence-strength enum defines truth.
- The initial PoC uses explicit graph query/mutation tools rather than an automatic context selector.
- Model inference remains a harness responsibility in the initial PoC.
- Replaceable infrastructure and policies are accessed through explicit ports/interfaces.
- Core code must not import or instantiate concrete providers.
- Concrete providers are selected through typed configuration and an explicit registry/composition root.
- Provider-specific configuration must not leak into core/domain code.
- In-memory and SQLite are initial persistence adapters, not special cases.
- Prefer mechanically reproducible or external evidence over worker self-assessment when they address the same claim, but keep evidence scope explicit.
- Verifier output is evidence, not ground truth.
- Root goals, anchors, governor policy, audit history, and verification thresholds must not be silently mutable by the worker agent.
- UI is an observer of telemetry/projections and must not be required for correctness.
- Do not build a generic plugin framework unless a real requirement justifies it.

## Scope discipline

- Implement only the current phase and issue.
- Do not implement later phases speculatively.
- Routing is architecturally anticipated but not part of the first graph/governance PoC.
- Avoid broad ontologies in the initial graph schema.
- Avoid multi-agent complexity unless an experiment specifically requires it.
- Do not introduce `ModelProvider`, `ContextSelector`, snapshots, or other future abstractions into P1 unless a current issue proves the need.
- Prefer the smallest mechanism that can falsify or support the current hypothesis.

## Work procedure

Before coding:

1. read the current issue;
2. read all referenced specifications and ADRs;
3. verify that the issue is consistent with them;
4. identify tests and observable evidence required for completion;
5. identify whether an architectural decision is missing.

For every behavioral change or bug fix:

1. demonstrate the previous behavior with a failing test or reproducible check;
2. implement the change;
3. demonstrate that the test/check passes;
4. run relevant regression tests.

For research-facing changes:

- preserve raw experimental data and configuration;
- record model/provider/version where possible;
- record random seeds when applicable;
- distinguish measured results from interpretation;
- do not replace negative results with a more favorable metric after the fact;
- do not change frozen benchmark/task/model/metric choices after observing results without versioning the experiment contract.

## Issues and planning

High-level issues are epics. Before implementing an epic, decompose it into bounded sub-issues with:

- context;
- scope;
- explicit non-scope;
- dependencies;
- acceptance criteria;
- verification evidence.

## Pull requests

A PR should explain:

- what changed;
- why it is within the current issue scope;
- how it was verified;
- whether architecture/specification changed;
- what remains explicitly out of scope.

Architecture-changing implementation discoveries require an ADR proposal before the implementation silently adopts a new direction.
