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
            "persist the experiment start time and absolute stop deadline",
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
            "Each C slot uses a unique persisted `run_id`",
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
            "candidate cannot write evaluator tests",
            "recorder, ledger, or credentials",
            "evaluator bundle digest",
            "trusted runner",
            "slot ledger key includes `run_id`",
            "run registration binds manifest hash, task ID, and configuration",
            "invocation record binds",
            "raw-output digest only on the terminal result",
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
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

    def test_evaluator_deadline_is_separate_from_agent_deadline(self):
        evaluation = " ".join(read("docs/evaluation.md").split())
        for phrase in (
            "`absolute_evaluator_deadline`",
            "separate from `absolute_evaluator_deadline`",
            "agent deadline fences agent attempts and operations",
            "evaluator deadline fences evaluator writes",
            "experiment-wide stop deadline",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

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
            "trusted runner confirms the same invocation is active",
            "Otherwise `EVALUATION_INCOMPLETE`",
            "does not by itself make the attempt nonretryable",
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
            "one evaluator run for each produced candidate patch",
            "twelve agent runs",
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
            "CANDIDATE_PATCH_INVALID",
            "EVIDENCE_INCOMPLETE",
            "INCOMPLETE_EVIDENCE",
            "No reason code is silently converted into a favorable result",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evaluation)

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
            "restart recovery of an incomplete receipt",
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

    def test_run_registration_and_graph_version_rules_remain_explicit(self):
        module = read("docs/modules.md")
        self.assertIn("create_run(run_id, run_metadata)", module)
        self.assertIn("RUN_METADATA_CONFLICT", module)
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
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, verification)

    def test_plan_keeps_p11_portability_and_package_level_p6(self):
        plan = read("PLAN.md")
        self.assertIn("portability validation belongs to P11", plan)
        self.assertIn("one compact manifest", plan)
        self.assertIn("small paired A/C pilot", plan)
        self.assertIn("at least one controlled benchmark compares the baseline", plan)

    def test_methodology_is_discoverable_and_not_a_second_algorithm(self):
        methodology = " ".join(read("docs/methodology.md").split())
        self.assertIn("not a publication-grade uncertainty model", methodology)
        self.assertIn("current contract is owned by `docs/evaluation.md`", methodology)
        self.assertIn("SENSITIVITY_DISCORDANT", methodology)
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
