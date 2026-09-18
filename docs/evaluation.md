# Evaluation

## Rule

Evaluation design is part of the specification, not an afterthought.

The first experiment is intentionally small and mechanistic. It is not intended to establish state-of-the-art coding performance.

## Ablation ladder

At minimum:

- **A — harness baseline**
- **B — A + explicit ProblemGraph interaction**
- **C — B + deterministic mutation governance**
- **D — C + learned verifier**
- **E — D + calibration/abstention**
- **F — E + model routing**

Do not combine multiple new layers and attribute aggregate improvement to one component.

### Interpretation

A→B measures the graph interaction layer as a package. It necessarily changes the available tool/API surface and minimal system instructions, so it is **not** a pure "storage-only" comparison.

B→C is the cleaner early governance ablation: B and C must expose the same ProblemForger tools, graph schema, and instructions. They differ only in deterministic governance/evidence policy.

## Frozen P6 mechanism experiment (v1)

This section is the P0 experiment contract for configurations A/B/C.

Changes after implementation begins require an explicit documented amendment before any affected measured run. Never silently replace a task/model/metric after seeing results.

### Harness

Primary P6 harness:

- HarnessX
- pinned revision: `bf5f199ee65034d55db0c536e582f1e7c8abf669`

P6 is intentionally single-harness. Pi is used later as an independent portability check rather than mixed into the first causal comparison.

### Model

Primary P6 model:

- provider: Anthropic direct provider supported by HarnessX;
- model: `claude-sonnet-4-6`;
- `extended_thinking=false`;
- `max_tokens=16384` per model response;
- `temperature=0`;
- same provider/model settings for A, B, and C.

If this exact provider/model becomes unavailable before the first measured run, update this document **before** running the experiment and restart the A/B/C experiment contract with one replacement model. Do not mix models within the v1 comparison.

### Agent budget

Per run:

- maximum 60 HarnessX agent steps;
- maximum wall-clock time: 30 minutes;
- no configuration-specific retry allowance;
- provider transport/rate-limit retries that occur before a semantic model result are recorded as infrastructure retries rather than extra agent steps.

Token usage, billed cost, and wall time are measured outcomes rather than normalized away. Added graph context/tool calls must pay their actual overhead.

### Pre-P6 frozen artifacts

Before any task selected by the P6 selector is intentionally identified, inspected, opened, or executed for development/evaluation, three version-controlled artifacts must be frozen:

1. **`graph-intervention-v1`**
   - exact agent-visible ProblemForger tool/API schemas;
   - exact graph-use system/user instruction additions;
   - graph schema/version used by B and C;
   - core schema/version invariants active in both B and C;
   - graph-query defaults, bounds, serialization/context formatting, and mutation operation schema;
   - HarnessX adapter mapping that can affect agent-visible behavior;
   - relevant service/protocol versions;
2. **`governance-policy-v1`**
   - every deterministic check that can affect C;
   - evidence consumed and the exact property each check evaluates;
   - decision precedence;
   - mapping to `COMMIT`, `REJECT`, `RETRY`, or `ESCALATE`;
   - protected-anchor behavior, exceptions, and thresholds;
3. **`graph-metrics-v1`**
   - executable or otherwise exact queries/rules for every **journal-derived** graph/governance metric;
   - the frozen decision reason codes considered a deterministic contradiction/block;
   - the exact edge types/directions and traversal rule used for downstream causal-dependency counts;
   - the evidence methods/scopes that qualify as later contradiction/invalidation;
   - time/version cutoffs, denominators, exclusions, and `UNKNOWN/UNRESOLVED` handling;
   - any adjudication rule for non-machine-classifiable secondary analysis;
4. **`telemetry-metrics-v1`**
   - exact observation schema/fields required for P6 secondary overhead metrics;
   - attribution rules for ProblemForger-added model tokens, tool calls, and latency;
   - clock/latency boundaries and missing-observation handling;
   - aggregation rules and denominators for telemetry-derived metrics.

