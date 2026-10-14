"""Public-information contracts for v09 probe controls and counters."""
from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe, resolve_night
from mafia_lab import strategies_v09 as v9


class V9StrategyTests(unittest.TestCase):
    def test_anchor_probe_ignores_hidden_world(self):
        a = resolve_night(from_roles(["civilian", "police", "mafia", "civilian"]), 3, 2)
        b = resolve_night(from_roles(["civilian", "mafia", "police", "civilian"]), 3, 1)
        self.assertEqual(observe(a, 0), observe(b, 0))
        for rule in ("anchor_first", "anchor_pair"):
            self.assertEqual(v9.public_probe_target(observe(a, 0), rule),
                             v9.public_probe_target(observe(b, 0), rule))

    def test_echo_counter_prioritizes_public_follower(self):
        state = from_roles(["mafia", "police", "civilian", "civilian"])
        state = add_message(state, Message(2, "nominate", 3, context="day", day=0))
        state = add_message(state, Message(1, "nominate", 3, context="day", day=0))
        policy = v9.MafiaPolicyV9(inference="echo")
        self.assertEqual(v9.choose_kill(observe(state, 0), policy, Random(1)), 1)

    def test_echo_public_repeats_latest_legal_target(self):
        state = from_roles(["mafia", "police", "civilian", "civilian"])
        state = add_message(state, Message(2, "nominate", 3, context="day", day=0))
        policy = v9.MafiaPolicyV9(bluff="nominate", nomination_style="echo_public",
                                  nomination_probability=1)
        message = v9.message(observe(state, 0), policy, Random(1))
        self.assertEqual((message.kind, message.target), ("nominate", 3))

    def test_echo_deterministic_target_is_common(self):
        state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)
        policy = v9.MafiaPolicyV9(inference="echo", vote_style="deterministic")
        targets = [v9.vote(observe(state, p), policy, Random(p)) for p in range(4)]
        self.assertEqual(len(set(targets)), 1)

    def test_v09_accepts_anchor_rules_and_rejects_unknown(self):
        v9.GoodPolicyV9(probe_pattern=("anchor_first", "anchor_pair"))
        with self.assertRaises(ValueError):
            v9.GoodPolicyV9(probe_pattern=("secret",))


if __name__ == "__main__":
    unittest.main()
