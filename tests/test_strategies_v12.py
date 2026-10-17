from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import Investigation, Message, add_message, from_roles, observe, resolve_night
from mafia_lab import strategies_v12 as v12


class V12StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police"]*4 + ["mafia"]*4 + ["civilian"]*8)

    def test_selfkill_and_ordinary_targets_are_legal_and_information_bounded(self):
        obs = observe(self.state, 4)
        selfkill = v12.MafiaPolicyV12(opening_mode="selfkill")
        ordinary = v12.MafiaPolicyV12()
        self.assertIn(v12.choose_kill(obs, selfkill, Random(1)), range(4, 8))
        self.assertNotIn(v12.choose_kill(obs, ordinary, Random(1)), range(4, 8))

    def test_dead_police_can_truthfully_report_or_cover_teammate(self):
        state = resolve_night(self.state, 0, 4)
        truth = v12.message(observe(state, 0), v12.GoodPolicyV12(), Random(1), "last_words")
        cover = v12.message(observe(state, 0),
                            v12.GoodPolicyV12(dead_police_message="teammate_clear"),
                            Random(1), "last_words")
        self.assertEqual((truth.target, truth.verdict), (4, True))
        self.assertIn(cover.target, {1, 2, 3})
        self.assertFalse(cover.verdict)

    def test_dead_mafia_nonally_clear_cannot_select_by_good_role(self):
        state = resolve_night(self.state, 4, 8)
        policy = v12.MafiaPolicyV12(opening_mode="selfkill", dead_mafia_message="nonally_clear")
        targets = {v12.message(observe(state, 4), policy, Random(seed), "last_words").target
                   for seed in range(50)}
        self.assertTrue(targets <= (set(range(16)) - set(range(4, 8))))
        self.assertTrue(targets & set(range(4)))
        self.assertTrue(targets & set(range(8, 16)))

    def test_police_recognize_dead_outsider_and_single_counter_is_unique(self):
        state = resolve_night(self.state, 4, 8)
        state = add_message(state, Message(4, "report", 8, True, "last_words", 1))
        policy = v12.GoodPolicyV12(live_counter="single")
        messages = [v12.message(observe(state, p), policy, Random(1)) for p in range(4)]
        self.assertEqual(sum(m.kind == "report" for m in messages), 1)

    def test_accused_civilian_does_not_vote_for_self(self):
        state = resolve_night(self.state, 4, 5)
        state = add_message(state, Message(4, "report", 8, True, "last_words", 1))
        vote = v12.vote(observe(state, 8), v12.GoodPolicyV12(), Random(1))
        self.assertNotEqual(vote, 8)


if __name__ == "__main__":
    unittest.main()
