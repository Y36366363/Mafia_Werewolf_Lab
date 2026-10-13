"""Common tie-break and public multi-probe contracts for v08."""
from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe, publish_live_ballot, resolve_night
from mafia_lab import strategies_v08 as v8


class V8StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)

    def test_every_mafia_computes_same_deterministic_main_target(self):
        policy = v8.MafiaPolicyV8(vote_style="deterministic", inference="combined")
        targets = [v8.vote(observe(self.state, p), policy, Random(100 + p)) for p in range(4)]
        self.assertEqual(len(set(targets)), 1)

    def test_common_target_survives_public_live_ballots(self):
        policy = v8.MafiaPolicyV8(vote_style="deterministic", inference="combined")
        state = self.state
        choices = []
        for player in range(4):
            choice = v8.vote(observe(state, player), policy, Random(player))
            choices.append(choice)
            state = publish_live_ballot(state, player, choice)
        self.assertEqual(len(set(choices)), 1)

    def test_live_margin_only_decorates_after_safe_common_lead(self):
        policy = v8.MafiaPolicyV8(vote_style="deterministic_live_margin")
        main = v8.vote(observe(self.state, 0), replace(policy, vote_style="deterministic"), Random(1))
        state = self.state
        for player in range(3):
            state = publish_live_ballot(state, player, main)
        self.assertNotEqual(v8.vote(observe(state, 3), policy, Random(1)), main)

    def test_later_civilian_probe_uses_only_public_observation(self):
        roles_a = ["civilian", "civilian", "police", "mafia", "police", "mafia", "civilian", "civilian"]
        roles_b = ["civilian", "civilian", "mafia", "police", "police", "mafia", "civilian", "civilian"]
        a = resolve_night(from_roles(roles_a), 0, 3)
        b = resolve_night(from_roles(roles_b), 0, 2)
        a = add_message(a, Message(1, "civilian", context="day", day=1))
        b = add_message(b, Message(1, "civilian", context="day", day=1))
        oa, ob = observe(a, 6), observe(b, 6)
        self.assertEqual(oa, ob)
        for rule in v8.PROBE_RULES:
            self.assertEqual(v8.public_probe_target(oa, rule), v8.public_probe_target(ob, rule))

    def test_probe_window_controls_eligible_public_positions(self):
        state = resolve_night(self.state, 15, 4)
        first, second = 0, 1
        policy = v8.GoodPolicyV8(day1_timing="civilian_first", probe_window=1,
                                 probe_pattern=("next",))
        # Mafia speakers are delegated; use a civilian-role board for direct window test.
        board = resolve_night(from_roles(["civilian", "civilian", "police", "mafia"]), 3, 3)
        self.assertEqual(v8.message(observe(board, 0), policy, Random(1)).kind, "nominate")
        self.assertEqual(v8.message(observe(board, 1), policy, Random(1)).kind, "civilian")


if __name__ == "__main__":
    unittest.main()
