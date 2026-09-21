# P6-AC practical whole-system pilot

<a id="p6-practical-pilot"></a>

P6 is a practical feasibility pilot. It asks whether the complete
ProblemForger package is useful on a small, real workflow. It is not an
academic population study, a calibration study, or a claim of exact hosted
model replay. Academic uncertainty is acceptable; correctness, isolation,
durable-audit, and honest reporting are not optional.

This document is the pre-measurement P6-AC-v1 contract. It replaces the earlier
unmeasured multi-stage draft. Changes after the first measured slot require a
new manifest/version and must not be silently pooled with the old one.

## Scope and configurations

P6 compares two complete configurations on the same HarnessX workflow:

- **A — baseline:** the existing HarnessX workflow and benchmark adapter;
- **C — complete package:** the same workflow plus the ProblemForger service,
  explicit graph interaction, and deterministic governance.

A and C use the same selected model, task order, harness, benchmark adapter,
resource limits, and evaluator. The intended A→C difference is the
ProblemForger package. Configuration B, additional models, and a second harness
are useful later diagnostics, not prerequisites for this pilot.

The pilot uses six tasks selected by a deterministic benchmark-adapter rule.
There is one fresh agent run per task/configuration and one evaluator run for
each produced candidate patch. The planned size is therefore twelve agent runs
and at most twelve candidate-patch evaluations. These counts describe an
operational pilot, not statistical precision.

Out of scope for P6: holdout/calibration data, fallback-model chains,
population-level uncertainty, automatic routing, Pi portability, and a full
A/B/C ablation. Those require their own measured question and manifest.

<a id="spec-evaluation-model"></a>
<!-- spec-id: EVALUATION.MODEL -->
## Model and provider

P6 selects one provider/model entry before the manifest is frozen. Record the
requested model identifier, provider, endpoint/deployment when relevant, all
observable generation settings, and `temperature=0` when the provider supports
it. The same request settings are used for A and C.

P6 has no implicit fallback. If the selected model is unavailable before task
exposure, fix the setup or create a new manifest; do not silently choose a
different model. If it becomes unavailable after exposure, preserve the
affected missing slots and continue independent slots where possible. A new
model requires a new experiment version.

<a id="p6-hosted-model-metadata"></a>
### Hosted-model identity limits

The manifest identifies the requested API entry and observable settings, not
necessarily the exact weights or future provider execution. Record provider
revision, deployment/build identifier, response-version header, or equivalent
metadata when the provider exposes it. Record `UNKNOWN` explicitly when it does
not.

A digest of the harness or runtime image identifies those bytes. It does not
prove that a hosted provider will use the same model implementation later, or
that future inference will be bit-for-bit identical. A local model may include
its weights, configuration, and inference runtime in the content-addressed
identity; a hosted model cannot be upgraded into that guarantee by hashing the
client image.

## Pre-P6 manifest

<a id="spec-evaluation-pre-p6"></a>
<!-- spec-id: EVALUATION.PRE-P6 -->

Before exposing any selected task to the agent, freeze one compact manifest
containing:

- manifest version and experiment ID;
- benchmark adapter source/version and its deterministic task-selection rule;
- the six task IDs and fixed order;
- selected provider/model metadata and generation settings;
- HarnessX source/runtime identity and the ProblemForger service source/runtime
  identity;
- execution platform, dependency lockfiles, and image/archive digests when
  images or archives are used;
- evaluator version and required-test definition;
- workspace isolation mode, semantic deadline, resource limits, retry rule,
  and human-intervention definition;
- primary result rule, secondary cost/latency measures, and continuation
  tolerances;
- random seeds where a component actually uses randomness.

The manifest is hashed and retained with every run. A compact manifest is
intentional: it pins the inputs needed to operate and interpret the pilot
without pretending that every opaque provider behavior is content-addressable.

### What the execution image is for

An execution image is an implementation artifact, not a scientific identity
claim. It is useful for pinning the harness, benchmark tooling, interpreter,
dependencies, and—when packaged there—the local ProblemForger service. The
image digest helps detect environment drift and makes setup repeatable. It does
not identify a hosted provider's model or later provider-side optimizations.

If no container/image is used, record the equivalent source revision,
dependency-lockfile hash, interpreter version, and platform. Do not invent an
image merely to obtain a digest.

## Task selection and preflight

The benchmark adapter selects six eligible tasks deterministically from its
declared candidate order. Development and smoke tasks must be separate from
the selected IDs. No selected task is inspected for its gold patch while the
manifest or runtime is being prepared.

If fewer than six tasks are eligible before measured execution, stop as
`INCOMPLETE_TASK_POOL`, preserve the reason, and prepare a new manifest after
fixing the cause. There are no hidden reserves or post-hoc task substitutions
in P6.

<a id="spec-evaluation-preflight"></a>
<!-- spec-id: EVALUATION.PREFLIGHT -->
### Preflight

Before the first measured agent run:

1. verify the recorded benchmark content and any task execution image/archive;
2. verify HarnessX, ProblemForger service startup, evaluator availability, and
   the selected model capability;
