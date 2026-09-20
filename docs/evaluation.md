# Evaluation

<a id="p6-practical-pilot"></a>
## Rule

Evaluation design is part of the specification, not an afterthought.

The first experiment is a **practical whole-system feasibility pilot**: does the
complete ProblemForger package run usefully, at tolerable cost, on a small fixed
task set?
It is not intended to establish state-of-the-art coding performance, population
equivalence, or exact reproducibility of hosted model behavior. Academic uncertainty
is acceptable when reported; outcome-dependent selection and missing audit evidence
are not. Correctness, isolation, and security invariants remain unchanged.
P6 is not confirmatory evidence or population-level proof of benefit or equivalence.

## Practical comparison ladder

The first executable PoC compares the baseline with the complete ProblemForger
package. This answers the practical adoption question directly and avoids
pretending that a small pilot can attribute every observed change to one internal
mechanism.

- **A — pinned HarnessX runtime + common benchmark-adapter baseline**
- **C — A + explicit ProblemGraph interaction + deterministic mutation governance**

The following configurations remain available for later diagnostic work:

- **B — A + explicit ProblemGraph interaction**
- **D — C + learned verifier**
- **E — D + calibration/abstention**
- **F — E + model routing**

P6 does not claim that a C−A result isolates graph or governance. A/B/C
mechanism attribution is a separately versioned diagnostic experiment and is not
required for the first practical go/no-go decision.

### Interpretation

A→B measures the graph interaction layer as a package. It necessarily changes the available tool/API surface and minimal system instructions, so it is **not** a pure "storage-only" comparison.

B→C is the cleaner early governance ablation: B and C must expose the same ProblemForger tools, graph schema, and instructions. They differ only in deterministic governance/evidence policy.

## Frozen P6 whole-system practical experiment (v1)

This section is the P0 experiment contract for the A/C whole-system comparison.
The experiment identifier is `P6-AC-v1`; it replaces the unpublished A/B/C draft
and is not a continuation of an already-started run.

Changes after implementation begins require an explicit documented amendment before any affected measured run. Never silently replace a task/model/metric after seeing results.

Practical-PoC amendment (2026-09-20): the unpublished draft is replaced before
execution by a direct A/C package comparison. The pilot is intentionally sized for
operational usefulness, not population precision. No selected tasks or live
provider calls are needed to prepare this documentation amendment.

The pilot has three distinct task pools:

- **Smoke pool:** three separate development tasks, one A/C run each. Smoke data
  validates integration, cost accounting, service startup, journaling, and
  evaluator wiring; it never enters the P6 result.
- **Primary pool:** twelve deterministically selected candidates: eight target
  tasks and four predeclared reserves. Preflight may replace a target only with
  the next reserve for a documented patch-independent task/evaluator defect
  discovered before measurement. A transient infrastructure failure never
  activates a reserve.
- **Holdout pool:** eight task-level, repository-family-disjoint identifiers
  reserved for later verifier/calibration work. Holdout images need not be
  materialized for P6 and holdout tasks are never used for smoke or diagnosis.

The primary experiment measures eight eligible tasks, two independent agent runs
per task and configuration, and two configurations (A and C): 32 measured slots
before retries. Each candidate patch still receives the two mandatory evaluator
repetitions, so the run count is not the total operational workload.

### Harness

Primary P6 harness:

- HarnessX
- pinned revision: `bf5f199ee65034d55db0c536e582f1e7c8abf669`

P6 is intentionally single-harness. Pi is used later as an independent portability check rather than mixed into the first causal comparison. A project-level harness comparison is a separate frozen experiment described below; its whole-stack results are never pooled with P6.

<a id="spec-evaluation-model"></a>
<!-- spec-id: EVALUATION.MODEL -->
### Model

The P6 treatment uses one model selected from a predeclared, ordered model chain. The
chain is a frozen artifact (`model-chain-v1`) and is selected once for the complete
A/C experiment, never independently per task, configuration, replicate, or retry.
Before any selected task is exposed, `model-chain-v1` must contain the exact ordered
entries (provider, model identifier, model/API revision or deployment when available,
and all model-call settings) and its SHA-256 must be recorded in the run manifest.
The first entry is the primary model below; every fallback entry must be explicitly
named in that artifact. An unspecified model is never an implicit fallback.

Primary P6 model (the first chain entry):

- provider: Anthropic direct provider supported by HarnessX;
- model: `claude-sonnet-4-6`;
- `extended_thinking=false`;
- `max_tokens=16384` per model response;
- `temperature=0`;
- same provider/model settings for A and C.

The explicit `temperature=0` setting is part of this pinned HarnessX treatment, not an
assumption about other harnesses. Before task exposure, the benchmark adapter must run
a non-task capability probe in the pinned HarnessX environment and verify that the
serialized setting is accepted. Record requested `temperature=0`, acceptance
evidence, and the provider-reported effective value if available; otherwise record
effective value `UNKNOWN`. Acceptance does not prove a hidden implementation or
deterministic output. Lack of an effective-value acknowledgement alone does not
disqualify the model. If the request is rejected or the bounded availability probe
fails under the provider retry policy, this chain entry is
unavailable; do not silently omit the field, emulate it, or infer an undocumented
default. The frozen model-chain rule then selects the next predeclared entry, or
terminates the experiment if no entry remains. Record the probe request, result,
evidence, and environment/configuration hashes in the run manifest.

From chain freeze until the first measured run starts, a model-unavailability event
consumes the next unused chain entry in order, subject to the frozen provider
availability/retry policy. This includes an entry that was selected earlier but
becomes unavailable before measurement. The entry selected when that window closes
is then locked for every A/C run. The same predeclared chain rule also applies after
the task manifest or patch-independent preflight results have been exposed, so
knowledge of the evaluation set cannot affect which fallback is selected. Record the
selected chain index, exact requested provider/model identifier, any exposed revision
metadata, and every exhausted entry in
the run manifest.

If all chain entries are unavailable after task-manifest or preflight exposure and
before the first measured run, terminate the experiment as
`INCOMPLETE_INFRASTRUCTURE` with terminal reason
`MODEL_UNAVAILABLE_AFTER_EXPOSURE`. Preserve the exposed manifest, preflight outputs,
availability attempts, and their raw evidence; report no primary point delta; and
do not edit the manifest or choose an unlisted model. To
continue with another model, create a new experiment version and perform the complete
pre-P6 freeze plus a new blinded task selection without using the exposed manifest or
preflight results to select tasks. If the chain is exhausted before task-manifest
exposure, fail materialization with `MODEL_UNAVAILABLE_BEFORE_EXPOSURE`; expose no
selected task and report no measured result. If the selected model becomes unavailable
after the first measured run starts, do not select a fallback or regenerate an
already-started run; apply the frozen provider/whole-run retry policy to the affected
schedule slots and stop/report the experiment only if that policy's experiment-wide
stop condition is reached. Models are never mixed within one v1 comparison.

<a id="p6-hosted-model-metadata"></a>
#### Hosted model metadata and identity limits

Here, model identity means the selected API entry and observable settings, not
verified access to immutable hosted weights. Record provider/API revision,
deployment/build identifiers, response-version headers, and timestamps when exposed;
use status `UNKNOWN` with value `null/unavailable` when they are not. Hosted model
revision/provider metadata may be `UNKNOWN`; this alone is not a PoC blocker.
Record observed provider-side changes against the affected slots and discuss drift
as a limitation; neither missing metadata nor an incidental response-version change
permits exclusion, replacement, or changing the selected API entry. An intentional
model/settings switch still requires a new experiment version. Do not claim that
one model name or a runtime image hash guarantees identical future inference.

### Separate harness-comparison experiment

