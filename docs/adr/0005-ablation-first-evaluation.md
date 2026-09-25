# ADR 0005: Start with a practical whole-system comparison

- Status: Accepted
- Date: 2026-09-18

## Context

If graph representation, retries, verification, calibration, routing, and prompt
changes are introduced together, the result cannot attribute an improvement to a
single mechanism. The first unpublished PoC nevertheless needs to answer a more
basic practical question: does the complete ProblemForger package help enough to
justify its operational cost?

## Decision

The first P6 experiment compares the complete package directly:

A. pinned HarnessX baseline;
C. + explicit problem graph and deterministic mutation governance.

Use B (+ graph without governance) only as a separately frozen diagnostic when the
whole-system result leaves the source of a regression or benefit operationally
unclear. The later ablation ladder remains:

B. + explicit problem graph;
C. + deterministic mutation governance;
D. + learned verifier;
E. + calibration/abstention;
F. + model routing.

P6-AC primary metrics and task sets are frozen before implementation can optimize
against them. A/C measures the package as a package; it must not be described as an
isolated graph or governance effect. Any B diagnostic has its own manifest and
analysis contract.

## Consequences

- The first practical decision is available with a smaller operational budget than
  a full ablation ladder.
- Mechanism attribution may require a later diagnostic experiment.
- Negative/null results remain valuable.
- Each layer needs an independently runnable configuration.
