"""Information and action contracts for v04; no performance selection here."""

from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import (Investigation, Message, PublicEvent, add_message,
                              from_roles, observe, resolve_night)
from mafia_lab import policies as base
from mafia_lab import strategies_v04 as v4


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police", "police", "mafia", "mafia",
                                 "civilian", "civilian", "civilian", "civilian"])

    def ballot(self, day, mapping, kind="vote"):
        return PublicEvent(kind, day, ballots=tuple(sorted(mapping.items())))

    def test_probabilities_and_modes_validate(self):
        for field in ("civilian_cover_probability", "police_nominate_probability", "hit_nominate_probability"):
            for value in (-.1, 1.1, float("nan")):
                with self.assertRaises(ValueError):
                    v4.GoodPolicyV4(**{field: value})
        with self.assertRaises(ValueError):
            v4.MafiaPolicyV4(inference="oracle")
        with self.assertRaises(ValueError):
            v4.MafiaPolicyV4(nomination_probability=-1)

    def test_plain_policy_wrapper_equivalence(self):
        for player in (0, 2, 4):
            obs = observe(self.state, player)
            policy = base.MafiaPolicy() if player == 2 else base.GoodPolicy()
            self.assertEqual(v4.message(obs, policy, Random(1)), base.message(obs, policy, Random(1)))
            self.assertEqual(v4.vote(obs, policy, Random(1)), base.vote(obs, policy, Random(1)))
        self.assertEqual(v4.choose_kill(observe(self.state, 2), base.MafiaPolicy(), Random(1)),
                         base.choose_kill(observe(self.state, 2), base.MafiaPolicy(), Random(1)))
        self.assertEqual(v4.choose_inspection(observe(self.state, 0), base.GoodPolicy(), Random(1)),
                         base.choose_inspection(observe(self.state, 0), base.GoodPolicy(), Random(1)))

    def test_hidden_world_invariance_for_each_role(self):
        alternatives = {
            0: ["police", "police", "civilian", "mafia", "mafia", "civilian", "civilian", "civilian"],
            2: ["civilian", "police", "mafia", "mafia", "police", "civilian", "civilian", "civilian"],
            7: ["mafia", "police", "police", "mafia", "civilian", "civilian", "civilian", "civilian"],
        }
        for player, roles in alternatives.items():
            a, b = observe(self.state, player), observe(from_roles(roles), player)
            self.assertEqual(a, b)
            policy = v4.MafiaPolicyV4() if player == 2 else v4.GoodPolicyV4(vote_reasoning=True, inspect_reasoning=True)
            for seed in range(12):
                self.assertEqual(v4.message(a, policy, Random(seed)), v4.message(b, policy, Random(seed)))
                self.assertEqual(v4.vote(a, policy, Random(seed)), v4.vote(b, policy, Random(seed)))
                if player == 0:
                    self.assertEqual(v4.choose_inspection(a, policy, Random(seed)), v4.choose_inspection(b, policy, Random(seed)))
                if player == 2:
                    self.assertEqual(v4.choose_kill(a, policy, Random(seed)), v4.choose_kill(b, policy, Random(seed)))

    def test_mix_endpoints_and_hit_override(self):
        for player, field in ((0, "police_nominate_probability"), (4, "civilian_cover_probability")):
            obs = observe(self.state, player)
            for seed in range(12):
                no = v4.message(obs, v4.GoodPolicyV4(**{field: 0}), Random(seed))
                yes = v4.message(obs, v4.GoodPolicyV4(**{field: 1}), Random(seed))
                self.assertNotEqual(no.kind, "nominate")
                self.assertEqual(yes.kind, "nominate")
        obs = observe(resolve_night(self.state, 7, 2), 0)
        yes = v4.message(obs, v4.GoodPolicyV4(police_nominate_probability=0), Random(4))
        self.assertEqual((yes.kind, yes.target), ("nominate", 2))
        no = v4.message(obs, v4.GoodPolicyV4(police_nominate_probability=1, hit_nominate_probability=0), Random(4))
        self.assertEqual(no.kind, "civilian")

    def test_non_nominating_police_and_civilians_use_same_public_declaration(self):
        policy = v4.GoodPolicyV4(police_nominate_probability=0, civilian_cover_probability=0,
                                 hit_nominate_probability=0)
        for override in (None, "pass"):
            for context in ("day", "pk", "last_words"):
                police = v4.message(observe(self.state, 0), policy, Random(3), context, override)
                civilian = v4.message(observe(self.state, 4), policy, Random(3), context, override)
                self.assertEqual(police.kind, "civilian")
                self.assertEqual(replace(police, speaker=civilian.speaker), civilian)
        # Exhausted private target pool uses the same fallback marker too.
        obs = replace(observe(self.state, 0), alive=(0, 1))
        no_target = v4.message(obs, replace(policy, police_nominate_probability=1), Random(3))
        self.assertEqual(no_target.kind, "civilian")

    def test_mafia_mimic_mixing_endpoints(self):
        obs = observe(self.state, 2)
        self.assertEqual(v4.message(obs, v4.MafiaPolicyV4(nomination_probability=0), Random(1)).kind, "civilian")
        self.assertEqual(v4.message(obs, v4.MafiaPolicyV4(nomination_probability=1), Random(1)).kind, "nominate")

    def test_cover_uses_only_public_plurality_and_ignores_own_nomination(self):
        obs = observe(add_message(self.state, Message(0, "nominate", 6)), 4)
        g = v4.GoodPolicyV4(civilian_cover_probability=1)
        self.assertEqual(v4.message(obs, g, Random(2)).target, 6)
        own = replace(obs, messages=obs.messages + (Message(4, "nominate", 5),) * 10)
        self.assertEqual(v4.message(own, g, Random(2)), v4.message(obs, g, Random(2)))
        choices = {v4.message(obs, replace(g, cover_target="random"), Random(seed)).target for seed in range(32)}
        self.assertGreater(len(choices), 1)
        self.assertNotIn(4, choices)

    def test_own_fabricated_claim_and_nomination_do_not_change_good_vote(self):
        obs = observe(self.state, 4)
        own = replace(obs, messages=(Message(4, "report", 5, True), Message(4, "nominate", 5)))
        for reasoning in (False, True):
            policy = v4.GoodPolicyV4(trust="all", vote_reasoning=reasoning)
            for seed in range(16):
                self.assertEqual(v4.vote(obs, policy, Random(seed)), v4.vote(own, policy, Random(seed)))

    def test_police_known_roles_dominate_public_pressure(self):
        state = resolve_night(self.state, 7, 2)
        state = add_message(state, Message(3, "report", 1, True, day=1))
        for reasoning in (False, True):
            obs = observe(state, 0)
            g = v4.GoodPolicyV4(trust="all", vote_reasoning=reasoning)
            self.assertEqual(v4.vote(obs, g, Random(3)), 2)
            self.assertNotEqual(v4.vote(obs, g, Random(3), candidates=(1, 4)), 1)
        obs = replace(observe(state, 0), investigations=(Investigation(1, 4, False),))
        for seed in range(12):
            self.assertNotIn(v4.vote(obs, v4.GoodPolicyV4(vote_reasoning=True), Random(seed)), (0, 1, 4))

    def test_no_ballot_buffer_or_future_events_used(self):
        obs = observe(self.state, 2)
        altered = replace(obs, public_events=(self.ballot(0, {0: 2}, "pending_vote"),
                                              self.ballot(1, {1: 3})),
                          messages=(Message(1, "nominate", 2, day=1),))
        for mode in ("signals", "history", "votes", "combined"):
            p = v4.MafiaPolicyV4(inference=mode)
            self.assertEqual(v4.mafia_scores(obs, p), v4.mafia_scores(altered, p))

    def test_pk_replaces_daily_ballot_without_extra_sample(self):
        obs = replace(observe(self.state, 2), day=1)
        first = self.ballot(1, {0: 2, 1: 4})
        last = self.ballot(1, {0: 4, 1: 2}, "pk_vote")
        a = replace(obs, public_events=(first, last))
        b = replace(obs, public_events=(last,))
        self.assertEqual(v4.published_ballots(a), v4.published_ballots(b))
        self.assertEqual(v4.mafia_scores(a, v4.MafiaPolicyV4()), v4.mafia_scores(b, v4.MafiaPolicyV4()))

    def test_same_day_repeated_nomination_not_extra_evidence(self):
        obs = observe(self.state, 2)
        one = replace(obs, messages=(Message(0, "nominate", 4), Message(1, "nominate", 4)))
        many = replace(obs, messages=one.messages + (Message(0, "nominate", 4, context="pk"),) * 8)
        self.assertEqual(v4.mafia_scores(one, v4.MafiaPolicyV4()), v4.mafia_scores(many, v4.MafiaPolicyV4()))

    def test_mafia_ablation_channels_and_known_team_constraints(self):
        obs = observe(self.state, 2)
        nominated = replace(obs, messages=(Message(0, "nominate", 4),))
        voted = replace(obs, public_events=(self.ballot(0, {1: 3, 0: 4}),))
        votes = v4.MafiaPolicyV4(inference="votes")
        history = v4.MafiaPolicyV4(inference="history")
        signals = v4.MafiaPolicyV4(inference="signals")
        self.assertEqual(v4.mafia_scores(obs, votes), v4.mafia_scores(nominated, votes))
        self.assertEqual(v4.mafia_scores(obs, history), v4.mafia_scores(voted, history))
        self.assertEqual(v4.mafia_scores(obs, signals), v4.mafia_scores(voted, signals))
        self.assertEqual(v4.choose_kill(voted, votes, Random(1)), 1)
        self.assertEqual(v4.choose_kill(nominated, history, Random(1)), 0)
        for mode in ("signals", "history", "votes", "combined"):
            p = v4.MafiaPolicyV4(inference=mode)
            self.assertNotIn(v4.choose_kill(nominated, p, Random(1)), (2, 3))
            self.assertNotIn(v4.vote(nominated, p, Random(1)), (2, 3))

    def test_police_ballot_reasoning_changes_unknown_choice_and_inspection(self):
        obs = replace(observe(self.state, 0), day=2,
                      investigations=(Investigation(1, 2, True),),
                      public_events=(self.ballot(1, {2: 6, 4: 6, 5: 7}),))
        scores = v4.good_history_scores(obs, (4, 5))
        self.assertEqual(scores, {4: .75, 5: 0})
        g = v4.GoodPolicyV4(vote_reasoning=True, inspect_reasoning=True)
        self.assertEqual(v4.vote(obs, g, Random(1), candidates=(4, 5)), 4)
        self.assertEqual(v4.choose_inspection(obs, g, Random(1)), 4)
        no_events = replace(obs, public_events=())
        for seed in range(12):
            off = replace(g, inspect_reasoning=False)
            self.assertEqual(v4.choose_inspection(obs, off, Random(seed)), v4.choose_inspection(no_events, off, Random(seed)))

    def test_history_ablation_preserves_covert_baseline_without_evidence(self):
        obs = observe(resolve_night(self.state, 7, 6), 0)
        obs = replace(obs, messages=(Message(4, "nominate", 5, day=1),
                                     Message(6, "nominate", 5, day=1)))
        off = v4.GoodPolicyV4(vote_reasoning=False)
        on = replace(off, vote_reasoning=True)
        self.assertEqual(base._covert_target(obs), 2)
        for pool in (None, (4, 5)):
            for seed in range(12):
                left, right = Random(seed), Random(seed)
                self.assertEqual(v4.vote(obs, off, left, pool), v4.vote(obs, on, right, pool))
                self.assertEqual(left.getstate(), right.getstate())
        self.assertEqual(v4.vote(obs, on, Random(1)), 2)

    def test_only_stronger_history_displaces_covert_baseline(self):
        obs = replace(observe(self.state, 0), day=2,
                      alive=tuple(p for p in self.state.alive if p != 2),
                      investigations=(Investigation(1, 2, True),),
                      messages=(Message(4, "nominate", 5, day=2),
                                Message(6, "nominate", 5, day=2)),
                      public_events=(self.ballot(1, {2: 6, 3: 7, 4: 6}),))
        off = v4.GoodPolicyV4(vote_reasoning=False)
        on = replace(off, vote_reasoning=True)
        self.assertEqual(base._covert_target(obs), 3)
        self.assertEqual(v4.vote(obs, off, Random(1)), 3)
        self.assertEqual(v4.vote(obs, on, Random(1)), 4)
        tied = replace(obs, public_events=(self.ballot(1, {2: 6, 3: 6, 4: 6}),))
        for seed in range(12):
            self.assertEqual(v4.vote(tied, on, Random(seed)), 3)

    def test_civilian_history_is_bounded_and_requires_repeated_public_rounds(self):
        obs = replace(observe(self.state, 7), day=3)
        one = self.ballot(1, {0: 6, 1: 6, 4: 5})
        two = self.ballot(2, {0: 4, 1: 4, 4: 6})
        self.assertEqual(v4.good_history_scores(replace(obs, public_events=(one,)), (0, 1, 4)), {0: 0, 1: 0, 4: 0})
        obs = replace(obs, public_events=(one, two))
        scores = v4.good_history_scores(obs, (0, 1, 4))
        self.assertEqual(scores, {0: 1 / 3, 1: 1 / 3, 4: 0})
        for seed in range(12):
            self.assertIn(v4.vote(obs, v4.GoodPolicyV4(vote_reasoning=True), Random(seed), (0, 1, 4)), (0, 1))
            off = v4.GoodPolicyV4(vote_reasoning=False)
            self.assertEqual(v4.vote(obs, off, Random(seed)), v4.vote(replace(obs, public_events=()), off, Random(seed)))

    def test_generated_actions_are_legal_for_speech_and_pk_pools(self):
        state = resolve_night(self.state, 7, 2)
        for player in state.alive:
            obs = observe(state, player)
            policy = v4.MafiaPolicyV4() if player in (2, 3) else v4.GoodPolicyV4(vote_reasoning=True)
            for seed in range(8):
                add_message(state, v4.message(obs, policy, Random(seed)))
                choice = v4.vote(obs, policy, Random(seed), candidates=(0, 2, 4))
                self.assertTrue(choice is None or (choice in (0, 2, 4) and choice != player))


if __name__ == "__main__":
    unittest.main()
