import json
from pathlib import Path
import unittest

from mafia_lab.nomination_followup_experiment_v13b import build_spec
from mafia_lab.position_nomination_experiment_v13 import (
    _cell_nomination, _select_nomination_openings,
)


class NominationFollowupV13bTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("configs/nomination_followup_v13b.json").read_text())
        cls.rules, cls.good, cls.mafia = build_spec(cls.config)

    def test_fresh_blocks_and_random_kill(self):
        self.assertTrue(all(p.kill_position == "random" for p in self.mafia))
        self.assertGreaterEqual(self.config["train"]["seed_start"], 125000000)
        self.assertGreaterEqual(self.config["holdout"]["seed_start"], 126000000)

    def test_non_degenerate_smoke_cohort(self):
        openings = _select_nomination_openings(
            self.rules, {"n":64,"seed_start":127000000,"scan_limit":10000},
            self.good[0], self.mafia[0])
        cell = _cell_nomination(("smoke", openings, self.good[2], self.mafia[0]))
        self.assertGreater(sum(cell["raw"]["listed_mafia"]), 0)
        self.assertLess(sum(cell["raw"]["listed_mafia"]), 64)
        self.assertGreater(sum(cell["raw"]["day1_exile_mafia"]), 0)
        self.assertLess(sum(cell["raw"]["day1_exile_mafia"]), 64)


if __name__ == "__main__":
    unittest.main()
