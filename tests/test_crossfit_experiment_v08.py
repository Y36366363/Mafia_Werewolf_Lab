"""Design contracts for v08 disjoint-fold experiments."""
import json
from pathlib import Path
import unittest

from mafia_lab.crossfit_experiment import (build_spec, evaluate_games,
                                            _holdout_good, _table_policy)


ROOT = Path(__file__).resolve().parents[1]


class CrossfitExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/crossfit_v08.json").read_text())

    def test_main_board_and_external_seed_blocks(self):
        rules, mafia = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        self.assertEqual(len(mafia), 6)
        self.assertGreaterEqual(self.config["table_crossfit"]["fit"]["seed_start"], 60_000_000)

    def test_all_coordinate_subblocks_are_pairwise_disjoint(self):
        spec = self.config["table_crossfit"]
        fit = [(spec["fit"]["seed_start"] + i * spec["fit"]["n"],
                spec["fit"]["seed_start"] + (i + 1) * spec["fit"]["n"])
               for i in range(18)]
        validate = [(spec["validate"]["seed_start"] + i * spec["validate"]["n"],
                     spec["validate"]["seed_start"] + (i + 1) * spec["validate"]["n"])
                    for i in range(18)]
        intervals = fit + validate
        self.assertTrue(all(a[1] <= b[0] or b[1] <= a[0]
                            for i, a in enumerate(intervals) for b in intervals[i + 1:]))

    def test_deterministic_baseline_has_no_mafia_split_rounds(self):
        rules, mafia = build_spec(self.config)
        learned = {"cover_table": [.25, .5, .75, .75, 1, 1],
                   "police_table": [.5, .75, 1]}
        good = _holdout_good(self.config, learned)[1]
        cell = evaluate_games((rules, good, mafia[0], 16, 66_000_000, True))
        self.assertEqual(cell["mafia_split_rounds"], 0)

    def test_crossfit_table_round_trips(self):
        learned = {"cover_table": [0, .25, .5, .75, 1, 1],
                   "police_table": [.25, .5, .75]}
        policy = _table_policy(self.config, learned["cover_table"], learned["police_table"])
        self.assertEqual(tuple(learned["cover_table"]), policy.conditional_cover_table)


if __name__ == "__main__":
    unittest.main()
