# Specification ownership and checks

## Contract ownership

Accepted ADRs own architectural decisions. The operational specifications below own their detailed algorithms. Change an ADR first when a proposed algorithm conflicts with its decision. Plans and issues define work and acceptance evidence; they reference these sources instead of maintaining another copy of an algorithm.

| Contract | Normative operational source |
| --- | --- |
| Proposal identity, request hash, recovery, and fencing | [Protocol](protocol.md#proposal-identity-idempotency-and-recovery) |
| Exclusive durable-store ownership | [STORE-OWNER](protocol.md#store-owner) |
| Restart-stable lease time | [LEASE-CLOCK](protocol.md#lease-clock) |
| Trusted evidence producers and local isolation | [EVIDENCE-TRUST](verification.md#evidence-trust) |
| Immutable evidence/subject binding | [EVIDENCE-BINDING](verification.md#evidence-binding) |
| Evidence retention and restart behavior | [EVIDENCE-RECOVERY](verification.md#evidence-recovery) |
| Provider port and contract-suite responsibilities | [Modules](modules.md) |
| Bootstrap stream and reference computation | [BOOTSTRAP-RNG](evaluation.md#bootstrap-rng) |
| P6 model selection and HarnessX runtime freeze | [Evaluation — Model](evaluation.md#model), [Pre-P6 frozen artifacts](evaluation.md#pre-p6-frozen-artifacts) |
| P6 task selection, ordering, outcomes, metrics, and raw data | [Evaluation](evaluation.md) |
| Review automation and human checkpoints | [Review loop](review-loop.md) |

Stable requirement IDs are section headings in the owning specification. A reference is not a second definition. Audit reports record past findings and changes, not current algorithms.

## Run checks

From the repository root, use Python 3.12+ in a virtual environment and Node.js 18+. The pinned NumPy dependency is only for the analysis reference checks; no credentials are needed:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/review-workflow.test.mjs
git diff --check
```

The Python suite executes the normative bootstrap reference against golden synthetic fixtures for N=8..12, verifies input-order and RNG-state isolation, and checks invalid inputs. It also checks the corrected specification boundaries, including the predeclared model chain and post-exposure exhaustion rule, the content-addressed HarnessX runtime lock, mandatory completion of both candidate evaluator repetitions unless an experiment-wide stop applies, the absence of the obsolete mandatory third control, a single home for the lease-clock algorithm, and relative document links. These are document regression checks, not proof that a future provider or governor implements the prose.

In CI, the whitespace check uses the actual event range: pull requests compare the base and head SHAs, while pushes compare the event's previous and current SHAs. The checkout fetches complete history so both endpoints are available; a new-branch push falls back to the new commit's parent.

The Node suite extracts and executes the actual inline script in the review-request workflow with a mocked GitHub client. It checks trusted-marker deduplication, spoofed/missing comments, new heads, pagination arguments, and API failure propagation. It also checks the pinned review action, least-privilege permissions, and the event-aware whitespace contract. No comments or reviews are posted. It does not validate GitHub event delivery or prove that the external Codex integration accepts the bot's request.

The specification-checks workflow runs these commands with read-only repository permission and no repository secrets. The separate review-request workflow uses write permissions to post its review request. Its trusted `pull_request_target` context must never check out or execute PR-head code.

## Regression evidence for the P0 audit fixes

Before the specification edits, the Python suite reported five failures: missing store ownership, missing trusted evidence ingress, missing immutable/recoverable evidence, the mandatory third preflight, and duplicated clock formulas. The existing relative links passed. All nine mocked workflow cases passed before and after the edits; no workflow behavior change was necessary.

Two reasoning fixtures motivate implementation tests:

- **Clock ownership:** A anchors at 1,000 seconds; B opens at 1,100 seconds after a forward UTC jump and claims a 30-second lease. After 31 seconds, A reads 1,031 and incorrectly considers B's 1,130 deadline unexpired. The P1 solution rejects B's open, rather than treating an independently anchored provider as supported. Test real racing opens, aliases, crash release, and restart in issue #16; this document does not implement a lock.
- **Preflight:** complete vectors `[fail, pass]` and `[pass, pass]` already establish instability. None of the four possible third binary vectors can make all vectors equal. A diagnostic infrastructure failure must not change the task result or abort the experiment. Test this in the benchmark adapter without opening any selected P6 task.

P1/P3/P6 issues retain responsibility for real persistence, isolation, evidence, and evaluator behavior tests. A passing document check cannot replace those suites. Do not materialize or execute selected P6 tasks while adding these checks.

## Follow-up review regression evidence

Three added document checks failed on the previous head (six failing subcases): caller-provided claim/renewal deadlines, optional or omitted graph-append fencing, and unspecified bootstrap stream allocation. They pass after the contract corrections. The complete suite now has 16 Python tests and 11 workflow-script tests.

The three new Python contract checks (ordered model-chain exhaustion, complete
HarnessX runtime identity, and mandatory completion of the other evaluator
repetition) and the two workflow checks (full action pin/least privilege and
event-aware diff range) were red on the preceding PR head; they pass on the current
head. This red-to-green record covers the newly fixed review findings and is still
documentation/test evidence, not proof of live provider behavior.

The expiry-before-reclaim lease check was also red before the latest protocol fix:
the previous contract checked only `claim_epoch`, not an active unexpired lease.
It now requires an atomic `lease_expires_at_ms > lease_now_ms` check for renewal,
finalization, and graph append, and passes in the current 16-test suite.

The bootstrap fixtures fix the full index-matrix digest and both confidence intervals for every permitted retained task count. The reference sorts tasks, initializes once, draws once, and shares the draw across ordered comparisons. A separate scalar calculation verified the interval reductions for N=8 and N=12. P1 provider tests must still prove transactional TTL calculation, expiry-before-reclaim rejection, and rejection of missing/stale fencing; document checks are not a substitute for those runtime tests.
