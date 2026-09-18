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

Resolution: each run owns an append-only durable journal with separate `journal_position` and `graph_version`. Graph-changing writes use optimistic `expected_graph_version`; each atomic committed mutation advances graph version exactly once even when it emits multiple graph events, while audit-only records do not advance graph version. Proposal receipt and every externally returned governance outcome are durable. Proposal receipts persist the normalized request; pending processing uses finite leases plus monotonic claim epochs so restart recovery can reclaim work while stale workers are fenced. The in-memory EventStore is explicitly ephemeral/test-only; SQLite is moved into P1 as the first provider allowed for normal service execution so restart durability is real rather than nominal.

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
- a frozen `benchmark-adapter-v1` bridges SWE-smith/train into the pinned HarnessX runtime identically for A/B/C, bypassing HarnessX's built-in SWE-bench Verified/test defaults;
- 12 primary tasks, 3 repetitions, 3 configurations = 108 measured runs;
- 8 additional task-level holdout tasks reserved for later verifier/calibration work;
- benchmark executable result is end-to-end ground truth;
- A→B measures graph interaction as a package;
- B→C measures deterministic governance with graph interface/prompt parity;
- cost, latency, token, graph-overhead, invalidation, and propagation metrics are retained;
- infrastructure failures are separated from agent failures;
- each primary task gets a patch-independent evaluator preflight; the stable baseline must exactly satisfy FAIL_TO_PASS=failing and PASS_TO_PASS=passing, otherwise it is excluded as `BASELINE_INVALID`;
- every measured candidate patch is evaluated twice in fresh pinned environments, and candidate-specific disagreement is scored as `PATCH_UNSTABLE` failure rather than removing the task;
- primary B−A/C−B estimates use a frozen per-task estimator and a 100,000-iteration percentile task bootstrap with fixed PCG64 seed;
- every measured agent attempt starts from a clean pinned repository state and fresh HarnessX session; only B/C allocate fresh ProblemForger runs/journals, while A uses harness-neutral experiment bookkeeping only;
- every measured attempt retains the exact canonical candidate-patch bytes and SHA-256 (plus an auditable frozen workspace diff/snapshot where available), and evaluator outputs are linked to the exact patch digest;
- every measured attempt also retains a complete harness-native raw trajectory artifact for reproducibility and later P7/P8 data construction; these artifacts remain adapter-owned and outside core/EventStore/journal schemas;
- the complete A/B/C execution schedule is generated by a frozen SHA-256 ordering algorithm and hashed before measured execution;
- provider/evaluator retry eligibility, machine-readable infrastructure reason classes, whole-run replacement eligibility, and maximum attempt counts are frozen; a trajectory is never regenerated after its first semantic model response;
- every materialized primary/holdout task resolves to a verified immutable image/content digest before preflight; mutable tags are never re-resolved during P6 or later holdout use;
- the 30-minute semantic deadline starts immediately before the first model request after setup, includes all provider/backoff/tool/ProblemForger trajectory time, and freezes/evaluates the current workspace at deadline;
- journal-derived graph metrics and telemetry-derived overhead metrics are specified separately; P6 freezes `telemetry-metrics-v1` and requires the corresponding telemetry capture;
- if fewer than 8 of the planned 12 primary tasks survive patch-independent preflight, P6 reports `INSUFFICIENT_VALID_TASKS` and does not run/estimate the primary A/B/C experiment;
- P6 is explicitly not presented as a frontier coding-capability benchmark.

## Unresolved decisions

No unresolved decision blocks P1.

The following are deliberately deferred and must not be silently decided inside unrelated implementation work:

1. **Local service transport.** P1 includes a bounded spike comparing practical Python/TypeScript options. The selected transport requires an ADR.
2. **Exact initial graph node/edge schema.** P1 defines the command/wire contracts; P2 finalizes the minimal graph schema under ADR/spec constraints.
3. **P6 materialized task manifest.** The deterministic selector is frozen now. The exact 20 IDs are materialized and hashed only after the benchmark adapter, graph intervention, governance policy, graph metric rules, and telemetry metric rules are frozen; they are not hand-picked or used for artifact development.
4. **P8 calibration dataset size.** The eight reserved P6 tasks are only an initial task-level holdout. P8 must expand it before making calibration claims.
5. **P11 external-validity benchmark.** It is intentionally re-audited close to P11 because coding benchmarks are changing quickly.

## Files changed

- `README.md`
- `PLAN.md`
- `AGENTS.md`
- `.github/workflows/request-codex-review.yml`
- `docs/architecture.md`
- `docs/modules.md`
- `docs/problem-graph.md`
- `docs/protocol.md`
- `docs/verification.md`
- `docs/evaluation.md`
- `docs/risks.md`
- `docs/related-work.md`
- `docs/p0-audit.md`
- `docs/review-loop.md`
- `docs/adr/0003-ports-adapters-config-modules.md`
- `docs/adr/0006-authoritative-domain-events-and-stream-concurrency.md`
- `docs/adr/0007-separate-lifecycle-verification-and-evidence-axes.md`
- `docs/adr/0008-explicit-agent-graph-api-for-initial-poc.md`
- `docs/adr/0009-separate-local-process-service-boundary.md`

## P1 readiness

P1 is safe to start **after this P0 branch is reviewed and merged**.

P1 should be implemented through the bounded sub-issues created under epic #2 rather than directly from `PLAN.md`.
