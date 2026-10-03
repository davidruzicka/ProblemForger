# AGENTS.md

## Purpose

This repository is a practical feasibility prototype. Prefer the smallest useful implementation and evaluation that inform the next decision. Report evidence and limitations honestly, preserve architectural invariants, and do not change frozen experiment choices after observing results.

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

Owners: [ADR 0001](docs/adr/0001-harness-neutral-core.md) and [ADR 0009](docs/adr/0009-separate-local-process-service-boundary.md) (harness neutrality, service boundary, HarnessX/Pi adapters); [ADR 0002](docs/adr/0002-event-sourced-authoritative-state.md) and [ADR 0006](docs/adr/0006-authoritative-domain-events-and-stream-concurrency.md) (journal, versions, outcomes, receipts); [ADR 0003](docs/adr/0003-ports-adapters-config-modules.md) (ports, providers, configuration, EventStore durability); [ADR 0004](docs/adr/0004-external-graph-governor.md) (worker vs. governor authority); [ADR 0007](docs/adr/0007-separate-lifecycle-verification-and-evidence-axes.md) (outcome, lifecycle, and evidence axes); [ADR 0008](docs/adr/0008-explicit-agent-graph-api-for-initial-poc.md) (explicit graph API); [Verification](docs/verification.md) (evidence preference, verifier output); [UI](docs/ui.md) and [Architecture](docs/architecture.md) (observer role; observers use the service/application read API, never EventStore directly).

- ProblemForger core is harness-neutral.
- ProblemForger core/application logic runs behind the same separate local service boundary for HarnessX and Pi.
- Harness adapters contain translation/integration logic only, never domain policy.
- The worker model is not the authority for graph state.
- Each run has an append-only durable run journal. Governance proposals/outcomes and graph-changing domain events are durable records; harness/model/tool observations remain optional telemetry.
- Every durable journal record has a monotonic `journal_position`; each committed mutation batch advances `graph_version` exactly once, and all graph-changing events in that batch share the resulting version.
- Authoritative graph state is reconstructable from the graph-changing records in the durable journal.
- Harness/model/tool observations are telemetry and must not be required for graph replay or auditability.
- Every externally returned governance outcome (`COMMIT`, `REJECT`, `RETRY`, `ESCALATE`, `CONFLICT`) must be durably recorded before the response is considered complete.
- Durable proposal receipts must contain enough normalized/versioned input for restart recovery. The initial P1 service has one exclusive owner and serializes proposal processing, so it does not add claims, leases, or fencing epochs before a measured need for parallel workers exists.
- Each run uses optimistic graph-version checks for graph-changing writes; stale writes fail explicitly rather than silently overwriting.
- Mutation outcome, entity lifecycle, and evidence-derived verification status are separate concepts.
- Evidence origin and verification method are separate metadata; no single evidence-strength enum defines truth.
- The initial PoC uses explicit graph query/mutation tools rather than an automatic context selector.
- Model inference remains a harness responsibility in the initial PoC.
- Replaceable infrastructure and policies are accessed through explicit ports/interfaces.
- Core code must not import or instantiate concrete providers.
- Concrete providers are selected through typed configuration and an explicit registry/composition root.
- Provider-specific configuration must not leak into core/domain code.
- In-memory and SQLite implement the same EventStore port, but durability is an explicit capability: memory is ephemeral/test-only, while normal service execution requires a durable provider such as SQLite.
- Prefer mechanically reproducible or external evidence over worker self-assessment when they address the same claim, but keep evidence scope explicit.
- Verifier output is evidence, not ground truth.
- Root goals, anchors, governor policy, audit history, and verification thresholds must not be silently mutable by the worker agent.
- UI is an observer of optional telemetry, graph projections, and read-only durable governance/audit projections; it must not be required for correctness or access EventStore directly.

## Scope discipline

- Do not build a generic plugin framework unless a real requirement justifies it.
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
4. run relevant regression tests, and before claiming completion run every command in [Run checks](docs/specification-checks.md#run-checks).

For research-facing changes:

- follow the normative [evaluation contract](docs/evaluation.md) for frozen artifacts, task exposure, attempt budgets, exclusions, metrics, and raw-data retention; do not duplicate those algorithms in instructions or issues;
- do not change frozen research choices after observing results or pool different experiment versions;
- preserve raw evidence and distinguish measured results from interpretation, including null/negative results;
- keep harness-native trajectories adapter-owned; only normalized observations cross core boundaries;
- follow [STORE-OWNER](docs/protocol.md#spec-protocol-store-owner) and [PROPOSAL-RECOVERY](docs/protocol.md#spec-protocol-proposal-recovery) for persistence/recovery, and [EVIDENCE-TRUST](docs/verification.md#spec-verification-evidence-trust), [EVIDENCE-BINDING](docs/verification.md#spec-verification-evidence-binding), and [EVIDENCE-RECOVERY](docs/verification.md#spec-verification-evidence-recovery) for evidence;
- all run-scoped protocol/tool operations carry explicit `run_id`; no ambient/session-selected run context.

Use the [contract ownership map](docs/specification-checks.md#contract-ownership) to find the normative source. ADRs retain decision authority; operational specifications own algorithms. Plans, audit notes, and issues summarize scope and reference requirements rather than restating policy.

## Before you commit

1. Review the net diff against the branch you will merge into, not only your own edits: `git diff $(git merge-base origin/<target> HEAD)` runs from the merge base to your working tree, so it covers uncommitted work. Lines disappearing that you never wrote mean you dropped someone else's merged work.
2. Run `scripts/review_diff.sh --target <target>` (default `main`) and fix what it reports.
3. If your change relies on "all X do Y", produce that list mechanically instead of assuming it.
4. Execute every branch you added at least once, the error path included.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <subject>`, for example `docs(agents): link invariants to owning ADRs` or `fix(persistence): reject stale graph-version writes`. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`. The scope names a real code or documentation area, never a phase, issue, or internal ID; the subject says what changed in plain English.

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


## Pull-request review loop

For pull requests labeled `review-loop`, follow `docs/review-loop.md`.

In particular:

- automatically fix and verify mechanical/consistency defects that do not change accepted architecture or the frozen research contract;
- stop for human input before accepting architecture, ADR, experiment-design, benchmark, primary-metric, or other research-method changes with multiple defensible choices;
- push the verified fix before replying in the original review thread and resolving it;
- continue until the latest review covers the current head and no valid unresolved thread remains.
