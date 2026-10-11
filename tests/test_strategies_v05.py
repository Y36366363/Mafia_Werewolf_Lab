"""Information and action contracts for v05 refinements."""
from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import Investigation, Message, PublicEvent, add_message, from_roles, observe
from mafia_lab import strategies_v05 as v5


class V5StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police", "police", "mafia", "mafia",
                                 "civilian", "civilian", "civilian", "civilian"])

    def ballot(self, day, mapping):
        return PublicEvent("vote", day, ballots=tuple(sorted(mapping.items())))

    def test_modes_validate(self):
        with self.assertRaises(ValueError):
            v5.MafiaPolicyV5(inference="oracle")
        with self.assertRaises(ValueError):
            v5.MafiaPolicyV5(vote_style="oracle")
        with self.assertRaises(ValueError):
            v5.GoodPolicyV5(police_vote_reasoning=1)

    def test_role_separated_vote_switches_only_affect_named_role(self):
        event = self.ballot(1, {2: 6, 4: 6, 5: 7, 6: 5, 7: 5})
        police = replace(observe(self.state, 0), day=2,
                         investigations=(Investigation(1, 2, True),), public_events=(event,))
        civilian = replace(observe(self.state, 4), day=2,
                           public_events=(event, self.ballot(2, {5: 7, 6: 5, 7: 5})))
        base = v5.GoodPolicyV5()
        police_on = replace(base, police_vote_reasoning=True)
        civilian_on = replace(base, civilian_vote_reasoning=True)
        self.assertEqual(v5.vote(police, police_on, Random(1), (4, 5)), 4)
        for seed in range(12):
            self.assertEqual(v5.vote(civilian, police_on, Random(seed), (5, 6, 7)),
                             v5.vote(civilian, base, Random(seed), (5, 6, 7)))
            self.assertEqual(v5.vote(police, civilian_on, Random(seed), (4, 5)),
                             v5.vote(police, base, Random(seed), (4, 5)))

    def test_inspection_only_does_not_change_votes(self):
        obs = replace(observe(self.state, 0), day=2,
                      investigations=(Investigation(1, 2, True),),
                      public_events=(self.ballot(1, {2: 6, 4: 6, 5: 7}),))
        off = v5.GoodPolicyV5()
        inspect = replace(off, inspect_reasoning=True)
        for seed in range(12):
            self.assertEqual(v5.vote(obs, off, Random(seed)), v5.vote(obs, inspect, Random(seed)))
        self.assertEqual(v5.choose_inspection(obs, inspect, Random(1)), 4)

    def test_origin_score_distinguishes_initiator_from_follower(self):
        state = add_message(self.state, Message(0, "nominate", 6, day=0))
        state = add_message(state, Message(1, "nominate", 6, day=0))
        obs = observe(state, 2)
        scores = v5.mafia_scores(obs, v5.MafiaPolicyV5(inference="origin"))
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(v5.choose_kill(obs, v5.MafiaPolicyV5(inference="origin"), Random(1)), 0)

    def test_origin_uses_message_order_not_hidden_role(self):
        a = from_roles(["civilian", "police", "mafia", "mafia",
                        "police", "civilian", "civilian", "civilian"])
        b = from_roles(["police", "civilian", "mafia", "mafia",
                        "police", "civilian", "civilian", "civilian"])
        for state in (a, b):
            state2 = add_message(state, Message(0, "nominate", 6, day=0))
            state2 = add_message(state2, Message(1, "nominate", 6, day=0))
            if state is a:
                obs_a = observe(state2, 2)
            else:
                obs_b = observe(state2, 2)
        self.assertEqual(obs_a, obs_b)
        policy = v5.MafiaPolicyV5(inference="origin")
        self.assertEqual(v5.mafia_scores(obs_a, policy), v5.mafia_scores(obs_b, policy))

    def test_split_vote_disperses_teammates_and_remains_legal(self):
        policy = v5.MafiaPolicyV5(vote_style="split")
        choices = [v5.vote(observe(self.state, player), policy, Random(1)) for player in (2, 3)]
        self.assertEqual(len(set(choices)), 2)
        self.assertTrue(all(choice not in (2, 3) for choice in choices))

    def test_good_speech_delegates_without_new_role_marker(self):
        policy = v5.GoodPolicyV5(police_nominate_probability=0,
                                 civilian_cover_probability=0,
                                 hit_nominate_probability=0)
        police = v5.message(observe(self.state, 0), policy, Random(1))
        civilian = v5.message(observe(self.state, 4), policy, Random(1))
        self.assertEqual(police.kind, civilian.kind)
        self.assertEqual(police.kind, "civilian")


if __name__ == "__main__":
    unittest.main()
