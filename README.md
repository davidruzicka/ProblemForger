# ProblemForger

> Externally governed problem graphs for AI-agent work.

ProblemForger is a practical feasibility prototype for making long-running AI-agent work more explicit, observable, and locally verifiable.

The core idea is to keep an **externally governed, versioned problem graph** outside the worker model. The model may propose graph mutations, produce artifacts, and suggest progress, but it does not own authoritative state. A governor combines explicit evidence and policy before changes are committed; learned verification and calibrated routing are later experimental layers.

ProblemForger is intended to be a **harness-neutral reliability layer**, not another agent framework.

## Initial scope

The first experiments focus on software-engineering agents because they provide strong external evidence: tests, compilers, type checkers, static analysis, repository state, and executable behavior.

The architecture itself is intended to remain domain-neutral.

The initial PoC compares an existing harness with and without the complete graph/governance package. Learned verification and model routing are planned later work. Phase ordering lives in [PLAN.md](PLAN.md); experiment definitions live in [Evaluation](docs/evaluation.md).

## Integration

ProblemForger is not a standalone agent harness. An existing harness retains model, tool, and session execution. A thin adapter connects it to the local ProblemForger service, where the worker queries graph state and proposes changes. ProblemForger governs those changes using evidence and policy and records durable decisions.

The same core serves different harnesses; adapters translate the protocol without owning domain policy. See [Architecture](docs/architecture.md) for service boundaries and persistence.

## Repository status

This repository is in early P1 implementation. It now has a Python 3.12+ package scaffold and an automated core dependency-boundary check; journal, provider, and service behavior remain to be implemented through the ordered P1 issues. Claims about reliability improvements, calibration quality, routing efficiency, or benchmark gains remain hypotheses until supported by controlled experiments.

## Documentation

### Start here

- [Vision](docs/vision.md)
- [Architecture](docs/architecture.md)
- [PLAN.md](PLAN.md) — phases and exit criteria.

### Contributor workflow

- [AGENTS.md](AGENTS.md) — contributor and agent instructions.
- [Pull-request review loop](docs/review-loop.md)
- [Specification ownership and checks](docs/specification-checks.md)

### Normative contracts and decisions

- [Ports, adapters, and modules](docs/modules.md)
- [Problem graph](docs/problem-graph.md)
- [Harness-neutral protocol](docs/protocol.md)
- [Verification](docs/verification.md)
- [Model routing](docs/model-routing.md)
- [Evaluation](docs/evaluation.md)
- [UI](docs/ui.md)
- [Architecture decisions](docs/adr/)

### Supporting material and historical audits

- [Risks](docs/risks.md)
- [Related work](docs/related-work.md)
- [P0 specification audit](docs/p0-audit.md)
- [Methodology audit and decision register](docs/methodology.md)

## Development checks

Python 3.12+ and Node.js are required. From the repository root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e . -r tests/requirements.txt
python -m scripts.check_architecture
python -m coverage run --branch -m unittest discover -s tests -p 'test_*.py' -v
python -m coverage report --fail-under=90
node --test tests/review-workflow.test.mjs
```

The Python tests use only the standard library. Coverage tooling is test-only. See [Specification ownership and checks](docs/specification-checks.md) for the P0 contract checks and their limits.

## License

Apache License 2.0. See [LICENSE](LICENSE).
