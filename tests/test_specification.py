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

    def test_every_graph_append_signature_requires_fencing(self):
        for path in (ROOT / "docs").rglob("*.md"):
            for match in re.finditer(r"\bappend_graph\((.*?)\)", path.read_text(), re.S):
                with self.subTest(path=str(path), signature=match[0]):
                    args = match[1]
                    self.assertTrue("proposal_id" in args and "expected_claim_epoch" in args)
                    self.assertFalse("proposal_id?" in args or "expected_claim_epoch?" in args)

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
