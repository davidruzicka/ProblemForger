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

Resolution: ADR 0006 defines the durable journal and atomic graph-version boundary. The normative [proposal recovery and ownership contract](protocol.md#spec-protocol-proposal-recovery) keeps transport identity, durable receipts, and store ownership explicit while serializing the initial service. SQLite is the first durable provider; memory remains ephemeral/test-only.

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

Resolution: `docs/evaluation.md` now contains a small versioned P6-AC practical
pilot contract with deterministic task selection and paired comparison. It keeps
the operational checks needed for a useful result and defers academic
population/holdout claims.

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

- **Persistence scope:** restrict P1 to one live provider per durable store with serialized proposal processing. ADR 0006 records the decision; `STORE-OWNER` defines enforcement and restart tests. Parallel claims and leases are deferred.
- **Evidence trust:** distinguish worker claims from service-assigned provenance and bind support to immutable checked content. ADR 0007 records the decision; `EVIDENCE-TRUST`, `EVIDENCE-BINDING`, and `EVIDENCE-RECOVERY` define the operational contract.
- **Preflight:** preflight checks obvious setup failures before measurement, but does not turn the pilot into a reserve/holdout study. Optional diagnostics occur after primary execution and cannot invalidate it.
- **Document ownership:** detailed algorithms now have one normative home, linked from instructions, planning, ADR rationale, and implementation issues.
- **Verification:** checked-in specification regression checks and tests of the actual inline review-request script replace unreproducible claims of local checks. The PR also includes executable GitHub Actions automation, not only documentation.

No production implementation or P6 measured execution was added by these amendments. The [check instructions](specification-checks.md) describe both reproducible verification and its limits.

### Follow-up PR contract corrections

The accepted corrections are tracked here as finding-to-source pointers; the
operational rules remain in their normative documents:

| Finding | Normative source | Regression/evidence source |
| --- | --- | --- |
| exclusive EventStore ownership and serialized recovery | [PROTOCOL.STORE-OWNER](protocol.md#spec-protocol-store-owner), [PROTOCOL.PROPOSAL-RECOVERY](protocol.md#spec-protocol-proposal-recovery) | issue #16 and restart-recovery checks |
| one proposal-bound EventStore graph-append port | [MODULES.EVENTSTORE-PORT](modules.md#spec-modules-eventstore-port), [PROTOCOL.PROPOSAL-RECOVERY](protocol.md#spec-protocol-proposal-recovery) | EventStore contract checks |
| superseded bootstrap stream | historical `docs/evaluation.md` draft | `tests/fixtures/bootstrap-v1.json` retained as audit evidence |
| compact model/runtime manifest | [EVALUATION.PRE-P6](evaluation.md#spec-evaluation-pre-p6) | P6 manifest checks |
| selected runtime/model metadata | [EVALUATION.PRE-P6](evaluation.md#spec-evaluation-pre-p6) | P6 manifest checks |
| one evaluator outcome per produced patch | [EVALUATION.MEASURED-EVALUATION](evaluation.md#spec-evaluation-measured-evaluation) | measured-run checks |
| review action pin, permissions, and event-aware diff range | [REVIEW.LOOP](review-loop.md#spec-review-loop) | `tests/review-workflow.test.mjs` |
| red-to-green document regression evidence | [Specification checks](specification-checks.md) | Python/Node suites in CI |

## Unresolved decisions

No unresolved decision blocks P1.

The following are deliberately deferred and must not be silently decided inside unrelated implementation work:

1. **Local service transport.** P1 includes a bounded spike comparing practical Python/TypeScript options. The selected transport requires an ADR.
2. **Exact initial graph node/edge schema.** P1 defines the command/wire contracts; P2 finalizes the minimal graph schema under ADR/spec constraints.
3. **P6 materialized task manifest.** The six task IDs, their order, the selected model/provider metadata, service/runtime configuration, and metric definitions are frozen in one compact manifest before task exposure. No reserve or holdout pool is required for the practical pilot; later claims need a separately designed dataset.
4. **P8 calibration dataset size.** The practical P6 pilot is not a calibration dataset. P8 must define and freeze its own held-out data before making calibration claims.
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
