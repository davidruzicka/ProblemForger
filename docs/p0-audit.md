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

Resolution: ADR 0006 defines the durable journal and atomic graph-version boundary. The normative [proposal recovery, ownership, and clock contract](protocol.md#proposal-identity-idempotency-and-recovery) separates transport identity, proposal claims, and store ownership. SQLite is the first durable provider; memory remains ephemeral/test-only.

### Graph lifecycle mixed unrelated state dimensions

The initial lifecycle combined proposal status, verification, and later invalidation in one conceptual sequence.

Resolution: mutation outcome, entity lifecycle, and evidence-derived verification status are separate axes.

### Evidence taxonomy mixed origin and method

Terms such as "observed", "deterministic", and "learned verification" were treated as one hierarchy even though they describe different properties.

Resolution: evidence origin, method, scope/subject, result, provenance, and optional uncertainty are represented independently. Deterministic evidence is authoritative only for the property it tests.

### The worker-to-graph interaction path was missing

The architecture defined a ProblemGraph but not how an agent would actually query or mutate it without hidden prompt/context machinery.

Resolution: the initial PoC exposes explicit graph query and versioned mutation tools/API. Every run-scoped operation carries explicit `run_id`; there is no ambient session-selected run. The application read API also exposes bounded durable governance/audit timeline records for observers. Automatic context selection is deferred.

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

The normative contract owns task selection, preflight, failure classification, ordering, statistical analysis, efficiency metrics, and raw-data retention. This audit records the rationale and changes; it does not duplicate the operational rules.

### Deep-review amendments before implementation

The follow-up audit identified five issues and the user authorized their correction before commit/push:

- **Lease ownership:** restrict P1 to one live provider per durable store rather than coordinate independent process clock anchors. ADR 0006 records the decision; `STORE-OWNER` defines enforcement and future tests.
- **Evidence trust:** distinguish worker claims from service-assigned provenance and bind support to immutable checked content. ADR 0007 records the decision; `EVIDENCE-TRUST`, `EVIDENCE-BINDING`, and `EVIDENCE-RECOVERY` define the operational contract.
- **Preflight:** the first two disagreeing complete vectors now determine instability immediately. Optional diagnostics occur after primary execution and cannot invalidate it. This explicitly amends the pre-implementation P6 envelope; it does not change the selected population, A/B/C treatment, or primary estimator.
- **Document ownership:** detailed algorithms now have one normative home, linked from instructions, planning, ADR rationale, and implementation issues.
- **Verification:** checked-in specification regression checks and tests of the actual inline review-request script replace unreproducible claims of local checks. The PR also includes executable GitHub Actions automation, not only documentation.

No production implementation or P6 measured execution was added by these amendments. The [check instructions](specification-checks.md) describe both reproducible verification and its limits.

### Follow-up PR contract corrections

- Claim/renewal inputs now carry TTL; the owning EventStore transaction computes deadlines under `LEASE-CLOCK`.
- Every documented graph-append signature requires proposal identity and fencing epoch; initialization has no unfenced graph-write exception.
- `BOOTSTRAP-RNG` fixes task order, one fresh generator and one shared draw matrix, comparison order, dtype, and reference arithmetic. Synthetic fixtures cover every retained N=8..12 without exposing P6 tasks.
- The reproducible checks now include the numerical reference and the three previously failing contract checks; issues #8 and #16 carry implementation acceptance criteria.

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
