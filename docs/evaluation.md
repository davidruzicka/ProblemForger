# P6-AC practical whole-system pilot

<a id="p6-practical-pilot"></a>

P6 is a practical feasibility pilot. It asks whether the complete
ProblemForger package is useful on a small, real workflow. It is not an
academic population study, a calibration study, or a claim of exact hosted
model replay. Academic uncertainty is acceptable; correctness, isolation,
durable-audit, and honest reporting are not optional.

This document is the pre-measurement P6-AC-v1 contract. It replaces the earlier
unmeasured multi-stage draft. Changes after the first measured slot require a
new manifest/version and must not be silently pooled with the old one.

## Scope and configurations

P6 compares two complete configurations on the same HarnessX workflow:

- **A — baseline:** the existing HarnessX workflow and benchmark adapter;
- **C — complete package:** the same workflow plus the ProblemForger service,
  explicit graph interaction, and deterministic governance.

A and C use the same selected model, task order, harness, benchmark adapter,
resource limits, and evaluator. The intended A→C difference is the
ProblemForger package. Configuration B, additional models, and a second harness
are useful later diagnostics, not prerequisites for this pilot.

The pilot uses six tasks selected by a deterministic benchmark-adapter rule.
There is one fresh agent run per task/configuration and one evaluator run for
each produced candidate patch, except when trusted validation rejects it as
`CANDIDATE_PATCH_INVALID`: that terminal outcome records
`evaluator_invocation: NOT_DISPATCHED` and has no evaluator run. The planned
size is therefore twelve A/C slots and at most twelve candidate-patch
evaluations; invalid-patch terminalizations are counted separately. An eligible
first-attempt
failure can require one clean whole-slot retry, so the actual agent attempt
count can exceed twelve and must be reported separately from the planned slot
count. These counts describe an operational pilot, not statistical precision.

Out of scope for P6: holdout/calibration data, fallback-model chains,
population-level uncertainty, automatic routing, Pi portability, and a full
A/B/C ablation. Those require their own measured question and manifest.

<a id="spec-evaluation-model"></a>
<!-- spec-id: EVALUATION.MODEL -->
## Model and provider

P6 selects one provider/model entry before the manifest is frozen. Record the
requested model identifier, provider, endpoint/deployment when relevant, all
observable generation settings, and `temperature=0` when the provider supports
it. The same request settings are used for A and C.

P6 has no implicit fallback. If the selected model is unavailable before task
exposure, fix the setup or create a new manifest; do not silently choose a
different model. If it becomes unavailable after exposure, preserve the
affected missing slots and continue independent slots where possible. A new
model requires a new experiment version.

<a id="p6-hosted-model-metadata"></a>
### Hosted-model identity limits

The manifest identifies the requested API entry and observable settings, not
necessarily the exact weights or future provider execution. Record provider
revision, deployment/build identifier, response-version header, or equivalent
metadata when the provider exposes it. Record `UNKNOWN` explicitly when it does
not.

A digest of the harness or runtime image identifies those bytes. It does not
prove that a hosted provider will use the same model implementation later, or
that future inference will be bit-for-bit identical. A local model may include
its weights, configuration, and inference runtime in the content-addressed
identity; a hosted model cannot be upgraded into that guarantee by hashing the
client image.

## Pre-P6 manifest

<a id="spec-evaluation-pre-p6"></a>
<!-- spec-id: EVALUATION.PRE-P6 -->

Before exposing any selected task to the agent, freeze one compact manifest
containing:

- manifest version and experiment ID;
- benchmark adapter source/version and its deterministic task-selection rule;
- the six task IDs and fixed order;
- selected provider/model metadata and generation settings;
- HarnessX source/runtime identity and the ProblemForger service source/runtime
  identity;
- effective graph-intervention content identity for each configuration (version
  and digest, or `NONE`), covering agent-visible graph tools, schemas,
  graph-use instructions, schema/version, query bounds/defaults, serialization,
  resolved defaults, and adapter mapping;
- effective governance-policy content/configuration identity for each
  configuration (version and digest, or `NONE`), covering decision rules,
  thresholds, required evidence, resolved defaults, and policy configuration;
- complete ordered A/C slot list: each task's A slot before its C slot;
- execution platform, dependency lockfiles, and image/archive digests when
  images or archives are used;
- evaluator version and required-test definition, plus evaluator adapter/source/runtime identity, and evaluator-identity verification profile, frozen as `evaluator_verification_profile`;
- workspace isolation mode, candidate sandbox policy identity/configuration,
  and worker/agent network policy identity;
- agent semantic deadline, evaluator wall-clock allowance, resource limits, retry
  rule, and human-intervention definition;
- primary result rule, secondary cost/latency measures, and continuation
  tolerances;
- random seeds where a component actually uses randomness.

The evaluator adapter/source/runtime identity is a content identity of the
loaded adapter and source/runtime artifacts, resolved evaluator configuration,
and runtime/dependency inputs; a version label alone is not sufficient.

The evaluator-identity verification profile is frozen before manifest hashing.
It is `evaluator_verification_profile` and contains
`verification_method`, `checker_version`,
`verifier_command_identity`, and
`effective_verifier_configuration`. `verifier_command_identity` binds the complete verifier execution identity:
retained checker executable/script bytes, its interpreter/runtime, and all
transitive checker/helper dependency bytes—or a pinned image/archive containing
them—each by immutable reference and SHA-256 digest, plus its entry point. `effective_verifier_configuration` records
behavior-affecting arguments, environment, resolved defaults, dependency roots
relative to pinned artifacts, symlink handling, and transitive-content
traversal rules, including immutable identities of referenced configuration
content. The profile preserves all required loaded-artifact and
transitive-content coverage; a matching profile alone is not proof of coverage.
The profile and referenced content are fixed before manifest hashing and contain
no `manifest_hash`, computed evaluator identity, or post-freeze evidence,
invocation, or result references. Per-execution subject/scope bindings remain
in the verification record. The frozen manifest and each verification-record digest cover the profile;
neither depends on a future evidence digest.

For every clean-baseline execution and candidate evaluator launch, the trusted
runner persists an immutable `EVALUATOR_IDENTITY_VERIFIED` record before
execution or launch. Its schema is
`EVALUATOR_IDENTITY_VERIFIED_V1`; a trusted recorder sets
`verification_result=VERIFIED` only after checking the actual loaded and
pinned artifacts. The record contains the frozen `manifest_hash`, the
baseline or evaluator-invocation scope, the observed
`evaluator_adapter_source_runtime_identity` recomputed from those artifacts,
the effective `evaluator_verification_profile` actually used, including
`verification_method`, `checker_version`,
`verifier_command_identity`, and
`effective_verifier_configuration`. The trusted runner observes this profile
from the invocation; it is not copied from the manifest. The profile and its
referenced checker/configuration content are part of the normalized record
bytes covered by `evaluator_identity_evidence_sha256`; they are content
identities, not mutable labels. It also contains non-empty `artifact_refs`
entries of
`{role, ref, sha256}` covering the adapter, source, resolved configuration,
runtime, dependencies, transitively referenced evaluator content, and all
verifier command identity content. The record is
created from the artifacts actually loaded and pinned for that execution;
mutable paths, copied manifest labels, and version labels are not evidence.
The record also contains `producer_id` and `producer_provenance`, assigned
through the approved evidence-producing integration under EVIDENCE-TRUST, not
accepted from worker/candidate claims. `producer_id` identifies the
authenticated producer and `producer_provenance` identifies its assigned
origin/integration plus a non-self-referential producer-assignment identifier.
After the unsigned canonical payload is frozen and its evidence reference and
digest are computed, the trusted recorder emits a separate immutable
`EVALUATOR_PRODUCER_ATTESTATION_V1` envelope. The envelope authenticates the
trusted recorder and binds `producer_id` and `producer_provenance` to the
exact `evaluator_identity_evidence_ref` and
`evaluator_identity_evidence_sha256`; generic producer registration is not
sufficient. The V1 record carries only `producer_attestation_ref` as a
non-self-referential metadata identifier outside the unsigned canonical payload.
The attestation reference is derived from the envelope with its own reference
omitted, and the payload does not contain that reference, so this construction
is acyclic. The presence of producer fields or a matching content digest alone
does not establish trusted provenance. The V1 record has an unsigned canonical
payload that includes `producer_id` and `producer_provenance` and omits
`evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`,
and `producer_attestation_ref`. Its content-addressed immutable reference and
SHA-256 digest are both derived from that payload; neither self-derived field is
part of its own preimage. This introduces no manifest/evidence hash cycle. The
evidence reference and digest bind the complete V1 payload, including
`producer_id` and `producer_provenance`, while consumer records bind
`producer_attestation_ref` alongside them into the corresponding
`BASELINE_VECTOR_VERIFIED`, evaluator `STARTED`, and terminal result
records. A missing, unreadable, corrupt, untrusted, or mismatched record,
reference, digest, or referenced artifact is `EVIDENCE_INCOMPLETE` and
prevents execution, launch, reuse, and scoring.

