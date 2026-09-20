"""P0 document regression checks, not tests of a production implementation."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class SpecificationChecks(unittest.TestCase):
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
        self.assertIn("classify the task as `EVALUATOR_UNSTABLE` immediately", preflight)
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
            "difference-in-differences",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, comparison)

    def test_continuation_and_sensitivity_rules_are_frozen(self):
        evaluation = read("docs/evaluation.md")
        interpretation = evaluation.split("### Frozen continuation and interpretation rule\n", 1)[1].split("### Secondary end-to-end metrics\n", 1)[0]

        for phrase in (
            "delta = 10",
            "U < -delta",
            "L > delta",
            "L >= -delta",
            "U <= delta",
            "Equality at either boundary",
            "REDESIGN",
            "PRACTICALLY_NULL",
            "ADVANCE_P7",
            "B-A point estimate is at least `+delta`",
            "B-A lower\n  bound is greater than `-delta`",
            "C-B lower bound is greater than `-delta`",
            "No\nanalyst may choose a different threshold",
            "SENSITIVITY_DISCORDANT",
            "zero effects fixed",
            "all `2^m` assignments",
            "inclusive tail `abs(T*) >= abs(T_observed)`",
            "replicate-disagreement rate",
            "leave-one-repetition-out",
            "Do not select a favorable omitted replicate",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, interpretation)
        self.assertNotIn("does not exclude material harm", interpretation)

    def test_sensitivity_discordance_uses_sign_and_practical_band(self):
        evaluation = read("docs/evaluation.md")
        sensitivity = evaluation.split("### Frozen sensitivity analyses\n", 1)[1].split("### Secondary end-to-end metrics\n", 1)[0]
        for phrase in (
            "point-estimate category",
            "sign(x)",
            "NEGATIVE`, `ZERO`, or `POSITIVE",
            "band(x)",
            "MATERIAL_HARM`, `WITHIN_MARGIN`, or `PRACTICAL_BENEFIT",
            "x < -delta",
            "x > delta",
            "SENSITIVITY_DISCORDANT` iff",
            "sign or practical band",
            "max_abs_deviation_pp",
            "does not alter the P7 gate",
            "p-values and replicate-disagreement rates do not drive",
            "new blinded replication before making a positive claim",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, sensitivity)
        self.assertNotIn("If primary and sensitivity conclusions disagree", sensitivity)

    def test_task_artifact_exclusion_is_pre_measurement_only(self):
        evaluation = read("docs/evaluation.md")
        artifact = evaluation.split("### Task-artifact preflight exclusions\n", 1)[1].split("<a id=\"spec-evaluation-measured-evaluation\">", 1)[0]

        for phrase in (
            "`INFRA_TASK_ARTIFACT`",
            "configuration-neutral, patch-independent preflight",
            "before `N` is computed",
            "before\nthe measured schedule is hashed",
            "missing, corrupt, or schema-incompatible",
            "Network/image-pull failures",
            "must not be relabeled as task invalidity",
            "every A/B/C\nconfiguration and all three repetitions",
            "with no replacement task",
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

    def test_unavailable_images_cannot_be_task_artifact_exclusions(self):
        evaluation = read("docs/evaluation.md")
        artifact = evaluation.split("### Task-artifact preflight exclusions\n", 1)[1].split("### Measured candidate patches", 1)[0]
        normalized = " ".join(artifact.split())
        for phrase in (
            "intrinsic defect in successfully retrieved, digest-verified task content",
            "Unavailable image content takes precedence over `INFRA_TASK_ARTIFACT`",
            "`EVAL_IMAGE_SETUP`",
            "missing mirror/cache object",
            "cannot change `N`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, normalized)

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
        self.assertIn("graph_version=0, last_journal_position=0", contract)
        self.assertIn("get_run(run_id)", contract)
        self.assertIn("| NOT_FOUND", contract)
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

    def test_terminal_writes_bind_claim_owner_and_epoch(self):
        module = read("docs/modules.md")
        protocol = read("docs/protocol.md")
        audit = re.search(r"\bappend_audit\((.*?)\)", module, re.S).group(1)
        graph = re.search(r"\bappend_graph\((.*?)\)", module, re.S).group(1)
        self.assertIn("expected_owner_id", audit)
        self.assertIn("expected_claim_epoch", audit)
        self.assertIn("expected_owner_id", graph)
        self.assertIn("both expected owner identity and claim epoch", protocol)

    def test_candidate_patch_failure_has_frozen_classification(self):
        evaluation = read("docs/evaluation.md")
        retries = evaluation.split("### Evaluator infrastructure retries\n", 1)[1].split("### Task/evaluator preflight", 1)[0]
        self.assertIn("CANDIDATE_PATCH_INVALID", retries)
        self.assertIn("nonretryable agent/system outcome", retries)
        self.assertIn("not eligible for whole-run replacement", retries)
        self.assertIn("other mandatory evaluator repetition", retries)

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
            "EVALUATION.BOOTSTRAP-RNG": "docs/evaluation.md",
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

    def test_bootstrap_has_one_shared_index_draw(self):
        evaluation = read("docs/evaluation.md")
        self.assertTrue("#### BOOTSTRAP-RNG" in evaluation, "Missing canonical RNG contract")
        self.assertTrue("size=(100_000, n)" in evaluation, "Missing draw shape")
        self.assertTrue("dtype=np.int64" in evaluation, "Missing integer dtype")
        self.assertTrue("shared" in evaluation and "instance_id" in evaluation)

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
            "do not include the degenerate",
            "generation-policy-v1` record",
            "Secondary-metric multiplicity",
            "Benefit/cost utility",
            "Normative owner if accepted",
            "README documentation index",
            "Robert E. Blackwell, Jon Barry, and Anthony G. Cohn",
            "Quantifying Uncertainty in LLM Benchmark Scores",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, methodology)
        self.assertIn("Resolved 2026-09-20", methodology)
        self.assertIn("evaluation.md#frozen-sensitivity-analyses", methodology)

    def test_relative_document_links_resolve(self):
        for path in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue((path.parent / target.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
