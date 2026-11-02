# Future exploration candidates

These are non-normative candidates, not commitments or changes to the P2 graph
contract or the frozen P6 experiment. Each needs a separately scoped issue and
evaluation before adoption.

## Hybrid reasoning worker

[Hybrid Reasoning Agents](https://arxiv.org/abs/2610.18861) switches between
latent reasoning and textual tool calls using a trained adapter and model-owned
KV working memory. Its [released code and checkpoints](https://github.com/togethercomputer/HybridAgent)
offer a candidate worker for a later harness comparison. Explore whether its
inference engine can call the existing graph tools and whether a fresh worker can
continue from the external graph and journal after its KV state is lost. The
harness owns inference and KV state; the graph, governance outcomes, and trusted
evidence stay outside the model. Decoded latent pseudo-text is diagnostic, not
trusted evidence.

## Compact checkpoints for opaque reasoning

Explore optional, human-readable summaries of intent, action, and observed
evidence at tool or graph-mutation boundaries. An observer could use these to
diagnose a worker whose internal reasoning is unavailable. Worker summaries
remain telemetry; durable governance records and evidence checks retain their
existing authority. Compare error detection and localization, verified task
success, and token/latency overhead against the same worker without summaries.

## Audit-aware model suitability

When testing later model routing, profile a pinned hybrid checkpoint as one
candidate model on matched software-engineering tasks and budgets. Measure
verified success, valid/useful tool calls, audit quality, tokens, latency, and
cost. Explore whether audit quality should constrain selection alongside the
existing success and budget target in [model routing](model-routing.md). The
paper's reported efficiency gains are not evidence of gains on ProblemForger's
tasks; this comparison needs its own frozen evaluation design.

## Experience-guided graph execution

Explore whether verified experience from earlier problem-graph executions can improve decisions on new, related tasks. Store reusable lessons from successful and failed runs, retaining their provenance, verification status, applicable constraints, and known limitations. Retrieve potentially relevant lessons before planning or executing similar work, but treat them as advisory context rather than trusted evidence or authority to change graph state.

Start with a controlled comparison of the same worker, tasks, tools, and budgets with and without experience retrieval. Separate repeated-task performance from transfer to unseen related tasks. Measure verified success, recurring failures, invalid transfers, and token, latency, and storage costs. Require evidence that retrieval helps before considering automatic memory updates, graph-based experience abstractions, or broader procedural learning.

Research leads include the agentic memory and self-evolving reasoning approaches surveyed in [A Survey of Agentic Reasoning for Large Language Models](https://arxiv.org/abs/2601.12538), including ReasoningBank, SEDM, and ACE. Their reported results do not establish effectiveness within ProblemForger. Any future mechanism must preserve the external graph's authority, evidence checks, and the frozen evaluation contract.
