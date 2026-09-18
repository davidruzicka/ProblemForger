# Related work

This file maps adjacent work and closest conceptual precedents. It is **not** a novelty claim.

## Agent harnesses

### HarnessX

HarnessX frames the harness as a first-class composition of runtime behavior around a model. The paper describes typed harness primitives, trace-driven adaptation, and reuse of trajectories for harness/model improvement. The current public repository exposes composable processors/event middleware, `HarnessBuilder.add()`, separate model/harness configuration, tracing/JSONL export, and benchmark integrations.

- Paper: https://arxiv.org/abs/2606.14249
- Repository: https://github.com/Darwin-Agent/HarnessX

ProblemForger intends to use HarnessX as an execution substrate. Its graph is problem/epistemic state, not HarnessX's processor/control structure.

### Pi

Pi is a terminal coding agent with a TypeScript extension API. Current documentation exposes lifecycle events, tool interception/blocking, custom tools, context modification, state persistence, custom TUI components, and headless/JSON/RPC modes.

- Extensions: https://pi.dev/docs/latest/extensions
- Providers/models: https://pi.dev/docs/latest/providers
- Custom models: https://pi.dev/docs/latest/models

ProblemForger uses Pi as an independent portability target because the integration mechanism and implementation language differ from HarnessX.

## Graph-centric agent systems

### Graph Engineering

"Graph Engineering in the Era of LLM Agents: From Individual Intelligence to System Intelligence" explicitly describes dynamic, evolving graphs representing tasks, agents, and system states as a system-level organization mechanism.

- https://arxiv.org/abs/2608.21156

This makes "agents + explicit dynamic graph" alone an insufficient novelty claim for ProblemForger.

### Dynamic graph transformation for self-evolving agents

"Self-Evolving Agents as Dynamic Graph Transformation" models agent state as typed nodes, edges, and subgraphs updated through schema-constrained rewrites and discusses graph-aware evaluation/governance.

- https://arxiv.org/abs/2608.18104

This is particularly close to ProblemForger's mutation vocabulary. ProblemForger must therefore distinguish its empirical contribution through the specific combination of externally authoritative problem state, event-sourced provenance, governed mutations, executable evidence, calibrated verification, and later per-node model suitability.

### CaSKG

CaSKG builds an offline skill graph and explicitly calibrates graph-edge confidence using counterfactual probes and Bayesian smoothing before retrieval.

- https://arxiv.org/abs/2608.25500

It is relevant evidence that calibrated edge confidence can be useful in graph-based agent systems, but its graph is an offline skill-retrieval structure rather than an authoritative live execution/problem graph.

### GALAX

GALAX uses step-wise graph/subgraph construction with a Graph Process Reward Model combining a pretrained GNN and schema checks.

- Paper: https://arxiv.org/abs/2509.20935
- ICLR 2026 version: https://openreview.net/

It is a close precedent for learned process supervision over graph construction, although its application and graph semantics are biomedical knowledge/subgraph reasoning rather than general software-agent work state.

## Process supervision and verification

### CodePRM

CodePRM trains a process reward model using code-execution feedback and scores intermediate code-generation reasoning steps; inference uses a Generate-Verify-Refine loop.

- ACL Findings 2025: https://aclanthology.org/2025.findings-acl.428/

ProblemForger shares the idea that executable feedback is valuable process evidence, but aims to score explicit graph mutations/entities rather than hidden/free-form reasoning steps.

### SWE-PRM

"When Agents go Astray: Course-Correcting SWE Agents with PRMs" applies process reward modeling to software-engineering agent trajectories and reports inference-time course correction on SWE-bench Verified.

- IBM Research / NeurIPS 2025 workshop: https://research.ibm.com/publications/when-agents-go-astray-course-correcting-swe-agents-with-prms

This is a direct adjacent approach for detecting trajectory-level software-agent failure.

### AgentPro

