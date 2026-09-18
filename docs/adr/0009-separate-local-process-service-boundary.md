# ADR 0009: Run ProblemForger core behind a separate local process/service boundary

- Status: Accepted
- Date: 2026-09-18

## Context

The core is Python, the Pi adapter is TypeScript, and the HarnessX adapter is Python. Importing the core directly into HarnessX while using RPC for Pi would create different integration architectures and weaken portability comparisons.

## Decision

During the PoC, ProblemForger core/application logic runs in a separate local Python 3.12+ process/service.

HarnessX and Pi use thin clients against the same versioned application protocol.

Transport is not fixed by this ADR. P1 must choose it through a bounded spike and record the result in a follow-up ADR.

## Consequences

- Both harnesses exercise the same public boundary.
- The core can evolve independently from harness dependencies.
- UI/observer clients can later reuse the same service.
- Serialization, process lifecycle, cancellation, and local transport overhead become explicit engineering concerns.
- The transport must remain replaceable without changing domain semantics.
