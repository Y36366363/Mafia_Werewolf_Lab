import json
from pathlib import Path
import unittest

from mafia_lab.robust_shortlist_experiment_v16 import build_spec, evaluate_cell, _matrix, _solution


class RobustShortlistExperimentV16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("configs/robust_shortlist_v16.json").read_text())
        cls.rules, cls.good, cls.mafia, cls.calibration = build_spec(cls.config)

    def test_board_pool_and_disjoint_seeds(self):
        self.assertEqual((self.rules.police, self.rules.mafia, self.rules.civilians), (4, 4, 8))
        self.assertEqual(self.calibration.name, "kill_random")
        blocks = [self.config[name] for name in ("train", "holdout", "calibration")]
        ranges = [set(range(x["seed_start"], x["seed_start"] + x["n"])) for x in blocks]
        self.assertTrue(all(ranges[i].isdisjoint(ranges[j])
                            for i in range(3) for j in range(i + 1, 3)))

    def test_small_matrix_runs_and_solves(self):
        cells = [evaluate_cell(("smoke", self.rules, g, m, 139000000, 4))
                 for g in self.good for m in self.mafia]
        matrix = _matrix(cells, [g.name for g in self.good], [m.name for m in self.mafia])
        solution = _solution(matrix, [g.name for g in self.good], [m.name for m in self.mafia])
        self.assertEqual((len(matrix), len(matrix[0])), (8, 4))
        self.assertEqual(solution["gap_exact"], "0")

    def test_opening_branches_pair_across_good_interventions(self):
        cells = [evaluate_cell(("smoke", self.rules, g, self.mafia[0], 139100000, 16))
                 for g in self.good]
        for key in ("leader_eligible", "eligible_hit", "eligible_clear"):
            first = cells[0]["raw"][key]
            self.assertTrue(all(cell["raw"][key] == first for cell in cells[1:]))

    def test_multi_person_lists_end_in_one_target(self):
        policy = next(g for g in self.good if g.name == "robust_list3")
        cell = evaluate_cell(("smoke", self.rules, policy, self.mafia[1], 139200000, 32))
        for size, target, eligible, hit in zip(
                cell["raw"]["shortlist_size"], cell["raw"]["final_target_exists"],
                cell["raw"]["leader_eligible"], cell["raw"]["eligible_hit"]):
            if eligible:
                self.assertEqual(target, 1)
                self.assertEqual(size, 1 if hit else 3)


if __name__ == "__main__":
    unittest.main()
