# Harness-neutral protocol

## Purpose

Pi and HarnessX must use the same ProblemForger core. Their adapters translate native lifecycle events into a stable protocol.

The protocol should be versioned independently from provider implementations.

## Candidate normalized events

The exact schema is finalized in P1. Expected event families include:

- `RunStarted`;
- `NodeProposed`;
- `NodeStarted`;
- `ModelCallRequested`;
- `ModelCallCompleted`;
- `ToolCallRequested`;
- `ToolCallCompleted`;
- `MutationProposed`;
- `VerificationCompleted`;
- `MutationCommitted`;
- `NodeInvalidated`;
- `RunCompleted`.

Do not create events merely because one harness exposes them. Every normalized event must have a ProblemForger-level semantic purpose.

## Decisions

Core/governor decisions may include:

- `ALLOW`;
- `DENY`;
- `MODIFY`;
- `RETRY`;
- `ESCALATE`.

Not every harness can enact every decision identically.

## Harness capabilities

An adapter declares capabilities separately from normalized events, for example:

- `can_block_tool_call`;
- `can_inject_context`;
- `can_replace_model`;
- `can_pause`;
- `can_resume`;
- `can_render_native_ui`.

This avoids designing the protocol around the least capable harness.

## Transport

Transport is intentionally not fixed in the bootstrap specification.

P1 should choose the smallest transport that:

- works from TypeScript and Python;
- preserves typed/versioned messages;
- supports local PoC use;
- can be replaced without changing the domain protocol.

Possible transports are implementation choices, not architecture.
