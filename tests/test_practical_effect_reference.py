"""Checks for the small P6-AC practical effect calculation."""

import unittest


class PracticalEffectChecks(unittest.TestCase):
    def test_c_minus_a_is_the_mean_of_six_task_pair_differences(self):
        tasks = [
            {"a": 0, "c": 1},
            {"a": 1, "c": 0},
            {"a": 0, "c": 0},
            {"a": 1, "c": 1},
            {"a": 0, "c": 1},
            {"a": 0, "c": 0},
        ]

        task_deltas = [100 * (task["c"] - task["a"]) for task in tasks]
        point_delta_pp = sum(task_deltas) / len(task_deltas)

        self.assertEqual(task_deltas, [100, -100, 0, 0, 100, 0])
        self.assertAlmostEqual(point_delta_pp, 100 / 6)
        self.assertLessEqual(abs(point_delta_pp), 100)
        self.assertEqual(100 / len(tasks), 100 / 6)


if __name__ == "__main__":
    unittest.main()
