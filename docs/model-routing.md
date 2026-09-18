# Model suitability and routing

## Status

Routing is a later experimental phase. Earlier phases must collect the data needed for it without actively changing model selection.

## Target

Do not treat node difficulty as one authoritative scalar.

The useful quantity is:

```text
P(success | node, graph_state, model, budget)
```

A task can be easy for one specialized model and difficult for another.

## Features

Possible inputs include:

- node/task type;
- graph neighborhood and dependency depth;
- available evidence/tests;
- context size;
- affected artifacts/files/modules;
- language/framework;
- novelty relative to historical tasks;
- semantic representation;
- previous node outcomes.

Feature utility must be measured rather than assumed.

## Local and fine-tuned models

A local or fine-tuned checkpoint is simply another candidate model. Its profile should be learned from measured outcomes for the exact checkpoint, not inherited unquestioningly from its base model.

Cold start may use:

- base-model priors;
- a small evaluation suite;
- similarity to known tasks;
- deliberately high uncertainty.

## Selection bias

If the router only sends "easy" nodes to a small model, observed outcomes cannot answer how that model performs on hard nodes.

The experiment therefore needs controlled exploration, for example:

- random assignment on a small fraction;
- shadow execution with non-committing alternative models;
- informative sampling for new models.

## Policy

A later policy may optimize cost/latency subject to a minimum success probability, but must account for uncertainty.

A cascade is expected to be safer than perfect pre-routing assumptions:

```text
route -> execute -> verify -> commit or escalate
```

## Metrics

Measure:

- task success;
- routing regret or counterfactual proxy where defensible;
- escalation rate;
- cost/tokens/latency per solved task;
- reliability of predicted success probabilities;
- performance by task family/model.