The manifest is hashed and retained with every run. A compact manifest is
intentional: it pins the inputs needed to operate and interpret the pilot
without pretending that every opaque provider behavior is content-addressable.
The manifest hash is finalized before any measured-run evidence is created. It
contains no IDs or references to post-freeze evidence records. The
`NETWORK_DENIAL_VERIFIED`, `BASELINE_VECTOR_VERIFIED`, each attempt-specific
`WORKER_NETWORK_DENIAL_VERIFIED`, and every `EVALUATOR_IDENTITY_VERIFIED`
record are immutable post-freeze evidence: each records the frozen
`manifest_hash` plus the bindings relevant to its scope, while consumer
records store its evidence reference. Creating, retaining, or validating these
records never mutates or rehashes the manifest.

For P6, A records `NONE`; C requires non-null intervention and governance
identities. Retain the identified content, including resolved defaults. Before
each slot's first dispatch and on recovery, the trusted runner verifies the
loaded graph intervention against the manifest, and the service verifies its
loaded governance policy/configuration. A mismatch prevents dispatch or
recovery and must not be repaired by relabeling existing evidence.

### What the execution image is for

An execution image is an implementation artifact, not a scientific identity
claim. It is useful for pinning the harness, benchmark tooling, interpreter,
dependencies, and—when packaged there—the local ProblemForger service. The
image digest helps detect environment drift and makes setup repeatable. It does
not identify a hosted provider's model or later provider-side optimizations.

If no container/image is used, record the equivalent source revision,
dependency-lockfile hash, interpreter version, and platform. Do not invent an
image merely to obtain a digest.

## Task selection and preflight

The candidate execution contract requires network-free evaluator
compatibility. The benchmark adapter's eligibility predicate therefore
requires that required tests and task setup must be network-free: they may not
require DNS, external sockets, loopback, local HTTP/DB/browser-driver
services, or arbitrary IPC. Only `CANDIDATE_EVAL_IPC_V1` is allowed for
candidate/evaluator communication. The eligibility predicate must also prove
that every required test and fixture preserves the frozen required-test
semantics through `CANDIDATE_EVAL_IPC_V1`: candidate code runs outside the
trusted evaluator process, and the trusted side does not disclose hidden test
or fixture code, expected outputs, or assertions to the candidate. Tasks that
require trusted-process candidate execution, candidate imports or monkeypatching
inside the evaluator, or another IPC/host path are ineligible. Prove this from
pinned task metadata, evaluator adapter/source/runtime identity, and the frozen
required-test definition before selecting the six tasks. If the predicate
cannot be proved, the task is ineligible. Do not inspect a selected task's
gold patch while evaluating this predicate.
The same eligibility predicate requires at least one non-empty `FAIL_TO_PASS`
test vector. A task with an empty `FAIL_TO_PASS` vector is ineligible; this
makes the success rule non-vacuous.

The benchmark adapter selects six eligible tasks deterministically from its
declared candidate order. Development and smoke tasks must be separate from
the selected IDs. No selected task is inspected for its gold patch while the
manifest or runtime is being prepared.

If fewer than six tasks are eligible before measured execution, stop as
`INCOMPLETE_TASK_POOL`, preserve the reason, and prepare a new manifest after
fixing the cause. There are no hidden reserves or post-hoc task substitutions
in P6.

<a id="spec-evaluation-preflight"></a>
<!-- spec-id: EVALUATION.PREFLIGHT -->
### Preflight

Before the first measured agent run:

1. verify the recorded benchmark content and any task execution image/archive;
2. verify HarnessX, ProblemForger service startup, evaluator availability, and
   the selected model capability;
3. run the evaluator on a separate smoke fixture, not on a selected task;
4. verify each selected task's recorded network-free compatibility and
   candidate/evaluator isolation compatibility, including its pinned task
   metadata, evaluator adapter/source/runtime identity, and required-test
   definition, against the manifest;
5. verify a clean isolated workspace and the declared resource accounting.

The network-denial smoke fixture is an authoritative isolation check, not just
a connectivity test. Before the candidate-side attempts, the trusted runner
performs direct namespace-policy verification and exposes controlled reachable
canaries for DNS, an external socket, and a loopback service. Candidate-side
attempts must produce a policy-specific denial distinguishable from ordinary
DNS resolution, timeout, or connection-refused errors; a failed lookup or a
connection to an unreachable endpoint is not evidence of denial. Persist a
`NETWORK_DENIAL_VERIFIED` result with bounded network-denial smoke diagnostics
that are manifest/runtime/sandbox-policy-bound, including the policy
verification result, canary identities/reachability, and candidate-side
denial classifications, before the first measured slot. The
`NETWORK_DENIAL_VERIFIED` record is the authority for every measured candidate
sandbox. Before each evaluator launch, the trusted runner applies the
manifest's candidate sandbox policy, computes its effective policy identity,
and requires exact equality with the policy identity in that record. It binds
`sandbox_policy_id` and `network_denial_evidence_ref` into the evaluator
`STARTED` record and terminal `TRUSTED_RESULT`; a missing or mismatched
identity or reference is `EVIDENCE_INCOMPLETE` and prevents launch and
scoring. If policy inspection, canary reachability, a policy-specific denial,
or the durable bound result is missing, record `EVIDENCE_INCOMPLETE`, do not
dispatch measured work, and do not evaluate a patch. These checks run without executing a selected task.
After the manifest is frozen and the policy checks above succeed, before any
selected task is exposed, the trusted evaluator executes each selected task's
unmodified clean baseline under the frozen runtime, evaluator, test, and
sandbox configuration. Before each clean-baseline execution and before every
candidate evaluator launch, the trusted runner computes the effective
`evaluator_adapter_source_runtime_identity` from the loaded evaluator adapter
and source/runtime artifacts, resolved evaluator configuration, and
runtime/dependency inputs. It requires exact equality with the manifest's
evaluator adapter/source/runtime identity and pins those verified artifacts for
the invocation. It persists the trusted
`EVALUATOR_IDENTITY_VERIFIED` record before the execution or launch, with its
content-addressed `evaluator_identity_evidence_ref` and
`evaluator_identity_evidence_sha256`, created from the artifacts actually
loaded and pinned for that invocation. The record's `producer_id`,
`producer_provenance`, and `producer_attestation_ref` are retained from the
authenticated trusted recorder; worker/candidate claims and manifest labels
cannot supply them. For both baseline and candidate verification, the trusted
runner records the effective
`evaluator_verification_profile` actually used, observed by the trusted runner
rather than copied from the manifest. Before setting
`verification_result=VERIFIED`, require exact equality with the frozen
profile and successful verification of its referenced checker, interpreter/runtime,
transitive dependency, and configuration content; resolve
`producer_attestation_ref` and verify the authenticated attestation binds the
exact evidence reference and digest to `producer_id` and
`producer_provenance`. The profile's effective verifier configuration (including dependency
roots, symlink policy, and transitive-content traversal rules) and exact
test/command identity must match that frozen profile. Checking mutable paths
without binding loaded artifacts is insufficient. A missing or mismatched
identity, profile, evidence record, reference, digest, or referenced artifact is
`EVIDENCE_INCOMPLETE` and prevents execution, launch, and scoring. Persist a
`BASELINE_VECTOR_VERIFIED` record only when
every required `FAIL_TO_PASS` test fails through a valid completed test outcome
and every required `PASS_TO_PASS` test passes. Infrastructure, missing-test,
timeout, protocol, or sandbox errors do not satisfy either condition. Bind the
record to the `manifest_hash`, task ID, clean-baseline identity, runtime/image
identity, `evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`,
`producer_attestation_ref`, evaluator bundle and test definition, effective
sandbox policy, `baseline_vector_ref`, `baseline_vector_sha256`, `baseline_raw_output_ref`,
and `baseline_raw_output_sha256`. Retain the exact per-test baseline vector
and bounded raw setup output under those immutable references. Keep this setup result hidden from the agent and separate from
the measured candidate-evaluation count. A wrong baseline vector or
baseline-condition failure is task-specific `MISSING_SETUP` with no task
substitution; missing, corrupt, or mismatched baseline evidence is
`EVIDENCE_INCOMPLETE`. A shared baseline-verification failure stops measured
dispatch as `INCOMPLETE_EVIDENCE`.
If a
selected task's compatibility predicate is missing, mismatched, or cannot be
verified, record task-specific `MISSING_SETUP`, do not expose or evaluate that
task, and do not substitute a different task. A shared inability to apply the
predicate before exposure invalidates the manifest and requires
`INCOMPLETE_TASK_POOL` or a new manifest/version.