`P6-HARNESS-v1` is a separate project-level experiment for comparing complete
harness/provider stacks on the same frozen task manifest. It must be frozen before
any task in that manifest is exposed for the comparison. If the design is created
after P6 outcomes on an already exposed manifest, it is exploratory only; it must
not be presented as a confirmatory comparison, and a confirmatory version requires
a new blinded task selection. Never pool `P6-HARNESS-v1` results with the single-
harness P6 estimate.

The estimand is the whole packaged system, not an isolated CLI feature. Freeze and
record, per harness, the prompts and tool surface, context/compaction behavior,
retry and timeout policy, model/provider/deployment revision, native generation
controls, runtime/dependency identity, and environment. The same model identifier
or nominal effort value is not semantic equivalence across harnesses. Where hidden
reasoning or token caps cannot be observed and enforced identically, do not claim an
equal token budget; match the observable wall-clock and environment constraints and
report the remaining difference as part of the estimand.

Generation controls are adapter-scoped. Freeze the per-harness records as a
content-addressed `generation-policy-v1` artifact before task exposure and record its
hash in the experiment manifest. For every requested control, record the
requested value, status, serialized request (when observable), effective value (only
when the interface reports one), source/evidence, configuration/environment
precedence, and relevant version/configuration hashes. Use these statuses:

- `EXPLICIT(value)` — the control was serialized and the pinned interface accepted
  it; retain acceptance evidence separately from the effective value, which remains
  `UNKNOWN` unless reported by the interface;
- `OMITTED_NATIVE` — the control was intentionally not serialized and native
  behavior was selected; absence from a request is not evidence of a particular
  default, so the effective value remains `UNKNOWN` unless the interface reports it;
- `UNSUPPORTED` — a capability probe or rejected request establishes that the
  requested control is unavailable; do not emulate it with another control;
- `UNKNOWN` — capability or effective behavior cannot be established.

For a harness that does not support `temperature`, request `temperature=0` only in
the capability probe, omit it from measured calls, and record `UNSUPPORTED`; never
record an inferred zero or silently call native defaults equivalent to zero. If the
project deliberately chooses native behavior instead, record `OMITTED_NATIVE` and
keep the effective value unknown unless the runtime reports it. Documentation may
support the record only with a pinned retrieval/version hash; it cannot replace an
observed acceptance check or establish an unobservable effective value. Record an
accepted explicit request with an unknown effective value without rejecting the
stack solely for that uncertainty.

Freeze an interleaved harness/configuration schedule, use the same task-level
repetitions and evaluator contract, and retain adapter-owned native trajectories.
A 2×2 harness-by-A/C design may report whole-stack differences, but it does not
isolate a harness-only causal effect unless all non-harness factors are actually
controlled. An A/B/C harness ablation is a later diagnostic experiment.

### Agent budget

Per valid measured run:

- maximum 60 HarnessX agent steps;
- maximum **semantic wall-clock budget**: 30 minutes;
- no configuration-specific retry allowance;
- provider transport/rate-limit retries follow the frozen infrastructure-retry policy below and do not create extra semantic agent steps.

The 30-minute semantic deadline is enforced identically for A/C:

1. workspace restoration, benchmark/container setup, HarnessX session construction, and (for C) ProblemForger process startup/health checks happen in the **setup phase before** the semantic timer starts; setup uses the separately frozen benchmark-adapter infrastructure timeouts/retry rules;
2. after setup succeeds and the task/prompt is fully rendered, start a monotonic 30-minute timer **immediately before issuing the first model request**;
3. from that instant, all elapsed time consumes the same deadline, including provider request latency, rate-limit/backoff sleeps, provider-call retries, HarnessX processing, ProblemForger graph/service calls, agent-invoked tool/subprocess execution, agent-invoked tests, and any agent/runtime waits;
4. the semantic timer ends when HarnessX reaches a terminal run result or the deadline expires, whichever occurs first;
5. every provider/tool/service operation started during semantic execution must be bounded by the remaining semantic deadline; no new semantic action may start after the deadline;
6. on deadline expiry, terminate/cancel outstanding semantic activity best-effort, freeze the current workspace, and extract the workspace diff. That frozen diff is evaluated normally; the run records exit reason `WALL_CLOCK_EXHAUSTED`. No model/tool action after the deadline may improve the candidate patch;
7. **semantic deadline expiry has precedence over provider retry classification**. If the remaining semantic deadline reaches zero during a provider attempt or retry/backoff interval—including the first model call—the run is `WALL_CLOCK_EXHAUSTED`, is not eligible for whole-run replacement, and follows the frozen-diff evaluation rule above. `INFRA_FIRST_PROVIDER_CALL` applies only when the first-call transport retry budget is exhausted while the semantic deadline still has positive remaining time.

This boundary intentionally gives A/C the same agent-interaction budget rather than
charging C for one-time service startup. ProblemForger calls **during** the
trajectory do consume the 30-minute budget, so graph/governance overhead can affect
task resolution.

Latency reporting remains end-to-end rather than hiding setup cost. Record separately:

- setup latency before the semantic timer;
- semantic-run latency from first model request to terminal/deadline;
- total schedule-slot latency including infrastructure-invalid attempts and clean replacements.

Token usage, billed cost, and all latency components are measured outcomes rather than normalized away. Added graph context/tool calls must pay their actual overhead.

<a id="p6-resource-budget"></a>
### Experiment resource envelope

The per-run limits above remain unchanged. Before any capability probe, required
preflight operation, or task exposure, the operator must
approve and freeze in `benchmark-adapter-v1` a predeclared experiment resource budget:
the finite total elapsed-time limit `experiment_wall_clock_limit_seconds` and the
finite provider-spend guard `experiment_provider_cost_limit_usd`, both positive and
chosen from available resources and separate development runs.
Record and enforce these limits, their accounting method, and
rationale in the manifest; this document
does not invent a universal price or add a separate token-cap tuning exercise.
No capability probe or preflight operation may start the experiment clock before
this budget freeze.

The elapsed limit runs from the first capability probe or required preflight
operation, whichever is earlier, and includes idle time, setup, retries, measured
runs, and evaluator work. All such operations use
finite timeouts bounded by the remaining experiment time as well as any applicable
semantic deadline. The spend guard includes probes, failed/retried requests, and
all A/C work; shared costs are reported separately from per-slot costs. Freeze
the accounting/reservation method and price schedule before exposure: reserve a
conservative estimated charge for an API request before dispatch, reconcile known
usage afterward, and keep an unknown charge reserved rather than treating it as
zero. If no conservative reservation can be made, do not issue that request.
This is an operational estimated-spend guard, not a guarantee of the provider's
final invoice or a claim to include evaluator/container charges.

The experiment coordinator must persist the start-time anchor, derived deadline,
configured limits, current elapsed/spend ledger, and every outstanding provider
spend reservation in a durable experiment record before dispatching work. A
runner restart reopens that same record; it must not reset the elapsed clock,
attempt counters, or release an unknown-charge reservation. In-flight operations
remain reserved until their outcome is reconciled or an explicitly recorded
recovery decision accounts for the uncertainty. Redispatch after a restart is
allowed only when the frozen retry policy permits it and the previous operation's
reservation and outcome are retained.

When another required operation cannot fit the remaining resource envelope, or
the elapsed deadline is reached, stop as `BUDGET_EXHAUSTED` and mark the analysis
`INCOMPLETE_BUDGET` if required work is unfinished. Cancel active work best-effort,
retain its trajectory/workspace/patch and all accrued costs, and record every
unfinished or unstarted required operation. Budget stops do not authorize a clean
replacement, extended retry budget, selective task removal, or primary analysis
with missing outcomes. They take precedence over a pending retry obligation; do
not reopen a budget-stopped experiment by increasing its cap after seeing results.
Any later differently budgeted pilot is a separately versioned, explicitly labeled
experiment, not completion of this comparison.

