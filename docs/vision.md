# Vision

## Problem

Long-running AI-agent execution is variable and difficult to audit. Intent, assumptions, intermediate conclusions, dependencies, and verification can remain implicit inside model context. A plausible-looking trajectory may therefore drift while still appearing coherent.

ProblemForger explores a different control boundary:

- the agent proposes work and graph mutations;
- an external system owns authoritative problem state;
- important claims become explicit nodes/edges/evidence;
- transitions are governed;
- uncertainty is measured rather than hidden;
- model choice can later become a per-node decision.

## Core idea

The problem graph is not the harness control-flow graph.

It represents the evolving problem state: goals, requirements, tasks, artifacts, evidence, dependencies, provenance, and verification state.

Different model runs may take different trajectories. They need not produce identical reasoning. The system instead asks whether the resulting graph mutations are justified and whether global anchors remain satisfied.

## Initial research questions

1. Does explicit problem-state representation reduce undetected error propagation?
2. Does mutation governance improve reliability beyond graph decomposition alone?
3. Can narrow node/edge verdicts be calibrated better than whole-session self-evaluation?
4. Can calibrated node-level success estimates support cheaper model routing without materially reducing task success?
5. Are effects portable across more than one agent harness?

## Positioning

ProblemForger is a research prototype and reliability layer, not a replacement for Pi, HarnessX, or other agent harnesses.

Avoid claims such as "solves nondeterminism", "first", "novel architecture", or "makes agents reliable" unless supported by evidence and a completed novelty review.
