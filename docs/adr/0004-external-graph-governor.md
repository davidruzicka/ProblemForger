# ADR 0004: Worker models propose; the external governor commits

- Status: Accepted
- Date: 2026-09-18

## Context

If the worker model can directly mutate goals, requirements, verification state, or acceptance thresholds, the graph does not provide an independent control boundary.

## Decision

Worker models may propose graph mutations. An external governor decides whether a proposed mutation is committed using graph invariants, evidence, verification, and policy.

Root anchors, audit history, governor policy, and verification thresholds are not silently mutable by the worker.

## Consequences

- Graph mutations become explicit audit events.
- Self-modification requires a separate governed/meta-level mechanism if introduced later.
- Integration adapters must be capable of enforcing at least the subset of decisions used by an experiment.
