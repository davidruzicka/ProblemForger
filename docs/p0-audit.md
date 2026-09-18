# P0 specification audit

- Issue: #1
- Branch: `p0-spec-audit`
- Date: 2026-09-18
- Status: Ready for human review; no production implementation started.

## Audit objective

The bootstrap specification was reviewed for contradictions, hidden coupling, ambiguous ownership, untestable requirements, premature abstractions, and threats to the planned ablation study.

The audit also re-checked the adjacent-work map and froze a small first A/B/C mechanism experiment before implementation can optimize against it.

## Problems found

### Authoritative state and telemetry were conflated

The original protocol listed graph mutations together with model/tool/harness lifecycle events without defining whether all were authoritative.

If every event changed graph version, replay and concurrency semantics would depend on the harness.

Resolution: each run now has a durable journal containing governance audit records plus graph-changing domain events, while harness/model/tool observations remain optional telemetry. Only graph-changing records reconstruct graph state; all returned governance outcomes remain durable across restart.

### EventStore concurrency semantics were underspecified

"Append-only event log" did not define atomicity, stream scope, or stale writers.

Resolution: each run owns an append-only durable journal with separate `journal_position` and `graph_version`. Graph-changing writes use optimistic `expected_graph_version`; each atomic committed mutation advances graph version exactly once even when it emits multiple graph events, while audit-only records do not advance graph version. Proposal receipt and every externally returned governance outcome are durable.

### Graph lifecycle mixed unrelated state dimensions

The initial lifecycle combined proposal status, verification, and later invalidation in one conceptual sequence.

Resolution: mutation outcome, entity lifecycle, and evidence-derived verification status are separate axes.

### Evidence taxonomy mixed origin and method

Terms such as "observed", "deterministic", and "learned verification" were treated as one hierarchy even though they describe different properties.

Resolution: evidence origin, method, scope/subject, result, provenance, and optional uncertainty are represented independently. Deterministic evidence is authoritative only for the property it tests.

### The worker-to-graph interaction path was missing

The architecture defined a ProblemGraph but not how an agent would actually query or mutate it without hidden prompt/context machinery.

Resolution: the initial PoC exposes explicit graph query and versioned mutation tools/API. Automatic context selection is deferred.

### The first ablation was not sufficiently isolated

Adding a graph inevitably adds tools/instructions, so A→B cannot be interpreted as a pure storage/data-structure effect.

Resolution: A→B is explicitly the graph-interaction package. B and C use the same graph tools and instructions; C alone adds deterministic governance, making B→C the cleaner governance ablation.

### Core/model ownership was over-generalized

The initial architecture listed a `ModelProvider` core port even though HarnessX/Pi already own inference.

Resolution: model execution remains in the harness. Routing later asks the harness to select a model; the initial core has no model-provider abstraction.

### Pi and HarnessX would otherwise use asymmetric integration boundaries

Direct Python imports for HarnessX but RPC for Pi would make portability comparisons structurally different.

Resolution: both adapters use the same separate local ProblemForger process/service.

### Initial module design risked premature abstractions

The bootstrap port list anticipated snapshot, artifact, verifier, calibration, routing, model, and context capabilities before the first PoC needed them.

Resolution: P1 introduces only currently required ports. Later ports appear in the phase that requires them.

### Evaluation was descriptive rather than frozen

The original document listed metrics but did not define a task set, model, run count, failure policy, or precise A/B/C parity.

Resolution: `docs/evaluation.md` now contains a versioned P6 mechanism experiment contract with deterministic task selection and paired comparisons.

## Architectural decisions added

- ADR 0006 — durable run journal for governance audit + graph events, separate from optional telemetry; optimistic graph-version writes.
- ADR 0007 — separate mutation outcome, entity lifecycle, verification, and evidence dimensions.
- ADR 0008 — explicit agent-facing graph API for the initial PoC.
- ADR 0009 — same separate local service boundary for HarnessX and Pi.

Existing ADRs 0001–0005 remain consistent with these decisions.

## Related-work findings

The audit confirmed that individual ingredients are well represented in existing work:

- HarnessX/Pi provide extensible execution substrates;
- graph engineering and dynamic graph transformation already cover dynamic graph-based agent organization;
- GALAX/CaSKG provide close precedents for graph-process scoring or calibrated edge confidence;
- CodePRM, SWE-PRM, and AgentPro cover process supervision/verification;
- RouteLLM and IRT-Router cover conditional model routing.

Therefore ProblemForger must not present "agents + graph", "step verification", or "model routing" alone as novel.

The current working differentiation is the combined architecture:

```text
externally authoritative dynamic problem graph
+ typed/versioned governed mutations
+ event-sourced provenance
+ deterministic/external evidence
+ learned graph mutation/entity verification
+ calibrated probability and abstention
+ per-node model suitability/routing
+ harness-neutral integration
```

This is a differentiation hypothesis, not a novelty claim.

## Evaluation contract frozen for P6

The first A/B/C mechanism experiment is specified in `docs/evaluation.md`.

Key properties:

- pinned HarnessX revision;
- one fixed model/configuration across A/B/C;
- deterministic SWE-smith task selection from a verified pinned dataset revision with explicit list-field schema validation;
- 12 primary tasks, 3 repetitions, 3 configurations = 108 measured runs;
- 8 additional task-level holdout tasks reserved for later verifier/calibration work;
- benchmark executable result is end-to-end ground truth;
- A→B measures graph interaction as a package;
- B→C measures deterministic governance with graph interface/prompt parity;
- cost, latency, token, graph-overhead, invalidation, and propagation metrics are retained;
- infrastructure failures are separated from agent failures;
- every measured candidate patch is evaluated twice in fresh pinned environments, with a third evaluation on disagreement and whole-task exclusion for confirmed evaluator instability;
- P6 is explicitly not presented as a frontier coding-capability benchmark.

## Unresolved decisions

No unresolved decision blocks P1.

The following are deliberately deferred and must not be silently decided inside unrelated implementation work:

1. **Local service transport.** P1 includes a bounded spike comparing practical Python/TypeScript options. The selected transport requires an ADR.
2. **Exact initial graph node/edge schema.** P1 defines the command/wire contracts; P2 finalizes the minimal graph schema under ADR/spec constraints.
3. **P6 materialized task manifest.** The deterministic selector is frozen now. The exact 20 IDs are materialized and hashed only after the graph intervention, governance policy, and graph metric rules are frozen; they are not hand-picked or used for artifact development.
4. **P8 calibration dataset size.** The eight reserved P6 tasks are only an initial task-level holdout. P8 must expand it before making calibration claims.
5. **P11 external-validity benchmark.** It is intentionally re-audited close to P11 because coding benchmarks are changing quickly.

## Files changed

- `AGENTS.md`
- `PLAN.md`
- `docs/architecture.md`
- `docs/modules.md`
- `docs/problem-graph.md`
- `docs/protocol.md`
- `docs/verification.md`
- `docs/evaluation.md`
- `docs/risks.md`
- `docs/related-work.md`
- ADRs 0006–0009
- this audit report

## P1 readiness

P1 is safe to start **after this P0 branch is reviewed and merged**.

P1 should be implemented through the bounded sub-issues created under epic #2 rather than directly from `PLAN.md`.
