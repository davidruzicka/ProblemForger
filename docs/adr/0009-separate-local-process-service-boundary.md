# ADR 0009: Run ProblemForger core behind a separate local process/service boundary

- Status: Accepted
- Date: 2026-09-18

## Context

The core is Python, while harness adapters may use different languages. Importing the core directly into one harness while using RPC for another would create different integration architectures and weaken portability comparisons.

## Decision

During the PoC, ProblemForger core/application logic runs in a separate local Python 3.12+ process/service.

Harness adapters use thin clients against the same versioned application protocol.

Transport is not fixed by this ADR. P1 must choose it through a bounded spike and record the result in a follow-up ADR.

## Consequences

- All harnesses exercise the same public boundary.
- The core can evolve independently from harness dependencies.
- UI/observer clients can later reuse the same service.
- Serialization, process lifecycle, cancellation, and local transport overhead become explicit engineering concerns.
- The transport must remain replaceable without changing domain semantics.
