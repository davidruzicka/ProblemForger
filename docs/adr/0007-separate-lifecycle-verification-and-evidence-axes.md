# ADR 0007: Separate mutation outcome, entity lifecycle, and verification evidence

- Status: Accepted
- Date: 2026-09-18

## Context

The bootstrap graph lifecycle mixed "proposed", "committed", "locally verified", "externally verified", and "invalidated". These are not one state machine.

Evidence classes also mixed origin ("observed") with method ("deterministic" or "learned").

## Decision

Represent three separate concerns.

### Mutation outcome

A proposal attempt can be committed, rejected, conflicted, have a retry requested, or be escalated. A subsequent retry is a new proposal attempt linked by causation/provenance; the earlier proposal is not rewritten.

### Entity lifecycle

A committed entity is active and may later be superseded or invalidated. Historical entities are not destructively rewritten for the PoC.

### Verification

Verification status is a projection over evidence and policy, not the entity lifecycle.

Evidence records preserve at least:

- origin;
- method;
- subject/scope;
- result/verdict;
- provenance;
- optional uncertainty.

No single global evidence-strength enum defines truth.

## Consequences

- Later contradictory evidence can be represented without rewriting history.
- UI may derive labels such as "locally supported" or "disputed".
- Training data can distinguish historical acceptance from later external outcome.
- Deterministic checks remain scoped to the property they actually evaluate.
