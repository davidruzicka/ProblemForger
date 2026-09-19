# ProblemForger

> Helping AI agents break down problems, verify their work, and choose the right model for each step.

ProblemForger is a research prototype for making long-running AI-agent work more explicit, observable, and locally verifiable.

The core idea is to keep an **externally governed, versioned problem graph** outside the worker model. The model may propose graph mutations, produce artifacts, and suggest progress, but it does not own authoritative state. A governor combines explicit evidence and policy before changes are committed; learned verification and calibrated routing are later experimental layers.

ProblemForger is intended to be a **harness-neutral reliability layer**, not another agent framework.

## Research questions

Primary:

> Can an externally governed problem graph turn variable AI-agent execution into locally verifiable decisions with measurable failure probabilities?

Secondary:

> Can those estimates safely route individual subproblems to the cheapest model that is likely to solve them?

## Initial scope

The first experiments focus on software-engineering agents because they provide strong external evidence: tests, compilers, type checkers, static analysis, repository state, and executable behavior.

The architecture itself is intended to remain domain-neutral.

The PoC is deliberately incremental:

1. explicit problem graph;
2. event-sourced authoritative state;
3. governed graph mutations;
4. deterministic/external evidence;
5. learned verification;
6. calibrated confidence and abstention;
7. model suitability estimation and routing;
8. observer/debug UI;
9. controlled ablation studies.

Each layer must be evaluated separately before later layers are allowed to hide its contribution.

## Architecture at a glance

```text
              Agent harness
           (HarnessX / Pi / ...)
                    |
               thin adapter
                    |
          versioned local service API
                    |
             ProblemForger
       +------------+------------+
       |                         |
 authoritative graph        observations
       |                         |
 ProblemGraph -> Governor    TelemetrySink
       |           |
       |           +-- evidence/verifier ports
       |
    EventStore
```

Authoritative graph-domain events are deliberately separate from harness/model/tool telemetry. Replaceable infrastructure and policies are accessed through explicit ports. Concrete providers are loaded from typed configuration. The core must not know whether the EventStore is memory, SQLite, PostgreSQL, or another implementation; provider capabilities remain explicit, so the in-memory adapter is test-only/ephemeral while normal service execution requires a durable provider such as SQLite.

See [PLAN.md](PLAN.md), the [P0 audit](docs/p0-audit.md), and [architecture](docs/architecture.md).

## Repository status

This repository is in the **specification and PoC stage**. Claims about reliability improvements, calibration quality, routing efficiency, or benchmark gains are hypotheses until supported by controlled experiments.

## Documentation

- [PLAN.md](PLAN.md) — roadmap, phases, and exit criteria.
- [AGENTS.md](AGENTS.md) — rules for AI-assisted implementation.
- [P0 specification audit](docs/p0-audit.md)
- [Vision](docs/vision.md)
- [Architecture](docs/architecture.md)
- [Ports, adapters, and modules](docs/modules.md)
- [Problem graph](docs/problem-graph.md)
- [Harness-neutral protocol](docs/protocol.md)
- [Verification](docs/verification.md)
- [Model routing](docs/model-routing.md)
- [Evaluation](docs/evaluation.md)
- [UI](docs/ui.md)
- [Risks](docs/risks.md)
- [Related work](docs/related-work.md)
- [Architecture decisions](docs/adr/)

## Specification checks

This branch contains specification documents and executable GitHub Actions automation. No production ProblemForger implementation exists yet. Run the reproducible checks described in [Specification ownership and checks](docs/specification-checks.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
