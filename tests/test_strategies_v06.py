"""Contracts for local mixtures, anti-bait cover and limited ballot disguise."""
from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import (Investigation, Message, add_message, from_roles, observe,
                              resolve_night, speech_order)
from mafia_lab import strategies_v06 as v6


class V6StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police", "police", "mafia", "mafia",
                                 "civilian", "civilian", "civilian", "civilian"])

    def test_modes_validate(self):
        for kwargs in ({"cover_mode": "oracle"}, {"police_nomination_mode": "oracle"},
                       {"day1_timing": "oracle"}, {"local_public_probability": float("nan")}):
            with self.assertRaises(ValueError):
                v6.GoodPolicyV6(**kwargs)
        for kwargs in ({"vote_style": "oracle"}, {"nomination_style": "oracle"}):
            with self.assertRaises(ValueError):
                v6.MafiaPolicyV6(**kwargs)

    def test_local_cover_endpoints_match_public_and_random(self):
        state = add_message(self.state, Message(0, "nominate", 6))
        obs = observe(state, 4)
        public = v6.GoodPolicyV6(civilian_cover_probability=1, cover_mode="public")
        random = replace(public, cover_mode="random")
        local_public = replace(public, cover_mode="local", local_public_probability=1)
        local_random = replace(public, cover_mode="local", local_public_probability=0)
        for seed in range(16):
            self.assertEqual(v6.message(obs, public, Random(seed)),
                             v6.message(obs, local_public, Random(seed)))
            self.assertEqual(v6.message(obs, random, Random(seed)),
                             v6.message(obs, local_random, Random(seed)))

    def test_confirm_cover_rejects_single_bait_and_accepts_two_speakers(self):
        policy = v6.GoodPolicyV6(civilian_cover_probability=1, cover_mode="confirm")
        one = observe(add_message(self.state, Message(0, "nominate", 6)), 4)
        two_state = add_message(add_message(self.state, Message(0, "nominate", 6)),
                                Message(1, "nominate", 6))
        two = observe(two_state, 4)
        self.assertEqual(v6.message(two, policy, Random(1)).target, 6)
        choices = {v6.message(one, policy, Random(seed)).target for seed in range(32)}
        self.assertGreater(len(choices), 1)

    def test_position_nomination_uses_public_rank_only(self):
        policy = v6.GoodPolicyV6(police_nomination_mode="position",
                                 police_nominate_probability=.5)
        outputs = []
        for player in (0, 1):
            obs = observe(self.state, player)
            outputs.append(v6.message(obs, policy, Random(1)).kind)
            for seed in range(2, 8):
                self.assertEqual(v6.message(obs, policy, Random(seed)).kind, outputs[-1])
        self.assertIn("nominate", outputs)

    def test_dead_police_position_policy_can_give_last_words(self):
        state = resolve_night(self.state, 0, 2)
        policy = v6.GoodPolicyV6(police_nomination_mode="position",
                                 police_nominate_probability=.5)
        message = v6.message(observe(state, 0), policy, Random(1), context="last_words")
        self.assertEqual(message.context, "last_words")

    def test_inspection_probability_endpoints_preserve_baselines(self):
        obs = replace(observe(self.state, 0), day=2,
                      investigations=(Investigation(1, 2, True),))
        off = v6.GoodPolicyV6(inspect_reasoning_probability=0)
        on = replace(off, inspect_reasoning_probability=1)
        for seed in range(12):
            self.assertEqual(v6.choose_inspection(obs, off, Random(seed)),
                             v6.v5.choose_inspection(obs, off, Random(seed)))
        self.assertIn(v6.choose_inspection(obs, on, Random(1)), obs.alive)

    def test_limited_decoy_preserves_three_of_four_votes(self):
        state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)
        choices = [v6.vote(observe(state, p), v6.MafiaPolicyV6(vote_style="one_decoy"), Random(1))
                   for p in range(4)]
        counts = {target: choices.count(target) for target in set(choices)}
        self.assertEqual(sorted(counts.values()), [1, 3])

    def test_late_decoy_is_defined_by_public_speech_order(self):
        state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)
        policy = v6.MafiaPolicyV6(vote_style="late_decoy")
        order = [p for p in speech_order(observe(state, 0)) if p < 4]
        choices = {p: v6.vote(observe(state, p), policy, Random(1)) for p in range(4)}
        majority = max(set(choices.values()), key=list(choices.values()).count)
        self.assertNotEqual(choices[order[-1]], majority)

    def test_day_one_timing_modes_use_only_legal_information(self):
        state = replace(self.state, day=1,
                        investigations=(Investigation(1, 2, True),))
        early = v6.GoodPolicyV6(day1_timing="early")
        late = replace(early, day1_timing="late")
        silent = replace(early, day1_timing="silent")
        self.assertTrue(all(v6.message(observe(state, p), early, Random(1)).target == 2
                            for p in (0, 1)))
        late_kinds = [v6.message(observe(state, p), late, Random(1)).kind for p in (0, 1)]
        self.assertEqual(late_kinds.count("nominate"), 1)
        self.assertTrue(all(v6.message(observe(state, p), silent, Random(1)).kind == "civilian"
                            for p in (0, 1)))

    def test_civilian_first_target_is_public_and_hidden_world_invariant(self):
        roles_a = ["civilian", "civilian", "police", "mafia",
                   "police", "mafia", "civilian", "civilian"]
        roles_b = ["civilian", "civilian", "mafia", "police",
                   "police", "mafia", "civilian", "civilian"]
        a = observe(resolve_night(from_roles(roles_a), 0, 3), 1)
        b = observe(resolve_night(from_roles(roles_b), 0, 2), 1)
        self.assertEqual(a, b)
        self.assertEqual(speech_order(a)[0], 1)
        self.assertIsNotNone(v6.civilian_first_alignment(a))
        self.assertEqual(v6.civilian_first_alignment(a), v6.civilian_first_alignment(b))


if __name__ == "__main__":
    unittest.main()
