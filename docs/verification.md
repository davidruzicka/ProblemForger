# Verification

## Principle

A verifier score is not ground truth.

ProblemForger separates:

- evidence origin;
- evidence method;
- the claim/subject being evaluated;
- verdict or measured result;
- uncertainty/confidence;
- eventual external outcome.

## Evidence is multidimensional

Do not encode evidence as a single global rank such as "deterministic > observed > learned".

A deterministic check is only authoritative for the property it actually checks. An external observation can be noisy or nondeterministic. A learned verifier can contribute useful evidence while still sharing errors with the worker.

Evidence records should therefore preserve orthogonal metadata.

### Origin

Examples:

- worker/model;
- harness/tool/environment;
- independent verifier;
- human;
- benchmark evaluator.

### Method

Examples:

- assertion;
- deterministic check;
- observed outcome;
- learned judge;
- human review.

### Scope

Evidence must identify the exact entity, edge, mutation, requirement, or root goal it supports or contradicts.

## Operational preference

When two sources address the same claim and are otherwise comparable, prefer mechanically reproducible/external evidence over model self-assessment.

Typical examples:

- compiler/type checker result;
- targeted test result;
- benchmark evaluator;
- static-analysis invariant;
- independently reproduced environment result.

This is policy guidance, not a universal trust ordering.

## Local and global verification

Local checks answer narrow questions such as:

- does this artifact satisfy this requirement?
- is this dependency supported?
- did the targeted test pass?
- are mutation preconditions true?

Global checks ask whether the evolving graph still satisfies root goals/anchors.

A graph can contain locally valid entities while failing the original task. Both levels are required.

## Deterministic governance phase

P3/P6 should begin with claims for which mechanically evaluable evidence exists.

Configuration C may reject or escalate a mutation when:

- schema/core graph invariants fail;
- the mutation is based on a stale graph version;
- required deterministic evidence is missing or contradicts the proposal;
- a protected anchor would be changed without an explicitly authorized meta-operation.

Do not invent deterministic checks for semantic properties that are not mechanically decidable.

## Learned verifier

The learned-verifier phase should expose a replaceable contract conceptually similar to:

```text
verify(graph_context, candidate_mutation, evidence)
  -> verdict + raw_score/features + metadata
```

Calibration is a separate concern. The raw verifier result must remain recoverable so calibration can be changed without rewriting historical observations.

## Calibration

Do not use model-generated textual confidence as calibrated probability.

Calibration must use task-level held-out data and report at least:

- Brier score;
- reliability/calibration plot data;
- ECE or a justified alternative;
- selective accuracy;
- abstention/coverage;
- error rate above operational confidence thresholds.

Split by task/run rather than randomly splitting individual transitions from the same task across train/calibration/evaluation sets.

Calibration is distribution-dependent. Record calibration domain/support and novelty/OOD indicators where possible.

## Outcome/label lifecycle

Training labels must not be created solely from the verifier's own prior decision.

Preserve separate observations such as:

- proposal committed at time/version v;
- deterministic evidence available at commit;
- later benchmark/environment outcome;
- later invalidation/dispute.

This allows later evidence to change the training target without rewriting historical events.

## Correlated errors and verifier hacking

Worker and verifier may share model-family, training-data, or proxy-objective errors.

Mitigations to evaluate include:

- executable/external evidence;
- verifier provenance and versioning;
- independent verifier families where cost permits;
- root-goal revalidation;
- held-out checks;
- delayed outcome labels;
- audit of high-confidence failures.

A stronger judge is not assumed independent merely because it is a different API call.
