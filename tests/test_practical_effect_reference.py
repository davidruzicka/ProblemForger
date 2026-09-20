"""Checks for the small P6-AC practical effect calculation."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PracticalEffectChecks(unittest.TestCase):
    def test_c_minus_a_is_the_mean_of_task_level_two_run_differences(self):
        tasks = [
            {"a": [0, 1], "c": [1, 1]},
            {"a": [1, 0], "c": [0, 0]},
            {"a": [0, 0], "c": [0, 1]},
            {"a": [1, 1], "c": [1, 1]},
        ]

        task_deltas = [
            (sum(task["c"]) - sum(task["a"])) / 2
            for task in tasks
        ]
        point_delta_pp = 100 * sum(task_deltas) / len(task_deltas)

        self.assertEqual(task_deltas, [0.5, -0.5, 0.5, 0.0])
        self.assertEqual(point_delta_pp, 12.5)
        self.assertEqual(100 / (2 * len(tasks)), 12.5)


if __name__ == "__main__":
    unittest.main()
