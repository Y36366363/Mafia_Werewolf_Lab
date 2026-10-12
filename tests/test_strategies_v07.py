"""Information contracts for v07 conditional tables and live decoration."""
from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import (Message, add_message, from_roles, observe,
                              publish_live_ballot, resolve_night)
from mafia_lab import strategies_v07 as v7


class V7StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 8)

    def test_tables_validate(self):
        with self.assertRaises(ValueError):
            v7.GoodPolicyV7(cover_mode="table", conditional_cover_table=(.5,))
        with self.assertRaises(ValueError):
            v7.GoodPolicyV7(police_nomination_mode="table", conditional_police_table=(0, 2, 0))
        v7.GoodPolicyV7(cover_mode="table", conditional_cover_table=(0, .25, .5, .75, 1, 1),
                        police_nomination_mode="table", conditional_police_table=(.5, .75, 1))

    def test_public_civilian_rules_ignore_hidden_permutations(self):
        roles_a = ["civilian", "civilian", "police", "mafia", "police", "mafia", "civilian", "civilian"]
        roles_b = ["civilian", "civilian", "mafia", "police", "police", "mafia", "civilian", "civilian"]
        a = observe(resolve_night(from_roles(roles_a), 0, 3), 1)
        b = observe(resolve_night(from_roles(roles_b), 0, 2), 1)
        self.assertEqual(a, b)
        for rule in ("next", "second", "opposite", "hashed", "cycle"):
            self.assertEqual(v7.civilian_rule_target(a, rule), v7.civilian_rule_target(b, rule))

    def test_table_cover_uses_public_support_and_speech_tercile(self):
        state = add_message(self.state, Message(4, "nominate", 2))
        obs = observe(state, 8)
        public = v7.GoodPolicyV7(cover_mode="table", conditional_cover_table=(1,) * 6)
        self.assertEqual(v7.message(obs, public, Random(1)).target, 2)
        random = replace(public, conditional_cover_table=(0,) * 6)
        choices = {v7.message(obs, random, Random(seed)).target for seed in range(20)}
        self.assertGreater(len(choices), 1)

    def test_live_margin_decorates_only_when_main_stays_unique_leader(self):
        policy = v7.MafiaPolicyV7(vote_style="live_margin", inference="combined")
        state = self.state
        # Speech order is 0..15. First three mafia ballots establish a 3-0 lead.
        for voter in (0, 1, 2):
            state = publish_live_ballot(state, voter, 4)
        choice = v7.vote(observe(state, 3), policy, Random(1))
        self.assertNotEqual(choice, 4)
        weak = self.state
        for voter, target in ((0, 4), (1, 5), (2, 5)):
            weak = publish_live_ballot(weak, voter, target)
        self.assertEqual(v7.vote(observe(weak, 3), policy, Random(1)), 4)

    def test_live_final_requires_last_overall_voter(self):
        policy = v7.MafiaPolicyV7(vote_style="live_final")
        state = self.state
        for voter in (0, 1, 2):
            state = publish_live_ballot(state, voter, 4)
        self.assertEqual(v7.vote(observe(state, 3), policy, Random(1)), 4)


if __name__ == "__main__":
    unittest.main()
