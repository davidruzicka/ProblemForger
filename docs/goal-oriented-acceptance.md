# Goal-oriented acceptance scenarios

## Purpose and authority

Tests target the problem being solved: an operator must be able to recover
authoritative work state and distinguish supported progress from a plausible
completion claim. Code structure, schema agreement, and passing local checks
are supporting evidence, not the definition of success.

This document translates existing contracts into acceptance scenarios for
[P2 #3](https://github.com/davidruzicka/ProblemForger/issues/3) and
[P3 governance #4](https://github.com/davidruzicka/ProblemForger/issues/4).
P2 replay [#42](https://github.com/davidruzicka/ProblemForger/issues/42) and
service integration [#43](https://github.com/davidruzicka/ProblemForger/issues/43)
are closed implementation issues.
It is a test-design checklist, not a new normative policy or evidence that these
behaviors are implemented. The linked specifications and accepted ADRs retain
authority. It adds no completion operation, status enum, protocol field, or
automatic dependency-invalidation algorithm.

## Design tests from the problem

For new scenarios, record before implementation:

1. The operator's objective and the requirement whose failure matters.
2. A concrete starting state, action or interruption, and externally observable
   expected result, including an example that must not be accepted.
3. The independent oracle: fixed expected facts or a separately specified
   behavioral check. Do not obtain expected results by running the same
   production projection, validator, or governor under test.
4. The public or port boundary exercised, permitted actor, immutable subjects,
   and retained evidence needed to diagnose a failure.
5. The implementing test and its failing-before/passing-after evidence. For
   existing behavior, map the scenario to tests and their observable assertions;
   do not require a retrospective failing-before run.

Keep structural/unit tests as additional diagnostics. A fixture declaring itself
valid is not an independent demonstration of the intended behavior. Multiple
implementations agreeing is useful, but both must also match the independent
oracle; they can share the same bug.

Use synthetic development work, not selected P6 tasks. Keep the
[frozen evaluation](evaluation.md#spec-evaluation-pre-p6) unchanged.

## P2: recoverable and consistent authoritative state

Use a small synthetic investigation: one run contains its authorized root
objective, a requirement, two dependent tasks, and an artifact reference. A
separate run deliberately reuses entity identifiers to expose scope mistakes.
Fix the expected entities, relationships, lifecycle, creation provenance, and
graph versions by hand before invoking the implementation. Assert domain facts,
not incidental representation or private helper calls.

Use graph-contract-valid history and an explicitly authorized anchor setup path.
Replay fixtures may use authorized committed history; worker integration must not
invent an anchor-creation bypass. If a supported bootstrap route is unavailable,
record that prerequisite as unmet rather than weakening protection to make tests
pass.

| ID | Problem and action | Acceptance oracle and counterexample |
| --- | --- | --- |
| P2-RECOVER | The operator resumes work after the SQLite service closes and restarts, with telemetry absent. | Public state and creation provenance match the fixed pre-restart facts and committed version. Missing tasks, invented state, or a reset version fail. Compare memory/SQLite replay against the same facts; only the durable provider proves process-restart persistence. |
| P2-ATOMIC | A dependent task and its required relationship form one mutation; interrupt before or after durable commit. Also submit a batch with an invalid later operation. | An observer sees the complete old or complete new committed state, never a dangling task or a partially applied batch. A successful batch advances one version; an invalid batch leaves graph state/version unchanged. Retained audit history is checked separately. |
| P2-RETRY | The service commits work, but its response is lost; the operator resubmits the identical proposal after restart. | The original durable outcome replays, with exactly one accepted change and no second version increment. Reusing that proposal ID for different work fails without changing state. |
| P2-STALE | Two actions are prepared from the same graph version; one commits before the other arrives. | The second cannot overwrite newer accepted work. Its explicit conflict is durable and graph state matches the first action only; a claimed completed conflict without durable audit fails. |
| P2-HISTORY | A task is explicitly superseded or invalidated while its prior relationships remain relevant to explaining earlier work. | Current projection retains the inactive entity and its historical provenance. Earlier journal facts remain unchanged. Neither deletion nor a fabricated recursive lifecycle change is acceptable; evidence admissibility belongs to P3. |
| P2-ISOLATE | The operator queries or mutates one of two runs with overlapping entity IDs; an unauthorized caller also attempts access. | Only the explicit authorized run is read or changed. No other-run entities or private metadata appear. Audit/telemetry-only additions do not alter either graph. Authorization and public redaction are exercised at the service boundary. |
| P2-UNKNOWN | Recovery encounters an unsupported graph event version or structurally invalid committed history. | Recovery fails explicitly instead of returning a plausible partial graph as complete. A valid control history still reconstructs the fixed expected state. |

Owners: [graph model](problem-graph.md#spec-graph-model),
[EventStore contract](modules.md#spec-modules-eventstore-port),
[proposal recovery](protocol.md#spec-protocol-proposal-recovery), and
[ADRs 0002](adr/0002-event-sourced-authoritative-state.md) and
[0006](adr/0006-authoritative-domain-events-and-stream-concurrency.md).
Service tests also resolve the applicable recovery/redaction/authorization gaps
tracked by closed issues #24, #25, and #26 through #43. This checklist does not choose their
precedence or access policy.

### Existing P2 test coverage

The tests below cover parts of the scenarios. They use smaller fixtures than the
synthetic investigation above; the full scenarios are not established by this
mapping. Assess remaining coverage under #3 and track confirmed gaps separately.

| Scenario | Existing test evidence | Remaining scenario coverage to assess |
| --- | --- | --- |
| P2-RECOVER | `tests/test_graph_replay.py::GraphReplayTests.test_lifecycle_evidence_audit_and_run_isolation_survive_restart` checks SQLite reopen and projection equality; `test_empty_and_multievent_batch_across_every_page_boundary` checks fixed provenance and version. | Public service restart with the complete fixed investigation and absent telemetry. |
| P2-ATOMIC | `tests/test_graph_service.py::GraphServiceTests.test_invalid_or_protected_batches_leave_graph_unchanged` checks rejected batches; `test_commit_replay_conflict_and_public_redaction` checks a committed version. | Interruption immediately before and after commit and the complete old-or-new observer result. |
| P2-RETRY | `tests/test_graph_service.py::GraphServiceTests.test_commit_replay_conflict_and_public_redaction` checks retry, changed input, and SQLite reopen. | Explicitly simulate a lost response and verify the complete scenario state. |
| P2-STALE | `tests/test_graph_service.py::GraphServiceTests.test_graph_append_conflict_is_durable_before_response` checks conflict and replay; `test_commit_replay_conflict_and_public_redaction` checks stale conflict. | Compare the full fixed state and retained audit facts for both prepared actions. |
| P2-HISTORY | `tests/test_graph_replay.py::GraphReplayTests.test_lifecycle_evidence_audit_and_run_isolation_survive_restart` checks retained lifecycle and SQLite replay. | Assert the full historical provenance and absence of recursive lifecycle changes in the proposed fixture. |
| P2-ISOLATE | `tests/test_graph_service.py::GraphServiceTests.test_authorization_precedes_every_store_access_including_create_retry` checks denied access; `test_commit_replay_conflict_and_public_redaction` checks redaction. | Exercise two populated runs with overlapping entity IDs through the service and verify both states. |
| P2-UNKNOWN | `tests/test_graph_replay.py::GraphReplayTests.test_invalid_committed_batches_fail_without_returning_partial_state` and `test_corrupt_versions_and_batch_boundaries_fail_closed` exercise invalid history. | Confirm the specific unsupported event-version case and fixed valid control against this scenario. |

## P3: evidence-backed progress toward the actual goal

Use an independently specified synthetic user requirement: an export must include
every eligible record exactly once and preserve its amount. The acceptance
fixture fixes input records, eligibility rules, and expected rows/amounts before
candidate code is written. A deliberately incomplete candidate exports only the
first eligible record while passing its own narrow formatting test. A correct
control candidate exports the independently expected result.

Concrete development input (amounts are exact decimal values):

| Record ID | Status | Amount |
| --- | --- | --- |
| A | ready | 10.25 |
| B | excluded | 99.00 |
| C | ready | 7.50 |

Only `ready` records are eligible. The expected output is exactly the multiset
`{(A, 10.25), (C, 7.50)}`, each once, with no B; ordering is irrelevant. The
faulty candidate returns only `(A, 10.25)`. Its formatting test can pass while
the independently specified coverage check fails. Missing/duplicate records,
included B, or changed amounts fail acceptance even if the output parses.

“Completion claim” below means the assertion being evaluated by the test; it
does not introduce a new graph completion API. Before implementation, #4 must
map each claim to the existing proposal/evidence surface and specify exact
governance outcomes and reasons in its policy. An unspecified mapping is a
design gap, not permission to invent a runtime behavior in a test.

| ID / owner | Problem and action | Acceptance oracle and counterexample |
| --- | --- | --- |
| P3-GOAL / #4 | The incomplete export passes all its own local tests and is presented as satisfying the root requirement. | Independent expected rows reveal the omitted record. Narrow passing evidence cannot establish the broader claim. The correct control has valid scoped support; blanket refusal is not a successful solution. |
| P3-SUBJECT / #4 | A valid export is checked, then its contents change to omit a record while the old passing evidence is reused. | Old evidence remains historical support for the original digest only. It cannot satisfy a requirement for the changed subject; new matching evidence is needed. A mutable filename or copied digest assertion is insufficient. |
| P3-DEPENDENCY / #4 | A downstream conclusion relies on an eligibility interpretation that later receives contradictory evidence or explicit invalidation. | Historical acceptance remains auditable; prior local passes alone cannot establish current root-goal support. Exercise the separately specified policy for reassessing affected support. Do not assume automatic recursive lifecycle changes or invent a propagation algorithm. |
| P3-ANCHOR / #4 | The worker tries to redefine success as exporting only the first record, remove the coverage requirement, or change its acceptance threshold. | Without the authorized meta-operation, the protected requirement remains unchanged. Passing checks against the weakened substitute do not demonstrate the original goal. |
| P3-TRUST / #4 | The incomplete candidate supplies invented producer metadata and claims an independent checker approved it. | Worker assertions cannot satisfy trusted-evidence requirements. Include a genuine registered-producer control; producer trust alone still does not establish that the check covers the whole goal. |
| P3-RECOVERY / #4 | A decision is retried/recovered after restart with telemetry disabled, and an external evidence location now has different bytes. | Completed decisions replay their historical outcome; incomplete recovery uses the frozen identities and owning recovery rules. New external content cannot silently replace the checked result. Missing required evidence produces the specified explicit recovery failure. |

Owners: [local and global verification](verification.md#local-and-global-verification),
[evidence trust](verification.md#spec-verification-evidence-trust),
[subject binding](verification.md#spec-verification-evidence-binding),
[evidence recovery](verification.md#spec-verification-evidence-recovery), and
[ADRs 0004](adr/0004-external-graph-governor.md) and
[0007](adr/0007-separate-lifecycle-verification-and-evidence-axes.md).

If a semantic property has no defensible oracle, preserve the missing evidence
and apply the specified uncertainty/escalation policy. Do not manufacture a
deterministic proof from a model's agreement or a passing unrelated test.

## Completion evidence

Map scenario IDs to executable tests and retained results in the active issue or
follow-up. For new behavior, record expected outcomes before running the candidate,
show that the faulty case is detected, and show that the supported control
succeeds. Run relevant regression suites and all
[required checks](specification-checks.md#run-checks).

Document-link, schema, and lifecycle-table checks establish only their respective
properties. None marks these scenarios as behaviorally covered. P2 completion
does not establish P3 goal satisfaction; P3 acceptance examples do not establish
general reliability gains, customer value, or calibrated success probabilities.
