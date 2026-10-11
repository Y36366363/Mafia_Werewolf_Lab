"""The proposed counter uses observable speech, not referee role labels."""

from copy import deepcopy
import json
from pathlib import Path
from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe, resolve_night
from mafia_lab.policies import MafiaPolicy, choose_kill
from scripts.run_signal_counter import build_spec, run_experiment


ROOT = Path(__file__).resolve().parents[1]


class PublicSignalTests(unittest.TestCase):
    def test_nominator_is_targeted_in_indistinguishable_hidden_worlds(self):
        a = from_roles(["mafia", "police", "civilian", "civilian", "police", "mafia"])
        b = from_roles(["mafia", "civilian", "police", "civilian", "police", "mafia"])
        public_nomination = Message(1, "nominate", 4)
        a = observe(add_message(a, public_nomination), 0)
        b = observe(add_message(b, public_nomination), 0)
        self.assertEqual(a, b)
        policy = MafiaPolicy("signal", "nominate", "signals")
        for seed in range(24):
            self.assertEqual(choose_kill(a, policy, Random(seed)), 1)
            self.assertEqual(choose_kill(a, policy, Random(seed)),
                             choose_kill(b, policy, Random(seed)))

    def test_claims_control_does_not_equate_nomination_with_police_claim(self):
        state = from_roles(["mafia", "police", "civilian", "civilian", "police", "mafia"])
        obs = observe(add_message(state, Message(1, "nominate", 4)), 0)
        policy = MafiaPolicy("control", "nominate", "claims")
        selected = {choose_kill(obs, policy, Random(seed)) for seed in range(24)}
        self.assertGreater(len(selected), 1)

    def test_live_claimants_and_nominators_are_signal_candidates(self):
        state = from_roles(["mafia", "police", "civilian", "civilian", "police", "mafia"])
        state = add_message(state, Message(1, "police"))
        state = add_message(state, Message(2, "nominate", 4))
        state = add_message(state, Message(5, "nominate", 3))
        policy = MafiaPolicy("signal", "always", "signals")
        selected = {choose_kill(observe(state, 0), policy, Random(seed))
                    for seed in range(24)}
        self.assertEqual(selected, {1, 2})

    def test_dead_nominator_and_mafia_teammate_are_excluded(self):
        state = from_roles(["mafia", "police", "civilian", "civilian", "police", "mafia"])
        state = add_message(state, Message(1, "nominate", 3))
        state = add_message(state, Message(5, "nominate", 3))
        state = resolve_night(state, 1, 2)
        state = add_message(state, Message(3, "nominate", 4, day=1))
        policy = MafiaPolicy("signal", "always", "signals")
        for seed in range(24):
            self.assertEqual(choose_kill(observe(state, 0), policy, Random(seed)), 3)


class FrozenCounterTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/signal_counter_v03.json").read_text())

    def test_contrast_cannot_bundle_bluff_change(self):
        config = deepcopy(self.config)
        config["mafia_policies"][-1]["bluff"] = "none"
        with self.assertRaises(ValueError):
            build_spec(config)

    def test_small_run_retains_whole_matrix_and_six_paired_contrasts(self):
        config = deepcopy(self.config)
        config["n_per_cell"] = 2
        config["seed_start"] = 13500000
        report = run_experiment(config)
        self.assertEqual(report["total_games"], 24)
        self.assertEqual(len(report["cells"]), 12)
        self.assertEqual(len(report["paired_contrasts"]), 6)
        self.assertEqual(report["seed_interval_inclusive"], [13500000, 13500001])
        cells = {(r["good_policy"], r["mafia_policy"]): r for r in report["cells"]}
        for cell in cells.values():
            self.assertEqual(len(cell["raw_outcomes"]), 2)
            self.assertEqual(len(cell["raw_nights"]), 2)
            self.assertEqual(cell["summary"]["n"], 2)
            self.assertEqual(sum(cell["first_death_counts"].values()), 2)
        for row in report["paired_contrasts"]:
            control = cells[row["good_policy"], row["control"]]["raw_outcomes"]
            treatment = cells[row["good_policy"], row["treatment"]]["raw_outcomes"]
            self.assertEqual(row["paired"]["delta"],
                             sum(b - a for a, b in zip(control, treatment)) / 2)
        for key in ("source_sha256", "script_sha256", "config_sha256"):
            self.assertEqual(len(report[key]), 64)


if __name__ == "__main__":
    unittest.main()
