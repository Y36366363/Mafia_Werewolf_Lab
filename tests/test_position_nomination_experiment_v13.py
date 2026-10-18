import json
from pathlib import Path
import unittest

from mafia_lab.position_nomination_experiment_v13 import (
    build_spec, _cell_position, _cell_nomination, _select_nomination_openings,
)


class PositionNominationExperimentV13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = json.loads(Path("configs/position_nomination_v13.json").read_text())
        cls.config = config
        cls.rules, cls.pg, cls.pm, cls.ng, cls.nm = build_spec(config)

    def test_position_smoke_metrics(self):
        cell = _cell_position(("smoke", self.rules, self.pg[1], self.pm[2], 120000000, 5))
        self.assertEqual(cell["n"], 5)
        self.assertTrue(all(len(values) == 5 for values in cell["raw"].values()))
        self.assertTrue(all(0 <= value <= 4 for value in cell["raw"]["mafia_in_first4"]))

    def test_conditional_cohort_and_shortlist_buckets(self):
        openings = _select_nomination_openings(
            self.rules, {"n":4, "seed_start":120010000, "scan_limit":10000},
            self.ng[0], self.nm[0])
        clean = _cell_nomination(("smoke", openings, self.ng[3], self.nm[0]))
        decoy = _cell_nomination(("smoke", openings, self.ng[4], self.nm[2]))
        self.assertEqual(clean["raw"]["has_shortlist"], [1]*4)
        self.assertEqual(clean["raw"]["listed_police"], [0]*4)
        self.assertEqual(decoy["raw"]["listed_police"], [1]*4)
        self.assertEqual(decoy["raw"]["removed_police"], [1]*4)

    def test_common_opening_is_independent_of_nomination_response(self):
        block = {"n":3, "seed_start":120020000, "scan_limit":10000}
        rows = [_select_nomination_openings(self.rules, block, self.ng[0], mafia)
                for mafia in self.nm]
        signatures = [[(seed, repr(state)) for seed, state in row] for row in rows]
        self.assertTrue(all(row == signatures[0] for row in signatures))


if __name__ == "__main__":
    unittest.main()
