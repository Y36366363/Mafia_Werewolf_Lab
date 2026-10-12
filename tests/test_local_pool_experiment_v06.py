"""Frozen design and train-only expansion contracts for v06."""
from fractions import Fraction
import json
from pathlib import Path
import unittest

from mafia_lab.local_pool_experiment import build_spec, incremental_pool


ROOT = Path(__file__).resolve().parents[1]


class LocalPoolExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/local_pool_v06.json").read_text())

    def test_main_board_and_candidate_contract(self):
        rules, good, mafia = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        self.assertEqual((len(good), len(mafia)), (9, 7))
        self.assertTrue(all(p.first_self_kill == 0 for p in mafia))

    def test_seed_scan_blocks_are_disjoint_and_new(self):
        build_spec(self.config)
        blocks = [self.config["matrix_train"], self.config["matrix_test"],
                  self.config["timing"]["hit_openings"],
                  self.config["timing"]["aligned_openings"]]
        intervals = [(b["seed_start"], b["seed_start"] + b.get("scan_limit", b["n"]))
                     for b in blocks]
        self.assertGreaterEqual(min(a for a, _ in intervals), 43_000_000)
        self.assertTrue(all(a[1] <= b[0] or b[1] <= a[0]
                            for i, a in enumerate(intervals) for b in intervals[i + 1:]))

    def test_incremental_pool_uses_only_supplied_train_cells(self):
        config = {"good_candidates": [{"name": n} for n in ("g0", "g1", "g2")],
                  "mafia_candidates": [{"name": n} for n in ("m0", "m1", "m2")],
                  "initial_pool": {"good": ["g0"], "mafia": ["m0"]},
                  "expansion": {"max_rounds": 3, "tolerance": 0}}
        values = [[1, 0, 0], [1, 1, 0], [1, 1, 1]]
        cells = [{"good": g, "mafia": m, "n": 1,
                  "summary": {"wins": values[i][j]}}
                 for i, g in enumerate(("g0", "g1", "g2"))
                 for j, m in enumerate(("m0", "m1", "m2"))]
        result = incremental_pool(cells, config)
        self.assertIn("g2", result["good_pool"])
        self.assertIn("m1", result["mafia_pool"])
        self.assertNotIn("m2", result["mafia_pool"])
        self.assertEqual(Fraction(result["train_value"]), 1)


if __name__ == "__main__":
    unittest.main()