All four artifacts must be content-addressed (for example SHA-256) and their hashes recorded in every P6 run manifest.

Development of these artifacts must use synthetic fixtures or separate development tasks. The selected P6 primary and reserved holdout tasks may not be used to tune any of the four artifacts.

Primary graph/governance metrics must be mechanically reproducible from the durable run journal plus the frozen `graph-metrics-v1` artifact. Ambiguous cases that the frozen rule cannot classify are reported as `UNRESOLVED` and are not manually reassigned into primary metric buckets after results are known.

Telemetry-derived secondary metrics must be reproducible from the required P6 telemetry plus `telemetry-metrics-v1`. Telemetry remains outside authoritative graph state; P6 simply requires the configured telemetry capture needed for those secondary measurements.

Any change to one of these artifact hashes after the first measured run creates a new experiment version and requires a complete new A/B/C comparison. Results with different artifact hashes must not be pooled as one v1 estimate.

### Task source

Use a deterministic subset of the public SWE-smith dataset:

- dataset: `SWE-bench/SWE-smith`;
- pinned dataset revision: `ea6d7173829c7ec8fa16c22055699ff2e9188091`;
- split: `train`;
- selection seed namespace: `problemforger-p6-v1`.

SWE-smith provides executable software-engineering tasks with failing/passing tests. It is public training data, so this experiment must **not** be presented as an uncontaminated measurement of frontier coding capability. Its purpose here is paired mechanism comparison under executable ground truth.

### Deterministic task selection

At the pinned SWE-smith revision, `FAIL_TO_PASS` and `PASS_TO_PASS` are dataset list/sequence fields, not JSON-encoded strings. Selection code must validate that both fields decode/load as sequences of test identifiers before applying count filters; if the pinned schema does not match this expectation, materialization must fail rather than reinterpret string length as test count.

Build the candidate set from the pinned snapshot using rows satisfying all of:

- non-empty `instance_id`;
- non-empty `problem_statement`;
- non-empty `image_name`;
- `1 <= len(FAIL_TO_PASS) <= 20`;
- `1 <= len(PASS_TO_PASS) <= 200`;
- `len(problem_statement) <= 12000` characters.

Define a repository family from the part of `repo` after the slash and before the first dot. This groups multiple SWE-smith snapshots of the same upstream repository family.

For every candidate compute:

```text
rank = SHA256("problemforger-p6-v1\0" + instance_id)
```

Sort ascending by the tuple `(rank, instance_id)` so even a theoretical hash collision has a deterministic tie-break.

Select the two sets with two explicit scans:

1. **Primary scan**
   - scan the sorted candidate list from the beginning;
   - select a candidate if its repository family currently has fewer than 2 selected primary tasks;
   - otherwise skip it for the primary set;
   - stop after selecting 12 primary tasks;
   - record the set of repository families represented in the primary set.

2. **Holdout scan**
   - start a fresh scan from the beginning of the same sorted candidate list;
   - exclude every primary task;
   - exclude every candidate whose repository family appears in the primary set, making the holdout repository-family-disjoint from primary;
   - maintain a new holdout-only family counter, reset to zero at the start of this scan;
   - select a candidate if its holdout family count is below 2;
   - stop after selecting 8 holdout tasks.

Candidates skipped by the primary family cap are therefore reconsidered by the holdout scan only if their repository family is not represented in primary; in practice, any candidate from a primary family remains excluded from holdout by the family-disjoint rule.

Materialization must fail rather than silently relax these rules if fewer than 12 primary or 8 holdout tasks can be selected.

Only after `graph-intervention-v1`, `governance-policy-v1`, `graph-metrics-v1`, and `telemetry-metrics-v1` are frozen, materialize the resulting 20 IDs into a version-controlled manifest and record its SHA-256. The selector above is frozen; materialization is not an opportunity to hand-pick tasks.

Before that freeze, do not intentionally derive/open/run the selected primary or holdout task IDs for development. After materialization, do not inspect gold patches when deciding inclusion beyond fields listed above.

