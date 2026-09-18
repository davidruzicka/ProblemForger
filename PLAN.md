# ProblemForger plan

## Goal

ProblemForger investigates whether an externally governed, versioned problem graph can make AI-agent work more observable, locally verifiable, and measurable.

Primary hypothesis:

> Can an externally governed problem graph turn variable agent execution into locally verifiable decisions with measurable failure probabilities?

Secondary hypothesis:

> Can those estimates safely route individual subproblems to the cheapest adequate model?

The initial domain is software engineering because tests, compilers, type checkers, static analysis, repository state, and executable behavior provide strong external evidence.

## Non-goals for the initial PoC

- building another full agent framework;
- autonomous harness self-modification;
- complex multi-agent orchestration;
- a universal problem ontology;
- production-scale graph storage;
- active model routing before graph/governance evaluation;
- making reliability claims before controlled evaluation;
- requiring a graphical UI for correctness.

## P0 decisions now fixed

The P0 audit established these implementation constraints:

- ProblemForger core runs as a separate Python 3.12+ local process/service.
- HarnessX and Pi use the same versioned service boundary through thin adapters.
- Each run has an append-only durable journal for governance audit records and graph-changing domain events, separate from harness/model/tool telemetry.
- The journal has monotonic `journal_position`; each atomic committed graph mutation advances optimistic `graph_version` exactly once, regardless of the number of graph events it emits.
- Mutation outcome, entity lifecycle, and verification status are separate concepts.
- Evidence origin and verification method are orthogonal metadata.
- The first PoC exposes explicit graph query/mutation tools; it does not introduce an automatic context selector.
- Model execution stays in the harness; the initial core does not define a `ModelProvider` abstraction.
- Replaceable infrastructure/policies use explicit ports and configuration-selected providers.
- P6 uses the frozen A/B/C experiment contract in `docs/evaluation.md`.

See ADRs 0001–0009.

## Phase order

- [ ] **P0 — Specification audit and experiment contract**
  - [x] audit specifications/ADRs for contradictions and hidden assumptions;
  - [x] verify and expand related work from current primary sources;
  - [x] freeze the first A/B/C evaluation protocol;
  - [x] resolve event, lifecycle, evidence, runtime-boundary, and graph-interaction ambiguities;
  - [x] decompose P1 into bounded implementation issues;
  - [ ] merge/review the P0 specification PR.

- [ ] **P1 — Harness-neutral core contracts and module system**
  - Python package/tooling and dependency boundaries;
  - durable run-journal envelope, audit records, graph-version semantics, and optimistic append contract;
  - `EventStore` port + ephemeral in-memory adapter + durable SQLite adapter/contract tests;
  - typed provider configuration and explicit module registry/composition root;
  - observation/telemetry contract;
  - local service transport decision and protocol skeleton;
  - graph command/query contract needed by later adapters.

- [ ] **P2 — Event-sourced ProblemGraph**
  - minimal node/edge schema;
  - deterministic replay/projection;
  - graph versions and provenance;
  - entity invalidation/supersession semantics;
  - provider-agnostic replay/projection tests over the EventStore contract.

- [ ] **P3 — Governed mutations and deterministic evidence**
  - proposed vs committed mutations;
  - preconditions/invariants;
  - deterministic/external evidence;
  - commit/reject/retry/escalate/conflict decisions;
  - protected root anchors and global checks.

- [ ] **P4 — HarnessX adapter**
  - thin processor/client integration only;
  - capability declaration;
  - ProblemForger graph tools;
  - observation telemetry;
  - no ProblemForger domain logic in the adapter.

- [ ] **P5 — Pi adapter**
  - independent portability validation;
  - same ProblemForger service/protocol;
  - thin TypeScript extension/client;
  - minimal native TUI status only.

- [ ] **P6 — Baseline and graph/governance evaluation**
  - freeze/hash `graph-intervention-v1`, `governance-policy-v1`, and executable `graph-metrics-v1` before exposing P6 tasks;
  - materialize the frozen task manifest only after those artifacts are fixed;
  - run frozen A/B/C experiment from `docs/evaluation.md`;
  - preserve the frozen graph intervention identically between B and C;
  - report task resolution, cost, latency, graph overhead, and propagation metrics;
  - retain null/negative results.

- [ ] **P7 — Learned verifier**
  - verifier port and baseline implementation;
  - verifier evidence remains distinct from ground truth;
  - independent evaluation against later external outcomes.

- [ ] **P8 — Calibration and abstention**
  - calibrated probability of verdict correctness;
  - task-level held-out calibration;
  - reliability/Brier/ECE/selective accuracy;
  - novelty/OOD signal;
  - abstention/escalation policy.

- [ ] **P9 — Model suitability estimation and routing**
  - target quantity: `P(success | node, graph_state, model, budget)`;
  - model profiles learned from outcomes, including local/fine-tuned models;
  - uncertainty-aware routing;
  - controlled exploration/shadow evaluation to reduce selection bias.

- [ ] **P10 — Observer/debug UI**
  - harness-neutral event/projection consumer;
  - current objective/node, provenance, evidence, model rationale, confidence, timeline, warnings, local graph;
  - graph visualization remains secondary to causal/provenance inspection.

- [ ] **P11 — Full ablation and portability study**
  - baseline;
  - + problem graph;
  - + deterministic governance;
  - + learned verifier;
  - + calibration/abstention;
  - + routing;
  - repeat across HarnessX and Pi where technically comparable;
  - re-audit and freeze an independent external-validity benchmark.

## Definition of done for the PoC

The PoC is complete when:

- the same core/service runs through at least HarnessX and Pi adapters;
- authoritative graph state is replayable from graph-changing durable journal records;
- every governance proposal/outcome needed for audit/evaluation survives restart;
- harness telemetry is not required for graph replay or governance audit;
- graph mutations cannot be silently committed by the worker model;
- deterministic evidence and learned evidence are represented separately;
- at least one controlled benchmark compares the planned ablations;
- calibration claims use task-level held-out data;
- routing, if enabled, includes uncertainty and exploration controls;
- all reported improvements include cost/latency and repeated-run statistics;
- negative or null results are retained.

## Execution model for ChatGPT Work

Do not implement an entire phase from this file directly.

For each phase:

1. audit the phase against specifications and accepted ADRs;
2. create/decompose GitHub issues;
3. implement the highest-priority unblocked issue only;
4. provide tests/evidence;
5. update documentation or propose ADR changes when necessary;
6. continue with the next issue.

P1 may begin only after the P0 specification PR is reviewed/merged.