A task-specific setup failure is recorded with a reason and does not authorize
selecting another task. Continue independent preflight/measurement slots when
the shared manifest and runtime remain valid. A shared setup failure before
any measured slot starts stops the pilot and requires a corrected manifest or
an explicit new version.

Preflight is an operational readiness check. It does not estimate task success
and its diagnostics cannot be used to tune the selected task set after
exposure.

## Execution controls

Every A/C slot receives a fresh task workspace. The worker may propose graph
changes, but the ProblemForger service remains authoritative for graph state
and governance outcomes. The durable service journal is required for C; its
telemetry is useful but not required to reconstruct the result.

Freeze before exposure:

- a semantic wall-clock deadline per agent run;
- a separate evaluator wall-clock allowance for each produced patch, identical
  for A and C;
- a provider-spend or request budget, where the provider exposes one;
- bounded tool/service-call and output limits;
- Freeze this retry mapping and precedence before exposure. Apply this
  classifier only to failed or interrupted attempts, after reconciling durable
  terminal agent/evaluator results. Retry ineligibility does not change outcome
  scoring:
  1. shared evidence/integrity failure takes precedence and stops new work;
  2. accepted or ambiguous semantic exposure, or an unresolved dispatched
     operation, prohibits retry. Retain any complete terminal result for scoring; a
     trusted, evidenced `CANDIDATE_PATCH_INVALID` outcome is an observed 0, while
     `MALFORMED_RESPONSE`, other incomplete/evidence-failure outcomes, no terminal
     result, or missing mandatory evidence remains missing;
  3. select one failure cause from durable observations. An explicit provider
     HTTP status takes precedence over a consequent harness exit: `HTTP_429`
     maps to 429, `HTTP_5XX` maps to 500–599, and other statuses are
     nonretryable. Conflicting explicit statuses are nonretryable;
  4. without an HTTP response, `TRANSPORT_TIMEOUT` requires a recorded
     transport timeout without an HTTP response, and `CONNECTION_FAILURE`
     requires a recorded connection failure without an HTTP response;
  5. `WORKSPACE_SETUP_FAILURE` requires failure during workspace preparation;
  6. `HARNESS_EXIT_BEFORE_RESPONSE` applies only when no more specific cause is
     recorded;
  7. Unknown or conflicting causes are nonretryable;
  8. with no accepted semantic response and every dispatched operation
     terminal, only `CONNECTION_FAILURE`, `TRANSPORT_TIMEOUT`, `HTTP_429`,
     `HTTP_5XX`, `HARNESS_EXIT_BEFORE_RESPONSE`, and
     `WORKSPACE_SETUP_FAILURE` classify as `PRE_SEMANTIC_FAILURE` and permit
     one clean whole-slot retry when the frozen deadline and budget permit it.
  This mapping is exhaustive and uses durable process/transport observations,
  not adapter-specific prose. It applies only to the first attempt; a failure
  of the clean retry is terminal.
- no replacement of a trajectory after a semantic response has been accepted;
- an explicit count of human interventions, including setup/recovery help.

### Durable attempt and operation ordering

Create a durable attempt record with `semantic_state=NOT_ACCEPTED` before any
dispatch. For every provider request, tool call, or service call counted
against a frozen request, spend, tool, or service limit, append an operation
reservation with a unique ID and reserved units before dispatch. The
reservation counts against the limit until settled; completion appends actual
usage and settles it. Do not dispatch if the reservation cannot be committed.
Reservation and limit check are one durable transaction under the budget
ledger. The transaction computes `settled + outstanding reservations +
requested units` for the relevant limit and rejects the reservation when that
sum exceeds the limit. Concurrent reservations therefore cannot both consume
the same remaining unit.

Before exposing the first semantic content, including non-streaming semantic
content or streamed content, or any tool call, append a durable
semantic-acceptance marker before the response is passed to the agent or tool
executor. If that marker cannot be committed, do not expose the response;
mark the attempt interrupted and missing. Treat an ambiguous interrupted
attempt as post-semantic and missing. On restart, an attempt or dispatched
operation without a durable terminal state is never retried or redispatched.
A retry is eligible only when durable state explicitly says
`PRE_SEMANTIC_FAILURE`, records every dispatched operation as terminal, and
proves that no semantic response was accepted, and the reason-code mapping
above classifies the terminal failure as `PRE_SEMANTIC_FAILURE`. An explicit
dispatched pre-semantic transport failure is therefore retryable only when its
reason code is in the allowlist above; dispatch alone neither grants nor
removes eligibility. A reservation is released only by a durable `NOT_DISPATCHED`
settlement; without that proof it remains consumed in budget accounting. The
rule is: an outstanding reservation alone does not make a terminal
`PRE_SEMANTIC_FAILURE` ineligible. That consumed reservation does not by itself
make the attempt nonretryable: a
terminal `PRE_SEMANTIC_FAILURE` may take its mandatory whole-slot retry when
all dispatched operations are terminal, no semantic response was accepted,
and a new reservation fits the remaining budget. The retry allocates a new
reservation and never reuses the failed operation. If neither acceptance nor
interruption record can be durably committed, classify the attempt as shared
evidence failure and stop new work.
Retain all attempt, reservation, settlement, and interruption records.

### Slot ledger, evaluator binding, and isolation

