"""Frozen design and conditional-record tests for v05."""
import json
from pathlib import Path
import unittest

from mafia_lab.refinement_experiment import build_spec, evaluate_cell


ROOT = Path(__file__).resolve().parents[1]


class RefinementExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/refinement_v05.json").read_text())

    def test_primary_and_all_sensitivity_boards_are_16_player(self):
        rules, _, _ = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        for variant in self.config["sensitivity"]["rule_variants"]:
            rules = variant["rules"]
            self.assertEqual((rules["police"], rules["mafia"], rules["civilians"]), (4, 4, 8))

    def test_seed_blocks_are_new_and_disjoint(self):
        build_spec(self.config)
        intervals = [(self.config[p]["seed_start"],
                      self.config[p]["seed_start"] + self.config[p]["n"])
                     for p in ("train", "test", "sensitivity")]
        self.assertTrue(all(a[1] <= b[0] or b[1] <= a[0]
                            for i, a in enumerate(intervals) for b in intervals[i + 1:]))
        self.assertGreaterEqual(min(a for a, _ in intervals), 31_000_000)

    def test_cell_saves_complete_conditional_partitions(self):
        rules, good, mafia = build_spec(self.config)
        cell = evaluate_cell((rules, good[0], mafia[0], 16, 34_000_000))
        self.assertEqual(len(cell["raw_first_death_role"]), 16)
        self.assertEqual(len(cell["raw_first_check_mafia"]), 16)
        self.assertEqual(sum(cell["conditional"][k]["n"] for k in
                             ("first_dead_police", "first_dead_civilian")), 16)
        self.assertEqual(sum(cell["conditional"][k]["n"] for k in
                             ("first_check_mafia", "first_check_good")), 16)
        self.assertTrue(set(cell["raw_first_death_role"]) <= {"police", "civilian"})


if __name__ == "__main__":
    unittest.main()
