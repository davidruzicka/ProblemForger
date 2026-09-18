# Related work

This file is a starting map, not a novelty claim. P0 should verify references and update the comparison before public research claims.

## Agent harnesses

### HarnessX

HarnessX separates model choice from harness behavior and exposes composable processors/hooks, evaluation, tracing, multi-model support, and harness adaptation.

- Paper: https://arxiv.org/abs/2606.14249
- Repository should be verified during P0 from the paper's canonical link.

ProblemForger intends to use HarnessX as an execution substrate, not replace it.

### Pi

Pi is a minimal coding-agent harness with an extension model suitable for a thin independent integration.

Canonical repository/documentation links should be verified during P0 before citing them in research output.

## Graph engineering

Recent work describes explicit dynamic graphs for agent tasks/state as a broader engineering pattern. ProblemForger's intended distinction is not simply "using a graph", but governing a versioned problem-state graph with explicit evidence and calibrated verification.

Candidate reference discussed during project conception:

- https://arxiv.org/abs/2608.21156

Verify terminology, claims, and publication metadata during P0.

## Process reward / step verification

Relevant lines include process reward models and step-level verification for code/software agents, including work such as CodePRM and SWE-agent course-correction approaches.

The project should compare:

- trajectory/step scoring;
- graph-mutation/node-edge verification;
- executable feedback;
- delayed external outcomes.

P0 should replace this section with canonical citations.

## Model routing

Relevant work includes routing stronger/weaker models, Item Response Theory based routing, and query-conditioned performance estimation.

Candidate references:

- RouteLLM: ICLR 2025;
- IRT-Router: ACL 2025.

ProblemForger's proposed routing target is node- and graph-state-conditioned model success probability rather than a fixed scalar node difficulty.

## Calibrated decision models

TypeSafe AI's Jev/System One Models proposal motivated part of the discussion around typed probabilistic decisions and calibrated confidence:

- https://typesafe.ai/blog/introducing-system-one-models-and-jev

This is related inspiration, not evidence that ProblemForger implements the same architecture or training method.

## Novelty discipline

Before claiming novelty:

1. search for systems combining dynamic problem graphs, governed mutations, node/edge verification, calibrated probabilities, and model routing;
2. separate papers that use execution graphs from papers that represent epistemic/problem state;
3. distinguish learned reward scores from calibrated probabilities of correctness;
4. document the closest competing systems and any negative finding.