The experiment has one exclusive experiment coordinator. It acquires a durable
owner record for the experiment ID before creating or recovering slots; no
concurrent owner is permitted. Slot and evaluator starts use an atomic
compare-and-set under that owner record, and the rule is: only the owner may
dispatch. A replacement coordinator may recover only after the prior owner is
known stopped and the ownership record is safely transferred; overlapping
recovery is forbidden.

Before the first measured dispatch, generate and persist the C `run_id` for
each slot. The slot ledger key uses a non-null `slot_identity`:
`(manifest_hash, task_id, configuration, slot_identity)`. For C,
`slot_identity` is the persisted `run_id`; for A, `slot_identity` is the literal
`A_SLOT` sentinel while the protocol `run_id` remains explicit `NULL`. No
uniqueness constraint uses nullable `run_id` alone. The slot record has state
`PLANNED`. The C run registration binds manifest hash, task ID, and
configuration plus `run_id` to the same slot record before dispatch and
scoring. Write
`SLOT_STARTED` with durable `slot_started_at` and
`absolute_slot_deadline` before agent dispatch. `absolute_slot_deadline` is the
agent deadline and is separate from `absolute_evaluator_deadline`. Retries and
restarts reload that same absolute slot deadline for read-only reconciliation;
downtime counts toward it and never creates a fresh slot deadline. After
restart, a completed slot with valid evidence is skipped only for read-only
reconciliation; no later slot dispatch is allowed. Before applying the missing
fallback, reconcile terminal
agent results first. Finalize `NO_PATCH` only with its durable no-evaluation
reason; absence of a patch artifact alone does not establish `NO_PATCH`.
If a retained patch passes frozen validation, its digest is valid, and no evaluator invocation exists, launch
the first
evaluator invocation if the coordinator remains live and the experiment-wide
stop deadline, evaluator-applicable budget, and setup permit; otherwise record
incomplete evaluation. Before
launching it, persist `evaluator_started_at` and `absolute_evaluator_deadline`
in its `STARTED` record. The evaluator deadline is the earlier of the frozen
evaluator allowance after start and the experiment-wide stop deadline; restarts
reload it for read-only reconciliation and downtime counts. A terminal agent
patch recorded before its agent deadline remains eligible for its first
evaluator after that deadline while the coordinator remains live. Keep the
slot nonterminal while this bound evaluation is running. If a coordinator
restart occurs first, the coordinator restart finalizes it as
`EVALUATION_INCOMPLETE` with reason `COORDINATOR_RESTART`, retains its
reservation/operation/phase records, and marks the slot missing; it launches no
evaluator. Then reconcile terminal evaluator evidence and finish the slot when
all bound terminal evidence is valid. A started slot may resume only its one
durably recorded eligible pre-semantic retry while the coordinator remains
live; after a coordinator restart, no active slot or retry resumes and no later
slot dispatch is allowed.
A nonterminal slot with a bound evaluator remains open until that evaluator
reaches terminal state or its evaluator or experiment deadline expires while
the coordinator remains live; on restart, the finalization above applies.

Each C slot uses a unique persisted `run_id` and a new run namespace. Before
dispatch, verify a version-zero empty graph (apart from run registration) with
no prior proposals, evidence, or graph events. Fresh workspaces also require
no session, memory, cache, or service-state reuse across slots. A failed
isolation check prevents dispatch and is recorded as missing evidence.

Before dispatch, record a clean-baseline identity for each slot, including the
task image/archive, repository tree and dependency identity, and a successful
clean-workspace check. This identity is bound to the slot and evaluator result;
a mismatch prevents dispatch or scoring and does not authorize substitution.

Slot state is monotonic from `PLANNED` through `SLOT_STARTED` to one terminal
state. For new work, the agent deadline fences agent attempts and operations;
the evaluator deadline fences evaluator writes. A terminal agent result does
not close the evaluator phase, and a bound first evaluator may finish after the
agent deadline but before its own deadline or the experiment-wide stop. The
slot remains nonterminal while that evaluator phase is active. Terminalize
atomically at the applicable phase deadline or explicit terminal outcome,
recording timeout/missing before accepting late outcome-changing work. The
terminal fence rejects new dispatch, semantic results, and outcome-changing
writes. The trusted coordinator may still append idempotent usage settlements
and cancellation/interruption records for operations reserved before the
fence; these records cannot reopen the slot or change the outcome. If
terminalization cannot be committed, stop new work as shared evidence failure.

For an eligible first-attempt failure, the runner must take that retry unless
a recorded deadline, exhausted budget, shared integrity failure, or operator
abort prevents it. This is one whole-slot restart, not an additional per-call
retry allowance; disable hidden harness/provider retries. Retain both attempt
records. Retries do not reset deadlines or resource counters. After any
semantic response (including accepted streamed content or a tool call), no
whole-slot restart is allowed. Candidate evaluation has no extra retry.

If an agent phase exhausts a limit, prevent new operations charged to that
phase. An already authorized operation may finish and settle, and may produce
its terminal agent result before the agent deadline. Limit exhaustion alone
does not mark the slot unresolved. If no authorized operation can produce a
terminal result, record a phase-specific unresolved reason and continue
unrelated slots if the experiment-wide runtime is still valid. A limit reached
after a valid terminal agent result does not invalidate that result and does
not suppress its first evaluator; check the evaluator-applicable budget
separately.
If the evaluator phase exhausts its own limit, record `EVALUATION_INCOMPLETE`
without invalidating the agent result. Do not treat a missing slot as success or
failure and do not buy extra retries after seeing its outcome.

