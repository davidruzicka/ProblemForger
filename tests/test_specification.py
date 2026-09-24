"""Practical P0 document regression checks, not production-implementation tests."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class SpecificationChecks(unittest.TestCase):
    def test_retry_evidence_and_restart_invariants(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "must take that retry",
            "Retries do not reset deadlines or resource counters",
            "exact candidate patch bytes and digest produced by either A or C",
            "Before a slot is scored as either 0 or 1",
            "Zero proposals is valid",
            "persist `experiment_started_at_utc`, `absolute_stop_deadline_utc`",
            "experiment_elapsed_floor_ms",
            "experiment_last_observed_utc_ms",
            "experiment_process_monotonic_started_ms",
            "suspend-inclusive monotonic clock",
            "`CLOCK_BOOTTIME` or equivalent",
            "suspend continuity cannot be established",
            "restart-stable clock domain",
            "backward UTC shift",
            "last observed UTC timestamp",
            "process-monotonic clock cannot establish continuity across restart",
            "Fail closed on every coordinator restart",
            "does not assume a restart-continuous trusted clock",
            "every coordinator restart is a clock continuity loss",
            "watermark is a lower bound and never clears restart ambiguity",
            "Every durable ledger write advances the floor",
            "process-monotonic elapsed time",
            "current process-monotonic elapsed time",
            "live-process maximum",
            "does not wait for a ledger write",
            "current_process_monotonic_elapsed_ms` is the difference",
            "experiment_stop_elapsed_limit_ms",
            "`experiment_stop_elapsed_limit_ms = absolute_stop_deadline_utc - experiment_started_at_utc`",
            "compute and freeze",
            "verify that equality",
            "mismatched value records `INCOMPLETE_COVERAGE`",
            "absolute UTC deadline is retained for reporting/audit only",
            "enforcement uses the frozen elapsed limit",
            "phase deadlines are elapsed-domain values",
            "compare phase deadlines with effective elapsed time",
            "never compare phase deadlines to raw UTC",
            "last observed UTC timestamp remains monotonically non-decreasing",
            "never overwrite it with a lower value",
            "Before dispatching any new slot or retry, persist the resulting floor",
            "Compare effective elapsed time with the frozen `experiment_stop_elapsed_limit_ms`",
            "never reset the deadline",
            "missing outcome is undefined, never 0",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_interrupted_attempts_and_inflight_usage_are_durable(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "durable semantic-acceptance marker",
            "before the response is passed to the agent",
            "Treat an ambiguous interrupted attempt as post-semantic and missing",
            "operation reservation",
            "before dispatch",
            "counts against the limit until settled",
            "outstanding reservation",
            "must not launch more work",
            "spend usage is `UNKNOWN`",
            "records every dispatched operation as terminal",
            "If a dispatched operation lacks durable terminal settlement",
            "Clock continuity is ambiguous",
            "do not launch later slots",
            "any nonterminal active attempt or evaluator",
            "local agent work after the last settled operation",
            "active agent attempt is terminalized as `RUN_INTERRUPTED`",
            "an outstanding reservation alone does not make a terminal",
            "If neither acceptance nor interruption record can be durably committed",
            "released only by a durable `NOT_DISPATCHED` settlement",
            "operation reservation/settlement ledger",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_summary_documents_do_not_restate_superseded_p6_rules(self):
        methodology = " ".join(read("docs/methodology.md").split())
        checks = " ".join(read("docs/specification-checks.md").split())
        for phrase in (
            "durable operation ledger",
            "semantic-acceptance marker",
            "ambiguous interruption is missing",
            "eligible retry is mandatory",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, methodology)
        self.assertNotIn("complete vectors `[fail, pass]`", checks)
        self.assertIn("separate smoke fixture", checks)

    def test_slots_evaluator_binding_and_c_isolation_are_frozen(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "`SLOT_STARTED`",
            "completed slot with valid evidence is skipped",
            "started slot may resume only",
            "nonterminal slot with a bound evaluator",
            "Persist an evaluator `STARTED` invocation record",
            "`EVALUATION_INCOMPLETE`",
            "never rerun the evaluator",
            "The invocation record binds the manifest hash, slot ID",
            "slot `run_id` (or explicit `NULL` for A)",
            "Each C slot uses a unique persisted `run_id`",
            "non-null `slot_identity`",
            "`A_SLOT` sentinel",
            "No uniqueness constraint uses nullable `run_id` alone",
            "version-zero empty graph",
            "no session, memory, cache, or service-state reuse",
            "complete and reconciled slot, attempt, operation, and evaluator records",
            "durable `slot_started_at`",
            "absolute_slot_deadline",
            "restarts reload that same absolute slot deadline",
            "downtime counts toward it",
            "agent-result record binds terminal state to the patch digest",
            "explicit `NO_PATCH`",
            "in one durable transition",
            "Terminalize atomically at the applicable phase deadline",
            "terminal fence rejects new dispatch, semantic results, and outcome-changing writes",
            "clean-baseline identity",
            "repository tree and dependency identity",
            "bound to the slot and evaluator result",
            "Reservation and limit check are one durable transaction",
            "settled + outstanding reservations + requested units",
            "rejects the reservation when that sum exceeds the limit",
            "immutable evaluator bundle",
            "read-only snapshot outside the candidate workspace",
            "worker cannot read evaluator or gold artifacts",
            "trusted evaluator process",
            "worker authority to read host paths outside its task workspace",
            "worker cannot read or write evaluator tests",
            "recorder, ledger, or credentials",
            "candidate sandbox has no network egress",
            "network-denied sandbox",
            "evaluator isolation test attempts network access and expects denial",
            "Candidate code runs in a separate restricted process/namespace",
            "inherits no evaluator authority",
            "Never import or execute candidate code in the trusted evaluator process",
            "CANDIDATE_EVAL_IPC_V1",
            "trusted evaluator retains hidden tests",
            "evaluator sends only declared test invocation inputs",
            "candidate emits only the untrusted `CANDIDATE_RESPONSE`",
            "trusted evaluator applies hidden assertions",
            "canonical data-only UTF-8 JSON",
            "CANDIDATE_RESPONSE {version, invocation_id, output_b64, declared_output_sha256}",
            "does not contain a `status` field",
            "TRUSTED_RESULT {version, invocation_id, status, observed_output_sha256, candidate_frame_sha256, terminal_payload}",
            "runner-owned terminal record",
            "status-specific terminal payload",
            "terminal failure envelope",
            "candidate frame with a `status` field is `MALFORMED_RESPONSE`",
            "response `version` and `invocation_id` equal the outstanding `REQUEST`",
            "Response binding is checked before digest and hidden assertions",
            "binding mismatch is `PROTOCOL_ERROR` and `EVIDENCE_INCOMPLETE`",
            "recomputes the observed output digest",
            "`observed_output_sha256` is nullable",
            "`candidate_frame_sha256` is computed by the trusted runner",
            "`candidate_frame_sha256` is null when no candidate frame was received",
            "`observed_output_sha256` is null when no output was decoded",
            "declared digest mismatch is `PROTOCOL_ERROR`",
            "Retain the bounded raw candidate frame as quarantined evidence",
            "both declared and observed digests",
            "quarantined frame is not passed to hidden assertions or scoring",
            "`TIMEOUT` records `EVALUATION_INCOMPLETE` in its terminal payload",
            "`PROTOCOL_ERROR` terminal payload includes `EVIDENCE_INCOMPLETE` and `quarantine_ref`",
            "`quarantine_ref` is bound to the terminal result",
            "A `PROTOCOL_ERROR` terminal result is not reclassified as `COORDINATOR_RESTART`",
            "non-executable decoder",
            "bounded schema validation",
            "never use native or object-capable deserialization",
            "status values are `OK`, `RUNTIME_ERROR`, `TIMEOUT`, `MALFORMED_RESPONSE`, `PROTOCOL_ERROR`, or `SANDBOX_VIOLATION`",
            "`RUNTIME_ERROR` produces a completed failing test vector",
            "failure_origin: CANDIDATE",
            "candidate execution began",
            "A process start or nonzero exit alone is insufficient",
            "failure_origin: INFRASTRUCTURE",
            "unknown attribution also maps to `EVIDENCE_INCOMPLETE`",
            "takes precedence over candidate-failure classification",
            "A completed validator `REJECT` is allowed only when",
            "A validator `ERROR`, crash, timeout, permission, disk, resource, or other infrastructure failure maps to `EVIDENCE_INCOMPLETE`",
            "never emits `CANDIDATE_PATCH_INVALID`",
            "`TIMEOUT` maps to `EVALUATION_INCOMPLETE`",
            "`MALFORMED_RESPONSE`, `PROTOCOL_ERROR`, or `SANDBOX_VIOLATION` maps to `EVIDENCE_INCOMPLETE`",
            "`CANDIDATE_PATCH_INVALID` remains a trusted runner outcome",
            "IPC or sandbox violation is `EVIDENCE_INCOMPLETE`",
            "evaluator bundle digest",
            "trusted runner",
            "slot ledger key uses a non-null `slot_identity`",
            "run registration binds manifest hash, task ID, and configuration",
            "invocation record binds",
            "plus the status-specific `terminal_payload` described above",
            "complete terminal evaluation without a test vector",
            "complete durable `CANDIDATE_PATCH_INVALID` outcome with `evaluator_invocation: NOT_DISPATCHED`",
            "For an evaluated candidate, verify the retained bytes against the digest",
            "no evaluator invocation digest is expected",
            "Then reconcile terminal evaluator evidence and finish the slot",
            "non-streaming semantic content",
            "reconcile terminal agent results first",
            "Finalize `NO_PATCH`",
            "launch the first evaluator invocation",
            "experiment-wide stop deadline, evaluator-applicable budget, and setup permit",
            "one exclusive experiment coordinator",
            "atomic compare-and-set",
            "only the owner may dispatch",
            "no concurrent owner",
            "no later slot dispatch is allowed",
            "Restart never resumes an active evaluator",
            "coordinator restart finalizes it as `EVALUATION_INCOMPLETE`",
            "active agent attempt is terminalized as `RUN_INTERRUPTED`",
            "mark the slot missing",
            "retain reservations, operations, and active phase/deadline records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_evaluator_deadline_is_separate_from_agent_deadline(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "`absolute_evaluator_deadline`",
            "separate from `absolute_evaluator_deadline`",
            "effective elapsed value at evaluator start plus the frozen evaluator allowance",
            "agent deadline fences agent attempts and operations",
            "evaluator deadline fences evaluator writes",
            "experiment-wide stop deadline",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_gold_information_leakage_mitigation_matches_evaluation(self):
        risks = " ".join(read("docs/risks.md").split())
        for phrase in (
            "worker authority must not read evaluator bundles",
            "host paths outside the task workspace",
            "trusted evaluator alone receives the read-only evaluator bundle",
            "must not expose evaluator outputs",
            "separate restricted process/namespace",
            "never inherits evaluator authority",
            "CANDIDATE_EVAL_IPC_V1",
            "declared invocation inputs",
            "serialized candidate results",
            "network-denied sandbox",
            "network egress is denied",
            "Response binding is checked before hidden assertions",
            "canonical data-only UTF-8 JSON",
            "non-executable decoder",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, risks)

    def test_graph_projection_preserves_evidence_references_without_raw_evidence(self):
        protocol = " ".join(read("docs/protocol.md").split())
        for phrase in (
            "Proposal-status and audit responses return only",
            "Graph-state projections may include immutable evidence references",
            "never expose evidence content",
            "internal recovery inputs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, protocol)

    def test_terminal_fence_preserves_post_deadline_accounting(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "idempotent usage settlements",
            "cancellation/interruption records",
            "cannot reopen the slot",
            "cannot reopen the slot or change the outcome",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_phase_limits_and_recovery_preserve_bound_work(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "does not invalidate that result",
            "does not suppress its first evaluator",
            "already authorized operation may finish and settle",
            "Limit exhaustion alone does not mark the slot unresolved",
            "phase-specific unresolved reason",
            "Restart never resumes an active evaluator",
            "started evaluation without a durable complete bound result at restart is recorded as `EVALUATION_INCOMPLETE`",
            "does not by itself make the attempt nonretryable",
            "trusted, evidenced `CANDIDATE_PATCH_INVALID` outcome is an observed 0",
            "`MALFORMED_RESPONSE`, other incomplete/evidence-failure outcomes",
            "new reservation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_p6_is_small_and_explicitly_practical(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "practical feasibility pilot",
            "Academic uncertainty is acceptable",
            "six tasks",
            "one fresh agent run per task/configuration",
            "one evaluator run for each produced candidate patch, except when trusted validation rejects it as `CANDIDATE_PATCH_INVALID`",
            "`evaluator_invocation: NOT_DISPATCHED` and has no evaluator run",
            "invalid-patch terminalizations are counted separately",
            "planned size is therefore twelve A/C slots",
            "at most twelve candidate-patch evaluations",
            "actual agent attempt count can exceed twelve",
            "not statistical precision",
            "Out of scope for P6: holdout/calibration data",
            "fallback-model chains",
            "population-level uncertainty",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_model_and_runtime_identity_have_honest_limits(self):
        evaluation = read("docs/evaluation.md")
        normalized = " ".join(evaluation.split())
        for phrase in (
            "one provider/model entry",
            "P6 has no implicit fallback",
            "new model requires a new experiment version",
            "digest of the harness or runtime image identifies those bytes",
            "does not prove that a hosted provider will use the same model",
            "local model may include its weights",
            "Record `UNKNOWN` explicitly",
            "What the execution image is for",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_compact_manifest_owns_setup_and_metric_choices(self):
        evaluation = read("docs/evaluation.md")
        manifest = " ".join(evaluation.split("## Pre-P6 manifest\n", 1)[1].split(
            "## Task selection and preflight\n", 1
        )[0].split())
        for phrase in (
            "the six task IDs and fixed order",
            "selected provider/model metadata",
            "HarnessX source/runtime identity",
            "ProblemForger service source/runtime identity",
            "evaluator version and required-test definition",
            "agent semantic deadline, evaluator wall-clock allowance, resource limits, retry rule",
            "primary result rule",
            "The manifest is hashed",
            "compact manifest is intentional",
            "manifest hash is finalized before any measured-run evidence is created",
            "contains no IDs or references to post-freeze evidence records"
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, manifest)

    def test_intervention_retry_and_slot_order_are_frozen(self):
        evaluation = read("docs/evaluation.md")
        manifest = " ".join(evaluation.split("## Pre-P6 manifest\n", 1)[1].split(
            "## Task selection and preflight\n", 1
        )[0].split())
        for phrase in (
            "graph-intervention content identity",
            "governance-policy content/configuration identity",
            "complete ordered A/C slot list",
            "each task's A slot before its C slot",
        ):
            with self.subTest(scope="manifest", phrase=phrase):
                self.assertIn(phrase, manifest)

        for phrase in (
            "A records `NONE`",
            "C requires non-null intervention and governance identities",
            "trusted runner verifies the loaded graph intervention",
            "service verifies its loaded governance policy/configuration",
            "mismatch prevents dispatch or recovery",
            "not be repaired by relabeling existing evidence",
        ):
            with self.subTest(scope="identity", phrase=phrase):
                self.assertIn(phrase, " ".join(evaluation.split()))

        controls = " ".join(evaluation.split("## Execution controls\n", 1)[1].split(
            "### Durable attempt and operation ordering\n", 1
        )[0].split())
        for phrase in (
            "Freeze this retry mapping and precedence",
            "`CONNECTION_FAILURE`",
            "`TRANSPORT_TIMEOUT`",
            "`HTTP_429`",
            "`HTTP_5XX`",
            "`HARNESS_EXIT_BEFORE_RESPONSE`",
            "`WORKSPACE_SETUP_FAILURE`",
            "Apply this classifier only to failed or interrupted attempts",
            "explicit provider HTTP status takes precedence over a consequent harness exit",
            "`TRANSPORT_TIMEOUT` requires a recorded transport timeout without an HTTP response",
            "`CONNECTION_FAILURE` requires a recorded connection failure without an HTTP response",
            "`HARNESS_EXIT_BEFORE_RESPONSE` applies only when no more specific cause is recorded",
            "Unknown or conflicting causes are nonretryable",
            "Retry ineligibility does not change outcome scoring",
        ):
            with self.subTest(scope="retry", phrase=phrase):
                self.assertIn(phrase, controls)

        measured = " ".join(evaluation.split("## Measured evaluation\n", 1)[1].split(
            "## Practical human decision\n", 1
        )[0].split())
        for phrase in (
            "Execute each manifest slot entry exactly once",
            "A immediately followed by C for each task",
            "Slots do not overlap",
            "before advancing",
            "Recovery preserves this order",
            "run A and C once",
        ):
            with self.subTest(scope="order", phrase=phrase):
                self.assertIn(phrase, measured)

        protocol = " ".join(read("docs/protocol.md").split())
        for phrase in (
            "effective graph-intervention identity",
            "effective governance-policy identity",
            "before resuming a pending proposal",
            "requires a new manifest/version",
            "C run registration must bind the verified, non-null identities",
            "service rejects missing or `NONE` identities",
            "verifies loaded policy/configuration against the bound identity",
        ):
            with self.subTest(scope="recovery", phrase=phrase):
                self.assertIn(phrase, protocol)

    def test_preflight_and_missingness_do_not_substitute_tasks(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "There are no hidden reserves or post-hoc task substitutions",
            "A task-specific setup failure is recorded with a reason",
            "Continue independent preflight/measurement slots",
            "shared setup failure before any measured slot starts",
            "Preflight is an operational readiness check",
            "MISSING_SETUP",
            "PROVIDER_UNAVAILABLE",
            "EVALUATION_INCOMPLETE",
            "`BASELINE_VECTOR_VERIFIED`",
            "`baseline_vector_ref`",
            "`baseline_vector_sha256`",
            "`baseline_raw_output_ref`",
            "`baseline_raw_output_sha256`",
            "exact per-test baseline vector and bounded raw setup output",
            "every required `FAIL_TO_PASS` test fails through a valid completed test outcome",
            "every required `PASS_TO_PASS` test passes",
            "Infrastructure, missing-test, timeout, protocol, or sandbox errors do not satisfy",
            "wrong baseline vector or baseline-condition failure is task-specific `MISSING_SETUP`",
            "separate from the measured candidate-evaluation count",
            "CANDIDATE_PATCH_INVALID",
            "EVIDENCE_INCOMPLETE",
            "INCOMPLETE_EVIDENCE",
            "No reason code is silently converted into a favorable result",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_network_free_task_eligibility_is_frozen(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "network-free evaluator compatibility",
            "required tests and task setup must be network-free",
            "DNS, external sockets, loopback, local HTTP/DB/browser-driver services, or arbitrary IPC",
            "Only `CANDIDATE_EVAL_IPC_V1` is allowed",
            "every required test and fixture preserves the frozen required-test semantics through `CANDIDATE_EVAL_IPC_V1`",
            "candidate code runs outside the trusted evaluator process",
            "trusted side does not disclose hidden test or fixture code",
            "candidate imports or monkeypatching inside the evaluator",
            "evaluator adapter/source/runtime identity",
            "before selecting the six tasks",
            "If the predicate cannot be proved, the task is ineligible",
            "recorded network-free compatibility and candidate/evaluator isolation compatibility",
            "pinned task metadata",
            "verify each selected task's recorded network-free compatibility",
            "without executing a selected task",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_evaluator_identity_is_bound_for_every_execution(self):
        raw_evaluation = read("docs/evaluation.md")
        evaluation = " ".join(raw_evaluation.split())
        manifest = " ".join(read("docs/evaluation.md").split("## Pre-P6 manifest\n", 1)[1].split(
            "## Task selection and preflight\n", 1
        )[0].split())
        preflight = " ".join(raw_evaluation.split("### Preflight\n", 1)[1].split(
            "## Execution controls\n", 1
        )[0].split())
        scoring = " ".join(raw_evaluation.split("Before a slot is scored", 1)[1].split(
            "## Measured evaluation\n", 1
        )[0].split())
        measured = " ".join(raw_evaluation.split("## Measured evaluation\n", 1)[1].split(
            "## Practical human decision\n", 1
        )[0].split())
        retained = " ".join(raw_evaluation.split("## Retained evidence and integrity rules\n", 1)[1].split())
        for scope, text, phrases in (
            ("manifest", manifest, (
                "evaluator adapter/source/runtime identity is a content identity of the loaded adapter",
                "evaluator-identity verification profile, frozen as `evaluator_verification_profile`",
                "`verification_method`, `checker_version`, `verifier_command_identity`, and `effective_verifier_configuration`",
                "complete verifier execution identity",
                "retained checker executable/script bytes, its interpreter/runtime, and all transitive checker/helper dependency bytes",
                "pinned image/archive containing them",
                "fixed before manifest hashing",
                "contain no `manifest_hash`, computed evaluator identity, or post-freeze evidence, invocation, or result references",
                "neither depends on a future evidence digest",
                "unsigned canonical payload that includes `producer_id` and `producer_provenance` and omits `evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`, and `producer_attestation_ref`",
                "separate immutable `EVALUATOR_PRODUCER_ATTESTATION_V1` envelope",
                "envelope authenticates the trusted recorder and binds `producer_id` and `producer_provenance` to the exact `evaluator_identity_evidence_ref` and `evaluator_identity_evidence_sha256`",
                "neither self-derived field is part of its own preimage",
                "evidence reference and digest bind the complete V1 payload, including `producer_id` and `producer_provenance`",
                "attestation reference is derived from the envelope with its own reference omitted, and the payload does not contain that reference",
                "no manifest/evidence hash cycle",
                "For every clean-baseline execution and candidate evaluator launch, the trusted runner persists an immutable `EVALUATOR_IDENTITY_VERIFIED` record",
            )),
            ("preflight", preflight, (
                "Before each clean-baseline execution and before every candidate evaluator launch",
                "computes the effective `evaluator_adapter_source_runtime_identity`",
                "requires exact equality with the manifest's evaluator adapter/source/runtime identity",
                "Checking mutable paths without binding loaded artifacts is insufficient",
                "persists the trusted `EVALUATOR_IDENTITY_VERIFIED` record before the execution or launch",
                "content-addressed `evaluator_identity_evidence_ref`",
                "`evaluator_identity_evidence_sha256`",
                "created from the artifacts actually loaded and pinned for that invocation",
                "record's `producer_id`, `producer_provenance`, and `producer_attestation_ref` are retained from the authenticated trusted recorder",
                "effective verifier configuration (including dependency roots, symlink policy, and transitive-content traversal rules)",
                "exact test/command identity",
                "referenced checker, interpreter/runtime, transitive dependency, and configuration content",
                "For both baseline and candidate verification",
                "observed by the trusted runner rather than copied from the manifest",
                "Before setting `verification_result=VERIFIED`, require exact equality with the frozen profile",
                "resolve `producer_attestation_ref` and verify the authenticated attestation binds the exact evidence reference and digest to `producer_id` and `producer_provenance`",
                "exact test/command identity must match that frozen profile",
                "A missing or mismatched identity, profile, evidence record, reference, digest, or referenced artifact is `EVIDENCE_INCOMPLETE`",
            )),
            ("scoring", scoring, (
                "runtime/image, `evaluator_adapter_source_runtime_identity`, `evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`, `producer_attestation_ref`, evaluator-bundle/test-definition",
                "Resolve `producer_attestation_ref` from that integrity-bound `BASELINE_VECTOR_VERIFIED` consumer record, verify it matches the retained V1 record metadata and the consumer's exact evidence reference and digest, then verify its authenticated `EVALUATOR_PRODUCER_ATTESTATION_V1` envelope binds that exact evidence reference and digest to the payload's `producer_id` and `producer_provenance`",
                "Missing, unknown, unauthenticated, or mismatched producer provenance or attestation is `EVIDENCE_INCOMPLETE`",
                "`EVALUATOR_IDENTITY_VERIFIED_V1` schema",
                "every referenced immutable artifact",
                "validate the complete `evaluator_verification_profile` against the frozen manifest",
                "Resolve and digest-check its retained checker, interpreter/runtime, transitive checker/dependency, and configuration content",
                "A changed checker helper, interpreter/runtime, or transitive dependency byte is a subject mismatch and produces `EVIDENCE_INCOMPLETE`",
                "Missing, unreadable, corrupt, untrusted, or mismatched profile fields or referenced content produce `EVIDENCE_INCOMPLETE`",
                "no candidate verification record is required when no candidate evaluator was dispatched",
                "Require the bound `NETWORK_DENIAL_VERIFIED` record and its bounded diagnostics for every slot",
                "If a candidate evaluator was actually dispatched",
                "For `NO_PATCH` or `CANDIDATE_PATCH_INVALID` with `evaluator_invocation: NOT_DISPATCHED`, do not require a candidate evaluator invocation or measured sandbox",
                "revalidate the retained preflight `NETWORK_DENIAL_VERIFIED` record and its policy identity and diagnostics against the manifest and candidate sandbox policy only",
                                "revalidate the effective `evaluator_adapter_source_runtime_identity`, `evaluator_identity_evidence_ref`/`evaluator_identity_evidence_sha256`, and `producer_attestation_ref` from the integrity-bound evaluator `STARTED` or terminal result record against the manifest, the immutable verification record, the invocation's exact evidence reference and digest, and the loaded evaluator used for that invocation",
                                "Resolve the attestation and verify its authenticated envelope binds that exact candidate evidence reference and digest to the candidate payload's producer fields",
            )),
            ("measured", measured, (
                "invocation record binds the manifest hash",
                "`evaluator_adapter_source_runtime_identity`, `evaluator_identity_evidence_ref`, `evaluator_identity_evidence_sha256`, `producer_attestation_ref`, evaluator bundle digest",
                "terminal result record repeats that full invocation binding",
                "`producer_attestation_ref` is bound in the evaluator `STARTED` and terminal result consumer records",
                "Before reusing a completed baseline after restart, obtain its `producer_attestation_ref` from the integrity-bound `BASELINE_VECTOR_VERIFIED` consumer record and cross-check it against the retained V1 record and exact evidence reference/digest",
                "For a candidate evaluation after restart, obtain `producer_attestation_ref` from the integrity-bound candidate `STARTED` or terminal result record and cross-check it against the retained V1 record and exact candidate evidence reference/digest; perform the same evaluator identity, producer-provenance, verifier-profile, producer-attestation, and retained-content checks only when a candidate evaluator was actually dispatched",
                "do not require a candidate `EVALUATOR_IDENTITY_VERIFIED` record, evaluator invocation, or measured sandbox",
                "revalidate the terminal outcome, its complete no-evaluation/patch-validation evidence, the explicit marker, and the mandatory baseline proof against the manifest and retained evidence",
                "Apply the same scoring-time producer identity/provenance, verifier-profile, trusted producer-attestation and retained-content checks to the mandatory baseline proof and any dispatched candidate proof during read-only restart reconciliation",
                "do not substitute current producer metadata or regenerate provenance",
            )),
            ("retained", retained, (
                "their effective evaluator adapter/source/runtime identities, the `EVALUATOR_IDENTITY_VERIFIED` records, their `producer_id`, `producer_provenance`, and `producer_attestation_ref` values, the retained authenticated producer attestation envelopes required to bind each evidence payload, their content-addressed `evaluator_identity_evidence_ref` values and `evaluator_identity_evidence_sha256` digests, and bound verification evidence",
                "Also retain every `evaluator_verification_profile` and all checker, interpreter/runtime, and transitive checker dependency bytes, plus all referenced configuration content (or a pinned image/archive containing them)",
            )),
        ):
            for phrase in phrases:
                with self.subTest(scope=scope, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_task_success_rule_is_non_vacuous(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "at least one non-empty `FAIL_TO_PASS` test",
            "A task with an empty `FAIL_TO_PASS` vector is ineligible",
            "makes the success rule non-vacuous",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_network_denial_requires_bound_authoritative_evidence(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "direct namespace-policy verification",
            "controlled reachable canaries",
            "policy-specific denial",
            "ordinary DNS resolution, timeout, or connection-refused errors",
            "Persist a `NETWORK_DENIAL_VERIFIED` result",
            "bounded network-denial smoke diagnostics",
            "manifest/runtime/sandbox-policy-bound",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_network_denial_binds_invocation_and_final_scoring(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "candidate sandbox policy identity/configuration",
            "The `NETWORK_DENIAL_VERIFIED` record is the authority for every measured candidate sandbox",
            "Before each evaluator launch",
            "`sandbox_policy_id`",
            "`network_denial_evidence_ref`",
            "Revalidate `sandbox_policy_id` and `network_denial_evidence_ref` against the manifest",
            "loss, corruption, or mismatch produces `EVIDENCE_INCOMPLETE`",
            "terminal `TRUSTED_RESULT`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_worker_network_isolation_precedes_task_exposure(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "every worker-controlled tool/process under a network-denied policy",
            "no DNS, external socket, loopback, or arbitrary host-IPC egress",
            "remote-solution retrieval attempt",
            "`WORKER_NETWORK_DENIAL_VERIFIED`",
            "before task exposure",
            "Before exposing any selected task and before every later agent-attempt launch",
            "including a clean whole-slot retry",
            "persist an attempt-specific `WORKER_NETWORK_DENIAL_VERIFIED` result",
            "`agent_attempt_id`",
            "slot-level record cannot be reused for a new attempt",
            "attempt-specific `WORKER_NETWORK_DENIAL_VERIFIED` record and bounded diagnostics",
            "do not launch the attempt or expose a selected task",
            "`worker_policy_id`",
            "`worker_network_evidence_ref`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_reopen_preserves_nonempty_journals(self):
        for path in ("docs/modules.md", "docs/protocol.md"):
            document = " ".join(read(path).split())
            with self.subTest(path=path):
                self.assertIn(
                    "Version zero and an empty journal apply only to a newly created run",
                    document,
                )
                self.assertIn(
                    "reopening preserves the persisted journal and current graph version",
                    document,
                )

    def test_missing_patch_bytes_remain_incomplete_evidence(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        reporting = evaluation.split("### Incomplete reporting", 1)[1].split(
            "## Practical human decision", 1
        )[0]
        self.assertIn(
            "`CANDIDATE_PATCH_INVALID` — a completed trusted validator `REJECT` proves retained, digest-verified candidate content is demonstrably malformed",
            reporting,
        )
        self.assertIn(
            "`EVIDENCE_INCOMPLETE` — mandatory evidence is missing, unreadable, corrupt, or fails its binding checks",
            reporting,
        )
        self.assertIn("takes precedence over candidate-failure classification", reporting)
        self.assertNotIn(
            "`CANDIDATE_PATCH_INVALID` — the produced patch is absent",
            reporting,
        )

    def test_patch_rejection_and_no_patch_have_distinct_outcomes(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "trusted, evidenced `CANDIDATE_PATCH_INVALID` rejection is an observed 0",
            "A durable terminal agent `NO_PATCH` outcome with complete required evidence",
            "Patch validation is a trusted coordinator transition separate from the evaluator's `TRUSTED_RESULT` status",
            "durable terminal agent/slot outcome with code `CANDIDATE_PATCH_INVALID`",
            "`agent_attempt_id`, candidate-patch digest and retained-byte reference",
            "`evaluator_invocation: NOT_DISPATCHED` marker",
            "absence of a patch artifact alone does not establish `NO_PATCH`",
            "candidate evaluation produced neither a completed required test vector nor a complete, evidenced candidate-patch rejection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

        methodology = " ".join(read("docs/methodology.md").split())
        for phrase in (
            "A completed, evidenced `CANDIDATE_PATCH_INVALID` rejection is also a terminal observed zero without a test vector",
            "An incomplete or missing rejection remains undefined",
        ):
            with self.subTest(scope="methodology", phrase=phrase):
                self.assertIn(phrase, methodology)

    def test_measured_contract_is_one_run_and_reports_raw_pairs(self):
        evaluation = read("docs/evaluation.md")
        measured = evaluation.split("## Measured evaluation\n", 1)[1].split(
            "## Practical human decision\n", 1
        )[0]
        for phrase in (
            "run A and C once",
            "Evaluate each produced candidate patch once",
            "exact candidate patch bytes and digest",
            "y_i(X) = 1",
            "d_i(C-A)",
            "mean_delta_pp",
            "per-task deltas",
            "unresolved reasons",
            "INCOMPLETE_COVERAGE",
            "do not assign the complete-pilot",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, measured)

    def test_continuation_labels_have_human_checkpoint_criteria(self):
        evaluation = read("docs/evaluation.md")
        decision = " ".join(evaluation.split("## Practical human decision\n", 1)[1].split(
            "## Practical sensitivity report\n", 1
        )[0].split())
        for phrase in (
            "CONTINUE",
            "ADAPT",
            "STOP",
            "useful local improvement or reduced failure",
            "without a critical regression",
            "acceptable",
            "concrete, plausibly correctable weakness",
            "critical correctness, isolation, security, or operational regression",
            "An incomplete pilot receives no one of these labels",
            "An unresolved critical regression precludes `CONTINUE`",
            "The decision maker",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, decision)

    def test_sensitivity_warning_is_simple_and_nonacademic(self):
        evaluation = read("docs/evaluation.md")
        sensitivity = " ".join(evaluation.split("## Practical sensitivity report\n", 1)[1].split(
            "## Retained evidence and integrity rules\n", 1
        )[0].split())
        for phrase in (
            "leave-one-task-out",
            "HARM",
            "NEUTRAL",
            "BENEFIT",
            "SENSITIVITY_DISCORDANT",
            "changes sign or band",
            "does not force `STOP`, `ADAPT`, or `CONTINUE`",
            "Do not compute a sensitivity label for incomplete coverage",
            "does not include bootstrap intervals, p-values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, sensitivity)

    def test_eventstore_port_uses_serialized_recovery(self):
        module = read("docs/modules.md")
        contract = module.split("Conceptual port contract:\n", 1)[1].split(
            "```\n\nRequirements:", 1
        )[0]
        self.assertIn("record_proposal(run_id, proposal_id", contract)
        self.assertIn("append_audit(run_id, records[], proposal_id?)", contract)
        self.assertIn("append_graph(run_id, proposal_id, expected_graph_version", contract)
        self.assertNotIn("claim_proposal(", contract)
        self.assertNotIn("renew_claim(", contract)
        for phrase in (
            "service startup refuses a second owner",
            "serialized recovery",
            "restart recovery of incomplete receipts",
            "Restart recovery of an incomplete receipt applies only to durable providers",
            "`MemoryEventStore` cannot claim process-restart recovery",
            "`IDEMPOTENCY_CONFLICT`",
            "stored and supplied canonical request hashes",
            "Add claims, leases, or parallel workers only after a measured requirement",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, module)

    def test_protocol_preserves_terminal_and_graph_integrity(self):
        protocol = read("docs/protocol.md")
        terminal = " ".join(protocol.split("#### Terminal append binding\n", 1)[1].split(
            "#### Graph append binding\n", 1
        )[0].split())
        graph = " ".join(protocol.split("#### Graph append binding\n", 1)[1].split(
            "#### Proposal recovery responses\n", 1
        )[0].split())
        for phrase in (
            "non-null `run_id` and `proposal_id`",
            "more than one terminal record",
            "no existing terminal outcome",
            "`COMMIT` is forbidden in `append_audit`",
            "never advance `graph_version`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, terminal)
        for phrase in (
            "expected graph version",
            "exactly one `COMMIT`",
            "`INVALID_GRAPH_BATCH`",
            "proposal receipt's recorded `expected_graph_version`",
            "current run `graph_version`",
            "increments graph version exactly once",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, graph)
        self.assertIn("serialized", protocol)
        self.assertNotIn("STALE_CLAIM", protocol)
        self.assertNotIn("expected_owner_id", protocol)
        self.assertNotIn("expected_claim_epoch", protocol)
        self.assertNotIn("spec-protocol-lease-clock", protocol)

    def test_stale_proposals_conflict_before_policy_and_terminal_append(self):
        protocol = " ".join(read("docs/protocol.md").split())
        for phrase in (
            "Before evaluating any governance policy",
            "compares it with the receipt's stored `expected_graph_version`",
            "do not invoke schema/evidence/governance policy",
            "do not append `REJECT`, `RETRY`, `ESCALATE`, or `COMMIT`",
            "append exactly one terminal `CONFLICT` audit record",
            "before returning `CONFLICT`",
            "rechecks this version precondition before any terminal append",
            "must never finalize `REJECT`, `RETRY`, or `ESCALATE` for a stale receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, protocol)

    def test_public_graph_audit_surface_is_bounded(self):
        protocol = " ".join(read("docs/protocol.md").split())
        for phrase in (
            "get_audit_timeline(run_id, limit, after_journal_position?)",
            "That limit is an integer, required, positive, finite",
            "next_after_journal_position",
            "has_more",
            "limit is an integer",
            "`has_more` indicates whether additional visible records existed after that cursor when the query was read",
            "Later appends may be retrieved by polling the returned cursor",
            "no unbounded journal response",
            "filtered public projections",
            "authorizes run creation before registering a supplied run ID",
            "performs caller-to-run authorization for the explicit `run_id` before any other run-scoped command or query reads or mutates that run",
            "they do not return normalized mutation operations",
            "Proposal-status and audit responses return only",
            "Graph-state projections may include immutable evidence references",
            "never expose evidence content",
            "raw `read_journal` records remain internal",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, protocol)

    def test_store_owner_and_recovery_are_the_initial_scope(self):
        protocol = read("docs/protocol.md")
        owner = protocol.split("#### STORE-OWNER\n", 1)[1].split(
            "#### Deferred parallel proposal claims\n", 1
        )[0]
        for phrase in (
            "exactly one live EventStore provider instance",
            "before loading journal state",
            "STORE_IN_USE",
            "same-process",
            "crash",
            "serialized by the owning service",
            "incomplete receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, owner)
        self.assertIn("does not expose `claim_ttl`", " ".join(protocol.split()))
        self.assertIn("Parallel claims are a deferred extension", protocol)

    def test_adr_and_instructions_match_practical_scope(self):
        adr = read("docs/adr/0006-authoritative-domain-events-and-stream-concurrency.md")
        agents = read("AGENTS.md")
        for text, phrases in (
            (adr, ("serializes proposal evaluation", "no `claim_ttl`", "Parallel workers, leases, and fencing are explicitly deferred")),
            (agents, ("one exclusive owner", "does not add claims, leases, or fencing epochs", "serializes proposal processing")),
        ):
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertIn(phrase, text)

    def test_requirement_ids_have_one_owner_and_are_mapped(self):
        expected = {
            "GRAPH.MODEL": "docs/problem-graph.md",
            "MODULES.EVENTSTORE-PORT": "docs/modules.md",
            "PROTOCOL.STORE-OWNER": "docs/protocol.md",
            "PROTOCOL.PARALLEL-CLAIMS": "docs/protocol.md",
            "PROTOCOL.PROPOSAL-RECOVERY": "docs/protocol.md",
            "VERIFICATION.EVIDENCE-TRUST": "docs/verification.md",
            "VERIFICATION.EVIDENCE-BINDING": "docs/verification.md",
            "VERIFICATION.EVIDENCE-RECOVERY": "docs/verification.md",
            "EVALUATION.MODEL": "docs/evaluation.md",
            "EVALUATION.PRE-P6": "docs/evaluation.md",
            "EVALUATION.PREFLIGHT": "docs/evaluation.md",
            "EVALUATION.MEASURED-EVALUATION": "docs/evaluation.md",
            "REVIEW.LOOP": "docs/review-loop.md",
        }
        found = {}
        for path in (ROOT / "docs").rglob("*.md"):
            for spec_id in re.findall(r"<!-- spec-id: ([A-Z0-9.-]+) -->", path.read_text(encoding="utf-8")):
                found.setdefault(spec_id, []).append(path.relative_to(ROOT).as_posix())
        self.assertEqual(set(found), set(expected))
        ownership = read("docs/specification-checks.md")
        for spec_id, owners in found.items():
            with self.subTest(spec_id=spec_id):
                self.assertEqual(owners, [expected[spec_id]])
                owner = read(expected[spec_id])
                anchor = "spec-" + re.sub(r"[^a-z0-9]+", "-", spec_id.lower()).strip("-")
                self.assertIn(f'<a id="{anchor}"></a>', owner)
                self.assertIn(f"`{spec_id}`", ownership)
                self.assertIn(f"({Path(expected[spec_id]).name}#{anchor})", ownership)

    def test_run_registration_and_graph_version_rules_remain_explicit(self):
        module = " ".join(read("docs/modules.md").split())
        self.assertIn("create_run(run_id, run_metadata)", module)
        self.assertIn("RUN_METADATA_CONFLICT", module)
        self.assertIn("proposal IDs are supplied by clients and are never minted or replaced by the service", module)
        self.assertIn("graph_version=0, last_journal_position=0", module)
        self.assertIn("every operation against an unknown run returns `NOT_FOUND`", module)
        for phrase in (
            "proposal receipt's recorded `expected_graph_version`",
            "`INVALID_GRAPH_BATCH`",
            "current run `graph_version`",
            "audit-only writes never advance graph version",
            "monotonic per-run `journal_position`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, module)

    def test_evidence_trust_and_recovery_remain_independent(self):
        verification = read("docs/verification.md")
        for phrase in (
            "Worker-supplied origin and method are claims",
            "cannot assign trusted provenance",
            "subject_digest",
            "checker_version",
            "EVIDENCE-RECOVERY",
            "ABANDONED",
            "the owning service records `ABANDONED`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, verification)

        verification_text = " ".join(verification.split())
        self.assertIn(
            "A stale graph version is a protocol `CONFLICT` before policy decision",
            verification_text,
        )
        self.assertIn(
            "not a C `REJECT` or `ESCALATE` classification",
            verification_text,
        )

    def test_plan_keeps_p11_portability_and_package_level_p6(self):
        plan = read("PLAN.md")
        self.assertIn("portability validation belongs to P11", plan)
        self.assertIn("one compact manifest", plan)
        self.assertIn("small paired A/C pilot", plan)
        self.assertIn("at least one controlled benchmark compares the baseline", plan)
        self.assertIn(
            "all reported improvements include cost/latency and the coverage/validity evidence required by their frozen experiment contract",
            plan,
        )
        self.assertIn(
            "the single-run P6 pilot is reported as a practical paired observation, not as repeated-run statistics",
            plan,
        )

    def test_methodology_is_discoverable_and_not_a_second_algorithm(self):
        methodology = " ".join(read("docs/methodology.md").split())
        self.assertIn("not a publication-grade uncertainty model", methodology)
        self.assertIn("current contract is owned by `docs/evaluation.md`", methodology)
        self.assertIn("SENSITIVITY_DISCORDANT", methodology)
        self.assertIn("[Methodology audit and decision register](docs/methodology.md)", read("README.md"))

    def test_relative_document_links_resolve(self):
        for path in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue((path.parent / target.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
