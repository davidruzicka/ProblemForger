# Ports, adapters, and configuration-driven modules

## Decision

Replaceable infrastructure and policies are modules behind stable APIs/ports. Concrete implementations are selected by configuration.

SQLite and in-memory persistence are the initial providers. They must not receive privileged treatment in core code.

## Goals

- allow storage replacement without graph-domain changes;
- allow multiple verifier/router implementations;
- keep experiments comparable across providers;
- isolate provider-specific dependencies;
- keep configuration validation close to each provider.

## Non-goal

This is not a generic third-party plugin ecosystem in the PoC.

Use a small typed registry/factory until requirements justify dynamic discovery.

## Illustrative layout

```text
src/problemforger/
  core/
    graph/
    governance/
    events/
  ports/
    event_store.py
    verifier.py
    telemetry.py
  modules/
    persistence/
      memory/
      sqlite/
      postgres/        # later
    verification/
    telemetry/
  config/
    loader.py
  adapters/
    harnessx/
    pi/
```

The final package layout may differ, but dependency direction must remain equivalent.

## Configuration rules

- configuration is versioned;
- unknown provider names fail explicitly;
- provider config is validated before provider construction;
- secrets are never serialized into graph events;
- provider-specific settings never appear in domain types;
- effective configuration for experiments is recordable with secrets redacted.

## Persistence contract

The exact API is defined during P1, but it must support at least:

- append events atomically in order;
- read a run/event stream in stable order;
- detect version conflicts;
- preserve event payloads exactly enough for deterministic replay.

SQLite should exercise the same contract as in-memory and future PostgreSQL adapters.