Before a slot is scored as either 0 or 1, require complete and reconciled slot,
attempt, operation, and evaluator records (or a durable no-evaluation reason
when no patch was produced, or a complete durable `CANDIDATE_PATCH_INVALID`
outcome with `evaluator_invocation: NOT_DISPATCHED`), then validate its mandatory
evidence: the
manifest/version reference, the agent terminal record, the exact candidate
patch bytes and digest where either A or C produced one, and the evaluator
output where evaluation ran.
For every selected task, require its bound `BASELINE_VECTOR_VERIFIED` setup
record and revalidate the manifest, task, clean-baseline, runtime/image,
`evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`,
`producer_attestation_ref`, evaluator-bundle/test-definition, sandbox-policy,
and vector-digest bindings.
Resolve `producer_attestation_ref` from that integrity-bound
`BASELINE_VECTOR_VERIFIED` consumer record, verify it matches the retained V1
record metadata and the consumer's exact evidence reference and digest, then
verify its authenticated `EVALUATOR_PRODUCER_ATTESTATION_V1` envelope binds
that exact evidence reference and digest to the payload's `producer_id` and
`producer_provenance`, and the `EVALUATOR_IDENTITY_VERIFIED_V1` schema, `verification_result=VERIFIED`,
baseline/scope bindings, and every referenced immutable artifact; recompute
the identity from those retained bytes and compare it with the proof, baseline
record, and frozen manifest. Missing, unknown, unauthenticated, or mismatched
producer provenance or attestation is `EVIDENCE_INCOMPLETE`; worker/candidate-
supplied labels, generic registrations, and matching content digests are not
authentication evidence. For every
baseline proof and every actually
dispatched candidate proof, validate the complete
`evaluator_verification_profile` against the frozen manifest, including
method, checker version, command identity, and effective configuration.
Resolve and digest-check its retained checker, interpreter/runtime, transitive
checker/dependency, and configuration content as well as the evaluator
artifacts. A changed checker helper, interpreter/runtime, or transitive
dependency byte is a subject mismatch and produces
`EVIDENCE_INCOMPLETE`. Do not accept matching identity digests as a
substitute for these checks. These checks use retained historical bytes only
and do not execute the verifier command. Missing, unreadable, corrupt,
untrusted, or mismatched profile fields or referenced content produce
`EVIDENCE_INCOMPLETE`. They apply to baseline proof even for `NO_PATCH` and
`CANDIDATE_PATCH_INVALID`/`NOT_DISPATCHED`; no candidate verification record
is required when no candidate evaluator was dispatched. Loss, corruption,
untrusted provenance, or mismatch produces `EVIDENCE_INCOMPLETE`; a failed baseline condition remains
`MISSING_SETUP` and is never a candidate outcome. For every candidate
evaluation, also revalidate the effective
`evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`/`evaluator_identity_evidence_sha256`, and
`producer_attestation_ref` from the integrity-bound evaluator `STARTED` or
terminal result record against the manifest, the immutable verification record,
the invocation's exact evidence reference and digest, and the loaded evaluator
used for that invocation. Resolve the attestation and verify its authenticated
envelope binds that exact candidate evidence reference and digest to the
candidate payload's producer fields; loss, corruption, or mismatch produces
`EVIDENCE_INCOMPLETE`. The same baseline proof remains mandatory for
`NO_PATCH`, `CANDIDATE_PATCH_INVALID`, and
`evaluator_invocation: NOT_DISPATCHED`; these outcomes do not authorize
substituting a current evaluator or omitting historical baseline evidence.
Require the bound `NETWORK_DENIAL_VERIFIED` record and its bounded
diagnostics for every slot. If a candidate evaluator was actually dispatched:
Revalidate `sandbox_policy_id` and `network_denial_evidence_ref` against the
manifest, the effective measured sandbox, and the evaluator invocation; loss,
corruption, or mismatch produces `EVIDENCE_INCOMPLETE` rather than a complete
slot. For `NO_PATCH` or `CANDIDATE_PATCH_INVALID` with
`evaluator_invocation: NOT_DISPATCHED`, do not require a candidate evaluator
invocation or measured sandbox; instead revalidate the retained preflight
`NETWORK_DENIAL_VERIFIED` record and its policy identity and diagnostics
against the manifest and candidate sandbox policy only. For every dispatched agent attempt, including clean retries, require its
attempt-specific `WORKER_NETWORK_DENIAL_VERIFIED` record and bounded
diagnostics. Revalidate `agent_attempt_id`, `worker_policy_id`, and
`worker_network_evidence_ref` against the manifest, the effective worker
namespace, and that attempt's `STARTED` and terminal agent records; loss,
corruption, or mismatch produces `EVIDENCE_INCOMPLETE` rather than a complete
slot. A slot cannot be scored unless every dispatched attempt has this bound
worker evidence. For an evaluated candidate, verify the retained bytes against the digest
bound to the evaluator invocation and all slot/configuration bindings. For a
`CANDIDATE_PATCH_INVALID` outcome, verify the retained bytes and digest against
the durable invalid-patch outcome binding, including the manifest, slot, task,
configuration, `run_id`, `agent_attempt_id`, verified baseline, validator
version, bounded validation evidence, and the explicit
`evaluator_invocation: NOT_DISPATCHED` marker; no evaluator invocation digest
is expected. For C,
the durable ProblemForger journal
must be readable, identify the run, and retain every received proposal and
every returned terminal outcome. Zero proposals is valid; an interrupted
pending proposal is not fabricated into a terminal outcome. If the manifest declares a native trajectory archive as
mandatory, that archive is checked here as well; otherwise native telemetry is
optional diagnostic data. A missing or corrupt mandatory artifact produces
`EVIDENCE_INCOMPLETE` for that slot and never gets regenerated after a semantic
response. If the shared manifest, journal, or recorder fails for the remaining
experiment, stop launching new slots as `INCOMPLETE_EVIDENCE`; retain all
available artifacts and do not assign a complete-pilot decision.

## Measured evaluation

<a id="spec-evaluation-measured-evaluation"></a>
<!-- spec-id: EVALUATION.MEASURED-EVALUATION -->

Run the complete ordered slot list from the manifest. Execute each manifest
slot entry exactly once, in the recorded task order, with A immediately
followed by C for each task. Slots do not overlap: finish or durably classify
the current slot, including its permitted retry and bound evaluator phase,
before advancing. Recovery preserves this order for live retries and read-only
reconciliation; it skips completed slots only for audit and never dispatches a
later slot after a coordinator restart. This is the frozen "run A and C once"
rule. An A failure does not reorder or
suppress its C slot unless a shared stop condition applies. Preserve the exact candidate patch bytes and digest produced by either A or C.
The agent-result record binds terminal state to the patch digest in one durable
transition, or records an explicit `NO_PATCH` outcome. An evaluator may use
only the patch digest linked by that record; a stale or separately discovered
patch is `EVIDENCE_INCOMPLETE`.
Before exposing any selected task and before every later agent-attempt launch,
including a clean whole-slot retry, place the agent/worker namespace and every
worker-controlled tool/process under a network-denied policy. The worker has no
DNS, external socket, loopback, or arbitrary host-IPC egress; it may use only
the declared harness/tool channel. Only a trusted harness/provider process
outside that namespace may reach the model/provider, and it exposes bounded
declared responses through the adapter channel. The trusted runner directly
verifies the worker policy and tests controlled reachable canaries, including a
remote-solution retrieval attempt; persist an attempt-specific
`WORKER_NETWORK_DENIAL_VERIFIED` result bound to the manifest, runtime
identity, and worker-policy identity. For every attempt, bind `agent_attempt_id`,
`worker_policy_id`, and `worker_network_evidence_ref` to the attempt `STARTED`
and terminal agent records; the slot-level record cannot be reused for a new
attempt. If policy enforcement, canary denial, or the attempt-specific bound
result cannot be verified, record `EVIDENCE_INCOMPLETE` and do not launch the
attempt or expose a selected task.
Evaluate each produced candidate patch once in a fresh evaluator workspace.
Use an immutable evaluator bundle from the manifest as a read-only snapshot
outside the candidate workspace. The worker cannot read evaluator or gold
artifacts. Deny the worker authority to read host paths outside its task
workspace that contain evaluator, gold, recorder, ledger, credential, or other
non-task artifacts; do not mount evaluator or gold artifacts in the worker
namespace.
Expose the evaluator bundle only to the trusted evaluator process. The worker
cannot read or write evaluator tests, gold artifacts, evaluator outputs, the
recorder, ledger, or credentials. The trusted runner verifies the evaluator
bundle digest before execution and records that evaluator bundle digest in the
bound result; a mismatch is `EVIDENCE_INCOMPLETE` and is not repaired by
rerunning.
Never import or execute candidate code in the trusted evaluator process.
Candidate code runs in a separate restricted process/namespace and inherits no
evaluator authority; it may access only its declared task workspace and
runtime dependencies. The candidate sandbox has no read access to evaluator or
gold artifacts, hidden tests, evaluator outputs, recorder, ledger, credentials,
or other non-task host paths. The candidate sandbox has no network egress and
uses a network-denied sandbox; the evaluator isolation test attempts network
access and expects denial. DNS, external sockets, and loopback access to
services are denied; required dependencies are preloaded. If network denial
cannot be verified, record `EVIDENCE_INCOMPLETE` and do not evaluate the patch.
Tasks that require loopback or another denied service are excluded by the
network-free eligibility and preflight rules, not classified as candidate
failures.
The trusted evaluator retains hidden tests and the evaluator bundle in its own
namespace. It launches the candidate through a narrow, length-bounded,
versioned `CANDIDATE_EVAL_IPC_V1` channel rather than importing candidate code.
The channel uses canonical data-only UTF-8 JSON and the protocol is:

