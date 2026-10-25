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
- durable journal, graph-version atomicity, exclusive provider ownership, serialized recovery — [MODULES.EVENTSTORE-PORT](docs/modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](docs/protocol.md#spec-protocol-proposal-recovery), [PROTOCOL.STORE-OWNER](docs/protocol.md#spec-protocol-store-owner), ADR 0006;
- evidence trust/binding/recovery and review-loop checkpoints — [VERIFICATION.EVIDENCE-TRUST](docs/verification.md#spec-verification-evidence-trust), [VERIFICATION.EVIDENCE-BINDING](docs/verification.md#spec-verification-evidence-binding), [VERIFICATION.EVIDENCE-RECOVERY](docs/verification.md#spec-verification-evidence-recovery), [REVIEW.LOOP](docs/review-loop.md#spec-review-loop);
- the frozen P6-AC practical experiment — [EVALUATION.MODEL](docs/evaluation.md#spec-evaluation-model), [EVALUATION.PRE-P6](docs/evaluation.md#spec-evaluation-pre-p6), [EVALUATION.PREFLIGHT](docs/evaluation.md#spec-evaluation-preflight), [EVALUATION.MEASURED-EVALUATION](docs/evaluation.md#spec-evaluation-measured-evaluation).

See the [accepted ADRs](docs/adr/).

## Phase order

- [x] **P0 — Specification audit and experiment contract**
  - [x] audit specifications/ADRs for contradictions and hidden assumptions;
  - [x] verify and expand related work from current primary sources;
  - [x] freeze the first P6-AC practical evaluation protocol;
  - [x] resolve event, lifecycle, evidence, runtime-boundary, and graph-interaction ambiguities;
  - [x] decompose P1 into bounded implementation issues;
  - [x] merge/review the P0 specification PR (#22, merged 2026-09-25).

P1 was unblocked when PR #22 merged on 2026-09-25.

- [ ] **P1 — Harness-neutral core contracts and module system**
  - Python package/tooling and dependency boundaries;
  - durable journal and graph-version implementation under [MODULES.EVENTSTORE-PORT](docs/modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](docs/protocol.md#spec-protocol-proposal-recovery), and ADR 0006;
  - `EventStore` providers and contract tests, including exclusive ownership, serialized proposal recovery, and restart-safe replay;
  - typed provider configuration and explicit module registry/composition root;
  - observation/telemetry contract;
  - local service transport decision and protocol skeleton;
  - graph command/query contract needed by later adapters.

- [ ] **P2 — Event-sourced ProblemGraph**
  - implementation sequence: [schema #41](https://github.com/davidruzicka/ProblemForger/issues/41), [replay #42](https://github.com/davidruzicka/ProblemForger/issues/42), [service integration #43](https://github.com/davidruzicka/ProblemForger/issues/43);
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

- [ ] **P5 — Claude Code plugin preparation**
  - adapter preparation and protocol smoke checks only; portability validation belongs to P11;
  - begin P5 execution only after the P1 service (#21), P2 graph (#3), and P3 governance (#4) prerequisites; follow accepted ADR 0012's Problem/run ownership boundary;
  - same ProblemForger service/protocol;
  - pin the Linux CLI release and plugin source commit/digest; load from a local plugin directory for the smoke test;
  - Claude Code starts a per-session stdio MCP bridge; the ADR 0010 supervisor owns service startup/shutdown, the worker socket, and the durable journal;
  - document configured socket discovery, worker-group permissions, bridge shutdown, and explicit unavailable-service behavior with no direct-store fallback; do not assume in-session plugin disable/uninstall immediately terminates the bridge, and verify termination after a successful plugin reload or a later session;
  - show the authoritative `run_id` from the run-creation contract, require that explicit ID on every call and resume, and never infer it from a Claude session ID; Problem-level associations remain outside this adapter scope;
  - keep authentication in unmodified Claude Code; separately test Claude.ai
    subscription login, keyless Console sign-in with an OAuth profile, legacy
    Console sign-in that creates/stores an API key, and
    `ANTHROPIC_API_KEY` environment authentication;
  - set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, allowlist the bridge environment, and verify a credential sentinel is absent from child environments, bridge input, logs, and telemetry;
  - use the hook capability map and smoke matrix in [Protocol](docs/protocol.md#claude-code-adapter); test whether existing contracts let a synchronous `PreToolUse` gate bind each work action to a service-authorized eligible graph node; if not, record the control gap and propose a separate spec/issue before adding node-binding semantics;
  - any command/HTTP `PreToolUse` gate must use `onFailure: "block"` on Claude Code v2.1.295 or later for hook failures; test explicit denial separately, pin the tested account/management mode, and claim enforcement only for tested tool routes; absent account access is an unmet smoke prerequisite, not evidence of support; native status is optional.

P5 completion is not a dependency blocking P6; the initial evaluation uses HarnessX.

- [ ] **P6 — Practical whole-system evaluation**
  - implement issue #8 against the normative evaluation IDs in `docs/evaluation.md`;
  - freeze one compact manifest containing the benchmark adapter, selected model/provider metadata, ProblemForger service/runtime configuration, task IDs, and metrics before exposing selected tasks;
  - run the small paired A/C pilot with one agent run and one evaluator run per task, enforce isolation/deadline/resource limits, retain raw artifacts, and compute simple paired outcomes and efficiency metrics;
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
  - independently validate portability through the Claude Code plugin prepared in P5;
  - freeze the exact CLI release, plugin source identity, effective plugin/MCP/hook state, management mode, active mod set and content identities (including relevant built-in mod state), subprocess credential-scrub setting, effective bridge/MCP environment allowlist (variable names and non-secret configuration only), authentication route, and model settings in each P11 manifest; never record secret values;
  - use one manifest per authentication route and report each separately; compare baseline and treatment within each route, treating each manifest as its own analysis stratum if useful;
  - baseline;
  - + problem graph;
  - + deterministic governance;
  - + learned verifier;
  - + calibration/abstention;
  - + routing;
  - run the separate frozen harness-comparison experiment in `docs/evaluation.md` and never pool it with P6;
  - repeat across HarnessX and Claude Code where technically comparable;
  - re-audit and freeze an independent external-validity benchmark.

## Conditional Problem-oriented direction

This is a candidate follow-up only if examination supports the direction; it does not change the initial PoC scope or phase order.

- Validate a Problem-centered workflow in which ProblemForger researches, decomposes, plans, and coordinates outcomes that may span multiple projects/resources.
- Treat semantic outcomes and resource/project relationships as the candidate primary model; repositories are resources, not necessarily Problem boundaries. Avoid assuming a universal ontology.
- Keep agent runs and harness sessions replaceable execution mechanisms, not product-level Problem identity.
- The design gate in [issue #37](https://github.com/davidruzicka/ProblemForger/issues/37) is resolved GO by [ADR 0012](docs/adr/0012-problem-identity-and-run-ownership.md): a thin Problem identity may link resource scopes and phase-labelled runs, while each graph and journal remains run-scoped. This accepts the identity/ownership direction only; it does not approve a product pivot.
- P2 remains a run-scoped graph and journal implementation. It does not implement the Problem registry/API, cross-run operations, or multi-project persistence. Keep v1 unchanged; any Problem persistence or cross-run read model requires a separately scoped design.
- After P6, if the direction remains justified, run a separately frozen evaluation spanning at least two repositories/resources, research plus implementation, and a replaced harness session. Keep it separate from P6; P6 does not validate this direction.
- Keep P10 as the observer/debug UI. A Problem-first, goal-oriented interface is a later decision tracked in issue #12, not a change to P10's current scope.

The PoC definition of done below remains unchanged.

## Definition of done for the PoC

The PoC is complete when:

- the same core/service runs through at least HarnessX and Claude Code adapters;
- authoritative graph state is replayable from graph-changing durable journal records;
- every governance proposal/outcome needed for audit/evaluation survives restart;
- harness telemetry is not required for graph replay or governance audit;
- graph mutations cannot be silently committed by the worker model;
- deterministic evidence and learned evidence are represented separately;
- at least one controlled benchmark compares the baseline with the complete ProblemForger package;
- calibration claims use task-level held-out data;
- routing, if enabled, includes uncertainty and exploration controls;
- all reported improvements include cost/latency and the coverage/validity evidence required by their frozen experiment contract; the single-run P6 pilot is reported as a practical paired observation, not as repeated-run statistics;
- negative or null results are retained.

## Contributor workflow

Follow [AGENTS.md](AGENTS.md#work-procedure) for implementation, issue decomposition, verification, and review procedures.
