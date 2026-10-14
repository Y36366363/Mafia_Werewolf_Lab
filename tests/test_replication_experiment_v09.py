"""Design contracts for the v09 replication experiment."""
import json
from pathlib import Path
import unittest

from mafia_lab.replication_experiment import build_spec, _good_policies

ROOT = Path(__file__).resolve().parents[1]


class ReplicationExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/replication_v09.json").read_text())

    def test_main_board_and_expanded_counter_pool(self):
        rules, mafia = build_spec(self.config)
        self.assertEqual((rules.police, rules.mafia, rules.civilians), (4, 4, 8))
        self.assertIn("echo_det", {p.name for p in mafia})
        self.assertIn("echo_mimic_det", {p.name for p in mafia})

    def test_every_external_block_is_disjoint(self):
        build_spec(self.config)
        blocks = list(self.config["replication"]["blocks"])
        blocks += list(self.config["probe_selection"]["fit_folds"])
        blocks += [self.config["probe_selection"]["validate"],
                   self.config["probe_selection"]["holdout"]]
        intervals = [(b["seed_start"], b["seed_start"] + b["n"]) for b in blocks]
        self.assertTrue(all(a[1] <= b[0] or b[1] <= a[0]
                            for i, a in enumerate(intervals) for b in intervals[i + 1:]))

    def test_v08_table_is_frozen_exactly(self):
        policies = {p.name: p for p in _good_policies(self.config)}
        table = policies["crossfit_table"]
        self.assertEqual(tuple(self.config["frozen_v08_table"]["cover"]),
                         table.conditional_cover_table)
        self.assertEqual(tuple(self.config["frozen_v08_table"]["police"]),
                         table.conditional_police_table)

    def test_probe_holdout_is_larger_than_each_fit_fold(self):
        spec = self.config["probe_selection"]
        self.assertGreater(spec["holdout"]["n"], max(b["n"] for b in spec["fit_folds"]))


if __name__ == "__main__":
    unittest.main()