```text
REQUEST            {version, invocation_id, input_b64}
CANDIDATE_RESPONSE {version, invocation_id, output_b64, declared_output_sha256}
TRUSTED_RESULT     {version, invocation_id, status, observed_output_sha256, candidate_frame_sha256, terminal_payload}
```

The evaluator sends only declared test invocation inputs; it never sends hidden
test source, evaluator-bundle bytes, expected outputs, or pass/fail assertions.
The candidate emits only the untrusted `CANDIDATE_RESPONSE`; it does not
contain a `status` field. Before decoding output or applying assertions, the
trusted runner requires response `version` and `invocation_id` equal the
outstanding `REQUEST`. Response binding is checked before digest and hidden
assertions. A binding mismatch is `PROTOCOL_ERROR` and `EVIDENCE_INCOMPLETE`;
quarantine the raw frame and bind that failure to the terminal result.
`declared_output_sha256` is untrusted metadata. The trusted runner then
decodes the bounded payload and recomputes the observed output digest. If the
declared digest does not equal the recomputed digest, the
declared digest mismatch is `PROTOCOL_ERROR`. Retain the bounded raw candidate
frame as quarantined evidence with both declared and observed digests and its
trusted `candidate_frame_sha256`; the quarantined frame is not passed to hidden
assertions or scoring. The separate
`TRUSTED_RESULT` is a runner-owned terminal record, not a candidate response.
`observed_output_sha256` is nullable. `observed_output_sha256` is null when no
output was decoded. `candidate_frame_sha256` is computed by the trusted runner
over the exact received candidate frame. `candidate_frame_sha256` is null when
no candidate frame was received. A
candidate frame with a `status` field is
`MALFORMED_RESPONSE`; the candidate cannot request a timeout, incomplete
evidence, or any other terminal classification. The trusted evaluator applies
hidden assertions to an accepted candidate result and constructs the required
test vector. A non-executable decoder performs bounded schema validation before
the evaluator consumes any field; never use native or object-capable
deserialization. The candidate sandbox can use only this channel and cannot
open arbitrary evaluator or host IPC. An IPC or sandbox violation is
`EVIDENCE_INCOMPLETE` and is not repaired by rerunning. The trusted runner,
not candidate-controlled output, assigns the status in `TRUSTED_RESULT`. The
status values are `OK`, `RUNTIME_ERROR`, `TIMEOUT`, `MALFORMED_RESPONSE`,
`PROTOCOL_ERROR`, or `SANDBOX_VIOLATION`. `OK` is evaluated by the hidden
assertions. `RUNTIME_ERROR` produces a completed failing test vector and an
observed zero only when its terminal payload proves `failure_origin: CANDIDATE`,
candidate execution began, the candidate process/namespace identity is bound,
candidate code caused the failure, and supervisor, IPC, sandbox, evaluator,
and dependency setup were healthy. A process start or nonzero exit alone is
insufficient. `TIMEOUT` maps to `EVALUATION_INCOMPLETE`. A launch, dependency,
supervisor, IPC, evaluator, or other infrastructure error maps to
`EVIDENCE_INCOMPLETE` with `failure_origin: INFRASTRUCTURE` and no completed
test vector; unknown attribution also maps to `EVIDENCE_INCOMPLETE`. A
`MALFORMED_RESPONSE`, `PROTOCOL_ERROR`, or `SANDBOX_VIOLATION` maps to
`EVIDENCE_INCOMPLETE` and takes precedence over candidate-failure
classification. A pre-output `RUNTIME_ERROR` remains a complete failing test
vector and observed zero even when `observed_output_sha256` is null only when
the same candidate-causation evidence is present; otherwise it is
`EVIDENCE_INCOMPLETE`.
`CANDIDATE_PATCH_INVALID` remains a trusted runner
outcome, not a candidate-controlled status, and is an observed zero only when
the patch-invalid evidence is complete.
`terminal_payload` is a status-specific terminal payload. The terminal failure
envelope is explicit: `TIMEOUT` records `EVALUATION_INCOMPLETE` in its terminal
payload; `MALFORMED_RESPONSE`, `PROTOCOL_ERROR`, and `SANDBOX_VIOLATION` record
`EVIDENCE_INCOMPLETE` plus a `quarantine_ref` when a raw frame was received.
The `PROTOCOL_ERROR` terminal payload includes `EVIDENCE_INCOMPLETE` and
`quarantine_ref`.
The `quarantine_ref` is bound to the terminal result and points to the retained
bounded artifact and its digests. A `PROTOCOL_ERROR` terminal result is not
reclassified as `COORDINATOR_RESTART` during restart recovery; it remains the
original terminal status. These failure payloads have no completed test vector
and are never scored as candidate behavior.
Persist an evaluator `STARTED` invocation record, bound to the slot and patch,
before launching it. The invocation record binds the manifest hash, slot ID,
task ID, configuration, slot `run_id` (or explicit `NULL` for A),
candidate-patch digest, evaluator version/test
definition, `evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`,
`producer_attestation_ref`, evaluator bundle digest, clean-baseline identity,
`sandbox_policy_id`, `network_denial_evidence_ref`,
`evaluator_started_at`, and `absolute_evaluator_deadline`. The trusted
runner verifies the effective measured sandbox policy against the bound
`NETWORK_DENIAL_VERIFIED` record before launch. It has no
raw-output digest. The terminal result record repeats that full invocation
binding, including the slot `run_id`,
`evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`,
`evaluator_identity_evidence_sha256`, `producer_attestation_ref`,
`sandbox_policy_id`, and `network_denial_evidence_ref`, and adds the recomputed `observed_output_sha256` when output was decoded (or
null), the trusted `candidate_frame_sha256` when a candidate frame was received
(or null), plus the status-specific `terminal_payload` described above. The
record is terminal even when it has no test vector. An evidenced patch rejection is a complete terminal evaluation without a test vector; it is a terminal evaluation-phase outcome and is marked `evaluator_invocation: NOT_DISPATCHED`. Before reusing a completed baseline after restart, obtain its
`producer_attestation_ref` from the integrity-bound
`BASELINE_VECTOR_VERIFIED` consumer record and cross-check it against the
retained V1 record and exact evidence reference/digest; revalidate its retained
`evaluator_adapter_source_runtime_identity`,
`evaluator_identity_evidence_ref`,
`evaluator_identity_evidence_sha256`, and immutable
`EVALUATOR_IDENTITY_VERIFIED` record plus its referenced historical artifacts
against the manifest; inspect retained bytes only. For a candidate evaluation
after restart, obtain
`producer_attestation_ref` from the integrity-bound candidate `STARTED` or
terminal result record and cross-check it against the retained V1 record and
exact candidate evidence reference/digest; perform the same evaluator identity,
producer-provenance, verifier-profile, producer-attestation, and retained-content
checks only when a candidate evaluator was actually dispatched. For `NO_PATCH` or
`CANDIDATE_PATCH_INVALID` with
`evaluator_invocation: NOT_DISPATCHED`, do not require a candidate
`EVALUATOR_IDENTITY_VERIFIED` record, evaluator invocation, or measured
sandbox; instead revalidate the terminal outcome, its complete
no-evaluation/patch-validation evidence, the explicit marker, and the mandatory
baseline proof against the manifest and retained evidence. Never rerun baseline
setup or the evaluator, execute retained evaluator code, regenerate
verification evidence, or substitute the currently installed evaluator. Apply
the same scoring-time producer identity/provenance, verifier-profile, trusted
producer-attestation and retained-content checks to the mandatory baseline
proof and any dispatched candidate proof during read-only restart
reconciliation; do not substitute current producer metadata or regenerate
provenance, and no current verifier configuration may replace the recorded
profile. A missing, corrupt, or mismatched identity is
`EVIDENCE_INCOMPLETE`; never rerun the evaluator. A
started evaluation without a durable complete bound result at restart is
recorded as `EVALUATION_INCOMPLETE` with reason `COORDINATOR_RESTART`; this is
the durable terminal transition for that evaluator and marks the slot missing.
Restart never resumes an active evaluator, and no later slot dispatch is allowed
in this pilot.