<a id="spec-evaluation-pre-p6"></a>
<!-- spec-id: EVALUATION.PRE-P6 -->
### Pre-P6 frozen artifacts

Before any task selected by the P6 selector is intentionally identified, inspected, opened, or executed for development/evaluation, the five version-controlled contract artifacts, the model chain, and the complete HarnessX runtime environment must be frozen:

1. **`benchmark-adapter-v1`**
   - exact code/configuration that bridges the pinned SWE-smith task source into the pinned HarnessX runtime;
   - direct loading of dataset `SWE-bench/SWE-smith` at the pinned revision and `train` split;
   - schema normalization/validation, preserving `FAIL_TO_PASS` and `PASS_TO_PASS` as sequences rather than JSON/string lengths;
   - exact task/prompt rendering shared by A/C, including deterministic rendering of failing-test identifiers;
   - exact workspace setup/startup procedure and finite setup/startup timeouts, patch extraction, result serialization, and complete harness-specific raw trajectory capture/serialization shared by A/C;
   - exact evaluator invocation using the SWE-smith dataset/`train` split, plus pinned `swebench` dependency/tooling version and deterministic per-task immutable-image resolution/cache policy;
   - exact infrastructure reason-code classifier, provider-call retry behavior, whole-agent-run replacement behavior, and evaluator retry behavior specified by this document;
   - the approved experiment resource envelope, accounting/reservation method, and resource-stop classification above;
   - the `INFRA_TASK_ARTIFACT` classifier follows the intrinsic-defect and infrastructure-precedence rules in Task-artifact preflight exclusions below;
   - explicit prohibition on inheriting HarnessX's built-in SWE-bench Verified/`test` dataset defaults;
   - no ProblemForger graph/governance behavior;
2. **`graph-intervention-v1`**
   - exact agent-visible ProblemForger tool/API schemas;
   - exact graph-use system/user instruction additions;
   - graph schema/version used by B and C;
   - core schema/version invariants active in both B and C;
   - graph-query defaults, bounds, serialization/context formatting, and mutation operation schema;
   - HarnessX adapter mapping that can affect agent-visible behavior;
   - relevant service/protocol versions;
3. **`governance-policy-v1`**
   - every deterministic check that can affect C;
   - evidence consumed and the exact property each check evaluates;
   - decision precedence;
   - mapping to `COMMIT`, `REJECT`, `RETRY`, or `ESCALATE`;
   - protected-anchor behavior, exceptions, and thresholds;
4. **`graph-metrics-v1`**
   - executable or otherwise exact queries/rules for every **journal-derived** graph/governance metric;
   - the frozen decision reason codes considered a deterministic contradiction/block;
   - the exact edge types/directions and traversal rule used for downstream causal-dependency counts;
   - the evidence methods/scopes that qualify as later contradiction/invalidation;
   - time/version cutoffs, denominators, exclusions, and `UNKNOWN/UNRESOLVED` handling;
   - any adjudication rule for non-machine-classifiable secondary analysis;
5. **`telemetry-metrics-v1`**
   - exact observation schema/fields required for P6 secondary overhead metrics;
   - attribution rules for ProblemForger-added model tokens, tool calls, and latency;
   - provider-cost normalization rules, currency, frozen price schedule/version when API responses do not expose monetary charge directly, and missing-cost handling;
   - clock/latency boundaries and missing-observation handling;
   - aggregation rules and denominators for total end-to-end efficiency metrics and ProblemForger-attributed telemetry metrics.

The following additional frozen artifacts are required before task exposure:

6. **`model-chain-v1`**
   - the finite ordered list defined in the Model section above, including the exact provider/model/revision/settings for every primary and fallback entry;
   - availability probing, selection, exhaustion, and experiment-stop reason codes;
   - the rule that the first available entry is selected once for all A/C runs and cannot be replaced after the first measured run starts.
7. **`harnessx-runtime-v1`**
   - the exact HarnessX source revision above and the platform/architecture on which it runs;
   - the exact interpreter/runtime version and the complete transitive dependency lockfile, including the frozen installation command;
   - a content-addressed OCI image reference (`repository@sha256:<digest>`) or an equivalent immutable runtime archive digest containing the base image, system packages, native tools, and installed dependencies;
   - all runtime configuration that can affect HarnessX behavior, with secrets excluded and secret sources/versioned interfaces identified;
   - a deterministic build/restore procedure that fails rather than resolving mutable tags, floating dependency ranges, or an unverified cache.

All five contract artifacts, `model-chain-v1`, and `harnessx-runtime-v1` must be
content-addressed (for example SHA-256) and their hashes recorded in every P6 run
manifest. Every A/C attempt must execute the recorded runtime image/archive and
resolved lockfile; the HarnessX commit alone is not a sufficient runtime identity.

<a id="p6-runtime-image-identity"></a>
The runtime digest identifies the retained runtime/harness bytes, **not hosted model identity**.
It supports restoring the local stack and checking A/C runtime parity, not exact
future model-output replay. A local model's weights/configuration can be identified
only when those artifacts are also retained and hashed; a hosted provider's exposed
version is recorded as metadata with that provider's stated guarantees. Neither
weight hashing nor provider versioning is mandatory for this hosted-model PoC.
Graph/journal replay and analysis of retained outcomes remain distinct from
rerunning inference, which may differ even with the same observable configuration.

Development of these artifacts must use synthetic fixtures or separate development tasks. The selected P6 primary/reserve and holdout tasks may not be used to tune any of the five contract artifacts, the model chain, or the runtime environment.

Primary graph/governance metrics must be mechanically reproducible from the durable run journal plus the frozen `graph-metrics-v1` artifact. Ambiguous cases that the frozen rule cannot classify are reported as `UNRESOLVED` and are not manually reassigned into primary metric buckets after results are known.

Telemetry-derived secondary metrics must be reproducible from the required P6 telemetry plus `telemetry-metrics-v1`. Telemetry remains outside authoritative graph state; P6 simply requires the configured telemetry capture needed for those secondary measurements.

Any change to one of these artifact hashes after the first measured run creates a new experiment version and requires a complete new A/C comparison. Results with different artifact hashes must not be pooled as one P6-AC estimate.

### Task source

Use a deterministic subset of the public SWE-smith dataset:

- dataset: `SWE-bench/SWE-smith`;
- pinned dataset revision: `ea6d7173829c7ec8fa16c22055699ff2e9188091`;
- split: `train`;
- selection seed namespace: `problemforger-p6-ac-v1`.

SWE-smith provides executable software-engineering tasks with failing/passing tests. It is public training data, so this experiment must **not** be presented as an uncontaminated measurement of frontier coding capability. Its purpose here is paired mechanism comparison under executable ground truth.

The pinned HarnessX commit's built-in SWE-bench runner/evaluator defaults target `princeton-nlp/SWE-bench_Verified` / `test`; they are therefore **not** the P6 benchmark runner. P6 uses the frozen `benchmark-adapter-v1` to feed SWE-smith/`train` tasks into the content-addressed `harnessx-runtime-v1` and to invoke evaluation consistently. The adapter may reuse pinned HarnessX runtime/harness entry points such as `make_swebench_harness`, but it owns dataset loading/evaluation plumbing. The same benchmark adapter hash and runtime hash are mandatory for A, B, and C.

### Deterministic task selection

