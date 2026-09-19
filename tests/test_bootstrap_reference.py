"""Run the normative document's bootstrap against synthetic golden fixtures."""

import copy
import json
from pathlib import Path
import re
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
document = (ROOT / "docs/evaluation.md").read_text()
source = re.search(
    r"<!-- bootstrap-reference:start -->\n```python\n(.*?)\n```\n<!-- bootstrap-reference:end -->",
    document, re.S,
).group(1)
namespace = {}
exec(compile(source, "docs/evaluation.md:bootstrap-reference", "exec"), namespace)
bootstrap = namespace["bootstrap_primary"]
fixture = json.loads((ROOT / "tests/fixtures/bootstrap-v1.json").read_text())


class BootstrapReferenceChecks(unittest.TestCase):
    def test_all_retained_task_counts_match_golden_indices_and_intervals(self):
        for n in range(8, 13):
            with self.subTest(n=n):
                actual = bootstrap(fixture["tasks"][:n])
                expected = fixture["expected"][str(n)]
                self.assertEqual(actual["task_ids"], expected["task_ids"])
                self.assertEqual(actual["comparisons"], ["B-A", "C-B"])
                self.assertEqual(actual["indices_sha256"], expected["indices_sha256"])
                for key in ["point_pp", "ci_pp"]:
                    np.testing.assert_allclose(actual[key], expected[key], atol=1e-12, rtol=0)

    def test_input_order_and_previous_analyses_do_not_change_results(self):
        tasks = fixture["tasks"][:8]
        expected = bootstrap(tasks)
        bootstrap(fixture["tasks"])
        self.assertEqual(bootstrap(list(reversed(tasks))), expected)

    def test_invalid_sample_and_outcomes_are_rejected(self):
        for tasks in [fixture["tasks"][:7], fixture["tasks"] + fixture["tasks"][:1],
                      [fixture["tasks"][0]] * 8]:
            with self.assertRaises(ValueError):
                bootstrap(tasks)
        tasks = copy.deepcopy(fixture["tasks"][:8])
        tasks[0]["resolved"][0][0] = 0.5
        with self.assertRaises(ValueError):
            bootstrap(tasks)


if __name__ == "__main__":
    unittest.main()