Patch validation is a trusted coordinator transition separate from the evaluator's
`TRUSTED_RESULT` status. A completed validator `REJECT` is allowed only when
healthy trusted validation proves that retained, digest-verified candidate
content is malformed or cannot be applied to the verified baseline and emits a
deterministic content/applicability reason and bounded evidence. A validator
`ERROR`, crash, timeout, permission, disk, resource, or other infrastructure
failure maps to `EVIDENCE_INCOMPLETE` with `failure_origin: INFRASTRUCTURE`
and never emits `CANDIDATE_PATCH_INVALID`. When a completed validator `REJECT`
occurs, append a
durable terminal agent/slot outcome with code `CANDIDATE_PATCH_INVALID` and bind
it to the manifest hash, slot ID, task ID, configuration, slot `run_id` (or
explicit `NULL` for A), `agent_attempt_id`, candidate-patch digest and
retained-byte reference, verified baseline identity, validator version, and a
bounded validation reason/evidence reference. Record an explicit
`evaluator_invocation: NOT_DISPATCHED` marker for this outcome. The transition
is idempotent and remains terminal across restart; final scoring requires the
complete binding and evidence. If any binding, retained bytes, digest, baseline,
validator, or evidence is missing or mismatched, record
`EVIDENCE_INCOMPLETE` instead and never count the rejection as an observed zero.

An agent result is a resolved binary outcome when the required evaluator tests
complete and the declared success rule is satisfied. The default success rule
is: all required `FAIL_TO_PASS` tests pass and all required `PASS_TO_PASS` tests
remain passing. A completed failing test vector or a trusted, evidenced
`CANDIDATE_PATCH_INVALID` rejection is an observed 0. A durable terminal agent
`NO_PATCH` outcome with complete required evidence and a no-evaluation reason is
also an observed 0; absence of a patch artifact alone does not establish
`NO_PATCH`. Infrastructure loss, an incomplete evaluator vector, an incomplete
or missing patch rejection, or missing mandatory evidence is a missing outcome,
not an observed failure. Preserve the specific reason in either case.

For a complete task pair:

```text
y_i(X) = 1 if configuration X resolves task i, 0 for an observed failure
missing outcome is undefined, never 0
d_i(C-A) = 100 * (y_i(C) - y_i(A)) percentage points
mean_delta_pp = mean(d_i(C-A)) over the six task pairs
```

Report every raw outcome, the six per-task deltas, the mean delta, tasks
improved/worsened/tied, unresolved reasons, and C's added cost, latency,
steps, tool calls, service calls, and human interventions. Report observed
values, not confidence intervals or significance claims.

If any planned pair is missing, the pilot is `INCOMPLETE_COVERAGE`: retain
descriptive completed-pair data but do not assign the complete-pilot
`CONTINUE`/`ADAPT`/`STOP` label. Continue independent slots before making that
classification.

<a id="p6-incomplete-reporting"></a>
### Incomplete reporting

Keep a row for every planned slot, including slots never started. Record the
last completed phase, exact reason code, retry attempts, patch/image/model
identities, and retained raw artifacts. A local infrastructure failure does
not become a task failure; a malformed candidate patch does not become an
infrastructure success. The report must distinguish:

- `MISSING_SETUP` — image, workspace, service, harness, or evaluator could not
  be prepared;
- `PROVIDER_UNAVAILABLE` — the selected provider/model could not answer;
- `RUN_INTERRUPTED` — execution began but did not finish;
- `EVALUATION_INCOMPLETE` — candidate evaluation produced neither a completed
  required test vector nor a complete, evidenced candidate-patch rejection;
- `CANDIDATE_PATCH_INVALID` — a completed trusted validator `REJECT` proves
  retained, digest-verified candidate content is demonstrably malformed or
  cannot be applied to the verified frozen baseline; with all other mandatory
  evidence complete, this is an observed 0. Validator errors are
  `EVIDENCE_INCOMPLETE`, not candidate failures;
- `EVIDENCE_INCOMPLETE` — mandatory evidence is missing, unreadable, corrupt, or
  fails its binding checks, including absent retained patch bytes for a
  recorded produced patch; this takes precedence over candidate-failure
  classification and remains missing;
- `INCOMPLETE_EVIDENCE` — shared mandatory evidence cannot be retained for the
  remaining experiment;
- `INCOMPLETE_TASK_POOL` / `INCOMPLETE_COVERAGE` — the planned pilot could not
  produce all six pairs.

No reason code is silently converted into a favorable result. A future run may
use the report to fix the setup, but it is a new manifest/version.

## Practical human decision

<a id="practical-continuation-decision"></a>

Before exposure, the operator records practical tolerances for cost, latency,
and human intervention, including how each is measured. Human judgment is
deliberately part of this feasibility decision; no percentage threshold is
pretended to be universal.

For a complete six-pair pilot, use exactly one label:

- **`CONTINUE`** — C shows useful local improvement or reduced failure without
  a critical regression, and its operational overhead is acceptable;
- **`ADAPT`** — a concrete, plausibly correctable weakness in benefit,
  overhead, or failure pattern warrants a stated change and reassessment;
- **`STOP`** — a critical correctness, isolation, security, or operational
  regression makes the package unsuitable for the tested workflow, or the
  observed practical value does not justify further work.

An unresolved critical regression precludes `CONTINUE`. `ADAPT` requires a
concrete remediation and reassessment plan and does not authorize broader use
while the regression remains. An incomplete pilot receives no one of these
labels; record a separate operational next action.

The decision maker records evidence, tolerance failures, missing evidence,
observed benefits/regressions, and next action. The label is a local workflow
decision, not an automatic P7 gate.

## Practical sensitivity report

<a id="practical-sensitivity-report"></a>

For a complete pilot, report the full `mean_delta_pp` and six leave-one-task-out
means. Use descriptive bands:

- `HARM` if the delta is below `-10` percentage points;
- `NEUTRAL` if it is between `-10` and `+10`, inclusive;
- `BENEFIT` if it is above `+10` percentage points.

Set `SENSITIVITY_DISCORDANT` if any leave-one-task-out estimate changes sign
or band relative to the full estimate. This is a warning that the small pilot
is sensitive to one task; it does not force `STOP`, `ADAPT`, or `CONTINUE` and
does not establish a population-level uncertainty claim. Do not compute a
sensitivity label for incomplete coverage; report the missingness instead.

P6 does not include bootstrap intervals, p-values, calibrated probabilities,
equivalence labels, or an automatic progression gate. Those may be appropriate
for a later, separately designed study.

## Retained evidence and integrity rules