At the pinned SWE-smith revision, `FAIL_TO_PASS` and `PASS_TO_PASS` are dataset list/sequence fields, not JSON-encoded strings. Selection code must validate that both fields decode/load as sequences of test identifiers before applying count filters; if the pinned schema does not match this expectation, materialization must fail rather than reinterpret string length as test count.

For every formula below written as `SHA256(text)`, `text` means the exact
concatenation shown, encoded as UTF-8 bytes with no Unicode normalization.
The `\0` separator is one zero byte (`0x00`). `instance_id` is serialized as
its exact validated string, `replicate` as unpadded ASCII decimal (`1` or `2`),
and `config` as one ASCII letter (`A` or `C`). This rule applies to
the task-rank and execution-order keys below. Hashes of binary artifacts, such
as `sha256(candidate_patch_bytes)`, operate directly on the specified bytes.

The selector also validates the repository field before candidate filtering. Every row in the pinned split must have `repo` as a string in the exact structural form `<owner>/<repository>`:

- exactly one `/`;
- non-empty owner and repository components;
- no leading/trailing whitespace in the field or either component;
- no whitespace within either component;
- the repository component before its first `.` must be non-empty.

If any row violates this repository schema, materialization fails with a schema error rather than excluding/grouping the row differently across implementations.

Build the candidate set from the pinned snapshot using rows satisfying all of:

- non-empty `instance_id`;
- non-empty `problem_statement`;
- non-empty `image_name`;
- valid `repo` under the repository schema above;
- `1 <= len(FAIL_TO_PASS) <= 20`;
- `1 <= len(PASS_TO_PASS) <= 200`;
- `len(problem_statement) <= 12000` characters.

Define a repository family deterministically from the validated `repo`: take the repository component after the single slash, then take the non-empty prefix before its first dot (or the full repository component if no dot exists). This groups multiple SWE-smith snapshots of the same upstream repository family.

For every candidate compute:

```text
 rank = SHA256("problemforger-p6-ac-v1\0" + instance_id)
```

Sort ascending by the tuple `(rank, instance_id)` so even a theoretical hash collision has a deterministic tie-break.

Select the candidate pools with two explicit scans:

1. **Primary/reserve scan**
   - scan the sorted candidate list from the beginning;
   - select a candidate if its repository family currently has fewer than 2
     selected primary/reserve tasks;
   - otherwise skip it for the primary/reserve pool;
   - stop after selecting 12 candidates: eight targets followed by four
     predeclared reserves;
   - record the set of repository families represented in the pool.

2. **Holdout scan**
   - start a fresh scan from the beginning of the same sorted candidate list;
   - exclude every primary/reserve candidate;
   - exclude every candidate whose repository family appears in the
     primary/reserve pool, making the holdout repository-family-disjoint from it;
   - maintain a new holdout-only family counter, reset to zero at the start of this scan;
   - select a candidate if its holdout family count is below 2;
   - stop after selecting 8 holdout tasks.

Candidates skipped by the primary/reserve family cap are therefore reconsidered by
the holdout scan only if their repository family is not represented in the
primary/reserve pool; in practice, any candidate from a represented family remains
excluded from holdout.

Materialization must fail rather than silently relax these rules if fewer than 12
primary/reserve or 8 holdout candidates can be selected. The holdout identifiers
are recorded for later use, but their images are not materialized for P6.

Only after `benchmark-adapter-v1`, `graph-intervention-v1`, `governance-policy-v1`,
`graph-metrics-v1`, and `telemetry-metrics-v1` are frozen, materialize the twelve
primary/reserve IDs into a version-controlled manifest and record its SHA-256. The
selector above is frozen; materialization is not an opportunity to hand-pick tasks.

For **every** materialized primary/reserve task, resolve its dataset `image_name`
to an immutable content identity **before preflight**:

- preferred form: the platform-specific OCI image manifest reference `repository@sha256:<digest>` for the frozen execution platform;
- acceptable alternative: an archived/mirrored image artifact addressed and verified by a cryptographic content digest, with the restore procedure frozen in `benchmark-adapter-v1`;
- mutable tags/names alone are never execution identities.

The task manifest records the original `image_name`, execution platform, immutable
digest/content identity, and content-addressed mirror/cache reference where used.
Materialization must fail if any primary/reserve task cannot be resolved and
verified to an immutable execution identity. Holdout images are resolved only when
that later holdout experiment is materialized.

A materialization-time image resolution failure prevents manifest creation and
does not enter preflight or consume a required evaluator repetition. Retain selected
IDs and resolution diagnostics as incomplete materialization artifacts, not a valid
experiment manifest; do not silently skip or backfill the task. Publish/freeze the
final manifest and its hash only after every selected image has a verified,
recorded immutable identity.

All preflight evaluations, A/C measured runs, repeated candidate evaluations, and later reserved-holdout use must execute the recorded immutable identity, never re-resolve the original mutable tag. If the immutable content later becomes unavailable, treat that as infrastructure unavailability; do not fall back to a mutable tag or newly resolved image.

Before that freeze, do not intentionally derive/open/run the selected primary or holdout task IDs for development. After materialization, do not inspect gold patches when deciding inclusion beyond fields listed above.

### Repetitions, run isolation, and execution ordering

For P6-AC:

- the primary/reserve pool contains eight target tasks and four predeclared
  reserves;
- preflight selects the first eight eligible tasks in deterministic pool order;
- two independent runs per task per configuration;
- 16 task-runs per configuration and 32 measured runs total before retries;
- if fewer than eight tasks are eligible after the allowed pre-measurement
  replacements, classify the experiment as `INCOMPLETE_TASK_POOL` and do not
  start measured execution.

Every measured **agent run** is isolated. Experiment orchestration uses identifiers that are independent of ProblemForger:

- every frozen schedule slot has an `experiment_run_id`;
- every whole-run attempt for that slot has a distinct `attempt_id`;
- A/C all use those orchestration identifiers for raw-data linkage.

Before starting an agent-run attempt:

- restore the exact pinned pristine task repository state in a fresh writable workspace/container layer;
- start a new HarnessX agent/session with no conversation, scratchpad, tool state, or mutable workspace inherited from any prior run;
- for **C only**, start/use ProblemForger and allocate a distinct ProblemForger `run_id` backed by an empty durable journal for that attempt;
- for **A**, do **not** start ProblemForger, allocate a ProblemForger run, or create a ProblemForger journal; baseline bookkeeping remains solely in the experiment runner/benchmark adapter;
- do not import graph state, proposal history, telemetry state, candidate patches, or mutable benchmark-runner state from another configuration/replicate/attempt;
- immutable base images and read-only dependency/download caches may be reused only if they cannot carry task-generated mutable state into the run.

If C receives a clean whole-run replacement under the frozen retry policy, the replacement gets a new `attempt_id` and a new empty ProblemForger `run_id`/journal; it never reuses the failed attempt's ProblemForger state.

Immediately before the first model request, the frozen benchmark adapter performs a **pre-semantic reset validation**. At minimum it verifies:

- the writable task workspace is at the expected pristine base state and contains no state inherited from another attempt;
- the HarnessX session has no prior conversation/scratchpad/tool state and is bound to the current `attempt_id`;
- configuration A has no ProblemForger process/run/journal;
- configuration C has the current attempt's newly allocated ProblemForger `run_id` with an empty journal / initial graph state;
- no writable cache, overlay, temporary directory, or benchmark-runner state reused by the attempt contains task-generated mutable state from another run.

A reset-validation failure terminates the attempt **before any model request is issued** with reason `INFRA_RESET_VALIDATION`. It is eligible for clean replacement only under the frozen whole-agent-run replacement policy and therefore consumes the same maximum-attempt budget as every other retryable pre-semantic infrastructure failure.

