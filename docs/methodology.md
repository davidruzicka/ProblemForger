# Methodology audit and decision register

## Status and authority

This is a **non-normative audit**, recorded on 2026-09-19 against local commit
`313c167` (published equivalent: `3ae96d3ee5fd7645dac01cd885e23771bc26a840`).
The register itself is checked in as `docs/methodology.md` on branch
`p0-spec-audit` in commit `6f7a7ae320e07ea7be39dc9ad1fe1ee3c206510f`.
The audited snapshot predates the register; `git diff --stat` between the
audited snapshot and that commit shows this file as the only added path. The
register therefore records the audit artifact separately from the audited
content. It records the parameter review and subsequent discussion, not an
approved replacement experiment. Creating this document does not approve its
proposals. No selected benchmark tasks were opened or executed for this audit.

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
more isolated thresholds.

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
prove reference-stream reproducibility but do not include the degenerate
counterexample in §1.

## 1. Estimand and interpretation

The first decision is whether P6 is a feasibility pilot or evidence for a
practically useful improvement. Its current small budget and automatic
continuation/equivalence rules serve different purposes.

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

### Bootstrap degeneracy: confirmed synthetic counterexample

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

Proposal: simulate coverage and decision errors before treating these intervals
as evidence for equivalence or progression. Do not automatically substitute BCa,
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
| 12 primary tasks | Defensible feasibility budget; adequacy for detecting a 10 percentage-point effect is not established. | Keep the pilot interpretation; size a later study for required precision using separate pilot evidence. |
| Three runs per task/configuration | Detects some variation but estimates it coarsely. 108 executions are not 108 independent tasks. | Choose task count versus repetition count using between-task and within-task variability. |
| Minimum eight retained tasks | Two-thirds retention is an administrative completeness threshold, not a precision guarantee. | Separate completeness from evidential adequacy. |
| Eight holdout tasks | Useful initial independent check, not established calibration support. | Expand before calibration claims; transitions within a task are not independent tasks. |
| Maximum two tasks per family | Reduces dominance, not within-family dependence. Task resampling does not explicitly model family clustering. | Define task versus family generalization and evaluate the corresponding analysis. |
| Family from repository name prefix before the first dot | Deterministic heuristic, not proof of common upstream; owner identity is ignored. | Validate against provenance metadata and document collisions/splits. |
| Family-disjoint holdout | Protects against leakage but tests cross-family transfer, not merely new tasks in familiar repositories. | Retain with an explicit generalization claim. |
| 1–20 failing and 1–200 passing tests | Counts are weak proxies for runtime and difficulty; filters change the population. | Justify operationally and report filtered population composition. |
| At most 12,000 problem-statement characters | Characters are not tokens; the limit can select particular task types. | Relate to actual context limits, including tools and history. |
| Fixed hash ordering and selection seed | Good reproducibility; no scientific advantage of the particular seed. | Retain; avoid interpreting deterministic selection as representativeness. |
| SWE-smith training split | Suitable for a bounded mechanism pilot, not an uncontaminated capability claim. Familiarity need not affect all treatments equally. | Scope conclusions to this population and replicate independently. |
| Schema errors abort materialization | Fail-fast behavior avoids silent population changes but can make unrelated malformed rows experiment-fatal. | Keep population rules explicit; evaluate robustness on development data before freeze, not by skipping rows after exposure. |

At the audited repetition count, the primary point-estimate grid is about
2.78 percentage points at N=12 and 4.17 at N=8. This is numerical granularity,
not uncertainty or a minimum detectable effect.

## 3. Thresholds and sensitivity

### Direction and magnitude are different diagnostics

The earlier proposal to flag any sign change tests direction only:

| Primary estimate to omitted-repetition estimate | Absolute change | Sign-change flag |
| --- | --- | --- |
| -1 to +1 percentage points | 2 percentage points | Yes |
| +1 to +18 percentage points | 17 percentage points | No |

These are explanatory arithmetic examples, not exact realizable points on every
N=8..12 outcome grid. A magnitude diagnostic would rank them differently.

For sensitivity of a success-rate difference, absolute percentage-point change
is interpretable. Relative change divides by a potentially tiny, zero, or
negative effect and is unsuitable as the default instability criterion.

The subsequent proposal to flag a maximum absolute change of at least 10
percentage points was also insufficiently justified as a standalone instability
threshold. Keep these three choices separate:

- minimum worthwhile benefit;
- maximum acceptable harm;
- tolerated estimator sensitivity.

