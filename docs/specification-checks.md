# Specification ownership and checks

## Contract ownership

Accepted ADRs own architectural decisions. The operational specifications below
own their detailed algorithms and interfaces. Change an ADR first when a
proposed algorithm conflicts with its decision. Plans, issues, and audit reports
define work or record evidence; they link to these IDs instead of maintaining a
second copy of the contract.

Stable requirement IDs are metadata on normative headings. The table is the
single navigation map; the linked document is the only normative definition.

| Requirement ID | Contract | Normative owner |
| --- | --- | --- |
| `GRAPH.MODEL` | Problem-graph vocabulary and lifecycle | [Problem graph](problem-graph.md#spec-graph-model) |
| `MODULES.EVENTSTORE-PORT` | EventStore port and provider contract | [Modules — EventStore](modules.md#spec-modules-eventstore-port) |
| `PROTOCOL.PROPOSAL-RECOVERY` | Proposal identity, recovery, and fencing | [Protocol — proposal recovery](protocol.md#spec-protocol-proposal-recovery) |
| `PROTOCOL.STORE-OWNER` | Exclusive durable-store ownership | [Protocol — STORE-OWNER](protocol.md#spec-protocol-store-owner) |
| `PROTOCOL.LEASE-CLOCK` | Restart-stable lease time | [Protocol — LEASE-CLOCK](protocol.md#spec-protocol-lease-clock) |
| `VERIFICATION.EVIDENCE-TRUST` | Trusted evidence producers and local isolation | [Verification — EVIDENCE-TRUST](verification.md#spec-verification-evidence-trust) |
| `VERIFICATION.EVIDENCE-BINDING` | Immutable evidence/subject binding | [Verification — EVIDENCE-BINDING](verification.md#spec-verification-evidence-binding) |
| `VERIFICATION.EVIDENCE-RECOVERY` | Evidence retention and restart behavior | [Verification — EVIDENCE-RECOVERY](verification.md#spec-verification-evidence-recovery) |
| `EVALUATION.MODEL` | P6 model and runtime selection | [Evaluation — Model](evaluation.md#spec-evaluation-model) |
| `EVALUATION.PRE-P6` | Pre-P6 frozen artifacts | [Evaluation — frozen artifacts](evaluation.md#spec-evaluation-pre-p6) |
| `EVALUATION.PREFLIGHT` | Task/evaluator preflight | [Evaluation — preflight](evaluation.md#spec-evaluation-preflight) |
| `EVALUATION.MEASURED-EVALUATION` | Measured candidate patches | [Evaluation — measured runs](evaluation.md#spec-evaluation-measured-evaluation) |
| `REVIEW.LOOP` | Review automation and human checkpoints | [Review loop](review-loop.md#spec-review-loop) |

## Run checks

From the repository root, use Python 3.12+ in a virtual environment and Node.js 18+. The pinned NumPy dependency is only for the analysis reference checks; no credentials are needed:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/review-workflow.test.mjs
git diff --check
```

The Python suite checks the P6-AC practical contract, including the direct A/C
comparison, eight-task target with predeclared reserves, operational continuation
decision, resource-envelope interpretation, predeclared model/fallback behavior,
content-addressed runtime identity with explicit hosted-model limitations,
conditional native-generation controls and the separate harness-comparison
contract, sensitivity reporting, distinct image materialization/setup phases,
pre-measurement task-artifact exclusions, candidate-patch failure
classification, durable run registration with metadata-conflict protection and
bounded journal reads, owner-plus-epoch fencing, non-rewindable lease recovery
across provider generations, mandatory completion of both evaluator repetitions
unless an experiment-wide stop applies, the absence of the obsolete mandatory
third control, single normative homes for the lease-clock and EventStore port
contracts, mapped requirement anchors, and relative document links. These are
document regression checks, not proof that a future provider or governor
implements the prose.

In CI, the whitespace check uses the actual event range: pull requests compare the base and head SHAs, while pushes compare the event's previous and current SHAs. The checkout fetches complete history so both endpoints are available; a new-branch push falls back to the new commit's parent.

The Node suite extracts and executes the actual inline script in the review-request workflow with a mocked GitHub client. It checks trusted-marker deduplication, spoofed/missing comments, new heads, pagination arguments, and API failure propagation. It also checks the pinned review action, least-privilege permissions, and the event-aware whitespace contract. No comments or reviews are posted. It does not validate GitHub event delivery or prove that the external Codex integration accepts the bot's request.

The specification-checks workflow runs these commands with read-only repository permission and no repository secrets. The separate review-request workflow uses write permissions to post its review request. Its trusted `pull_request_target` context must never check out or execute PR-head code.

## Regression evidence for the P0 audit fixes

Before the specification edits, the Python suite reported failures for missing store ownership, missing trusted evidence ingress, missing immutable/recoverable evidence, the mandatory third preflight, and duplicated clock formulas. The existing relative links passed. The mocked workflow cases passed before and after the edits; no workflow behavior change was necessary.

Two reasoning fixtures motivate implementation tests:

- **Clock ownership:** A anchors at 1,000 seconds; B opens at 1,100 seconds after a forward UTC jump and claims a 30-second lease. After 31 seconds, A reads 1,031 and incorrectly considers B's 1,130 deadline unexpired. The P1 solution rejects B's open, rather than treating an independently anchored provider as supported. Test real racing opens, aliases, crash release, and restart in issue #16; this document does not implement a lock.
- **Preflight:** complete vectors `[fail, pass]` and `[pass, pass]` already establish instability. None of the four possible third binary vectors can make all vectors equal. A diagnostic infrastructure failure must not change the task result or abort the experiment. Test this in the benchmark adapter without opening any selected P6 task.

P1/P3/P6 issues retain responsibility for real persistence, isolation, evidence, and evaluator behavior tests. A passing document check cannot replace those suites. Do not materialize or execute selected P6 tasks while adding these checks.

## Follow-up review regression evidence

The added document checks failed on the previous head (including caller-provided claim/renewal deadlines, optional or omitted graph-append fencing, and unspecified bootstrap stream allocation). They pass after the contract corrections. Exact suite counts are intentionally not duplicated here because the test runner is the source of current pass/fail status.

The three new Python contract checks (ordered model-chain exhaustion, complete
HarnessX runtime identity, and mandatory completion of the other evaluator
repetition) and the two workflow checks (full action pin/least privilege and
event-aware diff range) were red on the preceding PR head; they pass on the current
head. This red-to-green record covers the newly fixed review findings and is still
documentation/test evidence, not proof of live provider behavior.

The expiry-before-reclaim lease check was also red before the latest protocol fix:
the previous contract checked only `claim_epoch`, not an active unexpired lease.
It now requires an atomic `lease_expires_at_ms > lease_now_ms` check for renewal,
finalization, and graph append. The regression check passes after that fix.

The methodology regression checks now pin the practical-effect decision boundaries
and secondary sensitivity calculations, reject silent temperature fallback, keep
harness comparison separate from P6, and constrain task-artifact exclusions to the
pre-measurement common-task freeze. These checks protect the contract wording; they
do not substitute for adapter capability probes or live harness/evaluator tests.

The superseded bootstrap fixtures remain only as historical audit evidence and are
not part of P6-AC. P1 provider tests must still prove transactional TTL
calculation, expiry-before-reclaim rejection, and rejection of missing/stale
fencing; document checks are not a substitute for those runtime tests.