Retain the manifest, its hash, task order, task/image identities, source and
dependency identities, model/provider metadata, exact request settings,
candidate-patch digest, durable ProblemForger journal, raw evaluator output,
slot ledger, evaluator invocation/result records, their effective evaluator
adapter/source/runtime identities, the `EVALUATOR_IDENTITY_VERIFIED` records,
their `producer_id`, `producer_provenance`, and
`producer_attestation_ref` values, the retained authenticated producer
attestation envelopes required to bind each evidence payload, their
content-addressed `evaluator_identity_evidence_ref` values and
`evaluator_identity_evidence_sha256` digests, and bound verification evidence,
operation reservation/settlement ledger, cost/latency measurements,
human-intervention log, the bounded manifest/runtime/sandbox-policy-bound
`NETWORK_DENIAL_VERIFIED` and `WORKER_NETWORK_DENIAL_VERIFIED` diagnostics,
including their policy identities and evidence references, the
`BASELINE_VECTOR_VERIFIED` records, exact per-test baseline vectors, bounded
raw baseline setup outputs, immutable artifact references, and their digests,
and all failure reasons. Retain the evaluator verification records, their
reference/digest fields, and all transitively referenced evaluator artifact
bytes outside worker/candidate authority for the lifetime of the pilot
evidence. Also retain every `evaluator_verification_profile` and all checker,
interpreter/runtime, and transitive checker dependency bytes, plus all
referenced configuration content (or a pinned image/archive containing them),
under the same lifetime and worker/candidate isolation requirements. A missing, corrupt, or mismatched
baseline vector, raw setup artifact, evaluator verification artifact, or
verifier-profile content is `EVIDENCE_INCOMPLETE`; never regenerate it after
task exposure.
Redact credentials without changing content that was visible to the agent or
affected its behavior.

Every run-scoped service operation carries an explicit `run_id`. Governance
outcomes are durable before they are returned. A worker cannot directly commit
authoritative graph state. A hosted-model identity limitation is recorded as a
limitation, not hidden behind an image digest.

The optional B diagnostic or a second harness must use a new manifest and must
not be pooled with P6-AC. This keeps the pilot useful for engineering while
leaving stronger causal and external-validity questions for later work.

<a id="p6-resource-budget"></a>
### Resource budget record

The operator must write the actual agent deadline, evaluator wall-clock
allowance, request/spend limit, tool limit, and experiment-wide stop limit into
the manifest before task exposure.
The values are practical operating limits, not validity thresholds. If a limit
is unavailable from a provider, record `UNKNOWN` and use the observable local
limit rather than treating unknown usage as zero.

Before starting the first slot, persist `experiment_started_at_utc`,
`absolute_stop_deadline_utc`, a nonnegative, monotonically non-decreasing
`experiment_elapsed_floor_ms`, `experiment_last_observed_utc_ms`,
`experiment_process_monotonic_started_ms`, and
`experiment_stop_elapsed_limit_ms` with the experiment ID in the retained
execution record. At experiment start, compute and freeze
`experiment_stop_elapsed_limit_ms = absolute_stop_deadline_utc -
experiment_started_at_utc`; it must be nonnegative. On reload, verify that
equality; a missing, corrupt, negative, or mismatched value records
`INCOMPLETE_COVERAGE` and forbids further dispatch. The absolute UTC deadline is
retained for reporting/audit only; enforcement uses the frozen elapsed limit
and the effective elapsed clock described below. Capture `experiment_process_monotonic_started_ms` at the
same experiment-start transition. `current_process_monotonic_elapsed_ms` is
the difference between the current reading and that experiment-start reading;
never use unanchored process uptime. It must come from a suspend-inclusive
monotonic clock such as `CLOCK_BOOTTIME` or equivalent. If suspend continuity
cannot be established, record `INCOMPLETE_COVERAGE`, fail closed, and do not
launch later slots. This is the restart-stable
clock domain. Every durable ledger write
advances the floor to the greatest of its previous value, the elapsed time
observed from `experiment_started_at_utc`, and the process-monotonic elapsed
time. Persist `experiment_last_observed_utc_ms` with the same record; it is the
restart-surviving last observed UTC timestamp. The last observed UTC timestamp
remains monotonically non-decreasing. Update it atomically with the floor on
every durable ledger write to `max(previous_value, now_utc_ms)`. If a write
observes a lower current UTC reading, record `INCOMPLETE_COVERAGE`, retain the
previous value, and never overwrite it with a lower value; do not launch later
slots. Before dispatching any new slot or retry, persist the resulting floor
and last observed timestamp. A process-monotonic clock cannot establish
continuity across restart;
it is supplemental evidence only.
If a dispatched operation lacks durable terminal settlement, or its
dispatch/settlement status is ambiguous after restart, treat any interval
after the last durable floor update as unmeasurable. Clock continuity is
ambiguous: record `INCOMPLETE_COVERAGE`, retain the reservation and operation,
and do not reconcile it by releasing budget; do not launch later slots. The
unresolved in-flight interval remains charged to the incomplete pilot rather
than becoming available for new work.
A coordinator restart with any nonterminal active attempt or evaluator is also
clock-ambiguous even when every provider/tool operation is terminal: local
agent work after the last settled operation and evaluator execution can consume
unrecorded elapsed time. Record `INCOMPLETE_COVERAGE`. The active agent attempt
is terminalized as `RUN_INTERRUPTED`; the active evaluator is terminalized as
`EVALUATION_INCOMPLETE`; in either case, mark the slot missing, retain
reservations, operations, and active phase/deadline records, and do not launch
later slots.
The pilot does not assume a restart-continuous trusted clock. The persisted
watermark is a lower bound and never clears restart ambiguity. Therefore,
every coordinator restart is a clock continuity loss, even when current UTC is
later than the watermark: a backward UTC shift during downtime can still
refund elapsed time, and the process-monotonic clock resets. Fail closed on
every coordinator restart: record `INCOMPLETE_COVERAGE`, retain all
reservations, operations, and active phase/deadline records, apply the active
phase terminalization above, and do not launch later slots. In this contract, phase
deadlines are elapsed-domain values: `absolute_slot_deadline` is the effective
elapsed value at slot start plus the frozen agent allowance, and
`absolute_evaluator_deadline` is the effective elapsed value at evaluator start
plus the frozen evaluator allowance, bounded by `experiment_stop_elapsed_limit_ms`.
While the coordinator
remains live, read the current process-monotonic elapsed time at every
dispatch, retry, budget check, and active-phase deadline check. Anchor effective
elapsed time at the live-process maximum:
`max(experiment_elapsed_floor_ms, max(0, now_utc_ms -
experiment_started_at_utc), current_process_monotonic_elapsed_ms)`. This live-
process maximum does not wait for a ledger write; a forward UTC shift may expire
the budget earlier. Before accepting work or terminalizing a phase, compare
phase deadlines with effective elapsed time; never compare phase deadlines to
raw UTC. Compare effective elapsed time with the frozen
`experiment_stop_elapsed_limit_ms`; `absolute_stop_deadline_utc` is reporting
metadata only and is never used as an independent enforcement value.
Reload
that record and cumulative resource usage; never
reset the deadline, elapsed floor, or spent budgets. Downtime counts toward
the stop limit. If the record is missing, corrupt, or the clock source cannot
be read, stop the pilot as `INCOMPLETE_COVERAGE` with the restart reason; do
not launch more slots. Interrupted semantic trajectories remain missing and
are not rerun.
Replay the operation ledger on restart. An outstanding reservation is included
in remaining-budget calculations and is treated as consumed at its reserved
amount until settled; if its state cannot be reconciled, stop and must not
launch more work. For a spend limit, reserve a bounded pre-dispatch charge
when one is available. If no bounded charge can be known before dispatch,
record that spend usage is `UNKNOWN` and do not claim that a local counter
enforces the provider spend limit.
Check the remaining budget before every slot/retry, and terminate active work
when the experiment deadline is reached. Preserve completed results and mark
unfinished or unstarted slots missing. An operator abort has the same no-new-work
effect and must be recorded; it does not reset or extend the experiment.

<a id="p6-runtime-image-identity"></a>
### Runtime identity record

For each image/archive used, record its immutable digest, source/reference,
platform, and the role it plays (benchmark task environment, HarnessX runtime,
ProblemForger service, or dependency bundle). For non-image execution record
the equivalent source and lockfile identities. Runtime identity supports
repeatable setup and drift detection; it is not a promise of exact hosted-model
replay.