`SENSITIVITY_DISCORDANT` was resolved 2026-09-20 by the combined sign-and-
practical-band point-estimate rule in
[Evaluation](evaluation.md#frozen-sensitivity-analyses). That rule reuses the
already frozen `delta = 10` percentage-point margin, while the separate utility
rationale for the margin remains an analysis-parameter question. Report all
omitted-repetition effects and their maximum absolute departure descriptively;
the normative predicate is maintained in Evaluation rather than duplicated here.

### Analysis parameter register

| Parameter | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| Practical margin of 10 percentage points | Human-selected, without a documented cost/latency or utility derivation. | Derive from value of additional successes and intervention cost. |
| Symmetric benefit/harm margins | Acceptable harm need not equal worthwhile benefit. | Decide separately, with reasons. |
| 95% marginal intervals | Familiar convention, not a joint 95% guarantee for two contrasts or an automatic decision justification. | Specify simultaneous-error requirements if making confirmatory claims. |
| Percentile task bootstrap | Transparent, but small/discrete/clustered data can make interval interpretation fragile; see the counterexample. | Validate operating characteristics for the chosen estimand. |
| 100,000 resamples | Reduces Monte Carlo error, not lack of independent observations. | May retain; do not present as additional evidence. |
| PCG64, fixed seed, shared task indices | Useful reproducibility and paired-analysis controls. | Retain one executable owner and golden fixtures. |
| Numerical tolerance of 1e-12 percentage points | Cross-implementation fidelity check, not measurement precision. | Do not report empirical effects with this precision. |
| Exact paired sign permutation | Enumeration is exact conditional on a valid sign-exchangeability model; it does not remove dependence or small-sample limitations. | Keep diagnostic and explain assumptions. |
| Leave-one-repetition-out | Measures dependence on groups of observed runs. Replicate ordinals are not a common time window or provider seed. | Report every omission; do not attribute changes to an identified causal source. |
| Replicate-disagreement rate | Depends on success probability; an always-failing system is perfectly stable. | Always report with task success, never as standalone quality. |

### Progression gate interaction

The audited P7 gate can admit a B-A point effect near +10 percentage points and
a C-B effect near -9 when their lower bounds meet its conditions. The complete
C-A gain can then be near +1, before accounting for overhead. This is an
illustrative gate interaction, not an observed experiment.

Proposal: report the complete-system C-A effect and costs when deciding whether
the package is useful. Adding a new primary contrast or decision gate would be
a research amendment, not a mechanical fix.

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
| Verification of effective temperature | Accepted requests establish API acceptance, not hidden provider implementation. Effective-value acknowledgement may be unavailable. | Distinguish requested, accepted, provider-reported, and unobservable values. |
| EXPLICIT / OMITTED_NATIVE / UNSUPPORTED / UNKNOWN statuses | These statuses summarize the richer `generation-policy-v1` record; the status alone must not be read as proof of an effective value. | Preserve the normative record. Derive separate capability, request-mode, and effective-value fields only if analysis needs them, and never infer an effective value from acceptance or documentation. |
| 16,384 output tokens per response | Not a run-level cost/token cap. | Justify on development data; measure truncation and total usage. |
| 60 agent steps | A step need not correspond to one tool call; graph work consumes budget. | Define step semantics and interpret effects at that budget, including graph overhead. |
| 30-minute semantic deadline | Mixes model speed, provider delays, tests, and service overhead. Appropriate for end-to-end utility, not isolated reasoning quality. | Report the binding limit and latency breakdown. |
| Setup outside semantic deadline | Separates startup from interaction budget but does not make startup cost disappear. | Retain end-to-end time/cost alongside semantic time. |
| Same model and effort across harnesses | Does not establish equivalent prompts, sampling, reasoning budget, or tool policy. | Compare packaged systems unless actual parity is demonstrated. |
| Freezing hidden prompts/defaults | May be impossible for opaque hosted systems. | Pin observable versions/configuration and record unobservable behavior as a limitation. |
| Interleaved frozen execution order | Reduces some temporal confounding but does not guarantee balanced positions or independence under drift. | Examine scheduling behavior on synthetic manifests and record provider/version changes. |
| Separate harness comparison | Correct separation from P6 attribution; two harnesses by three configurations increases cost and interaction-analysis complexity. | Freeze scope and analysis before exposure; do not assume P6 sample size is sufficient. |

Documentation is supporting capability evidence, not proof of a hidden runtime
value. Non-task probes should use only interfaces the adapter actually exposes;
they should not emulate unsupported controls or inspect selected evaluation tasks.

## 5. Evaluation repetition and infrastructure

| Rule | Assessment | Proposed disposition/evidence needed |
| --- | --- | --- |
| Two matching baseline evaluations | Can detect instability; agreement twice does not prove stability. | Describe as passing a check, not proof of deterministic behavior. |
| Candidate must pass twice | Measures repeatable benchmark success, not only patch semantics. | Preserve this distinction and report individual evaluation outcomes. |
| Three transport attempts and three whole-run attempts | Nested budgets permit up to nine first-call transport attempts if replacement conditions hold. | Measure aggregate budgets, timeouts, and backoff, not only local retry counts. |
| One exhausted slot stops the experiment | Conservative missing-data policy; completion probability declines as required slots increase. | Consider a predeclared pause/resume policy without regenerating accepted trajectories. Requires approval. |
| No task exclusion after measurement starts | Strong protection against outcome-dependent selection. | Retain. |
| Intrinsic task defects versus unavailable images | Necessary distinction: inability to retrieve verified content does not establish an intrinsic defect. | Retain the normative preflight/infrastructure precedence. |
| New blinded selection after fallback-chain exhaustion | Prevents informed model selection, but repeated aborted experiments can themselves create selection. | Retain all attempted experiment versions and report reasons for failure. |
| No primary estimate for incomplete experiment | Defensible conservative rule; partial evidence still has descriptive value. | Preserve raw/descriptive outputs without claiming a complete paired comparison. |
| No regeneration after accepted semantic response | Protects against choosing favorable trajectories. | Retain; recovery proposals must preserve that boundary. |

Illustrative calculations, not measured project failure rates:

- If a valid candidate passes an evaluation with probability 0.95 and evaluations
  are independent, its probability of passing both is 0.95 squared = 0.9025.
- If each of 108 slots independently has a 0.01 probability of exhausting its
  infrastructure budget, the chance of at least one exhaustion is
  `1 - 0.99**108`, approximately 66.2%.

Actual failures may be correlated. These examples show why local attempt counts
must be assessed together with experiment-level stopping rules; they do not
predict actual reliability.

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
| Benefit/cost utility | A small measured benefit can be outweighed by direct or induced cost; the frozen contract has no cost-effectiveness decision rule. | Decide utility together with the benefit/harm margins before cost is used to justify progression. |
| Provider cost | Excludes other system/evaluator infrastructure cost. | Do not label as total system cost. |
| Attributed token/latency overhead | Direct graph calls are observable; induced changes to later trajectories are not uniquely attributable. | Separate direct overhead from total A/B/C differences. |
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
| Pi before P6 | Valid portability objective but delays the first usefulness result. A minimal portability smoke test is an alternative requiring planning approval. |
| Text-based specification tests | Guard wording, not scientific validity. Add executable synthetic decision/boundary and simulation checks where decisions depend on numbers. |

## 8. Proposed evidence and decision workflow

This is a proposal for resolving the audit, not an authorization to alter P6.

1. Define the estimand, population, and whether P6 is feasibility or a benefit
   decision. Separate scientific claims from further-research decisions.
2. Simulate the complete estimator and gate together, before selecting thresholds.
   Include zero/small/large effects, task and family heterogeneity, stochastic
   repeats, rare successes, degenerate task differences, and infrastructure loss.
3. Measure interval coverage, false benefit/equivalence decisions, progression
   rates, completion probability, and expected cost under those assumptions.
   Record simulation inputs, versions, and limits; simulation is not real evidence
   of the intervention's effectiveness.
4. Run an operational pilot only on separate development tasks. Measure execution
   variance, truncation, binding budgets, service latency, and retry behavior.
5. Select task/repetition counts and distinguish benefit, harm, and sensitivity
   margins using the resulting evidence and explicit utility assumptions.
6. Obtain human approval, amend the normative owners once, and freeze the final
   experiment configuration before task exposure. Do not pool changed versions.

### Required synthetic checks before stronger decision claims

- The equal-task-means/variable-repetitions counterexample above.
- All-success, all-failure, sparse-success, and identical-paired-effect cases.
- Boundary cases at practical margins and precedence between decision labels.
- Small sign change versus large same-sign change; zero as a distinct sign.
- Improved B-A but degraded C-B, including near-zero total C-A benefit.
- Correlated tasks within families and unequal retained family composition.
- Independent and correlated infrastructure interruptions with nested retries.
- Unsupported controls and explicit requests with unknown effective values.

### Open decisions

| Priority | Decision | State | Normative owner if accepted |
| --- | --- | --- | --- |
| High | Intended estimand and evidential role of P6 | Needs explicit clarification | `evaluation.md` |
| High | Bootstrap/gate operating characteristics | Needs simulation evidence | `evaluation.md` |
| High | Mechanical sensitivity-discordance rule and its consequence | Resolved 2026-09-20; see [Evaluation](evaluation.md#frozen-sensitivity-analyses) | `evaluation.md` |
| High | Benefit/harm margins and complete-system utility | Needs rationale and approval | `evaluation.md` |
| Medium | Sample/repetition allocation and family dependence | Needs pilot/simulation evidence | `evaluation.md` |
| Medium | Observable generation-control record | Needs schema clarification | `evaluation.md` (and `protocol.md` only if service-boundary semantics change) |
| Medium | Experiment pause/resume versus fatal infrastructure stop | Alternative requiring approval | `evaluation.md` |
| Later | Calibration/routing thresholds and technical runtime limits | Resolve in owning implementation/research phase | `verification.md` / `model-routing.md` / `protocol.md` / `modules.md` in their respective phases |

## Maintenance and references

When a decision is accepted, update its normative owner and replace the open state
here with a dated link to the decision and evidence. Do not maintain a second
implementation of selectors, bootstrap, leases, retries, or gates in this audit.
Preserve counterexamples as evidence; do not convert recommendations into policy
merely because they are written under `docs/`.
When this branch merges, add this register to the README documentation index;
the register remains non-normative.

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
