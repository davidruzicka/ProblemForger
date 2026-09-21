"""P0 document regression checks, not tests of a production implementation."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class SpecificationChecks(unittest.TestCase):
    def test_service_runtime_is_frozen_and_recorded(self):
        evaluation = read("docs/evaluation.md")
        freeze = evaluation.split("### Pre-P6 frozen artifacts", 1)[1].split("### Task source", 1)[0]
        self.assertIn("8. **`problemforger-runtime-v1`**", freeze)
        self.assertIn("Every C attempt records", freeze)
        self.assertIn("ProblemForger source", freeze)
        self.assertIn("`problemforger-runtime-v1` hash and actual service image/archive digest", evaluation)

    def test_transport_retry_acceptance_is_call_scoped(self):
        evaluation = read("docs/evaluation.md")
        retries = evaluation.split("### Provider-call transport retries", 1)[1].split("### Whole-agent-run replacement", 1)[0]
        self.assertIn("no response for the current model call has been accepted", retries)
        self.assertIn("Earlier calls' accepted responses do not disable", retries)
        self.assertIn("partially accepted assistant content or tool calls", retries)

    def test_store_ownership_is_enforced_before_clock_initialization(self):
        protocol = read("docs/protocol.md")
        self.assertIn("#### STORE-OWNER", protocol)
        self.assertIn("STORE_IN_USE", protocol)
        self.assertIn("before initializing the lease clock", protocol)
        self.assertIn("same-process", protocol)
        self.assertIn("crash", protocol)

    def test_evidence_trust_is_not_worker_controlled(self):
        verification = read("docs/verification.md")
        self.assertIn("### EVIDENCE-TRUST", verification)
        self.assertIn("Worker-supplied origin and method are claims", verification)
        self.assertIn("cannot assign trusted provenance", verification)

    def test_evidence_is_bound_and_recoverable(self):
        verification = read("docs/verification.md")
        self.assertIn("### EVIDENCE-BINDING", verification)
        self.assertIn("subject_digest", verification)
        self.assertIn("checker_version", verification)
        self.assertIn("### EVIDENCE-RECOVERY", verification)
        self.assertIn("ABANDONED", verification)
        self.assertIn("evidence content identities", read("docs/protocol.md"))

    def test_preflight_disagreement_is_terminal_without_third_control(self):
        evaluation = read("docs/evaluation.md")
        preflight = evaluation.split("### Task/evaluator preflight\n", 1)[1].split("### Measured candidate patches", 1)[0]
        self.assertNotIn("run one third control evaluation", preflight)
        self.assertIn("classify the candidate as `EVALUATOR_UNSTABLE` immediately", preflight)
        self.assertIn("cannot abort the experiment", preflight)
        self.assertIn("diagnostic", preflight)

    def test_model_chain_handles_post_exposure_exhaustion(self):
        evaluation = read("docs/evaluation.md")
        model = evaluation.split("### Model\n", 1)[1].split("### Agent budget", 1)[0]
        self.assertIn("model-chain-v1", model)
        self.assertIn("ordered model chain", model)
        self.assertIn("MODEL_UNAVAILABLE_AFTER_EXPOSURE", model)
        self.assertIn("INCOMPLETE_INFRASTRUCTURE", model)
        self.assertIn("MODEL_UNAVAILABLE_BEFORE_EXPOSURE", model)
        self.assertIn("new blinded task selection", model)
        self.assertIn("Models are never mixed", model)

    def test_p6_temperature_capability_is_frozen_and_harness_comparison_is_separate(self):
        evaluation = read("docs/evaluation.md")
        model = evaluation.split("### Model\n", 1)[1].split("### Separate harness-comparison experiment\n", 1)[0]
        comparison = evaluation.split("### Separate harness-comparison experiment\n", 1)[1].split("### Agent budget\n", 1)[0]

        self.assertIn("temperature=0", model)
        self.assertIn("capability probe", model)
        self.assertIn("chain entry is\nunavailable", model)
        self.assertIn("do not silently omit the field", model)

        for phrase in (
            "separate project-level experiment",
            "Never pool `P6-HARNESS-v1` results",
            "exploratory only",
            "new blinded task selection",
            "same model identifier",
            "not semantic equivalence",
            "generation-policy-v1",
            "EXPLICIT(value)",
            "OMITTED_NATIVE",
            "UNSUPPORTED",
            "UNKNOWN",
            "absence from a request is not evidence",
            "do not emulate it",
            "interleaved harness/configuration schedule",
            "A 2×2 harness-by-A/C design",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, comparison)

    def test_p6_is_a_practical_pilot_with_bounded_operational_reporting(self):
        evaluation = read("docs/evaluation.md")
        normalized = " ".join(evaluation.split())
        for phrase in (
            "practical whole-system feasibility pilot",
            "P6-AC",
            "eight target tasks and four predeclared reserves",
            "two independent agent runs per task and configuration",
            "32 measured slots",
            "C - A",
            "CONTINUE",
            "ADAPT",
            "STOP",
            "Academic uncertainty is acceptable",
            "finite total elapsed-time limit",
            "finite provider-spend guard",
            "runtime digest identifies the retained runtime/harness bytes, **not hosted model identity**",
            "do not automatically start P7",
            "No primary point delta",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_practical_continuation_rule_is_frozen(self):
        evaluation = read("docs/evaluation.md")
        interpretation = evaluation.split("### Practical continuation decision\n", 1)[1].split("### Practical sensitivity report\n", 1)[0]
        interpretation = " ".join(interpretation.split())

        for phrase in (
            "CONTINUE",
            "ADAPT",
            "STOP",
            "critical correctness, isolation, security, or operational regression",
            "operational overhead is acceptable",
            "not a statistical gate",
            "can be deduced from the current plan",
            "Incomplete experiments receive no continuation label",
            "zero or unavailable baseline",
            "measurement units and sources",
            "insufficient practical value",
            "Record the decision maker, evidence, and rationale",
            "does not force any continuation label",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, interpretation)

    def test_sensitivity_discordance_is_a_practical_warning(self):
        evaluation = read("docs/evaluation.md")
        sensitivity = evaluation.split("### Practical sensitivity report\n", 1)[1].split("### Secondary end-to-end metrics\n", 1)[0]
        sensitivity = " ".join(sensitivity.split())
        for phrase in (
            "two fresh repetitions",
            "For `k ∈ {1,2}`",
            "SENSITIVITY_DISCORDANT",
            "differs in sign or band",
            "delta = 10",
            "max_abs_deviation_pp",
            "does not block the local operational decision",
            "No bootstrap, p-value, confidence interval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, sensitivity)

    def test_sensitivity_sign_and_closed_neutral_band_are_explicit(self):
        section = read("docs/evaluation.md").split("### Practical sensitivity report\n", 1)[1].split("### Secondary end-to-end metrics\n", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "`sign(x) = -1` for `x < 0`, `0` for `x = 0`, and `+1` for `x > 0`",
            "`HARM` for `x < -10`",
            "`NEUTRAL` for `-10 <= x <= +10`",
            "`BENEFIT` for `x > +10`",
            "exactly -10 and +10 are `NEUTRAL`",
            "if and only if at least one leave-one-repetition-out estimate",
            "differs in sign or band from the full two-repetition point estimate",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_provider_retries_require_bounded_progression(self):
        section = read("docs/evaluation.md").split("### Provider-call transport retries\n", 1)[1].split("### Whole-agent-run replacement\n", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "Every eligible transport failure requires the next transport attempt",
            "must not voluntarily stop",
            "until a semantic response is produced, a nonretryable result occurs, the semantic deadline or resource budget is exhausted, or all 3 attempts are exhausted",
            "`WALL_CLOCK_EXHAUSTED` takes precedence and no whole-run replacement is allowed",
            "`INFRA_FIRST_PROVIDER_CALL`",
            "`PRE_SEMANTIC_PROVIDER_FAILURE`",
            "unresolved `RUN_INTERRUPTED`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_evaluator_retries_require_bounded_progression(self):
        section = read("docs/evaluation.md").split("### Evaluator infrastructure retries\n", 1)[1].split("### Task/evaluator preflight\n", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "Every eligible pre-test infrastructure failure requires the next evaluator attempt",
            "must not voluntarily stop",
            "until a complete required-test vector is produced, a nonretryable result occurs, or all 3 attempts are exhausted",
            "experiment-wide stop takes precedence",
            "`EVAL_IMAGE_SETUP`", "`EVAL_CONTAINER_START`", "`EVAL_EVALUATOR_START`",
            "`EVALUATOR_INVALID`", "`EVALUATION_INCOMPLETE`", "`CANDIDATE_PATCH_INVALID`",
            "classify the experiment `INCOMPLETE_INFRASTRUCTURE`",
            "report no primary point delta",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_post_test_preflight_failure_cannot_activate_reserve_on_outage(self):
        evaluation = read("docs/evaluation.md")
        section = evaluation.split("### Evaluator infrastructure retries\n", 1)[1].split("### Task-artifact preflight exclusions\n", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "positively identifies container, host, storage, or equivalent shared-infrastructure loss",
            "`INCOMPLETE_INFRASTRUCTURE`",
            "must not activate a reserve",
            "demonstrated patch-independent task/evaluator defect",
            "unknown or mixed cause",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_task_artifact_exclusion_is_pre_measurement_only(self):
        evaluation = read("docs/evaluation.md")
        artifact = evaluation.split("### Task-artifact preflight exclusions\n", 1)[1].split("<a id=\"spec-evaluation-measured-evaluation\">", 1)[0]

        for phrase in (
            "`INFRA_TASK_ARTIFACT`",
            "configuration-neutral, patch-independent preflight",
            "before the eligible-task count\n`N` is computed",
            "before\nthe measured schedule is hashed",
            "missing, corrupt, or schema-incompatible",
            "Network/image-pull failures",
            "must not be relabeled as task invalidity",
            "primary/reserve\npool before measurement",
            "with the next predeclared reserve",
            "after the first measured slot starts",
            "INCOMPLETE_INFRASTRUCTURE",
            "unknown/mixed",
            "post-semantic failure",
            "does not exclude the task",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, artifact)

        whole_run = evaluation.split("### Whole-agent-run replacement\n", 1)[1].split("### Evaluator infrastructure retries\n", 1)[0]
        self.assertIn("If all 3 attempts fail", whole_run)
        self.assertIn("stop launching new measured schedule slots", whole_run)

    def test_eligible_whole_run_failures_consume_remaining_replacements(self):
        evaluation = read("docs/evaluation.md")
        whole_run = evaluation.split("### Whole-agent-run replacement\n", 1)[1].split("### Evaluator infrastructure retries\n", 1)[0]
        normalized = " ".join(whole_run.split())
        for phrase in (
            "Every eligible pre-semantic failure requires the next clean replacement",
            "while one of the two replacement attempts remains",
            "must not voluntarily stop",
            "until an attempt succeeds, terminates nonretryably, or all 3 attempts are exhausted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_unavailable_images_cannot_be_task_artifact_exclusions(self):
        evaluation = read("docs/evaluation.md")
        artifact = evaluation.split("### Task-artifact preflight exclusions\n", 1)[1].split("### Measured candidate patches", 1)[0]
        normalized = " ".join(artifact.split())
        for phrase in (
            "intrinsic defect in successfully retrieved, digest-verified task content",
            "Unavailable image content takes precedence over `INFRA_TASK_ARTIFACT`",
            "`EVAL_IMAGE_SETUP`",
            "missing mirror/cache object",
            "does not change `N`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_image_materialization_and_setup_failures_have_distinct_phases(self):
        evaluation = read("docs/evaluation.md")
        materialization = evaluation.split("### Deterministic task selection\n", 1)[1].split("### Repetitions, run isolation, and execution ordering\n", 1)[0]
        preflight = evaluation.split("### Task-artifact preflight exclusions\n", 1)[1].split("### Measured candidate patches", 1)[0]

        for phrase in (
            "materialization-time image resolution",
            "does not enter preflight",
            "recorded immutable identity",
        ):
            with self.subTest(phase="materialization", phrase=phrase):
                self.assertIn(phrase, materialization)
        for phrase in (
            "after materialization",
            "EVAL_IMAGE_SETUP",
            "does not change `N`",
        ):
            with self.subTest(phase="preflight", phrase=phrase):
                self.assertIn(phrase, preflight)

    def test_harness_runtime_is_fully_content_addressed(self):
        evaluation = read("docs/evaluation.md")
        runtime = evaluation.split("7. **`harnessx-runtime-v1`**\n", 1)[1].split("All five contract artifacts", 1)[0]
        self.assertIn("complete transitive dependency lockfile", runtime)
        self.assertIn("repository@sha256:<digest>", runtime)
        self.assertIn("mutable tags", runtime)
        self.assertIn("HarnessX commit alone is not a sufficient runtime identity", evaluation)

    def test_missing_candidate_vector_does_not_skip_other_repetition(self):
        evaluation = read("docs/evaluation.md")
        measured = evaluation.split("### Measured candidate patches\n", 1)[1].split("## Later verifier/calibration split", 1)[0]
        self.assertIn("still execute and retain the other mandatory repetition", measured)
        self.assertIn("unless an experiment-wide stop has already been triggered", measured)
        self.assertNotIn("may still be retained/executed", measured)

    def test_lease_clock_algorithm_has_one_normative_home(self):
        # These formulas previously appeared in independently maintained copies.
        copies = []
        for path in (ROOT / "docs").rglob("*.md"):
            if re.search(r"max\(persisted[_ ](?:lease_clock_floor_ms|floor)", path.read_text()):
                copies.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(copies, ["docs/protocol.md"])

    def test_lease_commands_accept_ttl_not_caller_deadline(self):
        for path in (ROOT / "docs").rglob("*.md"):
            for match in re.finditer(r"\b(?:claim_proposal|renew_claim)\((.*?)\)", path.read_text(), re.S):
                with self.subTest(path=str(path), signature=match[0]):
                    self.assertTrue("claim_ttl_ms" in match[1], "Provider must receive a TTL")
                    self.assertFalse("lease_expires_at_ms" in match[1], "Caller cannot set provider time")

    def test_lease_persistence_has_one_complete_requirement(self):
        protocol = read("docs/protocol.md")
        bullets = re.findall(r"^- the durable EventStore persists a per-store .*", protocol, re.M)
        self.assertEqual(bullets, [
            "- the durable EventStore persists a per-store `lease_clock_floor_ms` and `lease_clock_generation`;",
        ])

    def test_expired_claim_cannot_finalize_or_renew(self):
        protocol = read("docs/protocol.md")
        lease = protocol.split("#### LEASE-CLOCK\n", 1)[1].split("#### Proposal recovery responses", 1)[0]
        self.assertIn("an expired claim is no longer active", lease)
        self.assertIn("renewal of an expired claim fails `STALE_CLAIM`", lease)
        self.assertIn("lease_expires_at_ms > lease_now_ms", lease)
        self.assertIn("before any final decision or graph mutation", lease)
        self.assertIn("lease_clock_generation", lease)
        self.assertIn("earlier generation is treated as expired/inactive", lease)
        self.assertIn("current, unexpired claim", read("docs/adr/0006-authoritative-domain-events-and-stream-concurrency.md"))
        self.assertIn("expired claim as inactive", read("docs/modules.md"))

    def test_every_graph_append_signature_requires_fencing(self):
        matches = []
        for path in (ROOT / "docs").rglob("*.md"):
            for match in re.finditer(r"\bappend_graph\((.*?)\)", path.read_text(), re.S):
                matches.append((path.relative_to(ROOT).as_posix(), match[0]))
        self.assertEqual([path for path, _ in matches], ["docs/modules.md"])
        for path, signature in matches:
            with self.subTest(path=path, signature=signature):
                args = signature[signature.index("(") + 1 : -1]
                self.assertTrue(
                    "proposal_id" in args
                    and "expected_owner_id" in args
                    and "expected_claim_epoch" in args
                )
                self.assertFalse("proposal_id?" in args or "expected_claim_epoch?" in args)

    def test_claim_operations_have_one_normative_home(self):
        matches = []
        for path in (ROOT / "docs").rglob("*.md"):
            text = path.read_text()
            for name in ("claim_proposal", "renew_claim"):
                if re.search(rf"\b{name}\(", text):
                    matches.append((name, path.relative_to(ROOT).as_posix()))
        self.assertEqual(
            matches,
            [("claim_proposal", "docs/modules.md"), ("renew_claim", "docs/modules.md")],
        )
        module = read("docs/modules.md")
        self.assertIn("PENDING {claim_epoch, lease_expires_at_ms}", module)
        self.assertNotIn("BUSY {claim_epoch, lease_expires_at_ms}", module)
        self.assertIn("expected_claim_epoch, claim_ttl_ms", module)

    def test_eventstore_registers_runs_before_proposals(self):
        module = read("docs/modules.md")
        contract = module.split("Conceptual port contract:\n", 1)[1].split("```\n\nRequirements:", 1)[0]
        self.assertIn("create_run(run_id, run_metadata)", contract)
        self.assertIn("RUN_METADATA_CONFLICT", contract)
        self.assertIn("canonical serialization", module)
        self.assertIn("CREATED {metadata_hash, graph_version=0, last_journal_position=0}", contract)
        self.assertIn("graph_version=0, last_journal_position=0", contract)
        self.assertIn("get_run(run_id)", contract)
        self.assertIn("| NOT_FOUND", contract)
        self.assertNotIn("stream_id", contract)
        self.assertIn("read_journal(run_id, after_journal_position?, limit)", contract)
        self.assertIn("has_more", contract)
        self.assertIn("`after_journal_position` is an exclusive cursor", module)
        self.assertIn("persist run registration before accepting proposals", module)

        for operation in (
            "record_proposal",
            "claim_proposal",
            "renew_claim",
            "append_audit",
            "append_graph",
            "read_journal",
            "current_graph_version",
        ):
            match = re.search(
                rf"\b{operation}\(.*?\)\n    ->(?P<returns>.*?)(?=\n\n|\Z)",
                contract,
                re.S,
            )
            self.assertIsNotNone(match, operation)
            self.assertIn("NOT_FOUND", match.group("returns"), operation)

    def test_resource_budget_is_frozen_before_probe_and_survives_restart(self):
        evaluation = read("docs/evaluation.md")
        budget = evaluation.split("### Experiment resource envelope\n", 1)[1].split("### Pre-P6 frozen artifacts", 1)[0]
        for phrase in (
            "Before any capability probe",
            "No capability probe or preflight operation may start the experiment clock before this budget freeze",
            "persist the start-time anchor, derived deadline",
            "runner restart reopens that same record",
            "must not reset the elapsed clock",
            "unknown-charge reservation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, " ".join(budget.split()))

    def test_terminal_writes_bind_claim_owner_and_epoch(self):
        module = read("docs/modules.md")
        protocol = read("docs/protocol.md")
        audit = re.search(r"\bappend_audit\((.*?)\)", module, re.S).group(1)
        graph = re.search(r"\bappend_graph\((.*?)\)", module, re.S).group(1)
        self.assertIn("expected_owner_id", audit)
        self.assertIn("expected_claim_epoch", audit)
        self.assertIn("expected_owner_id", graph)
        self.assertIn("both expected owner identity and claim epoch", protocol)

    def test_audit_port_has_conditional_terminal_arguments(self):
        module = read("docs/modules.md")
        self.assertIn("append_audit(run_id, records[], proposal_id?, expected_owner_id?, expected_claim_epoch?)", module)
        returns = module.split("append_audit(", 1)[1].split("append_graph(", 1)[0]
        self.assertIn("INVALID_AUDIT_BATCH", returns)
        for phrase in (
            "`run_id` is always required for `append_audit`",
            "only `proposal_id`, `expected_owner_id`, and `expected_claim_epoch` are optional for non-terminal-only batches",
            "all four arguments are required and non-null",
            "[terminal append binding](protocol.md#terminal-append-binding)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, " ".join(module.split()))

    def test_terminal_binding_validates_stored_claim_and_entire_batch(self):
        protocol = read("docs/protocol.md")
        section = protocol.split("#### Terminal append binding\n", 1)[1].split("#### Proposal recovery responses\n", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "`REJECT`, `RETRY`, `ESCALATE`, `CONFLICT`, or `ABANDONED`",
            "Reject missing/null arguments, mismatched terminal record identity, or more than one terminal record",
            "including duplicates for the same proposal",
            "before writing any record",
            "entire batch leaves the journal and proposal state unchanged",
            "stored claim for the supplied `(run_id, proposal_id)`",
            "not from owner/epoch fields in submitted records",
            "same owner and epoch on a different proposal do not authorize this terminalization",
            "current `lease_clock_generation`",
            "`lease_expires_at_ms > lease_now_ms`",
            "no existing terminal outcome",
            "atomically append the records and finalize the proposal state",
            "same still-unexpired claim cannot append a second terminal outcome",
            "`COMMIT` is forbidden in `append_audit`",
            "exclusively through `append_graph`",
            "Non-terminal-only audit batches require no claim",
            "never advance `graph_version`",
            "`VersionConflict` does not reserve claim validity",
            "must recheck the claim",
            "must not return completed `CONFLICT` without its durable record",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)
        recovery = protocol.split("#### Proposal recovery responses\n", 1)[1]
        self.assertIn("without acquiring a fresh claim", recovery)

    def test_benchmark_is_an_independent_completion_criterion(self):
        criterion = "- at least one controlled benchmark compares the baseline with the complete ProblemForger package;"
        self.assertIn(criterion, read("PLAN.md").splitlines())

    def test_python_checks_do_not_claim_a_numpy_dependency(self):
        checks = read("docs/specification-checks.md").split("## Run checks\n", 1)[1].split("## Regression evidence", 1)[0]
        self.assertIn("The Python checks use only the standard library; no credentials are needed", checks)
        self.assertNotIn("NumPy", checks)
        self.assertFalse(any(line.strip() and not line.startswith("#") for line in read("tests/requirements.txt").splitlines()))

    def test_candidate_patch_failure_has_frozen_classification(self):
        evaluation = read("docs/evaluation.md")
        retries = evaluation.split("### Evaluator infrastructure retries\n", 1)[1].split("### Task/evaluator preflight", 1)[0]
        self.assertIn("CANDIDATE_PATCH_INVALID", retries)
        self.assertIn("nonretryable agent/system outcome", retries)
        self.assertIn("not eligible for whole-run replacement", retries)
        self.assertIn("other mandatory evaluator repetition", retries)

    def test_experiment_elapsed_time_has_conservative_recovery(self):
        evaluation = read("docs/evaluation.md")
        budget = evaluation.split("### Experiment resource envelope\n", 1)[1].split("### Pre-P6 frozen artifacts", 1)[0]
        normalized = " ".join(budget.split())
        for phrase in (
            "experiment_started_at_utc",
            "monotonically non-decreasing `experiment_elapsed_floor_ms`",
            "experiment_wall_clock_limit_ms = 1000 * experiment_wall_clock_limit_seconds",
            "elapsed_ms >= experiment_wall_clock_limit_ms",
            "process-monotonic elapsed time",
            "every ledger write advances the persisted floor",
            "the operation's elapsed-time deadline",
            "elapsed value at dispatch plus the operation's finite timeout",
            "never lowers the persisted floor",
            "stop as `BUDGET_EXHAUSTED` with reason `CLOCK_UNCERTAIN`",
            "UTC subtraction alone cannot establish remaining time",
            "default after coordinator restart is to stop",
            "keeps its full spend reservation",
            "restart recovery never makes redispatched work free",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)
        self.assertNotIn("experiment_started_at_utc + experiment_wall_clock_limit_seconds", normalized)
        self.assertNotIn("can therefore never extend", normalized)

    def test_task_materialization_requires_the_complete_pre_p6_freeze(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        self.assertIn("Only after all eight artifacts in [EVALUATION.PRE-P6](#spec-evaluation-pre-p6) are frozen", evaluation)
        self.assertIn("Before the pre-P6 artifact freeze", evaluation)
        self.assertNotIn("paired mechanism comparison under executable ground truth", evaluation)

    def test_c_startup_failure_has_explicit_no_journal_marker(self):
        evaluation = read("docs/evaluation.md")
        raw = evaluation.split("## Raw data and reproducibility\n", 1)[1]
        marker = next(line for line in raw.splitlines() if "problemforger_run_id = null" in line)
        normalized = " ".join(marker.split())
        for phrase in (
            "`INFRA_PROBLEMFORGER_START`",
            "before its ProblemForger run is allocated",
            "terminal reason and startup diagnostics",
            "must not fabricate an empty journal",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

    def test_claim_ttl_rejection_is_a_declared_port_result(self):
        module = read("docs/modules.md")
        contract = module.split("Conceptual port contract:", 1)[1].split("```", 2)[1]
        claim = contract.split("claim_proposal(", 1)[1].split("renew_claim(", 1)[0]
        renewal = contract.split("renew_claim(", 1)[1].split("append_audit(", 1)[0]
        for name, block in (("claim_proposal", claim), ("renew_claim", renewal)):
            with self.subTest(op=name):
                self.assertIn("INVALID_CLAIM_TTL", block)
        requirements = module.split("Requirements:\n", 1)[1].split("### TelemetrySink", 1)[0]
        normalized = " ".join(requirements.split())
        self.assertIn("`claim_ttl_ms` must be a positive finite integer", normalized)
        self.assertIn("`INVALID_CLAIM_TTL`", normalized)
        self.assertIn("persisted lease-clock floor unchanged", normalized)
        suite = module.split("## Contract testing\n", 1)[1]
        self.assertIn("rejected as `INVALID_CLAIM_TTL`", " ".join(suite.split()))

    def test_normative_contract_ids_have_one_owner_and_are_mapped(self):
        expected = {
            "GRAPH.MODEL": "docs/problem-graph.md",
            "MODULES.EVENTSTORE-PORT": "docs/modules.md",
            "PROTOCOL.STORE-OWNER": "docs/protocol.md",
            "PROTOCOL.LEASE-CLOCK": "docs/protocol.md",
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
            for spec_id in re.findall(r"<!-- spec-id: ([A-Z0-9.-]+) -->", path.read_text()):
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

    def test_hash_inputs_have_explicit_cross_implementation_serialization(self):
        evaluation = read("docs/evaluation.md")
        selection = evaluation.split("### Deterministic task selection\n", 1)[1].split("### Pre-P6 frozen artifacts\n", 1)[0]
        for phrase in (
            "encoded as UTF-8 bytes with no Unicode normalization",
            "one zero byte (`0x00`)",
            "unpadded ASCII decimal",
            "config` as one ASCII letter",
            "sha256(candidate_patch_bytes)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, selection)

    def test_methodology_registers_audit_provenance_and_routes_open_decisions(self):
        methodology = read("docs/methodology.md")
        for phrase in (
            "6f7a7ae320e07ea7be39dc9ad1fe1ee3c206510f",
            "only added path",
            "No contradiction with an accepted ADR",
            "conditional",
            "superseded A/B/C draft",
            "generation-policy-v1` record",
            "Secondary-metric multiplicity",
            "Benefit/cost utility",
            "Normative owner if accepted",
            "Recommended synthetic checks before stronger decision claims",
            "Robert E. Blackwell, Jon Barry, and Anthony G. Cohn",
            "Quantifying Uncertainty in LLM Benchmark Scores",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, methodology)
        self.assertIn("Resolved 2026-09-20", methodology)
        self.assertIn("evaluation.md#practical-sensitivity-report", methodology)
        self.assertNotIn("0.99**108", methodology)
        self.assertNotIn("When this branch merges", methodology)

    def test_methodology_register_is_discoverable_from_readme(self):
        self.assertIn("[Methodology audit and decision register](docs/methodology.md)", read("README.md"))

    def test_relative_document_links_resolve(self):
        for path in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue((path.parent / target.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
