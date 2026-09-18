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

## Phase order

- [ ] **P0 — Specification audit and experiment contract**
  - audit these documents for contradictions, ambiguous contracts, untestable requirements, and hidden assumptions;
  - select the first benchmark/task set and freeze primary metrics before implementation;
  - decompose P1 into bounded implementation issues.

- [ ] **P1 — Harness-neutral core contracts and module system**
  - domain types and stable ports;
  - typed provider configuration and module loader;
  - event schema and compatibility/versioning rules;
  - in-memory providers needed for tests.

- [ ] **P2 — Event-sourced ProblemGraph**
  - minimal node/edge schema;
  - immutable event log;
  - deterministic replay;
  - graph versions and provenance;
  - lifecycle and invalidation semantics;
  - in-memory + SQLite event-store adapters.

- [ ] **P3 — Governed mutations and deterministic evidence**
  - proposed vs committed mutations;
  - preconditions/invariants;
  - deterministic/external evidence;
  - commit/reject/retry/escalate decisions;
  - root anchors and drift-relevant provenance.

- [ ] **P4 — HarnessX adapter**
  - thin integration only;
  - capability declaration;
  - normalized ProblemForger events;
  - no ProblemForger domain logic in the adapter.

- [ ] **P5 — Pi adapter**
  - independent portability validation;
  - same ProblemForger core and protocol;
  - minimal native TUI status only.

- [ ] **P6 — Baseline and graph/governance evaluation**
  - compare harness baseline vs explicit graph vs deterministic governance;
  - repeated paired runs;
  - cost, latency, propagation, and transition-error measurements.

- [ ] **P7 — Learned verifier**
  - verifier port and baseline implementation;
  - verifier evidence remains distinct from ground truth;
  - independent evaluation against later external outcomes.

- [ ] **P8 — Calibration and abstention**
  - calibrated probability of verdict correctness;
  - held-out calibration set;
  - reliability diagrams/Brier/ECE;
  - novelty/OOD signal;
  - abstention/escalation policy.

- [ ] **P9 — Model suitability estimation and routing**
  - target quantity: `P(success | node, graph_state, model, budget)`;
  - model profiles learned from outcomes, including local/fine-tuned models;
  - uncertainty-aware routing;
  - controlled exploration/shadow evaluation to reduce selection bias.

- [ ] **P10 — Observer/debug UI**
  - harness-neutral event-stream consumer;
  - current objective/node, provenance, evidence, model rationale, confidence, timeline, warnings, local graph;
  - graph visualization is secondary to causal/provenance inspection.

- [ ] **P11 — Full ablation and portability study**
  - baseline;
  - + problem graph;
  - + deterministic governance;
  - + learned verifier;
  - + calibration/abstention;
  - + routing;
  - repeat across HarnessX and Pi where technically comparable.

## Definition of done for the PoC

The PoC is complete when:

- the same core runs through at least HarnessX and Pi adapters;
- authoritative graph state is replayable from events;
- graph mutations cannot be silently committed by the worker model;
- deterministic evidence and learned evidence are represented separately;
- at least one controlled benchmark compares the planned ablations;
- calibration claims use held-out data;
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