AgentPro uses MCTS-generated step annotations to train a process reward model and uses process supervision to avoid continuing erroneous reasoning paths.

- EMNLP 2025: https://aclanthology.org/2025.emnlp-main.506/

It is relevant to automated intermediate supervision but is not based on a persistent governed problem graph.

## Model routing

### RouteLLM

RouteLLM learns routers between stronger and weaker models using preference data to trade response quality against cost.

- Paper: https://arxiv.org/abs/2406.18665
- ICLR 2025: https://openreview.net/pdf?id=8sSqNntaMr

### IRT-Router

IRT-Router explicitly models relationships between model capability and query attributes with Item Response Theory and includes cold-start techniques.

- ACL 2025: https://aclanthology.org/2025.acl-long.761/

These support treating routing as conditional model suitability rather than a fixed global model ranking. ProblemForger's later target is narrower and stateful:

```text
P(success | node, graph_state, model, budget)
```

## Calibrated decision models

TypeSafe AI presents Jev/System One Models as typed probabilistic decision models and describes Reinforcement Learning for Calibrated Decisions. Architecture/training details needed to reproduce the system are not publicly established in the material reviewed here, so vendor performance/calibration claims should not be treated as independent evidence.

- https://typesafe.ai/blog/introducing-system-one-models-and-jev

Jev is conceptual inspiration for calibrated narrow decisions, not an implementation dependency.

## Software-engineering evaluation

### SWE-smith

SWE-smith generates executable software-engineering tasks at scale and publishes task instances/environments.

- Paper: https://arxiv.org/abs/2504.21798
- Repository: https://github.com/SWE-bench/SWE-smith
- Dataset: https://huggingface.co/datasets/SWE-bench/SWE-smith

ProblemForger uses a pinned deterministic subset for the first small A/B/C mechanism experiment. Because the dataset is public and has been used for model training, results are not presented as uncontaminated capability measurements.

### SWE-bench Verified

SWE-bench Verified contains 500 human-screened SWE-bench tasks and executable grading, but it is no longer a suitable frontier capability benchmark because of contamination and remaining task-quality problems.

- Original Verified release: https://openai.com/index/introducing-swe-bench-verified/
- 2026 contamination/task-quality analysis: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

It remains useful background and may be useful for compatibility smoke tests, but is not the planned P11 external-validity benchmark.

### SWE-Bench Pro and Pro Verified

SWE-Bench Pro was designed for longer-horizon, more diverse software tasks, but later audits reported substantial task-quality issues. A newer SWE-Bench Pro Verified proposal adds anti-hacking safeguards and task refinement.

- SWE-Bench Pro: https://arxiv.org/abs/2509.16941
- OpenAI audit: https://openai.com/index/separating-signal-from-noise-coding-evaluations/
- SWE-Bench Pro Verified: https://arxiv.org/abs/2609.08149

Pro Verified is currently a candidate for later external-validity testing, not a frozen choice for P11.

## Working differentiation hypothesis

The closest defensible description of the intended ProblemForger contribution is the **combination**, not any single component:

```text
externally authoritative dynamic problem graph
+ typed/versioned graph mutations
+ event-sourced provenance
+ deterministic/external evidence
+ learned node/mutation verification
+ calibrated probability / abstention
+ per-node model suitability and routing
+ harness-neutral adapters
```

The P0 literature review did not establish that this exact combination is already a standard architecture. It also did **not** establish novelty. Literature review must be repeated before any publication-quality novelty claim.

## Novelty discipline

Before claiming novelty:

1. search for systems combining dynamic problem graphs, governed mutations, node/edge verification, calibrated probabilities, and model routing;
2. separate control-flow graphs from epistemic/problem-state graphs;
3. distinguish process reward scores from calibrated probabilities of correctness;
4. distinguish offline retrieval graphs from live authoritative execution state;
5. document the closest competing systems, including negative findings;
6. avoid "first" claims unless a publication-grade search supports them.
