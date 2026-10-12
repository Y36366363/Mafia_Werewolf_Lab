"""Frozen design contracts for v07 adaptive experiments."""
import json
from pathlib import Path
import unittest

from mafia_lab.adaptive_experiment import (build_spec, evaluate_games,
                                            _good_holdout_policies, _table_policy)


ROOT = Path(__file__).resolve().parents[1]


class AdaptiveExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/adaptive_v07.json").read_text())

    def test_main_board_new_disjoint_seed_blocks(self):
        rules, mafia = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        self.assertEqual(len(mafia), 6)
        blocks = [self.config["table_training"], self.config["holdout"],
                  self.config["initiator_experiment"]["openings"]]
        intervals = [(b["seed_start"], b["seed_start"] + b.get("scan_limit", b["n"]))
                     for b in blocks]
        self.assertGreaterEqual(min(a for a, _ in intervals), 50_000_000)
        self.assertTrue(all(a[1] <= b[0] or b[1] <= a[0]
                            for i, a in enumerate(intervals) for b in intervals[i + 1:]))

    def test_frozen_table_round_trips_into_holdout_policy(self):
        learned = {"cover_table": [0, .25, .5, .75, 1, 1],
                   "police_table": [.25, .5, .75]}
        policy = _table_policy(self.config, learned["cover_table"], learned["police_table"])
        self.assertEqual(tuple(learned["cover_table"]), policy.conditional_cover_table)
        policies = _good_holdout_policies(self.config, learned)
        self.assertEqual([p.name for p in policies],
                         ["public_base", "confirm_mix", "position_mix", "learned_table"])

    def test_public_ballot_evaluation_records_split_rate(self):
        rules, mafia = build_spec(self.config)
        good = _table_policy(self.config, [0, .25, .5, .75, 1, 1], [.25, .5, .75])
        cell = evaluate_games((rules, good, mafia[3], 4, 53_000_000, True))
        self.assertEqual(cell["summary"]["n"], 4)
        self.assertGreaterEqual(cell["mafia_multi_vote_rounds"], cell["mafia_split_rounds"])


if __name__ == "__main__":
    unittest.main()