### Repetitions, run isolation, and execution ordering

For A/B/C:

- 12 primary tasks before patch-independent preflight exclusions;
- 3 independent runs per task per configuration;
- 36 task-runs per configuration before exclusions;
- 108 measured runs total before exclusions.

Every measured **agent run** is isolated. Before starting a run:

- restore the exact pinned pristine task repository state in a fresh writable workspace/container layer;
- start a new HarnessX agent/session with no conversation, scratchpad, tool state, or mutable workspace inherited from any prior run;
- allocate a distinct ProblemForger `run_id` backed by an empty durable journal;
- do not import graph state, proposal history, telemetry state, or candidate patches from another configuration/replicate;
- immutable base images and read-only dependency/download caches may be reused only if they cannot carry task-generated mutable state into the run.

A run failing this reset contract is an infrastructure-invalid attempt and is rerun from a clean state; it is not scored as an agent outcome.

Execution order is also frozen mechanically. Define the ordering seed namespace exactly as:

```text
problemforger-p6-order-v1
```

After patch-independent preflight exclusions are known, but **before the first measured agent run**, materialize the complete schedule for the remaining common task set:

1. for every `(instance_id, replicate)` block, where `replicate ∈ {1,2,3}`, compute
   ```text
   block_key = SHA256("problemforger-p6-order-v1\0block\0" + instance_id + "\0" + replicate)
   ```
2. sort blocks by `(block_key, instance_id, replicate)`;
3. within each block, for each `config ∈ {A,B,C}`, compute
   ```text
   config_key = SHA256("problemforger-p6-order-v1\0config\0" + instance_id + "\0" + replicate + "\0" + config)
   ```
4. sort A/B/C by `(config_key, config)` and execute those three measured runs consecutively in that order;
5. concatenate all sorted blocks to form the global schedule.

Write the complete schedule to a version-controlled or immutable run artifact and record its SHA-256 before execution starts. Do not reorder around provider performance, failures, or observed task outcomes; infrastructure retries retain the original schedule slot identity and are explicitly linked to it.

A provider-side random seed is not assumed available.

### End-to-end ground truth

A measured run is **resolved** only when both mandatory fresh-environment evaluations of its exact candidate patch produce an identical full required-test vector and that vector has all required `FAIL_TO_PASS` tests passing and all required `PASS_TO_PASS` tests remaining passing. Any candidate-vector disagreement is `PATCH_UNSTABLE` and counts as unresolved/failure.

The model/agent is not shown the gold patch or hidden evaluator result during execution.

### Primary outcomes

Predeclare two paired comparisons:

1. **B - A:** change in mean task resolution rate from adding explicit problem-graph interaction.
2. **C - B:** change in mean task resolution rate from deterministic governance with the same graph interface.

Report:

- per-task resolution across repetitions;
- paired percentage-point difference;
- bootstrap 95% confidence interval using the frozen procedure below;
- all raw task-run outcomes.

### Frozen primary effect estimator and bootstrap

For each task `i` remaining after preflight exclusions and each configuration `X ∈ {A,B,C}`, compute:

```text
r_i(X) = mean of the 3 binary resolved indicators for task i under X
```

Define paired task effects:

```text
d_i(B-A) = r_i(B) - r_i(A)
d_i(C-B) = r_i(C) - r_i(B)
```

The reported point estimate for each primary comparison is the arithmetic mean of its `d_i` values across the common included task set, expressed in percentage points.

The 95% confidence interval is a **percentile task bootstrap** with these frozen parameters:

- resampling unit: task;
- each sampled task retains all 3 repetitions for every compared configuration;
- bootstrap sample size: the number `N` of included tasks after preflight exclusions;
- sampling: `N` tasks with replacement;
- recompute `r_i`, paired `d_i`, and the mean paired effect for each resample;
- iterations: 100,000;
- RNG: NumPy `Generator(PCG64)`;
- seed: `0x505246365F423031`;
- interval: empirical 2.5th and 97.5th percentiles using NumPy `quantile(..., method="linear")`;
- no BCa/basic/studentized alternative is substituted for the primary analysis.

