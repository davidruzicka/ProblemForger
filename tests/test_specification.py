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
                self.assertTrue("proposal_id" in args and "expected_claim_epoch" in args)
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

    def test_relative_document_links_resolve(self):
        for path in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue((path.parent / target.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