3. run the evaluator on a separate smoke fixture, not on a selected task;
4. verify a clean isolated workspace and the declared resource accounting.

A task-specific setup failure is recorded with a reason and does not authorize
selecting another task. Continue independent preflight/measurement slots when
the shared manifest and runtime remain valid. A shared setup failure before
any measured slot starts stops the pilot and requires a corrected manifest or
an explicit new version.

Preflight is an operational readiness check. It does not estimate task success
and its diagnostics cannot be used to tune the selected task set after
exposure.

## Execution controls

Every A/C slot receives a fresh task workspace. The worker may propose graph
changes, but the ProblemForger service remains authoritative for graph state
and governance outcomes. The durable service journal is required for C; its
telemetry is useful but not required to reconstruct the result.

Freeze before exposure:

- a semantic wall-clock deadline per agent run;
- a provider-spend or request budget, where the provider exposes one;
- bounded tool/service-call and output limits;
- one clean retry only for a failure before the first semantic model response,
  when the failure is clearly setup/transport infrastructure;
- no replacement of a trajectory after a semantic response has been accepted;
- an explicit count of human interventions, including setup/recovery help.

For an eligible first-attempt failure, the runner must take that retry unless
a recorded deadline, exhausted budget, shared integrity failure, or operator
abort prevents it. This is one whole-slot restart, not an additional per-call
retry allowance; disable hidden harness/provider retries. Retain both attempt
records. Retries do not reset deadlines or resource counters. After any
semantic response (including accepted streamed content or a tool call), no
whole-slot restart is allowed. Candidate evaluation has no extra retry.

When a slot exhausts a limit, record an unresolved slot and continue unrelated
slots if the experiment-wide runtime is still valid. Do not treat a missing
slot as success or failure and do not buy extra retries after seeing its
outcome.

Before a slot is scored as either 0 or 1, validate its mandatory evidence: the
manifest/version reference, the agent terminal record, the exact candidate
patch bytes and digest where either A or C produced one, and the evaluator
output where evaluation ran. Verify the retained bytes against the digest
bound to the evaluator invocation. For C, the durable ProblemForger journal
must be readable, identify the run, and retain every received proposal and
every returned terminal outcome. Zero proposals is valid; an interrupted
pending proposal is not fabricated into a terminal outcome. If the manifest declares a native trajectory archive as
mandatory, that archive is checked here as well; otherwise native telemetry is
optional diagnostic data. A missing or corrupt mandatory artifact produces
`EVIDENCE_INCOMPLETE` for that slot and never gets regenerated after a semantic
response. If the shared manifest, journal, or recorder fails for the remaining
experiment, stop launching new slots as `INCOMPLETE_EVIDENCE`; retain all
available artifacts and do not assign a complete-pilot decision.

## Measured evaluation

<a id="spec-evaluation-measured-evaluation"></a>
<!-- spec-id: EVALUATION.MEASURED-EVALUATION -->

Run tasks in the frozen order. For each task, run A and C once in fresh
workspaces. Preserve the exact candidate patch bytes and digest produced by either A or C.
Evaluate each produced candidate patch once in a fresh evaluator workspace.

An agent result is a resolved binary outcome when the required evaluator tests
complete and the declared success rule is satisfied. The default success rule
is: all required `FAIL_TO_PASS` tests pass and all required `PASS_TO_PASS` tests
remain passing. A completed failing test vector or an evidenced agent failure
to produce a valid applicable patch is an observed 0. Infrastructure loss,
an incomplete evaluator vector, or missing mandatory evidence is a missing
outcome, not an observed failure. Preserve the specific reason in either case.

For a complete task pair:

```text
y_i(X) = 1 if configuration X resolves task i, 0 for an observed failure
missing outcome is undefined, never 0
d_i(C-A) = 100 * (y_i(C) - y_i(A)) percentage points
mean_delta_pp = mean(d_i(C-A)) over the six task pairs
```

Report every raw outcome, the six per-task deltas, the mean delta, tasks
improved/worsened/tied, unresolved reasons, and C's added cost, latency,
steps, tool calls, service calls, and human interventions. Report observed
values, not confidence intervals or significance claims.

If any planned pair is missing, the pilot is `INCOMPLETE_COVERAGE`: retain
descriptive completed-pair data but do not assign the complete-pilot
`CONTINUE`/`ADAPT`/`STOP` label. Continue independent slots before making that
classification.

<a id="p6-incomplete-reporting"></a>
### Incomplete reporting

Keep a row for every planned slot, including slots never started. Record the
last completed phase, exact reason code, retry attempts, patch/image/model
identities, and retained raw artifacts. A local infrastructure failure does
not become a task failure; a malformed candidate patch does not become an
infrastructure success. The report must distinguish:

- `MISSING_SETUP` — image, workspace, service, harness, or evaluator could not
  be prepared;
