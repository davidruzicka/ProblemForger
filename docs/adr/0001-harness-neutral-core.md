# ADR 0001: Keep ProblemForger core harness-neutral

- Status: Accepted
- Date: 2026-09-18

## Context

The PoC should run first with HarnessX and independently with Pi. Coupling domain logic to either harness would make portability claims weak and duplicate implementation.

## Decision

ProblemForger domain logic lives in a harness-neutral core. Harness-specific integration is implemented through thin adapters and a versioned protocol/capability boundary.

Adapters may translate lifecycle/events and enforce harness-specific actions, but must not contain graph/governance policy.

## Consequences

- The core can be tested without a harness.
- Pi and HarnessX integrations can be compared using the same implementation.
- Some harness capabilities will differ; a capability model is required.
- A small protocol boundary adds implementation overhead.
