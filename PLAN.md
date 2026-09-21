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

The P0 audit established constraints whose current normative details live in the
linked ADRs and requirement IDs:

- harness-neutral service boundary — [ADR 0001](docs/adr/0001-harness-neutral-core.md) and [ADR 0009](docs/adr/0009-separate-local-process-service-boundary.md);
- graph vocabulary and separated lifecycle/evidence axes — [GRAPH.MODEL](docs/problem-graph.md#spec-graph-model) and [ADR 0007](docs/adr/0007-separate-lifecycle-verification-and-evidence-axes.md);
- durable journal, graph-version atomicity, provider ownership, claims, and recovery — [MODULES.EVENTSTORE-PORT](docs/modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](docs/protocol.md#spec-protocol-proposal-recovery), [PROTOCOL.STORE-OWNER](docs/protocol.md#spec-protocol-store-owner), [PROTOCOL.LEASE-CLOCK](docs/protocol.md#spec-protocol-lease-clock), ADR 0006;
- evidence trust/binding/recovery and review-loop checkpoints — [VERIFICATION.EVIDENCE-TRUST](docs/verification.md#spec-verification-evidence-trust), [VERIFICATION.EVIDENCE-BINDING](docs/verification.md#spec-verification-evidence-binding), [VERIFICATION.EVIDENCE-RECOVERY](docs/verification.md#spec-verification-evidence-recovery), [REVIEW.LOOP](docs/review-loop.md#spec-review-loop);
- the frozen P6-AC practical experiment — [EVALUATION.MODEL](docs/evaluation.md#spec-evaluation-model), [EVALUATION.PRE-P6](docs/evaluation.md#spec-evaluation-pre-p6), [EVALUATION.PREFLIGHT](docs/evaluation.md#spec-evaluation-preflight), [EVALUATION.MEASURED-EVALUATION](docs/evaluation.md#spec-evaluation-measured-evaluation).

See the [accepted ADRs](docs/adr/).

## Phase order

- [ ] **P0 — Specification audit and experiment contract**
  - [x] audit specifications/ADRs for contradictions and hidden assumptions;
  - [x] verify and expand related work from current primary sources;
  - [x] freeze the first P6-AC practical evaluation protocol;
  - [x] resolve event, lifecycle, evidence, runtime-boundary, and graph-interaction ambiguities;
  - [x] decompose P1 into bounded implementation issues;
  - [ ] merge/review the P0 specification PR.

P1 may begin only after the P0 specification PR is reviewed/merged.

- [ ] **P1 — Harness-neutral core contracts and module system**
  - Python package/tooling and dependency boundaries;
  - durable journal and graph-version implementation under [MODULES.EVENTSTORE-PORT](docs/modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](docs/protocol.md#spec-protocol-proposal-recovery), and ADR 0006;
  - `EventStore` providers and contract tests, including fenced claims and restart-stable lease-clock behavior under [PROTOCOL.LEASE-CLOCK](docs/protocol.md#spec-protocol-lease-clock);
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

- [ ] **P5 — Pi adapter preparation**
  - adapter preparation and protocol smoke checks only; portability validation belongs to P11;
  - same ProblemForger service/protocol;
  - thin TypeScript extension/client;
  - minimal native TUI status only.

P5 completion is not a dependency blocking P6; the initial evaluation uses HarnessX.

- [ ] **P6 — Practical whole-system evaluation**
  - implement issue #8 against the normative evaluation IDs in `docs/evaluation.md`;
  - freeze/hash the benchmark, complete ProblemForger package, metrics, ordered model chain, and complete HarnessX runtime before exposing selected tasks;
  - materialize the pinned manifest/schedule, enforce preflight/isolation/deadline/retry rules, retain raw artifacts, and compute the frozen paired outcomes and efficiency metrics;
  - preserve null/negative results and report the declared validity limitations;
  - run the optional B diagnostic only as a separately frozen experiment when mechanism attribution is needed.

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
  - harness-neutral consumer of optional telemetry, graph projections, and the read-only durable governance/audit timeline exposed by the service;
  - current objective/node, provenance, evidence, model rationale, confidence, timeline, warnings, local graph;
  - graph visualization remains secondary to causal/provenance inspection.

- [ ] **P11 — Full ablation and portability study**
  - independently validate portability through the Pi adapter prepared in P5;
  - baseline;
  - + problem graph;
  - + deterministic governance;
  - + learned verifier;
  - + calibration/abstention;
  - + routing;
  - run the separate frozen harness-comparison experiment in `docs/evaluation.md` and never pool it with P6;
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
- at least one controlled benchmark compares the baseline with the complete ProblemForger package;
- calibration claims use task-level held-out data;
- routing, if enabled, includes uncertainty and exploration controls;
- all reported improvements include cost/latency and repeated-run statistics;
- negative or null results are retained.

## Contributor workflow

Follow [AGENTS.md](AGENTS.md#work-procedure) for implementation, issue decomposition, verification, and review procedures.
