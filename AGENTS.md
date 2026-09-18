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
- Harness adapters contain translation/integration logic only, never domain policy.
- The worker model is not the authority for graph state.
- Authoritative state is reconstructable from an append-only event log.
- Replaceable infrastructure and policies are accessed through explicit ports/interfaces.
- Core code must not import or instantiate concrete providers.
- Concrete providers are selected through typed configuration.
- Provider-specific configuration must not leak into core/domain code.
- In-memory and SQLite are initial persistence adapters, not special cases.
- Prefer deterministic or externally observed evidence over learned verification.
- Verifier output is evidence, not ground truth.
- Root goals, anchors, governor policy, audit history, and verification thresholds must not be silently mutable by the worker agent.
- UI is an observer of the event stream and must not be required for correctness.
- Do not build a generic plugin framework unless an actual second implementation requires it.

## Scope discipline

- Implement only the current phase and issue.
- Do not implement later phases speculatively.
- Routing is architecturally anticipated but not part of the first graph/governance PoC.
- Avoid broad ontologies in the initial graph schema.
- Avoid multi-agent complexity unless an experiment specifically requires it.
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
- do not replace negative results with a more favorable metric after the fact.

## Issues and planning

High-level issues are epics. Before implementing an epic, decompose it into bounded sub-issues with:

- scope;
- non-scope;
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