- `PROVIDER_UNAVAILABLE` — the selected provider/model could not answer;
- `RUN_INTERRUPTED` — execution began but did not finish;
- `EVALUATION_INCOMPLETE` — candidate evaluation did not produce the required
  test vector;
- `CANDIDATE_PATCH_INVALID` — the produced patch is absent, malformed, or
  cannot be applied;
- `EVIDENCE_INCOMPLETE` — a slot's mandatory raw evidence is missing or
  unreadable after execution;
- `INCOMPLETE_EVIDENCE` — shared mandatory evidence cannot be retained for the
  remaining experiment;
- `INCOMPLETE_TASK_POOL` / `INCOMPLETE_COVERAGE` — the planned pilot could not
  produce all six pairs.

No reason code is silently converted into a favorable result. A future run may
use the report to fix the setup, but it is a new manifest/version.

## Practical human decision

<a id="practical-continuation-decision"></a>

Before exposure, the operator records practical tolerances for cost, latency,
and human intervention, including how each is measured. Human judgment is
deliberately part of this feasibility decision; no percentage threshold is
pretended to be universal.

For a complete six-pair pilot, use exactly one label:

- **`CONTINUE`** — C shows useful local improvement or reduced failure without
  a critical regression, and its operational overhead is acceptable;
- **`ADAPT`** — a concrete, plausibly correctable weakness in benefit,
  overhead, or failure pattern warrants a stated change and reassessment;
- **`STOP`** — a critical correctness, isolation, security, or operational
  regression makes the package unsuitable for the tested workflow, or the
  observed practical value does not justify further work.

An unresolved critical regression precludes `CONTINUE`. `ADAPT` requires a
concrete remediation and reassessment plan and does not authorize broader use
while the regression remains. An incomplete pilot receives no one of these
labels; record a separate operational next action.

The decision maker records evidence, tolerance failures, missing evidence,
observed benefits/regressions, and next action. The label is a local workflow
decision, not an automatic P7 gate.

## Practical sensitivity report

<a id="practical-sensitivity-report"></a>

For a complete pilot, report the full `mean_delta_pp` and six leave-one-task-out
means. Use descriptive bands:

- `HARM` if the delta is below `-10` percentage points;
- `NEUTRAL` if it is between `-10` and `+10`, inclusive;
- `BENEFIT` if it is above `+10` percentage points.

Set `SENSITIVITY_DISCORDANT` if any leave-one-task-out estimate changes sign
or band relative to the full estimate. This is a warning that the small pilot
is sensitive to one task; it does not force `STOP`, `ADAPT`, or `CONTINUE` and
does not establish a population-level uncertainty claim. Do not compute a
sensitivity label for incomplete coverage; report the missingness instead.

P6 does not include bootstrap intervals, p-values, calibrated probabilities,
equivalence labels, or an automatic progression gate. Those may be appropriate
for a later, separately designed study.

## Retained evidence and integrity rules

Retain the manifest, its hash, task order, task/image identities, source and
dependency identities, model/provider metadata, exact request settings,
candidate-patch digest, durable ProblemForger journal, raw evaluator output,
cost/latency measurements, human-intervention log, and all failure reasons.
Redact credentials without changing content that was visible to the agent or
affected its behavior.

Every run-scoped service operation carries an explicit `run_id`. Governance
outcomes are durable before they are returned. A worker cannot directly commit
authoritative graph state. A hosted-model identity limitation is recorded as a
limitation, not hidden behind an image digest.

The optional B diagnostic or a second harness must use a new manifest and must
not be pooled with P6-AC. This keeps the pilot useful for engineering while
leaving stronger causal and external-validity questions for later work.

<a id="p6-resource-budget"></a>
### Resource budget record

The operator must write the actual per-run deadline, request/spend limit, tool
limit, and experiment-wide stop limit into the manifest before task exposure.
The values are practical operating limits, not validity thresholds. If a limit
is unavailable from a provider, record `UNKNOWN` and use the observable local
limit rather than treating unknown usage as zero.

Before starting the first slot, persist the experiment start time and absolute
stop deadline with the experiment ID in the retained execution record. On
coordinator restart, reload that record and cumulative resource usage; never
reset the deadline or spent budgets. Downtime counts toward the stop limit.
If the record is missing, corrupt, or clock continuity cannot be trusted, stop
the pilot as `INCOMPLETE_COVERAGE` with the restart reason; do not launch more
slots. Interrupted semantic trajectories remain missing and are not rerun.
Check the remaining budget before every slot/retry, and terminate active work
when the experiment deadline is reached. Preserve completed results and mark
unfinished or unstarted slots missing. An operator abort has the same no-new-work
effect and must be recorded; it does not reset or extend the experiment.

<a id="p6-runtime-image-identity"></a>
### Runtime identity record

For each image/archive used, record its immutable digest, source/reference,
platform, and the role it plays (benchmark task environment, HarnessX runtime,
ProblemForger service, or dependency bundle). For non-image execution record
the equivalent source and lockfile identities. Runtime identity supports
repeatable setup and drift detection; it is not a promise of exact hosted-model
replay.
