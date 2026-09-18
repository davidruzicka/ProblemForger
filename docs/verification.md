# Verification

## Principle

A verifier score is not ground truth.

ProblemForger separates evidence source, verdict, confidence, and eventual outcome.

## Evidence preference

When available, prefer:

1. deterministic/executable evidence;
2. external observation;
3. independent learned verifier;
4. independent LLM judge;
5. worker self-assessment.

This is a preference hierarchy, not an assumption that higher-ranked evidence is infallible.

## Local and global verification

Local checks answer narrow questions such as:

- does this artifact satisfy this requirement?
- is this dependency plausible?
- is this task complete under its explicit criteria?

Global checks ask whether the evolving graph still satisfies root goals/anchors.

A graph can contain locally valid nodes while failing the original task. Both levels are required.

## Learned verifier

The first learned-verifier phase should expose a contract such as:

```text
verify(graph_context, candidate_mutation, evidence)
  -> verdict + uncertainty + metadata
```

Exact types are defined later.

## Calibration

Do not use a model-generated textual confidence value as calibrated probability.

Calibration must use held-out data and report at least:

- Brier score;
- reliability/calibration plot data;
- ECE or a justified alternative;
- accuracy/selective accuracy;
- abstention/coverage;
- error rate above operational confidence thresholds.

Calibration is distribution-dependent. Record support/domain and novelty/OOD indicators where possible.

## Label lifecycle

Training labels should not be created solely from the verifier's own earlier decision.

Retain distinctions such as:

- accepted at time t;
- later externally confirmed;
- later invalidated.

This reduces self-confirming feedback loops.

## Reward/verification hacking

A worker may learn to satisfy a proxy verifier rather than the intended goal. Mitigations to evaluate include:

- executable evidence;
- independent verifier families;
- root-goal revalidation;
- held-out checks;
- delayed outcome labels;
- audit of high-confidence failures.