After the first semantic model response is accepted, reset/isolation concerns can never authorize regeneration of that trajectory. If later audit evidence demonstrates that a measured attempt actually violated the reset contract despite passing pre-semantic validation, classify the experiment `INVALID_EXPERIMENT_STATE`, stop launching new measured schedule slots, preserve all affected artifacts, and report no primary point delta. Do not discard and regenerate the affected measured trajectory.

Execution order is also frozen mechanically. Define the ordering seed namespace exactly as:

```text
problemforger-p6-ac-order-v1
```

After patch-independent preflight exclusions are known, but **before the first measured agent run**, materialize the complete schedule for the remaining common task set:

1. for every `(instance_id, replicate)` block, where `replicate ∈ {1,2}`, compute
   ```text
   block_key = SHA256("problemforger-p6-ac-order-v1\0block\0" + instance_id + "\0" + replicate)
   ```
2. sort blocks by `(block_key, instance_id, replicate)`;
3. within each block, for each `config ∈ {A,C}`, compute
   ```text
   config_key = SHA256("problemforger-p6-ac-order-v1\0config\0" + instance_id + "\0" + replicate + "\0" + config)
   ```
4. sort A/C by `(config_key, config)` and execute those two measured runs consecutively in that order;
5. concatenate all sorted blocks to form the global schedule.

Write the complete schedule to a version-controlled or immutable run artifact and record its SHA-256 before execution starts. Do not reorder around provider performance, failures, or observed task outcomes; infrastructure retries retain the original schedule slot identity and are explicitly linked to it.

A provider-side random seed is not assumed available.

### End-to-end ground truth

A measured run is **resolved** only when both mandatory fresh-environment evaluations of its exact candidate patch produce an identical full required-test vector and that vector has all required `FAIL_TO_PASS` tests passing and all required `PASS_TO_PASS` tests remaining passing. Any candidate-vector disagreement is `PATCH_UNSTABLE` and counts as unresolved/failure.

The model/agent is not shown the gold patch or hidden evaluator result during execution.

### Primary outcomes