If the implementation language differs, it must reproduce this procedure and seed semantics exactly or use a checked-in reference implementation/output fixture.

With only 12 tasks before exclusions, this is a PoC effect estimate, not strong population-level evidence. Avoid binary "significant/not significant" claims.

### Secondary end-to-end metrics

- input/output/cache tokens where provider reports them;
- provider cost;
- wall-clock latency;
- agent steps;
- tool calls;
- cost per resolved task;
- latency per resolved task.

### Journal-derived graph/governance metrics

Primary graph/governance metrics are computed from the durable run journal using the frozen `graph-metrics-v1` rules. Analysts must not decide after seeing outcomes what counts as "decisive", "contradicted", or "causally dependent".

Report at least:

- committed mutations later classified as contradicted by the exact frozen evidence/scope rule;
- downstream committed mutations reachable by the frozen causal-dependency traversal from an entity that is later invalidated/contradicted, subject to the frozen time/version cutoff;
- proposals blocked with one of the frozen deterministic-contradiction reason codes;
- durable `RETRY` / `ESCALATE` / `CONFLICT` decision counts;
- number of graph nodes/edges, durable journal records, and graph-changing events;
- `UNRESOLVED` count for cases the frozen automatic rule cannot classify.

Manual interpretation may be reported separately as qualitative/secondary analysis but may not silently alter primary machine-derived metric buckets.

A universal false-positive/false-negative transition rate is **not** claimed for semantically ambiguous transitions without independent labels.

### Telemetry-dependent overhead metrics

The following are secondary metrics and require the P6 telemetry capture defined by frozen `telemetry-metrics-v1`:

- ProblemForger-added model input/output/cache tokens where attributable;
- ProblemForger-added tool calls;
- ProblemForger/service/adapter latency according to the frozen timing boundaries;
- related per-run overhead aggregates.

These metrics are **not** derived from the authoritative journal and must not be copied into it merely to make the analysis convenient. Missing required telemetry makes the affected telemetry-derived metric unavailable/invalid according to `telemetry-metrics-v1`; it does not change graph correctness or replayability.

### Configuration parity

A:
- unmodified pinned HarnessX SWE task setup;
- no ProblemForger graph tools/instructions.

B:
- exactly the agent-visible surface captured by frozen `graph-intervention-v1`;
- durable run journal + event-sourced graph;
- only the schema/version/core-invariant behavior declared in that artifact;
- otherwise permissive mutation acceptance.

C:
- exactly the same frozen `graph-intervention-v1` as B;
- adds only frozen `governance-policy-v1`.

### Intervention freeze and parity

The P0 document freezes the experiment envelope, not implementation details that do not yet exist. P2/P3/P4 may develop the graph surface and deterministic policy on synthetic/separate development tasks, but the four pre-P6 artifacts above must be frozen **before** the selected P6 tasks are exposed.

For B→C, the `graph-intervention-v1` hash must be identical. The only intentional B→C difference is activation of `governance-policy-v1`.

Any other prompt, tool, memory, sandbox, model setting, graph-surface artifact, governance-policy artifact, or primary metric-rule difference invalidates the intended comparison and must be documented as a new experiment version.

## Infrastructure failure policy

Do not convert infrastructure faults into model failures.

Examples include:

- provider outage before a semantic response;
- container/image download failure;
- evaluator crash unrelated to candidate patch;
- corrupted local benchmark environment.

Record the failed attempt and retry the same task/configuration once the infrastructure is healthy. Agent max-step exhaustion, agent-produced invalid patches, and tool failures caused by the agent remain task outcomes.

Evaluator/task stability and candidate-patch stability are handled separately so an agent-produced flaky patch cannot remove an unfavorable task from the paired analysis.

### Task/evaluator preflight

Before any measured A/B/C agent run for a primary task:

