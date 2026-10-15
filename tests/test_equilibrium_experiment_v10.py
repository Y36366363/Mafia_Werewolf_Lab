"""Design and mixture contracts for v10."""
import json
from fractions import Fraction
from pathlib import Path
import unittest

from mafia_lab.equilibrium_experiment import build_spec, evaluate_frozen_mixture

ROOT = Path(__file__).resolve().parents[1]


class EquilibriumExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/equilibrium_v10.json").read_text())

    def test_expanded_main_board_matrix(self):
        rules, good, mafia = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        self.assertEqual((len(good), len(mafia)), (7, 13))

    def test_response_families_are_separate(self):
        families = self.config["response_learning"]
        pools = [set(spec["candidates"]) for spec in families.values()]
        self.assertTrue(all(a.isdisjoint(b) for i, a in enumerate(pools) for b in pools[i + 1:]))

    def test_train_and_holdout_are_disjoint(self):
        train, holdout = self.config["train"], self.config["holdout"]
        self.assertLessEqual(train["seed_start"] + train["n"], holdout["seed_start"])

    def test_frozen_mixture_bounds_recompute(self):
        matrix = [[Fraction(1, 4), Fraction(3, 4)],
                  [Fraction(3, 4), Fraction(1, 4)]]
        artifact = {"good_mixture": {"a": "1/2", "b": "1/2"},
                    "mafia_mixture": {"x": "1/2", "y": "1/2"}}
        result = evaluate_frozen_mixture(matrix, ["a", "b"], ["x", "y"], artifact)
        self.assertEqual(result["joint_exact"], "1/2")
        self.assertEqual(result["out_of_sample_gap_exact"], "0")


if __name__ == "__main__":
    unittest.main()