Primary estimates require a completed common schedule with all required binary
outcomes and no invalid/incomplete analysis flag. Follow
[Operational reporting of incomplete experiments](#p6-incomplete-reporting)
when required infrastructure work is missing. The task-level report below describes observed paired
task effects; it does not separately quantify hidden provider drift or the
uncertainty of future executions on the same tasks.

Predeclare one paired comparison:

1. **C - A:** change in complete-system task resolution rate when adding the
   ProblemForger graph and deterministic governance package.

For each retained task `i` and configuration `X ∈ {A,C}`, compute:

```text
r_i(X) = mean of the 2 binary resolved indicators for task i under X
d_i(C-A) = r_i(C) - r_i(A)
```

The primary point estimate is the arithmetic mean of `d_i(C-A)` across the eight
retained tasks, expressed in percentage points. With 16 slots per configuration,
one additional resolved slot changes the aggregate by 6.25 percentage points.
This is an observed pilot delta, not a confidence interval, significance test, or
estimate of performance on a wider task population.

Let `N` be the number of eligible tasks after preflight and reserve selection.
P6-AC requires `N = 8`; a smaller value is `INCOMPLETE_TASK_POOL`, not a smaller
version of the same experiment.

Report at minimum:

- every raw run/evaluator outcome;
- per-task A and C resolution rates and `d_i(C-A)`;
- the number of tasks improved, worsened, and tied under C;
- C-A point delta and the two replicate-specific deltas;
- provider cost, setup/semantic/end-to-end latency, agent steps, tool calls,
  human intervention, and failure reasons;
- direct graph/governance overhead separately from the total C-A difference.

If fewer than eight tasks are eligible after preflight and the allowed reserve
selection, classify the experiment as `INCOMPLETE_TASK_POOL`, preserve the partial
report, and do not compute a primary delta. A missing infrastructure slot or
evaluator repetition is handled by the incomplete-reporting contract below; it is
not silently scored as success or failure.

### Practical continuation decision

Before task exposure, record the operational tolerances for cost, latency, and
human intervention. The human decision is one of:

- `CONTINUE`: C shows useful local improvement or reduced failure without a
  critical regression, and its operational overhead is acceptable;
- `ADAPT`: there is no critical regression, but the observed benefit, overhead, or
  failure pattern requires a design change before broader use;
- `STOP`: a critical correctness, isolation, security, or operational regression
  makes the package unsuitable for the tested workflow.

These labels summarize the observed workflow decision. They are not a statistical
gate and do not automatically start P7. No universal cost, latency, or benefit
threshold can be deduced from the current plan; the chosen tolerances must be
recorded before exposure and cannot be tuned after seeing outcomes.

### Practical sensitivity report

`temperature=0` (when supported) does not make an end-to-end trajectory
deterministic. The two fresh repetitions are retained to expose operational
variation, not to support a population-level uncertainty claim.

For `k ∈ {1,2}`, remove repetition `k` from both configurations, recompute the
single-repetition C-A delta, and report both leave-one-repetition-out estimates.
Define `SENSITIVITY_DISCORDANT` when either estimate changes the sign or the
predeclared practical band relative to the full two-repetition point estimate.
Use `delta = 10` percentage points only as a descriptive band boundary; it does
not block the local operational decision or automatically trigger P7. Report
`max_abs_deviation_pp` and both individual repetition deltas. A positive claim
about broad generalization requires a new blinded replication, but a discordant
pilot can still inform local debugging or adoption decisions.

No bootstrap, p-value, confidence interval, equivalence label, or automatic
`ADVANCE_P7` rule is part of P6-AC. A/B/C ablation attribution, if needed, is a
new diagnostic experiment with its own frozen manifest and analysis.

### Secondary end-to-end metrics

Report:

- input/output/cache tokens where provider reports them;
- provider cost;
- wall-clock latency;
- agent steps;
- tool calls;
- provider cost per resolved schedule slot;
- end-to-end elapsed seconds per resolved schedule slot.

The two per-resolution efficiency aggregates are frozen as follows for each configuration `X` over the complete common retained task set and both repetitions:

```text
resolved_slots_X =
    count of schedule slots for X whose frozen binary outcome is resolved

total_provider_cost_usd_X =
    sum of billable model-provider cost across every provider request attempt
    belonging to every whole-run attempt attached to those X schedule slots,
    including provider-call retries and infrastructure-invalid/replaced attempts

provider_cost_per_resolved_slot_X =
    total_provider_cost_usd_X / resolved_slots_X

total_elapsed_seconds_X =
    sum of end-to-end schedule-slot elapsed time for those X slots,
    including setup, infrastructure-invalid attempts, replacement attempts,
    and the final measured attempt

elapsed_seconds_per_resolved_slot_X =
    total_elapsed_seconds_X / resolved_slots_X
```

Cost unit is USD. If the provider/API exposes an exact monetary charge for a request, use it. Otherwise compute cost from recorded billable usage using the currency/rates and cache-token rules frozen in `telemetry-metrics-v1` before task exposure. A request contributes zero cost only when the provider evidence establishes zero billable usage; unknown billable usage makes the affected monetary aggregate unavailable rather than silently zero.

Infrastructure-invalid/replaced attempts are included because they are real operational cost/latency attributable to that configuration's scheduled work. Benchmark evaluator/container compute is not included in `total_provider_cost_usd_X`; it is retained separately as evaluation infrastructure.

If `resolved_slots_X = 0`, both per-resolved-slot ratios are **undefined/NA**, not zero or infinity; report the numerator and zero denominator explicitly. If the experiment has any invalid/incomplete analysis flag, retain/report accrued raw cost/latency but do not report cross-configuration per-resolution aggregates. A complete-looking subset cannot override an experiment-wide stop.

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
- pinned HarnessX runtime/harness behavior at the declared revision;
- frozen `benchmark-adapter-v1` for SWE-smith task loading, task rendering, workspace setup, patch extraction, and evaluator invocation;
- no ProblemForger graph tools/instructions.

C:
- exactly the same pinned HarnessX runtime and frozen `benchmark-adapter-v1` as A;
- adds exactly the agent-visible surface captured by frozen `graph-intervention-v1`;
- durable run journal + event-sourced graph;
- deterministic mutation governance from frozen `governance-policy-v1`.

B remains a later diagnostic configuration: it uses the same graph surface as C
with governance disabled, but is not part of P6-AC and cannot be added after
seeing P6 outcomes without a new experiment version.

The benchmark adapter is experimental plumbing, not the treatment. Any adapter behavior that can influence the task prompt, workspace state, patch extraction, or evaluator result must therefore be identical across A/C and frozen before selected P6 tasks are exposed.

### Intervention freeze and parity

The P0 document freezes the experiment envelope, not implementation details that do not yet exist. P2/P3/P4 may develop the graph surface and deterministic policy on synthetic/separate development tasks, but the five pre-P6 contract artifacts, `model-chain-v1`, and `harnessx-runtime-v1` must be frozen **before** the selected P6 tasks are exposed.

Within P6-AC, the only intentional A→C difference is the complete ProblemForger
package defined by `graph-intervention-v1` and `governance-policy-v1`. A later B/C
diagnostic must freeze the same `graph-intervention-v1` hash and differ only in
governance activation.

Any other benchmark-adapter, prompt, tool, memory, sandbox, model setting, graph-surface artifact, governance-policy artifact, or primary metric-rule difference invalidates the intended comparison and must be documented as a new experiment version.

## Frozen infrastructure retry policy

Retry eligibility is mechanical and identical for A/C. Operators must not decide after observing a run whether to discard and repeat it.

### Definitions

A **schedule slot** is one frozen `(instance_id, replicate, configuration)` entry.

A **semantic model response** is the first provider response for that run that HarnessX accepts into agent state as assistant content and/or a tool call. Once such a response exists, the measured agent execution has begun semantically.

The frozen `benchmark-adapter-v1` emits machine-readable infrastructure reason codes. Only the reason codes explicitly listed below can authorize retries.

<a id="p6-incomplete-reporting"></a>
### Operational reporting of incomplete experiments

Exhausting all 3 eligible pre-semantic whole-run attempts or all 3 attempts for a
required evaluator repetition is a **hard experiment-wide stop**:
`INCOMPLETE_INFRASTRUCTURE`. Stop launching measured schedule slots and required
evaluations; do not resume this experiment, reset counters, or add a fourth attempt.
Retain the missing slot/repetition as `MISSING_INFRASTRUCTURE`, separately from
observed agent failures. If preflight exhausted its budget, eligibility is unknown;
do not exclude that task to finalize a smaller common set. No task, configuration,
replicate, or accepted semantic trajectory may be selectively replaced.

The operationally useful result of a stopped pilot is an auditable partial report,
not continued measurement under a relaxed contract. Preserve raw/descriptive
evidence but withhold the complete primary point delta.
Offline inspection of retained artifacts for debugging is allowed. Any later
diagnostic executions are separately labeled and cannot fill missing primary slots,
clear the stop, or change an observed outcome. A future measured pilot requires a
new predeclared experiment version; never pool it with this incomplete comparison.

An incomplete report retains every planned slot (or selected task if preflight
never completed), its observed outcomes, missing/not-started status and reason,
all attempts, and accrued costs/latency. Show coverage by task, configuration, and
replicate with planned and observed counts. Individual observed successes/failures
and their traces may inform debugging; they are not a complete paired comparison.
Do not run the primary estimator, continuation labels, or
complete-data sensitivity analyses on a favorable complete-case subset; do not
impute missing infrastructure outcomes as zero or replace the two-run denominator
with the number observed. No primary point delta is reported for the incomplete
experiment. Keep post-semantic `RUN_INTERRUPTED`,
`EVALUATION_INCOMPLETE`, and other defined agent/system failures as unresolved
binary outcomes when their contract supplies that classification; missing
pre-test infrastructure evidence is a different state.

### Provider-call transport retries

For each individual model call, including calls after semantic execution has begun:

- maximum 3 transport attempts total: the initial attempt plus at most 2 retries;
- retry only when **no semantic response was produced** and the attempt ends in one of:
  - connection/DNS/TLS failure before an HTTP response;
  - transport/read timeout before a semantic response;
  - HTTP 408;
  - HTTP 429;
  - HTTP 500–599;
- do not retry semantic/API validation failures, malformed provider responses that do not produce an accepted semantic response, content/tool behavior, or ordinary 4xx responses other than 408/429;
- all transport attempts and reason codes are retained in raw telemetry.

A nonretryable provider failure that occurs **before the run has accepted its first semantic model response** terminates the schedule slot as `PRE_SEMANTIC_PROVIDER_FAILURE`, is scored unresolved, and is **not** eligible for whole-run replacement. This includes API/request validation failures, malformed provider responses not accepted into agent state, and ordinary nonretryable 4xx responses. The specific provider/error code remains in raw data.

Exhausting the transport budget on the **first** model call without any semantic response terminates the attempt as `INFRA_FIRST_PROVIDER_CALL` and is eligible for whole-run replacement under the fixed attempt budget **only if the semantic deadline still has positive remaining time**. If the semantic deadline reaches zero first or simultaneously, `WALL_CLOCK_EXHAUSTED` takes precedence and no whole-run replacement is allowed. Exhausting a later model call's transport budget after semantic execution has begun terminates the slot as unresolved `RUN_INTERRUPTED`, unless semantic deadline expiry caused/preceded that termination, in which case `WALL_CLOCK_EXHAUSTED` takes precedence.

### Whole-agent-run replacement

A failed agent-run attempt is eligible for a clean whole-run replacement **only if no semantic model response has yet been accepted** and the attempt terminates with one of these frozen pre-semantic reason classes:

- `INFRA_WORKSPACE_SETUP` — failure creating/restoring the pristine workspace before task delivery;
- `INFRA_CONTAINER_START` — benchmark/container runtime image pull/create/start failure before task delivery;
- `INFRA_HARNESS_START` — HarnessX process/session startup failure before task delivery;
- `INFRA_PROBLEMFORGER_START` — C ProblemForger process or health-check startup failure before task delivery;
- `INFRA_RESET_VALIDATION` — the mandatory pre-semantic clean-state/reset validation failed before the first model request;
- `INFRA_FIRST_PROVIDER_CALL` — the first model call exhausted the provider-call transport budget without producing a semantic response.

Each schedule slot has **at most 3 whole-run attempts total**: one initial attempt plus at most 2 clean replacements. Every replacement must satisfy the same clean-state isolation contract and retains the same schedule-slot identity; prior invalid attempts remain in raw data.
Every eligible pre-semantic failure requires the next clean replacement while one
of the two replacement attempts remains; the runner must not voluntarily stop.
The runner must continue this sequence until an attempt succeeds, terminates
nonretryably, or all 3 attempts are exhausted. A failure made nonretryable by
the semantic-deadline precedence rule above does not consume a replacement.

If all 3 attempts fail with eligible pre-semantic infrastructure reasons, classify the experiment `INCOMPLETE_INFRASTRUCTURE`, stop launching new measured schedule slots, and report no primary point estimate. Do not substitute another task, replicate, or configuration.

After the first semantic model response has been accepted, **no whole-agent-run replacement is allowed**. If the run later terminates because provider retries are exhausted, a tool/container/process fails, or another runtime error occurs, the slot is scored unresolved with a frozen terminal reason such as `RUN_INTERRUPTED`. This prevents selective regeneration of an already-started trajectory.

The following are always agent/system outcomes rather than whole-run retry triggers once semantic execution has begun: max-step exhaustion, no patch, invalid patch, `CANDIDATE_PATCH_INVALID`, malformed tool use, non-zero exit from an agent-invoked command, agent-invoked command timeout, test failure, and ProblemForger/tool errors returned during the trajectory. The other mandatory evaluator repetition still runs in a separate fresh environment unless an experiment-wide stop applies.

### Evaluator infrastructure retries

Evaluator retries never regenerate the candidate patch or agent trajectory.

For each required control/candidate evaluation repetition:

- maximum 3 evaluator attempts total;
- retry only if no required-test vector was produced and the frozen benchmark adapter reports a pre-test infrastructure reason:
  - `EVAL_IMAGE_SETUP`;
  - `EVAL_CONTAINER_START`;
  - `EVAL_EVALUATOR_START`;
- once candidate/control repository tests have started executing, evaluator/test failure is not retrospectively reclassified as retryable infrastructure merely because no valid vector was produced;
- if a **control/preflight** evaluation has started repository tests and terminates without a complete required-test vector, classify that candidate `EVALUATOR_INVALID`; this is a patch-independent preflight exclusion, is not retried, and may activate the next predeclared reserve;
- if a **measured candidate-patch** evaluation has started repository tests and terminates without a complete required-test vector, record that evaluation repetition as `EVALUATION_INCOMPLETE`; the measured run is unresolved regardless of its other evaluator repetition, and the missing-vector repetition is never retried;
- if the canonical candidate patch is absent, malformed, or cannot be applied before repository tests start, record `CANDIDATE_PATCH_INVALID` for that evaluator repetition with the exact patch digest and application error; this is a nonretryable agent/system outcome, is not eligible for whole-run replacement, and scores the measured run unresolved rather than being reclassified as evaluator infrastructure failure;
- after such a measured missing-vector outcome, continue with the other mandatory evaluator repetition in a separate fresh environment. It must not be skipped merely because the first repetition is already unresolved; the only exception is an experiment-wide stop already required by this policy (for example, `INCOMPLETE_INFRASTRUCTURE`, `BUDGET_EXHAUSTED`, or `INVALID_EXPERIMENT_STATE`);
- if the 3-attempt pre-test evaluator infrastructure budget is exhausted for any required evaluation, classify the experiment `INCOMPLETE_INFRASTRUCTURE`, stop measured execution, retain all raw attempts, and report no primary point delta.

Infrastructure-invalid attempts are reported separately from valid agent outcomes in cost/latency accounting; they are never silently deleted.

Evaluator/task stability and candidate-patch stability are handled separately below so an agent-produced flaky patch cannot remove an unfavorable task from the paired analysis.

<a id="spec-evaluation-preflight"></a>
<!-- spec-id: EVALUATION.PREFLIGHT -->
### Task/evaluator preflight

Before any measured A/C agent run for a selected primary task:

1. evaluate the task's **unmodified pinned repository state** twice in separate fresh instances of the same pinned environment, subject to the frozen evaluator policy above;
2. if either required control evaluation starts repository tests but terminates without a complete required-test vector, classify the candidate `EVALUATOR_INVALID` and stop that candidate's preflight; do not retry or hand-adjudicate it, and continue with the next predeclared candidate;
3. otherwise compare the two full required-test outcome vectors (the pass/fail result for every required `FAIL_TO_PASS` and `PASS_TO_PASS` test);
4. both control vectors must be identical **and** match the benchmark's expected baseline contract:
   - every required `FAIL_TO_PASS` test is failing;
   - every required `PASS_TO_PASS` test is passing;
5. if the two complete vectors differ, classify the candidate as `EVALUATOR_UNSTABLE` immediately; no third control is required and no later result can restore eligibility;
6. if the two complete vectors agree but do not match the expected baseline contract, classify the candidate as `BASELINE_INVALID`;
7. otherwise the candidate is eligible for the common A/C task set.

Any additional control evaluation is diagnostic only and runs after the primary experiment terminates. Its result, missing vector, or infrastructure retry exhaustion cannot change the task's primary classification and cannot abort the experiment. Retain diagnostic attempts separately from required preflight attempts and measured schedule-slot cost/latency. This restriction prevents a redundant third control from adding an experiment-wide failure path or changing the measured execution schedule.

The following decision table is normative. The required-evaluation retry policy takes precedence before a complete vector exists; the rows for complete vectors are mutually exclusive.

| Required control evaluations | Task/experiment result | Additional required controls |
| --- | --- | --- |
| Pre-test infrastructure budget exhausted | `INCOMPLETE_INFRASTRUCTURE`; eligibility unknown, no measured runs | None for this task |
| Tests started but a complete vector is missing | `EVALUATOR_INVALID` (candidate) | Continue with next predeclared candidate |
| Two complete vectors disagree | `EVALUATOR_UNSTABLE` (candidate) | Continue with next predeclared candidate |
| Two complete vectors agree but violate the baseline | `BASELINE_INVALID` (candidate) | Continue with next predeclared candidate |
| Two complete vectors agree and match the baseline | Eligible task | None |

`EVALUATOR_INVALID`, `EVALUATOR_UNSTABLE`, and `BASELINE_INVALID` are
patch-independent preflight exclusions applied **before measured agent runs begin**.
Do not retry or hand-adjudicate the excluded candidate. Preserve/report all
preflight evaluator outputs and the exclusion reason, then continue with the next
predeclared primary/reserve candidate. A reserve may be activated only for this
documented pre-measurement defect, never for an observed agent outcome or a
transient infrastructure failure.

### Task-artifact preflight exclusions

The frozen benchmark adapter may additionally emit `INFRA_TASK_ARTIFACT` only during
configuration-neutral, patch-independent preflight, before the eligible-task count
`N` is computed and before
the measured schedule is hashed. This reason requires an intrinsic defect in
successfully retrieved, digest-verified task content: a required input within that
content is missing, corrupt, or schema-incompatible before any model execution.
Unavailable image content takes precedence over `INFRA_TASK_ARTIFACT`: a missing
mirror/cache object, inaccessible immutable image, or transport/storage corruption
that prevents digest verification follows `EVAL_IMAGE_SETUP` during preflight, with
the existing evaluator retry budget and experiment-wide stop on exhaustion. These
failures do not activate a reserve; inability to retrieve
verified content is not evidence of an intrinsic defect.
This rule applies **after materialization** established the recorded immutable
identity: later retrieval/setup failure is `EVAL_IMAGE_SETUP` and does not change `N`.
It does not reclassify materialization-time image resolution as evaluator work.
Network/image-pull failures, runtime or harness startup failures,
provider failures, and resource exhaustion are transient/shared infrastructure and
must not be relabeled as task invalidity.

An `INFRA_TASK_ARTIFACT` exclusion removes that candidate from the primary/reserve
pool before measurement. Retain the raw artifact, classifier output, and evidence
digest, then continue with the next predeclared reserve. This replacement is
allowed only while the common task set is being frozen; operators may not add,
remove, or reinterpret a task after the first measured slot starts or after
observing outcomes. If fewer than eight eligible tasks remain, apply the
`INCOMPLETE_TASK_POOL` stop before measured runs begin.

If immutable task invalidity is discovered late, its scope is disputed, or the cause
is unknown/mixed, classify the experiment `INCOMPLETE_INFRASTRUCTURE`, stop before
launching another measured slot, preserve all artifacts, and report no primary
point delta. A post-semantic failure that is not task-artifact
invalidity remains an unresolved schedule slot; it does not exclude the task or
authorize regeneration. Repeated generic pre-semantic failures in one schedule slot
therefore retain the experiment-level stop rule; they do not establish immutable
task invalidity.

<a id="spec-evaluation-measured-evaluation"></a>
<!-- spec-id: EVALUATION.MEASURED-EVALUATION -->
### Measured candidate patches

For **every measured candidate patch**, regardless of its first outcome:

1. execute the two mandatory evaluator repetitions in separate fresh instances of the pinned environment, subject to the frozen evaluator policy above;
2. if either repetition starts repository tests but terminates without a complete required-test vector, classify the candidate/run `EVALUATION_INCOMPLETE` and score it unresolved; still execute and retain the other mandatory repetition in its separate fresh environment unless an experiment-wide stop has already been triggered. That repetition cannot rescue the primary classification, but it remains mandatory raw evidence;
3. only when both repetitions produced complete vectors, compare the full required-test outcome vectors;
4. the run is scored **resolved** only if both complete vectors are identical and satisfy the end-to-end resolution criterion;
5. if both vectors are complete but differ, classify that candidate/run as `PATCH_UNSTABLE` and score the run as unresolved/failure; do **not** exclude the task or any paired runs.

Pre-test infrastructure exhaustion is not the missing-vector-after-tests outcome
in step 2: it leaves `MISSING_INFRASTRUCTURE` under the retry policy even if the
other repetition completed. Preserve that observed vector, but it cannot fill the
missing repetition. A resource stop similarly leaves unfinished required evidence
explicitly missing. Neither case permits a primary result for an incomplete schedule.

A third candidate-patch evaluation may be retained as diagnostic data only when both mandatory evaluations produced complete vectors; it cannot change the frozen primary classification above.

Evaluator attempts follow the frozen infrastructure-retry budget above. Retryable pre-test infrastructure failure does not by itself trigger task exclusion or `PATCH_UNSTABLE`; exhaustion makes the experiment `INCOMPLETE_INFRASTRUCTURE` rather than allowing post-hoc task replacement. All primary paired comparisons use the same common task set fixed after preflight task/evaluator exclusions.

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
- native harness/provider generation defaults and unsupported controls;
- trajectory nondeterminism and prompt sensitivity despite deterministic sampling controls;
- provider or benchmark infrastructure failures;
- cherry-picking peak runs.

## Raw data and reproducibility

Record enough structured data to reconstruct each reported result and audit every
attempt from retained evidence. Re-evaluating a retained patch in the recorded
environment is distinct from regenerating the original model trajectory; exact
hosted-inference replay is not promised.

For every schedule slot and every whole-run attempt, retain:

- `experiment_run_id`, `attempt_id`, task/configuration/replicate, and attempt ordinal/status;
- repository/base commit and immutable benchmark image/content identity;
- effective redacted configuration;
- harness version/commit;
- provider/model identifier and relevant settings;
- requested/effective generation controls with `EXPLICIT`, `OMITTED_NATIVE`, `UNSUPPORTED`, or `UNKNOWN` status, capability/effective-value evidence, and configuration/environment precedence;
- `model-chain-v1` hash, selected chain index, exact selected provider/model API identifier and exposed revision metadata, and every exhausted chain entry;
- `harnessx-runtime-v1` hash, runtime image/archive digest, dependency-lockfile hash, interpreter/runtime version, and execution platform/architecture;
- provider/API/model revision, deployment/build identifier, response-version header, or equivalent version metadata when exposed by the provider; record explicit `null/unavailable` when the provider exposes none;
- absolute UTC timestamps in RFC 3339 form for `attempt_started_at`, `semantic_started_at` (null if no first request was issued), and `attempt_ended_at`;
- task-manifest hash and execution-schedule artifact/hash;
- event/protocol schema versions;
- for C, the ProblemForger `run_id` and full durable run journal for that attempt; for A, an explicit `problemforger_run_id = null` / no-journal marker;
- `benchmark-adapter-v1`, `graph-intervention-v1`, `governance-policy-v1`, `graph-metrics-v1`, and `telemetry-metrics-v1` hashes;
- required **normalized harness-independent observation/telemetry** needed for non-authoritative usage/latency metrics;
- a **complete per-attempt raw harness trajectory artifact**, captured and owned by the harness/evaluation adapter, stored immutably/content-addressed with its schema version and SHA-256;
- for HarnessX P6 runs, that raw trajectory must preserve in execution order:
  - HarnessX step index and event type;
  - the complete semantic model request content visible to the model, including system/user/assistant/tool-context messages and effective model-call settings;
  - every provider response or response fragment that HarnessX accepted into agent state, with exact assistant/tool-call content;
  - every agent-issued tool/subprocess call and its arguments;
  - every tool/subprocess result returned to the agent, including stdout/stderr/exit status or structured error;
  - ProblemForger client requests/responses for C as seen by the adapter;
  - pre-semantic reset-validation result/reason plus retry/transport attempt reason codes and whether each model attempt produced a semantic response;
  - monotonic offsets from semantic-timer start for model request start/end, retry/backoff intervals, tool start/end, ProblemForger calls, HarnessX step transitions, and terminal/deadline event, anchored to the recorded absolute `semantic_started_at` timestamp;
  - terminal reason and observed step count;
- the **exact candidate patch bytes submitted to evaluation**, stored as an immutable artifact, plus `sha256(candidate_patch_bytes)`;
- if the attempt terminates before producing/submitting a patch, record an explicit no-candidate status and the SHA-256 of the canonical empty byte string rather than omitting the field;
- where workspace creation succeeded, retain a frozen final-workspace-diff artifact (or equivalent content-addressed workspace snapshot) and its SHA-256 so patch extraction can be audited independently;
- every evaluator attempt/output linked to the exact candidate-patch SHA-256 it evaluated.

At experiment level, also retain the approved resource envelope and usage ledger,
stop reasons and timestamps, persistent retry counters,
analysis-eligibility flags, planned-versus-observed coverage, and the computed pilot
labels separately from any human progression decision. A slot never launched has
an explicit `NOT_STARTED` record and reason, not a fabricated attempt or empty patch.

The benchmark adapter must define one canonical candidate-patch byte representation. The exact retained bytes—not a regenerated diff—are the bytes passed to every repeated evaluator invocation for that measured run. A repeated evaluator result is invalid if its recorded patch digest does not exactly match the run's canonical candidate-patch digest.

Raw trajectory artifacts are deliberately **outside the ProblemForger core contract**:

- ProblemForger core types, ProblemGraph, GraphGovernor, EventStore, and the durable run journal do not know or depend on the HarnessX trajectory schema;
- the raw trajectory is not written into the authoritative ProblemForger journal and is not required for graph replay or governance audit;
- `TelemetrySink` continues to receive only harness-neutral normalized observations;
- a future Pi adapter may retain a different Pi-native raw trajectory schema without changing ProblemForger core;
- any P7/P8 training dataset that combines HarnessX/Pi histories is produced by a separate offline normalization pipeline from these adapter-owned artifacts, not by adding harness-specific types to core.

Trajectory capture must be semantically complete while excluding credentials and transport secrets. Redaction may remove only data that was not visible to the model/agent and did not affect its behavior, such as API keys, authorization headers, cookies, or unrelated provider-account metadata. If sensitive task/model/tool content itself is part of the semantic trajectory, preserve it in access-controlled storage rather than replacing it with a behavior-changing public redaction.

Artifact storage may be access-controlled when redistribution of source-derived content is restricted, but the experiment record must retain the immutable content digest and enough authorized storage metadata to retrieve the exact artifact. Do not store secrets or private/licensed source material in public traces.
