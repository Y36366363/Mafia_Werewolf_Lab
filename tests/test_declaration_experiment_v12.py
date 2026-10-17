import json
from pathlib import Path
import unittest

from mafia_lab.declaration_experiment_v12 import build_spec, _select_dead_openings, _cell_from_openings, _cell_root


class DeclarationExperimentV12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = json.loads(Path("configs/declaration_v12.json").read_text())
        cls.config = config
        cls.rules, cls.dead, cls.good, cls.mafia = build_spec(config)

    def test_small_dead_cohorts_and_declarations(self):
        block = {"n": 3, "seed_start": 110000000, "scan_limit": 10000}
        cohorts = _select_dead_openings(self.rules, block, self.good[0], self.mafia[0])
        self.assertEqual({k: len(v) for k,v in cohorts.items()}, {"hit":3, "clear":3})
        hit = _cell_from_openings(("smoke", "hit", cohorts["hit"], self.dead[1], self.mafia[0]))
        self.assertEqual(hit["raw"]["dead_report_target_role"], ["mafia"]*3)
        clear = _cell_from_openings(("smoke", "clear", cohorts["clear"], self.dead[1], self.mafia[0]))
        self.assertNotIn("mafia", clear["raw"]["dead_report_target_role"])

    def test_root_selfkill_role_and_information_signature(self):
        ordinary = _cell_root(("smoke", self.rules, self.good[0], self.mafia[0], 110010000, 4))
        selfkill = _cell_root(("smoke", self.rules, self.good[0], self.mafia[2], 110010000, 4))
        self.assertTrue(set(ordinary["first_death_roles"]) <= {"police", "civilian"})
        self.assertEqual(selfkill["first_death_roles"], ["mafia"]*4)
        self.assertEqual(ordinary["root_signatures"], selfkill["root_signatures"])

    def test_counter_mode_does_not_change_ordinary_claim_continuation(self):
        rows = [_cell_root(("smoke", self.rules, policy, self.mafia[0], 110020000, 12))
                for policy in (self.good[0], self.good[2], self.good[3])]
        self.assertEqual(rows[0]["raw"], rows[1]["raw"])
        self.assertEqual(rows[0]["raw"], rows[2]["raw"])


if __name__ == "__main__":
    unittest.main()
