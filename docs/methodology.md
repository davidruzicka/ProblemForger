# P6 methodology decision note

This note explains the practical choices behind the normative
[P6-AC pilot](evaluation.md#p6-practical-pilot). It is intentionally short:
the project needs an executable engineering answer, not a publication-grade
uncertainty model.

## Methodological position

P6 asks whether the complete ProblemForger package is useful on one concrete
HarnessX workflow. It may reveal failures, overhead, operational friction, and
local benefit. It does not establish a universal success rate, calibrated
probability, causal mechanism for every component, or exact future hosted-model
behavior.

The acceptable evidence standard is therefore:

1. freeze the inputs needed to make the run understandable;
2. keep A and C operationally comparable;
3. preserve raw outcomes and missingness;
4. protect durable graph/audit integrity;
5. let a human make the practical next-step decision.

The six-task size, one agent run, and one evaluator run are scope controls.
They are not a claim that six tasks provide academic precision.

## Decisions and rationale

| Topic | P6 choice | Deliberately deferred |
| --- | --- | --- |
| Question | Local A/C feasibility | Population or causal claims |
| Workload | Six deterministic tasks | Holdout/calibration split |
| Execution | One fresh agent run per task/configuration | Repetition-based variance estimates |
| Evaluation | One evaluator run per produced patch | Redundant evaluator replication |
| Model | One selected provider/model, no fallback | Model ranking/routing |
| Runtime | One compact manifest and recorded identities | Full content-addressed provider replay |
| Analysis | Per-task delta, mean delta, cost/latency, missingness | Bootstrap, p-values, confidence intervals |
| Decision | Human `CONTINUE`/`ADAPT`/`STOP` checkpoint | Automatic progression gate |

This is a conscious complexity budget. Removing academic analysis does not
remove practical controls: a malformed patch remains a malformed patch, an
incomplete journal remains a recovery defect, and an isolated runtime failure
remains visible as missing evidence.

## Measurement

For task `i` and configuration `X`, record the binary resolved outcome
`y_i(X)`. A task is resolved only when the required test vector completes and
the declared success rule passes. For a complete pair:

```text
d_i(C-A) = 100 * (y_i(C) - y_i(A)) percentage points
mean_delta_pp = mean(d_i(C-A)) over the six pairs
```

The report must show the six rows, not only the mean. Also report provider cost,
wall-clock latency, agent/tool/service steps, human intervention, and every
unresolved reason. A completed failing vector is an observed zero; an
incomplete vector, infrastructure loss, or missing mandatory evidence is an
undefined outcome. A missing pair makes the pilot incomplete; it is not
silently converted to a zero or a favorable observation.

The comparison is package-level. A positive C-A result does not isolate graph
storage from governance, instructions, or service overhead. If that distinction
matters, run a new B/C diagnostic with a new manifest.

## Model and image interpretation

The selected model and observable settings are frozen before task exposure. A
hosted provider may change weights, routing, capacity, or server-side
optimizations without changing the client image. The manifest records provider
revision/deployment metadata when available and `UNKNOWN` otherwise.

The execution image has a narrower, useful purpose: it pins the bytes for the
benchmark environment, harness, dependencies, and local service. Its digest
helps detect setup drift and reproduce the software environment. It is not a
model identity token for hosted inference. For a local model, the weights,
configuration, and inference runtime can be added to the content identity.

This distinction is an honest practical limitation, not a reason to block the
pilot.

## Missingness and operational failures

The pilot continues independent slots after an isolated setup/provider failure
when the shared manifest and runtime remain valid. Every planned slot stays in
the report. A shared failure before measured execution stops the pilot and
requires a setup correction or new manifest. No task or model substitution is
allowed after exposure.

The exact ordering is owned by the normative evaluation contract. An eligible
retry is mandatory unless a recorded terminal condition prevents it. A durable
operation ledger reserves counted work before dispatch and settles actual usage;
a semantic-acceptance marker is durable before content or a tool call reaches
the agent. An ambiguous interruption is missing and is never regenerated.
Once a semantic model response has been accepted, the trajectory is retained
as-is. This protects practical comparability without requiring a distributed
retry coordinator.

## Sensitivity

The pilot uses one simple fragility warning rather than an inferential model.
Recompute the mean after removing each task. Compare each leave-one-task-out
value with the full value using `HARM` / `NEUTRAL` / `BENEFIT` bands with ±10
percentage points. Set `SENSITIVITY_DISCORDANT` if any estimate changes sign or
band. The warning says “one task matters”; it does not choose the human
decision and does not become a population uncertainty claim.

Do not calculate this warning when the six-pair coverage is incomplete. Report
the missingness instead.

## Human checkpoint

Before exposure, record practical tolerances for cost, latency, and human
intervention. After a complete pilot, choose one label:

- `CONTINUE` when C provides useful local improvement or reduced failure with
  no critical regression and acceptable overhead;
- `ADAPT` when a concrete, plausibly correctable weakness warrants a stated
  change and reassessment;
- `STOP` when correctness, isolation, security, or operation regresses
  critically, or the observed value does not justify more work.

Incomplete coverage receives no one of these labels. An unresolved critical
regression rules out `CONTINUE`; `ADAPT` requires a remediation and
reassessment plan. The decision maker records the evidence and rationale.

## Scope boundary for later work

P6 does not attempt to solve:

- calibration or abstention;
- model routing or fallback optimization;
- cross-harness portability;
- population-level benchmark validity;
- multi-worker claims, leases, or fencing;
- exact replay of opaque hosted inference.

These are later questions with different failure modes. Keeping them out of
the first pilot reduces implementation and interpretation risk.

## Historical material

The checked-in bootstrap fixture and earlier multi-repetition/holdout drafts
remain historical audit evidence only. They are not inputs to P6-AC-v1. The
current contract is owned by `docs/evaluation.md`; this note must not become a
second algorithmic source.
