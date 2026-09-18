# ADR 0003: Use ports/adapters with configuration-driven modules

- Status: Accepted
- Date: 2026-09-18

## Context

The initial PoC needs in-memory and SQLite persistence, while later experiments may use PostgreSQL or different verifier/router/telemetry providers. Core behavior must not depend on those implementation choices.

## Decision

Replaceable infrastructure and policies are exposed as explicit ports/interfaces. Concrete providers are modules selected by a typed configuration loader/registry.

Core code must not import, instantiate, or branch on concrete provider types.

Provider-specific configuration is validated and consumed inside the provider module.

The initial module mechanism is intentionally small; no generic plugin ecosystem is built without demonstrated need.

## Consequences

- SQLite and memory exercise the same event-store contract.
- Future PostgreSQL replacement should not require domain changes.
- Tests can use in-memory providers.
- Provider boundaries require explicit contracts early.
