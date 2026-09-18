# ADR 0002: Use an append-only event log as authoritative state

- Status: Accepted
- Date: 2026-09-18

## Context

The project needs provenance, replay, later invalidation, experiment datasets, and debugging of drift over time.

## Decision

Graph state is a projection of an append-only event stream. Mutable graph storage or snapshots may be used as derived optimizations but are not the source of truth.

## Consequences

- Runs can be replayed and inspected by graph version.
- Later evidence can invalidate earlier decisions without rewriting history.
- Persistence providers must preserve ordering/version semantics.
- Event schema evolution must be managed deliberately.
