import json
from pathlib import Path
import unittest

from mafia_lab.leadership_experiment_v15 import build_spec, evaluate_cell, _matrix, _solution


class LeadershipExperimentV15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("configs/leadership_v15.json").read_text())
        cls.rules, cls.good, cls.mafia = build_spec(cls.config)

    def test_main_board_fresh_disjoint_seeds_and_pk(self):
        self.assertEqual((self.rules.police, self.rules.mafia, self.rules.civilians), (4, 4, 8))
        self.assertEqual(self.rules.tie_rule, "pk")
        blocks = [self.config[name] for name in ("train", "holdout", "confirmation")]
        ranges = [set(range(b["seed_start"], b["seed_start"] + b["n"])) for b in blocks]
        self.assertTrue(ranges[0].isdisjoint(ranges[1]))
        self.assertTrue(ranges[0].isdisjoint(ranges[2]))
        self.assertTrue(ranges[1].isdisjoint(ranges[2]))

    def test_small_matrix_runs_and_solves(self):
        cells = [evaluate_cell(("smoke", self.rules, g, m, 129500000, 8))
                 for g in self.good for m in self.mafia]
        matrix = _matrix(cells, [p.name for p in self.good], [p.name for p in self.mafia])
        result = _solution(matrix, [p.name for p in self.good], [p.name for p in self.mafia])
        self.assertEqual((len(matrix), len(matrix[0])), (6, 4))
        self.assertEqual(result["gap_exact"], "0")

    def test_intervention_branches_pair_within_mafia_column(self):
        cells = [evaluate_cell(("smoke", self.rules, g, self.mafia[0], 129600000, 32))
                 for g in self.good]
        for key in ("leader_eligible", "eligible_hit", "eligible_clear"):
            first = cells[0]["raw"][key]
            self.assertTrue(all(c["raw"][key] == first for c in cells[1:]))

    def test_pk_intervention_reaches_actual_pk_rounds(self):
        policy = next(p for p in self.good if p.name == "pk_naive")
        cell = evaluate_cell(("smoke", self.rules, policy, self.mafia[0], 132500000, 64))
        self.assertGreater(sum(cell["raw"]["day1_pk"]), 0)

    def test_confirmation_uses_v14_pass_rule(self):
        rules, good, mafia = build_spec(self.config, confirmation=True)
        self.assertEqual(rules.tie_rule, "pass")
        self.assertEqual(len(good), 1)
        self.assertEqual([p.name for p in mafia],
                         ["kill_random", "safe_middle", "safe_late", "safe_mix"])


if __name__ == "__main__":
    unittest.main()
