# ADR 0005: Add reliability mechanisms as measurable ablations

- Status: Accepted
- Date: 2026-09-18

## Context

If graph representation, retries, verification, calibration, routing, and prompt changes are introduced together, any measured improvement is uninterpretable.

## Decision

Evaluate mechanisms incrementally:

A. harness baseline;
B. + explicit problem graph;
C. + deterministic mutation governance;
D. + learned verifier;
E. + calibration/abstention;
F. + model routing.

Primary metrics and task sets are frozen before implementation can optimize against them.

## Consequences

- Development may be slower than feature-first implementation.
- Negative/null results remain valuable.
- Each layer needs an independently runnable configuration.
