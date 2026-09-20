# P0 specification audit

- Issue: #1
- Branch: `p0-spec-audit`
- Date: 2026-09-18
- Status: Ready for human review; no production implementation started.

Historical amendment (2026-09-20): the unpublished A/B/C mechanism draft was
replaced by the practical P6-AC whole-system contract in `docs/evaluation.md`.
The A/B/C references below describe the audited draft; they are not the current
P6 execution plan.

## Audit objective

The bootstrap specification was reviewed for contradictions, hidden coupling, ambiguous ownership, untestable requirements, premature abstractions, and threats to the planned ablation study.

The audit also re-checked the adjacent-work map and froze a small first mechanism
experiment before implementation can optimize against it.

## Problems found

### Authoritative state and telemetry were conflated

The original protocol listed graph mutations together with model/tool/harness lifecycle events without defining whether all were authoritative.

If every event changed graph version, replay and concurrency semantics would depend on the harness.

Resolution: each run now has a durable journal containing governance audit records plus graph-changing domain events, while harness/model/tool observations remain optional telemetry. Only graph-changing records reconstruct graph state; all returned governance outcomes remain durable across restart.

### EventStore concurrency semantics were underspecified

"Append-only event log" did not define atomicity, stream scope, or stale writers.

Resolution: ADR 0006 defines the durable journal and atomic graph-version boundary. The normative [proposal recovery, ownership, and clock contract](protocol.md#spec-protocol-proposal-recovery) separates transport identity, proposal claims, and store ownership. SQLite is the first durable provider; memory remains ephemeral/test-only.

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

Resolution: `docs/evaluation.md` now contains a versioned P6-AC practical package
experiment contract with deterministic task selection and paired comparison.

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

The first P6-AC whole-system experiment is specified in `docs/evaluation.md`.

The normative contract owns task selection, preflight, failure classification, ordering, statistical analysis, efficiency metrics, and raw-data retention. This audit records the rationale and changes; it does not duplicate the operational rules.

### Deep-review amendments before implementation

The follow-up audit identified five issues and the user authorized their correction before commit/push:

- **Lease ownership:** restrict P1 to one live provider per durable store rather than coordinate independent process clock anchors. ADR 0006 records the decision; `STORE-OWNER` defines enforcement and future tests.
- **Evidence trust:** distinguish worker claims from service-assigned provenance and bind support to immutable checked content. ADR 0007 records the decision; `EVIDENCE-TRUST`, `EVIDENCE-BINDING`, and `EVIDENCE-RECOVERY` define the operational contract.
- **Preflight:** the first two disagreeing complete vectors now determine instability immediately. Optional diagnostics occur after primary execution and cannot invalidate it. This explicitly amends the pre-implementation P6 envelope; the current P6-AC contract also permits only predeclared reserve activation for patch-independent defects before measurement.
- **Document ownership:** detailed algorithms now have one normative home, linked from instructions, planning, ADR rationale, and implementation issues.
- **Verification:** checked-in specification regression checks and tests of the actual inline review-request script replace unreproducible claims of local checks. The PR also includes executable GitHub Actions automation, not only documentation.

No production implementation or P6 measured execution was added by these amendments. The [check instructions](specification-checks.md) describe both reproducible verification and its limits.

### Follow-up PR contract corrections

The accepted corrections are tracked here as finding-to-source pointers; the
operational rules remain in their normative documents:

| Finding | Normative source | Regression/evidence source |
| --- | --- | --- |
| lease TTL, fencing, and expiry-before-reclaim | [PROTOCOL.LEASE-CLOCK](protocol.md#spec-protocol-lease-clock), [MODULES.EVENTSTORE-PORT](modules.md#spec-modules-eventstore-port) | `test_expired_claim_cannot_finalize_or_renew`, issue #16 |
| one fenced EventStore graph-append port | [MODULES.EVENTSTORE-PORT](modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](protocol.md#spec-protocol-proposal-recovery) | `test_every_graph_append_signature_requires_fencing` |
| superseded bootstrap stream | historical `docs/evaluation.md` draft | `tests/fixtures/bootstrap-v1.json` retained as audit evidence |
| ordered model fallback and post-exposure exhaustion | [EVALUATION.MODEL](evaluation.md#spec-evaluation-model) | `test_model_chain_handles_post_exposure_exhaustion` |
| content-addressed HarnessX runtime | [EVALUATION.PRE-P6](evaluation.md#spec-evaluation-pre-p6) | `test_harness_runtime_is_fully_content_addressed` |
| mandatory candidate evaluator repetitions | [EVALUATION.MEASURED-EVALUATION](evaluation.md#spec-evaluation-measured-evaluation) | `test_missing_candidate_vector_does_not_skip_other_repetition` |
| review action pin, permissions, and event-aware diff range | [REVIEW.LOOP](review-loop.md#spec-review-loop) | `tests/review-workflow.test.mjs` |
| red-to-green document regression evidence | [Specification checks](specification-checks.md) | Python/Node suites in CI |

## Unresolved decisions

No unresolved decision blocks P1.

The following are deliberately deferred and must not be silently decided inside unrelated implementation work:

1. **Local service transport.** P1 includes a bounded spike comparing practical Python/TypeScript options. The selected transport requires an ADR.
2. **Exact initial graph node/edge schema.** P1 defines the command/wire contracts; P2 finalizes the minimal graph schema under ADR/spec constraints.
3. **P6 materialized task manifest.** The deterministic selector is frozen now. The exact 12 primary/reserve IDs are materialized and hashed only after the benchmark adapter, graph intervention, governance policy, graph metric rules, and telemetry metric rules are frozen; the eight holdout identifiers remain separate and their images do not block P6. None are hand-picked or used for artifact development.
4. **P8 calibration dataset size.** The eight reserved P6 tasks are only an initial task-level holdout. P8 must expand it before making calibration claims.
5. **P11 external-validity benchmark.** It is intentionally re-audited close to P11 because coding benchmarks are changing quickly.

## Files changed

- `.github/workflows/request-codex-review.yml`
- `.github/workflows/specification-checks.yml`
- `AGENTS.md`
- `PLAN.md`
- `README.md`
- `docs/architecture.md`
- `docs/adr/0003-ports-adapters-config-modules.md`
- `docs/adr/0006-authoritative-domain-events-and-stream-concurrency.md`
- `docs/adr/0007-separate-lifecycle-verification-and-evidence-axes.md`
- `docs/adr/0008-explicit-agent-graph-api-for-initial-poc.md`
- `docs/adr/0009-separate-local-process-service-boundary.md`
- `docs/evaluation.md`
- `docs/modules.md`
- `docs/p0-audit.md`
- `docs/problem-graph.md`
- `docs/protocol.md`
- `docs/risks.md`
- `docs/related-work.md`
- `docs/review-loop.md`
- `docs/specification-checks.md`
- `docs/verification.md`
- `tests/fixtures/bootstrap-v1.json`
- `tests/requirements.txt`
- `tests/review-workflow.test.mjs`
- `tests/test_practical_effect_reference.py`
- `tests/test_specification.py`

## P1 readiness

P1 is safe to start **after this P0 branch is reviewed and merged**.

P1 should be implemented through the bounded sub-issues created under epic #2 rather than directly from `PLAN.md`.
