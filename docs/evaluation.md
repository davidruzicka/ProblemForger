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

### Task source

Use a deterministic subset of the public SWE-smith dataset:

- dataset: `SWE-bench/SWE-smith`;
- pinned dataset revision: `c3261078cb87400c0152f2d72c89d6269f3697db`;
- split: `train`;
- selection seed namespace: `problemforger-p6-v1`.

SWE-smith provides executable software-engineering tasks with failing/passing tests. It is public training data, so this experiment must **not** be presented as an uncontaminated measurement of frontier coding capability. Its purpose here is paired mechanism comparison under executable ground truth.

### Deterministic task selection

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

Sort ascending by hexadecimal `rank`.

Greedily select:

- first 12 tasks, with at most 2 tasks per repository family: **P6 primary set**;
- next 8 eligible tasks under the same cap: **reserved task-level holdout** for later verifier/calibration work.

Before the first measured run, materialize the resulting 20 IDs into a version-controlled manifest and record its SHA-256. The selector above is frozen; materialization is not an opportunity to hand-pick tasks.

Do not inspect gold patches when deciding inclusion beyond fields listed above.

### Repetitions and ordering

For A/B/C:

- 12 primary tasks;
- 3 independent runs per task per configuration;
- 36 task-runs per configuration;
- 108 measured runs total.

Within each task and replicate index, interleave/randomize A/B/C execution order using a stable recorded ordering seed. This reduces time/provider-drift confounding.

A provider-side random seed is not assumed available.

### End-to-end ground truth

A task is **resolved** only when the benchmark evaluator reports all required `FAIL_TO_PASS` tests passing and required `PASS_TO_PASS` tests remaining passing.

The model/agent is not shown the gold patch or hidden evaluator result during execution.

### Primary outcomes

Predeclare two paired comparisons:

1. **B - A:** change in mean task resolution rate from adding explicit problem-graph interaction.
2. **C - B:** change in mean task resolution rate from deterministic governance with the same graph interface.

Report:

- per-task resolution across repetitions;
- paired percentage-point difference;
- bootstrap 95% confidence interval resampling at the **task** level;
- all raw task-run outcomes.

With only 12 tasks, this is a PoC effect estimate, not strong population-level evidence. Avoid binary "significant/not significant" claims.

### Secondary end-to-end metrics

- input/output/cache tokens where provider reports them;
- provider cost;
- wall-clock latency;
- agent steps;
- tool calls;
- cost per resolved task;
- latency per resolved task.

### Graph/governance metrics

Only label a transition "wrong" when later evidence makes that claim defensible.

Report at least:

- committed mutations later contradicted by decisive deterministic/external evidence;
- number of downstream committed mutations causally dependent on an eventually invalidated entity before invalidation;
- proposals blocked by a decisive deterministic contradiction;
- retries/escalations/conflicts;
- number of graph nodes/edges/events;
- ProblemForger-added tokens/tool calls/latency where separable.

A universal false-positive/false-negative transition rate is **not** claimed for semantically ambiguous transitions without independent labels.

### Configuration parity

A:
- unmodified pinned HarnessX SWE task setup;
- no ProblemForger graph tools/instructions.

B:
- ProblemForger graph tools and minimal graph-use instruction;
- authoritative event-sourced graph;
- schema/version/core-invariant checks;
- otherwise permissive mutation acceptance.

C:
- exactly the same graph tools/instruction as B;
- adds deterministic evidence/governance rules.

Any other prompt, tool, memory, sandbox, or model-setting difference invalidates the intended B→C comparison and must be documented as a new experiment version.

## Infrastructure failure policy

Do not convert infrastructure faults into model failures.

Examples include:

- provider outage before a semantic response;
- container/image download failure;
- evaluator crash unrelated to candidate patch;
- corrupted local benchmark environment.

Record the failed attempt and retry the same task/configuration once the infrastructure is healthy. Agent max-step exhaustion, agent-produced invalid patches, and tool failures caused by the agent remain task outcomes.

If benchmark tests themselves are unstable across identical patch/environment reruns, mark the run/task as evaluator-unstable and report the exclusion; do not substitute a friendlier task after results are known.

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
- full ProblemForger domain-event stream;
- observation/telemetry needed for metrics;
- benchmark evaluator output.

Do not store secrets or private/licensed source material in public traces.
