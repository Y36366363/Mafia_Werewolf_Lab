"""Information and action contracts for v10 public coordination and counters."""
from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe, resolve_night
from mafia_lab import strategies_v10 as v10


class V10StrategyTests(unittest.TestCase):
    def test_public_coordination_target_ignores_hidden_world(self):
        a = resolve_night(from_roles(["civilian", "police", "mafia", "civilian"]), 3, 2)
        b = resolve_night(from_roles(["civilian", "mafia", "police", "civilian"]), 3, 1)
        self.assertEqual(observe(a, 0), observe(b, 0))
        for mode in ("anchor", "pair", "deliberative"):
            self.assertEqual(v10.public_coordination_target(observe(a, 0), mode),
                             v10.public_coordination_target(observe(b, 0), mode))

    def test_civilian_and_clear_police_use_same_public_protocol(self):
        board = resolve_night(from_roles(["civilian", "police", "mafia", "civilian"]), 3, 0)
        policy = v10.GoodPolicyV10(coordination_mode="anchor", police_follow_timing="public")
        civilian = v10.message(observe(board, 0), policy, Random(1))
        police = v10.message(observe(board, 1), policy, Random(1))
        self.assertEqual(civilian.kind, "nominate")
        self.assertEqual(police.kind, "nominate")

    def test_follow_counter_scores_late_repeater(self):
        state = from_roles(["mafia", "police", "civilian", "civilian"])
        state = add_message(state, Message(2, "nominate", 3, context="day", day=0))
        state = add_message(state, Message(1, "nominate", 3, context="day", day=0))
        policy = v10.MafiaPolicyV10(counter_mode="follow", counter_weight=8)
        self.assertEqual(v10.choose_kill(observe(state, 0), policy, Random(1)), 1)

    def test_counter_modes_validate(self):
        for mode in ("none", "concentration", "dispersion", "follow"):
            v10.MafiaPolicyV10(counter_mode=mode)
        with self.assertRaises(ValueError):
            v10.MafiaPolicyV10(counter_mode="private_role")

    def test_public_coordination_also_coordinates_ballot(self):
        board = resolve_night(from_roles(["civilian", "police", "mafia", "civilian"]), 3, 0)
        policy = v10.GoodPolicyV10(coordination_mode="anchor")
        message = v10.message(observe(board, 0), policy, Random(1))
        target = v10.vote(observe(board, 0), policy, Random(2))
        self.assertEqual(target, message.target)

    def test_deterministic_counter_target_is_common(self):
        state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)
        policy = v10.MafiaPolicyV10(counter_mode="dispersion")
        targets = [v10.vote(observe(state, p), policy, Random(p)) for p in range(4)]
        self.assertEqual(len(set(targets)), 1)


if __name__ == "__main__":
    unittest.main()
