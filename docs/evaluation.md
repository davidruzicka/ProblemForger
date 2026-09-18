# Evaluation

## Rule

Evaluation design is part of the specification, not an afterthought.

Before implementation that could optimize against a benchmark, P0 must freeze:

- primary task set;
- primary metric(s);
- model(s);
- budget limits;
- number of repeated runs;
- randomization/pairing strategy;
- success ground truth;
- cost/latency accounting;
- exclusions and failure handling.

## Required ablations

At minimum:

- **A** — harness baseline;
- **B** — A + explicit ProblemGraph;
- **C** — B + deterministic mutation governance;
- **D** — C + learned verifier;
- **E** — D + calibration/abstention;
- **F** — E + model routing.

Do not combine multiple new layers and attribute the aggregate improvement to one component.

## Core metrics

### End-to-end

- task solve rate;
- repeated-run variance;
- tokens per solved task;
- model/API cost per solved task where applicable;
- latency per solved task.

### Graph/governance

- false-positive transition rate;
- false-negative/rejected-valid transition rate where measurable;
- errors caught before propagation;
- invalidations discovered later;
- retry/escalation counts;
- graph expansion/overhead.

### Verification/calibration

- error rate conditioned on high confidence;
- Brier score;
- ECE or justified alternative;
- abstention/coverage;
- selective accuracy;
- calibration by task family/novelty bucket.

### Routing

- success by selected model;
- escalation rate;
- cost/latency savings at matched task success;
- exploration/shadow-evaluation coverage;
- uncertainty quality.

## Threats to validity

Explicitly track:

- benchmark contamination/quality;
- small samples;
- same-task tuning and evaluation;
- model/version drift;
- judge/worker correlated errors;
- selection bias from routing;
- hidden prompt/context differences;
- differing harness capabilities;
- cherry-picking peak runs.

## Raw data

Retain enough structured event/configuration data to reproduce aggregate results while avoiding secrets or licensed/private source leakage.
