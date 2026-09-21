# Methodology audit and decision register

## Status and authority

This is a **non-normative audit**, recorded on 2026-09-19 against local commit
`313c167` (published equivalent: `3ae96d3ee5fd7645dac01cd885e23771bc26a840`).
The register itself is checked in as `docs/methodology.md` on branch
`p0-spec-audit` in commit `6f7a7ae320e07ea7be39dc9ad1fe1ee3c206510f`.
The audited snapshot predates the register; `git diff --stat` between the
audited snapshot and that commit shows this file as the only added path. The
register therefore records the audit artifact separately from the audited
content. No selected benchmark tasks were opened or executed for this audit.

Update 2026-09-20: the user clarified that the PoC plan is unpublished and may be
changed freely, and approved prioritizing practical usability over full academic
exactness. The normative amendment therefore replaces the draft A/B/C pilot with
P6-AC: direct A/C comparison, eight retained tasks, two repetitions, four
predeclared reserves, and operational rather than statistical continuation
decisions. The existing evaluator duplication, retry bounds, isolation rules,
resource envelope, and sensitivity warning remain. This register records the
rationale; [Evaluation](evaluation.md) remains authoritative.

The [evaluation contract](evaluation.md), accepted ADRs, and the
[contract ownership map](specification-checks.md#contract-ownership) remain
authoritative. Values mentioned here describe the audited snapshot; operational
algorithms are maintained only in their normative owners. Changes to research
choices require the [human checkpoint](review-loop.md), an explicit amendment,
and the applicable pre-exposure freeze/versioning procedure.

Scope: sampling, estimands, analysis, decisions, model/harness controls, budgets,
failure handling, metrics, technical constraints, and later-phase parameters.
This is a design audit, not a live provider capability test or power study.
Optimal numeric settings cannot be inferred without development/pilot evidence.

## Main conclusion

The design specifies reproducibility more precisely than it justifies its
parameters. Freezing a number prevents post-hoc choice; it does not establish
that the number is appropriate. Evaluate parameter interactions before adding
more isolated thresholds. The practical response is to limit what P6 claims, not
to require a full statistical validation program before a feasibility run. Preserve
auditable measurements and useful failures; defer population/confirmatory claims.

### Practical-PoC disposition (2026-09-20)

| Concern | Current disposition and normative anchor |
| --- | --- |
| Evidential role | P6-AC is a practical whole-system feasibility pilot, not confirmatory or population proof. See [pilot scope](evaluation.md#p6-practical-pilot). |
| Incomplete infrastructure | Preserve the hard experiment-wide stop and raw/descriptive evidence, with no primary delta; predeclared reserves apply only to patch-independent pre-measurement defects, never transient failures or observed outcomes. See [incomplete reporting](evaluation.md#p6-incomplete-reporting). |
| Finite resources | Predeclare, record, and enforce an experiment wall-clock limit and provider-spend guard; choose actual values before exposure. See [resource budget](evaluation.md#p6-resource-budget). |
| Opaque hosted model | Keep explicit `temperature=0`; acceptance evidence is sufficient when effective value/revision metadata is `UNKNOWN`. See [provider metadata](evaluation.md#p6-hosted-model-metadata). |
| Image identity | Digest identifies runtime/harness bytes, not hosted model identity or exact future inference. See [runtime identity](evaluation.md#p6-runtime-image-identity). |
| Progression and sensitivity | Replace the old interval/P7 gate with an operational `CONTINUE`/`ADAPT`/`STOP` decision; retain `SENSITIVITY_DISCORDANT` as a warning and local-use diagnostic. See [continuation](evaluation.md#practical-continuation-decision) and [sensitivity](evaluation.md#practical-sensitivity-report). |

Distinguish these evidence levels throughout this register:

- **Confirmed:** follows from the specified algorithm or a reproducible example.
- **Design risk:** a plausible failure mode; its frequency or size is unmeasured.
- **Proposal:** a change requiring a decision, not current policy.
- **Deferred:** appropriately unresolved until its implementation/research phase.

## Audit result

No contradiction with an accepted ADR or normative specification owner was
found. The material issues are parameter justification, decision provenance,
conditional-estimand wording, and generation-control status precision. The
checked-in bootstrap fixtures (`tests/fixtures/bootstrap-v1.json`, `N=8..12`)
belong to the superseded A/B/C draft and are retained only as audit history; they
are not part of P6-AC.

## 1. Estimand and interpretation

The evidential role is resolved for the practical PoC: P6-AC is a whole-system
feasibility pilot on the fixed retained tasks and observed executions. The small
budget may inform whether further development is worthwhile; it does not establish
population benefit, equivalence, or an isolated graph/governance effect. The local
continuation decision is operational and remains separate from starting/funding P7.

Before revising the analysis, distinguish:

1. performance on the fixed selected tasks and observed executions;
2. expected performance of new executions on those tasks;
3. expected performance on new tasks from the filtered benchmark population;
4. transfer to new repository families, harnesses, or real project work.

An interval appropriate for one target does not automatically support another.
The practical P6 estimand is also conditional: it concerns only tasks that pass
the frozen repository/problem filters and patch-independent preflight, not every
row in the pinned SWE-smith split. Interval claims therefore must not be
generalized to the unfiltered benchmark population.
Also distinguish funding further research, claiming a mechanism helps, and
deploying the complete system. These decisions need not share one gate.

### Superseded bootstrap design: confirmed synthetic counterexample

The following records a property of the discarded A/B/C draft. It is not a
requirement for P6-AC.

The current reference resamples tasks while retaining their observed repetitions.
It does not separately resample new executions within a task.

For each of 12 synthetic tasks, use these A/B/C binary outcomes:

| Configuration | Three repetitions | Task mean |
| --- | --- | --- |
| A | 0, 1, 0 | 1/3 |
| B | 1, 0, 0 | 1/3 |
| C | 0, 0, 1 | 1/3 |

All observed paired task effects are zero. Executing the normative reference on
this fixture returns `[0, 0]` for both intervals. The audited interpretation rule
therefore labels both contrasts practically equivalent despite within-task
variation. This is an exact property of this fixture, not an estimate of how
often the problem occurs. It does not prove the underlying success probabilities
differ; it demonstrates that a collapsed empirical interval cannot establish
their equality.

Proposal for stronger claims: simulate coverage and decision errors before treating
these intervals as population equivalence or confirmatory progression evidence.
This is not a blocker for feasibility data collection or exploratory development.
Do not automatically substitute BCa,
a hierarchical bootstrap, or a parametric model: each has assumptions that must
match the estimand and sampling design.
Before making stronger equivalence or progression claims, add this counterexample
to the synthetic decision checks. The current golden fixtures cover N=8..12
reference reproducibility but do not cover this failure mode.

## 2. Sample and task selection

The audited settings are described here for assessment, not as a second selector.
The exact selector remains in [Evaluation](evaluation.md).

| Parameter | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| Eight target tasks plus four predeclared reserves | Practical workload: 32 measured slots before retries, plus mandatory evaluator repetitions. No precision claim is attached. | Use reserves only for patch-independent pre-measurement defects; never for observed outcomes or transient infrastructure failures. |
| Two runs per task/configuration | Exposes basic trajectory variation at half the previous execution budget; it is not a population uncertainty estimate. | Report both repetitions and their leave-one-out deltas. |
| Eight retained tasks | This is a practical completeness requirement, not a precision guarantee. | Stop before measurement if the target pool cannot provide eight eligible tasks. |
| Eight repository-family-disjoint holdout identifiers | Useful later split, not established calibration support; holdout images do not block P6. | Expand before calibration claims; transitions within a task are not independent tasks. |
| Maximum two tasks per family | Reduces dominance, not within-family dependence. Task resampling does not explicitly model family clustering. | Define task versus family generalization and evaluate the corresponding analysis. |
| Family from repository name prefix before the first dot | Deterministic heuristic, not proof of common upstream; owner identity is ignored. | Validate against provenance metadata and document collisions/splits. |
| Family-disjoint holdout | Protects against leakage but tests cross-family transfer, not merely new tasks in familiar repositories. | Retain with an explicit generalization claim. |
| 1–20 failing and 1–200 passing tests | Counts are weak proxies for runtime and difficulty; filters change the population. | Justify operationally and report filtered population composition. |
| At most 12,000 problem-statement characters | Characters are not tokens; the limit can select particular task types. | Relate to actual context limits, including tools and history. |
| Fixed hash ordering and selection seed | Good reproducibility; no scientific advantage of the particular seed. | Retain; avoid interpreting deterministic selection as representativeness. |
| SWE-smith training split | Suitable for a bounded mechanism pilot, not an uncontaminated capability claim. Familiarity need not affect all treatments equally. | Scope conclusions to this population and replicate independently. |
| Schema errors abort materialization | Fail-fast behavior avoids silent population changes but can make unrelated malformed rows experiment-fatal. | Keep population rules explicit; evaluate robustness on development data before freeze, not by skipping rows after exposure. |

With 16 measured slots per configuration, one additional resolved slot changes the
aggregate by 6.25 percentage points. This is numerical granularity, not uncertainty
or a minimum detectable effect.

## 3. Thresholds and sensitivity

### Direction and magnitude are different diagnostics

The earlier proposal to flag any sign change tests direction only:

| Primary estimate to omitted-repetition estimate | Absolute change | Sign-change flag |
| --- | --- | --- |
| -1 to +1 percentage points | 2 percentage points | Yes |
| +1 to +18 percentage points | 17 percentage points | No |

These are explanatory arithmetic examples, not exact realizable points on the
P6-AC outcome grid. A magnitude diagnostic would rank them differently.

For sensitivity of a success-rate difference, absolute percentage-point change
is interpretable. Relative change divides by a potentially tiny, zero, or
negative effect and is unsuitable as the default instability criterion.

The subsequent proposal to flag a maximum absolute change of at least 10
percentage points was also insufficiently justified as a standalone instability
threshold. Keep these three choices separate:

- minimum worthwhile benefit;
- maximum acceptable harm;
- tolerated estimator sensitivity.

`SENSITIVITY_DISCORDANT` is retained in P6-AC as the combined sign-and-
practical-band point-estimate warning in
[Evaluation](evaluation.md#practical-sensitivity-report). It reuses `delta = 10`
percentage points only as a descriptive band boundary. Report both omitted-
repetition effects and their maximum absolute departure; the warning does not
block a local operational decision.

### Analysis parameter register

| Parameter | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| Practical band of 10 percentage points | Human-selected and not a cost/utility estimate. | Use only as a descriptive sensitivity boundary; do not use it as a P7 gate. |
| Two repetitions | Sufficient for a small operational flakiness signal, not for population uncertainty. | Report both repetition deltas and the leave-one-out values. |
| No bootstrap or confidence interval | Avoids false precision for a 16-slot-per-configuration feasibility pilot. | Use raw/per-task outcomes and operational metrics; add inferential analysis only in a new study. |
| Leave-one-repetition-out | Measures dependence on one observed execution block. | Report every omission; do not attribute changes to a specific causal source. |
| Replicate disagreement | Depends on task success probability; an always-failing system is perfectly stable. | Report alongside task success, never as standalone quality. |

### Progression decision

The superseded P7 gate depended on B-A and C-B intervals and therefore does not
apply to P6-AC. The current decision uses the complete-system C-A delta, per-task
outcomes, costs, latency, intervention burden, and observed failure mechanisms.
For a complete pilot, the human decision is recorded with evidence and rationale
as `CONTINUE`, `ADAPT`, or `STOP`, following
[Evaluation](evaluation.md#practical-continuation-decision). Incomplete experiments
receive no continuation label. Neither the descriptive bands nor sensitivity
warning dictate the decision, and no label automatically justifies a learned verifier.

A learned verifier also need not be justified by the same condition as graph
adoption. Failure of deterministic governance could motivate investigating a
different verifier, or reveal that the graph is not useful. The observed failure
mechanism, not a universal automatic rule, should inform a separately declared
research decision.

## 4. Models, harnesses, and budgets

| Parameter | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| One model and one harness for P6 | Controls scope; conclusions remain conditional on that stack. | Retain for the first pilot; replicate before broad claims. |
| Named primary model, thinking disabled | Rationale relative to intended deployment is not established. | Choose on separate development tasks and intended operating conditions. |
| Temperature zero | Legitimate operating policy, not a determinism guarantee. | Retain only with that interpretation. |
| Verification of effective temperature | Accepted requests establish API acceptance, not hidden provider implementation. Effective-value acknowledgement may be unavailable. | Resolved: require explicit `temperature=0` and observed acceptance; record effective value `UNKNOWN` when not reported, without rejecting the stack solely for this uncertainty. |
| EXPLICIT / OMITTED_NATIVE / UNSUPPORTED / UNKNOWN statuses | These statuses summarize the richer `generation-policy-v1` record; the status alone must not be read as proof of an effective value. | Preserve the normative record. Derive separate capability, request-mode, and effective-value fields only if analysis needs them, and never infer an effective value from acceptance or documentation. |
| 16,384 output tokens per response | Not a run-level cost/token cap. | Justify on development data; measure truncation and total usage. |
| 60 agent steps | A step need not correspond to one tool call; graph work consumes budget. | Define step semantics and interpret effects at that budget, including graph overhead. |
| 30-minute semantic deadline | Mixes model speed, provider delays, tests, and service overhead. Appropriate for end-to-end utility, not isolated reasoning quality. | Report the binding limit and latency breakdown. |
| Setup outside semantic deadline | Separates startup from interaction budget but does not make startup cost disappear. | Retain end-to-end time/cost alongside semantic time. |
| Experiment resource envelope | Per-response/per-run limits alone do not bound total pilot spend. | Record and enforce finite wall-clock and provider-spend limits before exposure; actual amounts require operator approval. A budget stop cannot purchase extra retries or a favorable subset. |
| Same model and effort across harnesses | Does not establish equivalent prompts, sampling, reasoning budget, or tool policy. | Compare packaged systems unless actual parity is demonstrated. |
| Freezing hidden prompts/defaults | May be impossible for opaque hosted systems. | Pin observable versions/configuration and record unobservable behavior as a limitation. |
| Runtime image digest | Identifies runtime/harness bytes, not hosted weights or provider execution. | Retain for local-stack parity; record provider revision metadata when available and `UNKNOWN` otherwise. Do not promise exact inference replay. |
| Interleaved frozen execution order | Reduces some temporal confounding but does not guarantee balanced positions or independence under drift. | Examine scheduling behavior on synthetic manifests and record provider/version changes. |
| Separate harness comparison | Correct separation from P6 attribution; two harnesses by two whole-system configurations still measures packaged systems, not an isolated harness effect. | Freeze scope and analysis before exposure; do not assume P6 sample size is sufficient. |

Documentation is supporting capability evidence, not proof of a hidden runtime
value. Non-task probes should use only interfaces the adapter actually exposes;
they should not emulate unsupported controls or inspect selected evaluation tasks.

## 5. Evaluation repetition and infrastructure

| Rule | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| Two matching baseline evaluations | Can detect instability; agreement twice does not prove stability. | Describe as passing a check, not proof of deterministic behavior. |
| Candidate must pass twice | Measures repeatable benchmark success, not only patch semantics. | Preserve this distinction and report individual evaluation outcomes. |
| Three transport attempts and three whole-run attempts | Nested budgets permit up to nine first-call transport attempts if replacement conditions hold. | Measure aggregate budgets, timeouts, and backoff, not only local retry counts. |
| One exhausted slot stops the experiment | Conservative missing-data policy; completion probability declines as required slots increase. | Retained by explicit user direction. Stop measured execution and preserve a descriptive partial report; continuing measured slots after exhaustion is not permitted. |
| No task exclusion after measurement starts | Strong protection against outcome-dependent selection. | Retain. |
| Intrinsic task defects versus unavailable images | Necessary distinction: inability to retrieve verified content does not establish an intrinsic defect. | Retain the normative preflight/infrastructure precedence. |
| New blinded selection after fallback-chain exhaustion | Prevents informed model selection, but repeated aborted experiments can themselves create selection. | Retain all attempted experiment versions and report reasons for failure. |
| No primary estimate for incomplete experiment | Partial evidence still has practical debugging and feasibility value. | Preserve raw/descriptive outputs, missing/not-started reasons, planned/observed counts and costs. No complete-case primary delta, imputation, or continuation label. |
| No regeneration after accepted semantic response | Protects against choosing favorable trajectories. | Retain; recovery proposals must preserve that boundary. |

Illustrative calculations, not measured project failure rates:

- If a valid candidate passes an evaluation with probability 0.95 and evaluations
  are independent, its probability of passing both is 0.95 squared = 0.9025.
- If each of `N` required slots independently has a 0.01 probability of exhausting its
  infrastructure budget, the chance of at least one exhaustion is
  `1 - 0.99**N`. Here `N` counts the operations being assessed; retries and controls
  must not be confused with the 32 measured P6-AC schedule slots.

Actual failures may be correlated. These examples show why local attempt counts
must be assessed together with experiment-level stopping rules; they do not
predict actual reliability.

The audit's earlier pause/resume suggestion is a future option only, not the
current policy. It requires explicit human approval and a predeclared amendment;
non-measured recovery or offline debugging cannot reopen exhausted slots. Keep the
maximum 3 attempts at each retry layer, mandatory second candidate evaluator
(except an experiment-wide stop), eligible pre-semantic replacement boundary, and
prohibition on post-semantic replacement. These operational protections are not
academic uncertainties to relax.

## 6. Metrics and causal claims

| Metric/design | Interpretation risk | Proposed disposition |
| --- | --- | --- |
| A-B ablation | Changes graph tools, prompts, context, and workflow; it does not isolate graph structure alone. | Keep package-level wording. A matched non-graph control would be a separate future design. |
| B-C ablation | Depends on the exact governance implementation, not the abstract existence of a governor. | Develop separately and freeze before exposure as already required. |
| All required tests pass | Objective benchmark outcome, not proof of complete semantic correctness. | Retain without stronger claims. |
| Blocked-proposal count | More blocks can indicate protection, a poor worker, or an overstrict governor. | Interpret alongside completion and independent evidence. |
| Later-contradicted committed mutations | A system that commits almost nothing can appear safe. | Report exposure/commit volume and task utility alongside contradictions. |
| Downstream graph dependencies | Depends on agent-selected granularity; a graph edge alone does not establish causality. | Call it structural reach unless causal evidence is available. |
| Cost per resolved slot | Unstable with few successes and undefined with none. | Preserve numerator, denominator, and uncertainty rather than only the ratio. |
| Secondary-metric multiplicity | Multiple frozen secondary outcomes still create selection pressure even when the primary gate is frozen. | Predeclare reporting order and interpretation; treat secondary metrics as hypothesis-generating unless separately powered. |
| Benefit/cost utility | A small measured benefit can be outweighed by direct or induced cost; there is no validated cost-effectiveness threshold. | Report C-A, overhead, and cost transparently; record practical human judgment separately, without rewriting the frozen labels or claiming validated utility. A new quantitative gate needs approval. |
| Provider cost | Excludes other system/evaluator infrastructure cost. | Do not label as total system cost. |
| Attributed token/latency overhead | Direct graph calls are observable; induced changes to later trajectories are not uniquely attributable. | Separate direct overhead from total A/C differences. |
| UNKNOWN/UNRESOLVED buckets | Honest treatment of ambiguity but missingness can differ by configuration. | Report frequency and denominators; do not silently convert unknowns to favorable values. |

## 7. Technical invariants and deferred parameters

Statistical threshold uncertainty does not weaken correctness or security
invariants. The detailed contracts remain in [Protocol](protocol.md),
[Modules](modules.md), [Problem graph](problem-graph.md), and
[Verification](verification.md).

| Choice | Assessment and next evidence |
| --- | --- |
| Atomic commit, idempotence, owner/epoch fencing, rejection after expiry | Preserve. These are consistency conditions, not tunable statistical thresholds. |
| One live durable-store owner | Proportionate PoC restriction; measure throughput before adding distributed coordination. |
| TTL and renewal cadence | Values are deferred. Derive from scheduling/transaction delays and recovery objectives; test pauses, expiry, and crashes. |
| Restart generation plus persistent clock machinery | Potential simplification opportunity because generations already invalidate old claims. Not a confirmed defect; requires invariant proof, tests, and an ADR amendment. |
| Five initial node categories | Reasonable starting vocabulary, not an empirically optimal ontology. Add types only for demonstrated operations. |
| Batch/query/evidence size limits and transport timeouts | Concrete values remain implementation work. Bound and test before freezing the runtime; do not invent arbitrary P0 constants. |
| Complete native trajectories | Valuable evidence with storage, access-control, and retention costs. Keep them adapter-owned and budget their lifecycle. |
| Core/harness service separation | Preserves integration symmetry but is not itself a security boundary. Test actual worker privilege isolation. |
| Brier/ECE and calibration | Reasonable candidates; target labels, method, binning where relevant, and independent support remain to be specified. |
| Minimum routing success probability | Cannot choose without failure cost, verification quality, uncertainty, and escalation policy. |
| Exploration rate, OOD, abstention thresholds | Appropriately deferred to later experiments; no justified numeric values yet. |
| Pi before P6 | Delays the first usefulness result and multiplies the comparison surface. Keep HarnessX as the primary P6 stack; run Pi later as a separate portability check. |
| Text-based specification tests | Guard wording, not scientific validity. Add executable synthetic decision/boundary and simulation checks where decisions depend on numbers. |

## 8. Practical evidence and decision workflow

This workflow summarizes the amended Evaluation contract; it does not replace its
algorithms or authorize additional changes.

1. Develop/check adapters and operating limits on synthetic or separate development
   tasks. Confirm acceptance of explicit controls and record unknown provider data;
   do not demand access to hidden model implementation details.
2. Obtain approval for concrete resource limits and freeze artifacts before task
   exposure. Freeze the P6-AC selector, eight-task target, two repetitions,
   operational tolerances, and sensitivity report.
3. Run the bounded P6-AC pilot with the existing retry/exclusion/isolation contract.
   Infrastructure-budget exhaustion stops measured execution. Keep partial evidence
   useful through descriptive reporting, not by selectively completing the sample.
4. Report complete paired results only when eligible; otherwise report coverage,
   missing reasons, observed outcomes, and accrued costs without a primary delta.
   Preserve negative/null outcomes and all failed attempts.
5. For a complete pilot, record a human continuation decision separately from the
   observed pilot delta. For incomplete work, record only an unlabeled next action.
   Debugging and exploratory development do not require confirmatory evidence;
   positive claims retain the sensitivity/replication restrictions in Evaluation.

Before stronger population/equivalence claims, separately propose simulations of
estimator/gate operating characteristics, including task/family heterogeneity,
stochastic repeats, sparse outcomes, and infrastructure loss. A later study may
change sample allocation or utility thresholds only with approval and a new freeze.
Neither such simulations nor a power study are prerequisites for this feasibility
pilot; simulation would not itself establish intervention effectiveness.

### Recommended synthetic checks before stronger decision claims

These are non-normative research recommendations, not P6 completion gates.

- The equal-task-means/variable-repetitions counterexample above.
- All-success, all-failure, sparse-success, and identical-paired-effect cases.
- Boundary cases at the descriptive practical margin, without treating that
  margin as an operational decision threshold.
- Small sign change versus large same-sign change; zero as a distinct sign.
- Improved and degraded C-A task outcomes, including near-zero total benefit.
- Correlated tasks within families and unequal retained family composition.
- Independent and correlated infrastructure interruptions with nested retries.
- Unsupported controls and explicit requests with unknown effective values.

### Open decisions

| Priority | Decision | State | Normative owner if accepted |
| --- | --- | --- | --- |
| Resolved | Intended estimand and evidential role of P6 | Resolved 2026-09-20: [practical pilot](evaluation.md#p6-practical-pilot), not population proof | `evaluation.md` |
| Later | Inferential analysis for stronger claims | Not part of P6-AC; requires a separate study and estimand | `evaluation.md` |
| Resolved | Mechanical sensitivity-discordance warning | Resolved 2026-09-20; see [Evaluation](evaluation.md#practical-sensitivity-report) | `evaluation.md` |
| Before P6 exposure | Operational tolerances and complete-system utility | Operator must record cost, latency, and intervention tolerances before exposure; no universal values are inferred here | `evaluation.md` |
| Resolved | Sample/repetition allocation | Resolved 2026-09-20 as eight target tasks, four reserves, and two repetitions; broader precision remains deferred | `evaluation.md` |
| Resolved | Observable generation-control/model record | Resolved 2026-09-20: accepted explicit requests and [unknown provider metadata](evaluation.md#p6-hosted-model-metadata) are distinguished from effective behavior | `evaluation.md` |
| Before P6 exposure | Concrete experiment resource limits and accounting | Operator must approve finite values and accounting/reservation method in the [resource envelope](evaluation.md#p6-resource-budget); no arbitrary amounts fixed by this audit | `evaluation.md` |
| Retained | Experiment pause/resume versus fatal infrastructure stop | Hard stop retained for exhausted infrastructure; predeclared reserves apply only before measured execution | `evaluation.md` |
| Later | Calibration/routing thresholds and technical runtime limits | Resolve in owning implementation/research phase | `verification.md` / `model-routing.md` / `protocol.md` / `modules.md` in their respective phases |

## Maintenance and references

Recommended maintenance: link accepted decisions to their normative owners and
dated evidence, preserving counterexamples without maintaining a second copy of
selectors, bootstrap, leases, retries, or gates. This register remains
non-normative; its recommendations do not create implementation or research gates.

Project sources: [Evaluation](evaluation.md), [Architecture](architecture.md),
[Problem graph](problem-graph.md), [Plan](../PLAN.md), [Review loop](review-loop.md),
[Specification checks](specification-checks.md), [Verification](verification.md),
[Routing](model-routing.md), [Protocol](protocol.md), [Modules](modules.md),
and [Risks](risks.md). Accepted ADRs 0001–0009 are indexed in
[Architecture decisions](adr/).

External context:

- [Robert E. Blackwell, Jon Barry, and Anthony G. Cohn, *Towards Reproducible
  LLM Evaluation: Quantifying Uncertainty in LLM Benchmark Scores*](https://arxiv.org/abs/2410.03492),
  revalidated 2026-09-20: reports that temperature zero and fixed seeds do not
  universally guarantee deterministic model answers. This does not establish
  behavior of our pinned stack.
- [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html):
  distinguishes resample count, confidence level, interval method, and paired
  resampling. It does not validate any particular method for this experiment.
