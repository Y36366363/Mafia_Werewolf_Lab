from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe, resolve_night
from mafia_lab import strategies_v13 as v13


class V13StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police"]*4 + ["mafia"]*4 + ["civilian"]*8)

    def test_shortlist_referee_validation(self):
        state = resolve_night(self.state, 0, 8)
        valid = Message(0, "shortlist", 1, None, "last_words", 1, (1, 5, 9))
        self.assertEqual(add_message(state, valid).messages[-1], valid)
        with self.assertRaises(ValueError):
            add_message(state, replace(valid, target=2))
        with self.assertRaises(ValueError):
            add_message(state, replace(valid, targets=(1, 1)))

    def test_position_inspection_is_information_legal(self):
        obs = observe(self.state, 0)
        for mode in ("preempt", "reply", "gap"):
            target = v13.choose_inspection(obs, v13.GoodPolicyV13(inspect_position=mode), Random(1))
            self.assertNotIn(target, {0, 1, 2, 3})
        # Swapping hidden mafia/civilian labels leaves a police observation and action unchanged.
        alternate = from_roles(["police"]*4 + ["civilian"]*4 + ["mafia"]*4 + ["civilian"]*4)
        for mode in ("preempt", "reply", "gap"):
            policy = v13.GoodPolicyV13(inspect_position=mode)
            self.assertEqual(v13.choose_inspection(obs, policy, Random(7)),
                             v13.choose_inspection(observe(alternate, 0), policy, Random(7)))

    def test_first_kill_places_mafia_first_without_knowing_good_roles(self):
        obs = observe(self.state, 4)
        policy = v13.MafiaPolicyV13(kill_position="first")
        target = v13.choose_kill(obs, policy, Random(1))
        order = v13._order_after(obs, target)
        self.assertIn(order[0], {4, 5, 6, 7})
        alternate = from_roles(["civilian"]*4 + ["mafia"]*4 + ["police"]*4 + ["civilian"]*4)
        self.assertEqual(target, v13.choose_kill(observe(alternate, 4), policy, Random(1)))

    def test_clean_and_decoy_shortlists(self):
        state = resolve_night(self.state, 0, 8)  # dead police, checked civilian
        clean = v13.message(observe(state, 0),
                            v13.GoodPolicyV13(dead_clear_plan="short3"), Random(1), "last_words")
        self.assertEqual(clean.kind, "shortlist")
        self.assertEqual(len(clean.targets), 3)
        self.assertFalse(set(clean.targets) & {0, 1, 2, 3, 8})
        decoy = v13.message(observe(state, 0),
                            v13.GoodPolicyV13(dead_clear_plan="decoy_remove"), Random(1), "last_words")
        self.assertIn(decoy.target, {1, 2, 3})
        self.assertIn(decoy.target, decoy.targets)

    def test_shortlist_concentrates_good_votes_after_removal(self):
        state = resolve_night(self.state, 0, 8)
        state = add_message(state, Message(0, "shortlist", 1, None, "last_words", 1, (1, 4, 9)))
        policy = v13.GoodPolicyV13()
        self.assertEqual(v13.vote(observe(state, 8), policy, Random(1)), 4)
        self.assertEqual(v13.vote(observe(state, 2), policy, Random(1)), 4)


if __name__ == "__main__":
    unittest.main()