1. evaluate the task's **unmodified pinned repository state** twice in separate fresh instances of the same pinned environment;
2. compare the full required-test outcome vector (the pass/fail result for every required `FAIL_TO_PASS` and `PASS_TO_PASS` test);
3. both control vectors must be identical **and** match the benchmark's expected baseline contract:
   - every required `FAIL_TO_PASS` test is failing;
   - every required `PASS_TO_PASS` test is passing;
4. if the two vectors differ, run one third control evaluation in another fresh instance;
5. if any control vectors differ, classify the task as `EVALUATOR_UNSTABLE`;
6. if the stable control vector does not match the expected baseline contract, classify the task as `BASELINE_INVALID`.

`EVALUATOR_UNSTABLE` and `BASELINE_INVALID` are patch-independent preflight exclusions applied **before measured agent runs begin**. Exclude all A/B/C configurations and repetitions for such a task from the primary paired A→B and B→C analysis, preserve/report all preflight evaluator outputs and exclusion reason, report the reduced denominator, and do not replace the task.

### Measured candidate patches

For **every measured candidate patch**, regardless of its first outcome:

1. evaluate the exact patch twice in separate fresh instances of the pinned environment;
2. compare the full required-test outcome vectors;
3. the run is scored **resolved** only if both vectors are identical and satisfy the end-to-end resolution criterion;
4. if the two vectors differ, classify that candidate/run as `PATCH_UNSTABLE` and score the run as unresolved/failure; do **not** exclude the task or any paired runs.

A third candidate-patch evaluation may be retained as diagnostic data but cannot change the frozen primary classification above.

A one-off provider/container/evaluator infrastructure failure that produces no valid required-test vector is retried as an infrastructure retry and does not by itself trigger task exclusion or `PATCH_UNSTABLE`. All primary paired comparisons use the same common task set fixed after preflight task/evaluator exclusions.

## Later verifier/calibration split

The 8 reserved SWE-smith tasks are held out at the **task** level from P6-driven verifier tuning.

For P7/P8:

- training/development may use P6 trajectories plus separately generated/training data;
- calibration/evaluation uses task-disjoint data;
- transitions from one task/run may not be randomly split across train and calibration/test sets.

The final calibration set will likely need more than 8 tasks; P8 must expand the task-level holdout before making calibration claims.

## P11 external-validity benchmark

Do not use SWE-bench Verified as the final capability benchmark. By 2026 it has known contamination and task-quality concerns.

At P11, re-audit then-current coding benchmarks and freeze an independent external-validity set. Current candidates include SWE-Bench Pro Verified, but it is recent and should not be adopted solely because it is new.

## Core metrics for later phases

### Verification/calibration

- Brier score;
- ECE or justified alternative;
- reliability plot data;
- high-confidence error rate;
- abstention/coverage;
- selective accuracy;
- calibration by task family/novelty bucket.

### Routing

- task success by selected model;
- escalation rate;
- cost/latency at matched task success;
- exploration/shadow-evaluation coverage;
- quality of predicted success probabilities.

## Threats to validity

Track explicitly:

- public-dataset contamination;
- benchmark/task-quality problems;
- small task sample;
- same-task tuning and evaluation;
- model/provider version drift;
- judge/worker correlated errors;
- routing selection bias;
- prompt/tool/interface confounding;
- differing harness capabilities;
- provider or benchmark infrastructure failures;
- cherry-picking peak runs.

## Raw data and reproducibility

Record enough structured data to reproduce aggregate results:

- repository commit;
- effective redacted configuration;
- harness version/commit;
- provider/model identifier and relevant settings;
- task-manifest hash;
- run/configuration/replicate identifiers;
- event schema versions;
- full ProblemForger durable run journal, including proposal/decision audit records and graph-changing events;
- `graph-intervention-v1`, `governance-policy-v1`, `graph-metrics-v1`, and `telemetry-metrics-v1` hashes;
- execution-schedule artifact/hash;
- required observation/telemetry needed for non-authoritative usage/latency metrics;
- benchmark evaluator output.

Do not store secrets or private/licensed source material in public traces.
