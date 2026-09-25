# Specification ownership and checks

## Contract ownership

Accepted ADRs own architectural decisions. The operational specifications below
own their detailed algorithms and interfaces. Change an ADR first when a
proposed algorithm conflicts with its decision. Plans, issues, and audit reports
define work or record evidence; they link to these IDs instead of maintaining a
second copy of the contract.

Stable requirement IDs are metadata on normative headings. This table maps those
IDs to their owners; it is not an exhaustive index of every contract. The linked
document is the only normative definition for each requirement.

| Requirement ID | Contract | Normative owner |
| --- | --- | --- |
| `GRAPH.MODEL` | Problem-graph vocabulary and lifecycle | [Problem graph](problem-graph.md#spec-graph-model) |
| `MODULES.EVENTSTORE-PORT` | EventStore port and provider contract | [Modules — EventStore](modules.md#spec-modules-eventstore-port) |
| `PROTOCOL.PROPOSAL-RECOVERY` | Proposal identity, recovery, and terminal binding | [Protocol — proposal recovery](protocol.md#spec-protocol-proposal-recovery) |
| `PROTOCOL.STORE-OWNER` | Exclusive durable-store ownership | [Protocol — STORE-OWNER](protocol.md#spec-protocol-store-owner) |
| `PROTOCOL.PARALLEL-CLAIMS` | Deferred multi-worker claims | [Protocol — deferred parallel claims](protocol.md#spec-protocol-parallel-claims) |
| `VERIFICATION.EVIDENCE-TRUST` | Trusted evidence producers and local isolation | [Verification — EVIDENCE-TRUST](verification.md#spec-verification-evidence-trust) |
| `VERIFICATION.EVIDENCE-BINDING` | Immutable evidence/subject binding | [Verification — EVIDENCE-BINDING](verification.md#spec-verification-evidence-binding) |
| `VERIFICATION.EVIDENCE-RECOVERY` | Evidence retention and restart behavior | [Verification — EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-recovery) |
| `EVALUATION.MODEL` | P6 model and runtime selection | [Evaluation — Model](evaluation.md#spec-evaluation-model) |
| `EVALUATION.PRE-P6` | Pre-P6 frozen artifacts | [Evaluation — frozen artifacts](evaluation.md#spec-evaluation-pre-p6) |
| `EVALUATION.PREFLIGHT` | Task/evaluator preflight | [Evaluation — preflight](evaluation.md#spec-evaluation-preflight) |
| `EVALUATION.MEASURED-EVALUATION` | Measured candidate patches | [Evaluation — measured runs](evaluation.md#spec-evaluation-measured-evaluation) |
| `REVIEW.LOOP` | Review automation and human checkpoints | [Review loop](review-loop.md#spec-review-loop) |

## Run checks

From the repository root, use Python 3.12+ in a virtual environment and Node.js 18+. The package, architecture checker, and tests use only the standard library; coverage.py is test-only. No credentials are needed:

```sh
python3 -m pip install -e . -r tests/requirements.txt
python3 -m scripts.check_architecture
python3 -m coverage run --branch -m unittest discover -s tests -p 'test_*.py' -v
python3 -m coverage report --fail-under=90
node --test tests/review-workflow.test.mjs
git diff --check
```

The bootstrap tests verify the package layers import without harness/provider dependencies and that the architecture check rejects absolute, relative, dynamic, SQLite, and harness imports from core. Coverage must remain at least 90%. The document tests check the practical P6-AC contract, including the direct A/C
comparison, six-task target with one agent/evaluator run per task, the compact
manifest, operational continuation decision, simple resource limits, explicit
hosted-model identity limits, sensitivity reporting, pre-measurement task
exclusions, candidate-patch failure classification, durable run registration
with metadata-conflict protection, bounded journal reads, exclusive ownership,
serialized restart recovery, mapped requirement anchors, and relative document
links. These are document regression checks, not proof that a future provider
or governor implements the prose.

In CI, the whitespace check uses the actual event range: pull requests compare the base and head SHAs, while pushes compare the event's previous and current SHAs. The checkout fetches complete history so both endpoints are available; a new-branch push falls back to the new commit's parent.

The Node suite extracts and executes the actual inline script in the review-request workflow with a mocked GitHub client. It checks trusted-marker deduplication, spoofed/missing comments, new heads, pagination arguments, and API failure propagation. It also checks the pinned review action, least-privilege permissions, and the event-aware whitespace contract. No comments or reviews are posted. It does not validate GitHub event delivery or prove that the external Codex integration accepts the bot's request.

The package, architecture, and specification-check workflow runs these checks with read-only repository permission and no repository secrets. The separate review-request workflow uses write permissions to post its review request. Its trusted `pull_request_target` context must never check out or execute PR-head code.

## Regression evidence and implementation fixtures

Document checks protect contract wording. Historical audit context belongs in the
[P0 audit](p0-audit.md); current pass/fail status comes from the test runner.

Two reasoning fixtures motivate implementation tests:

- **Serialized recovery:** a proposal receipt is durable before evaluation. A crash leaves it incomplete; after restart the exclusive owner replays or resumes the same normalized request by proposal ID, without creating a second final outcome. Test real open/close/crash recovery in issue #16; this document does not implement a lock.
- **Preflight:** run the evaluator on a separate smoke fixture before measured execution. A task-specific setup failure records a reason without authorizing task substitution; a shared failure before measured execution stops the pilot. Test this in the benchmark adapter without opening any selected P6 task.

P1/P3/P6 issues retain responsibility for real persistence, isolation, evidence, and evaluator behavior tests. A passing document check cannot replace those suites. Do not materialize or execute selected P6 tasks while adding these checks.

The superseded bootstrap fixtures remain historical audit evidence, not part of
P6-AC. Runtime suites must verify adapter capabilities, live evaluator behavior,
durable receipt recovery, and rejection of missing or stale graph-version
bindings against their normative contracts. Passing document checks cannot
establish those runtime properties.
