"""Independent hidden-world checks for v04 local policies in 16-player games."""

from dataclasses import replace
from random import Random
import unittest

from mafia_lab.engine import (
    Investigation, Message, add_message, from_roles, observe, resolve_night,
    resolve_votes,
)
from mafia_lab import strategies_v04 as decisions
from mafia_lab.simulation import continue_game


def history_state(roles):
    """Legal history with two same-target voting pairs and public nominations."""
    state = resolve_night(from_roles(roles), 15, 13)
    state = add_message(state, Message(6, "nominate", 10, day=1))
    state = add_message(state, Message(7, "nominate", 10, day=1))
    state = add_message(state, Message(5, "report", 11, True, day=1))
    votes = {p: None for p in state.alive}
    votes.update({0: 10, 1: 10, 2: 11, 3: 11})
    state = resolve_votes(state, votes)
    state = resolve_night(state, 14, 12)
    state = add_message(state, Message(6, "nominate", 10, day=2))
    state = add_message(state, Message(7, "nominate", 10, day=2))
    return state


class HiddenWorldInvarianceTests(unittest.TestCase):
    def compare_local_actions(self, first, second, role):
        a, b = observe(history_state(first), 0), observe(history_state(second), 0)
        self.assertEqual(a, b)
        good = decisions.GoodPolicyV4(vote_reasoning=True, inspect_reasoning=True)
        mafia = decisions.MafiaPolicyV4(inference="combined")
        policy = mafia if role == "mafia" else good
        for seed in range(16):
            with self.subTest(role=role, seed=seed):
                self.assertEqual(decisions.message(a, policy, Random(seed)),
                                 decisions.message(b, policy, Random(seed)))
                self.assertEqual(decisions.vote(a, policy, Random(seed)),
                                 decisions.vote(b, policy, Random(seed)))
                if role == "police":
                    self.assertEqual(decisions.choose_inspection(a, policy, Random(seed)),
                                     decisions.choose_inspection(b, policy, Random(seed)))
                elif role == "mafia":
                    self.assertEqual(decisions.mafia_scores(a, policy),
                                     decisions.mafia_scores(b, policy))
                    self.assertEqual(decisions.choose_kill(a, policy, Random(seed)),
                                     decisions.choose_kill(b, policy, Random(seed)))

    def test_civilian_cannot_use_unknown_police_or_mafia_voter_identity(self):
        roles = ["civilian"] + ["police"]*4 + ["mafia"]*4 + ["civilian"]*7
        alternative = roles.copy()
        alternative[1], alternative[5] = alternative[5], alternative[1]
        self.compare_local_actions(roles, alternative, "civilian")

    def test_mafia_cannot_read_unknown_police_identity_from_ballots(self):
        roles = ["mafia"]*4 + ["police"]*4 + ["civilian"]*8
        alternative = roles.copy()
        alternative[4], alternative[8] = alternative[8], alternative[4]
        self.compare_local_actions(roles, alternative, "mafia")

    def test_police_cannot_read_unchecked_mafia_identity_from_history(self):
        roles = ["police"]*4 + ["mafia"]*4 + ["civilian"]*8
        alternative = roles.copy()
        alternative[4], alternative[8] = alternative[8], alternative[4]
        self.compare_local_actions(roles, alternative, "police")


class RoleConditionalMixingTests(unittest.TestCase):
    def test_vote_history_switch_has_no_effect_without_published_ballots(self):
        roles = ["police"]*4 + ["mafia"]*4 + ["civilian"]*8
        state = resolve_night(from_roles(roles), 15, 13)
        # Current nominations are available in both arms, while no vote history
        # exists yet. The history ablation must not also switch coordination.
        state = add_message(state, Message(6, "nominate", 10, day=1))
        state = add_message(state, Message(7, "nominate", 10, day=1))
        before = decisions.GoodPolicyV4(vote_reasoning=False)
        after = replace(before, vote_reasoning=True)
        for observer in (0, 9):
            obs = observe(state, observer)
            for seed in range(8):
                with self.subTest(observer=observer, seed=seed):
                    self.assertEqual(decisions.vote(obs, before, Random(seed)),
                                     decisions.vote(obs, after, Random(seed)))

    def test_private_live_hit_can_change_police_nomination_probability(self):
        roles = ["police"]*4 + ["mafia"]*4 + ["civilian"]*8
        state = history_state(roles)
        clear = observe(state, 0)
        # Both records are correct for the same world; only police observation
        # changes. A civilian's view of the private check remains unchanged.
        checked = replace(state, investigations=state.investigations[:-1] +
                          (Investigation(2, 6, True),))
        hit = observe(checked, 0)
        self.assertEqual(observe(state, 9), observe(checked, 9))
        policy = decisions.GoodPolicyV4(police_nominate_probability=0,
                                       hit_nominate_probability=1)
        for seed in range(8):
            with self.subTest(seed=seed):
                self.assertNotEqual(decisions.message(clear, policy, Random(seed)).kind,
                                    "nominate")
                claim = decisions.message(hit, policy, Random(seed))
                self.assertEqual((claim.kind, claim.target), ("nominate", 6))

    def test_civilian_cover_can_follow_mafia_public_nomination(self):
        roles = ["civilian"] + ["police"]*4 + ["mafia"]*4 + ["civilian"]*7
        state = history_state(roles)
        obs = observe(state, 0)
        policy = decisions.GoodPolicyV4(civilian_cover_probability=1)
        self.assertEqual(obs.teammates, ())
        for seed in range(8):
            claim = decisions.message(obs, policy, Random(seed))
            self.assertEqual((claim.kind, claim.target), ("nominate", 10))


class PublishedVoteTimingTests(unittest.TestCase):
    def test_runner_exposes_complete_first_ballot_only_after_submission(self):
        roles = ["police"]*4 + ["mafia"]*4 + ["civilian"]*8
        state = from_roles(roles)
        state = replace(state, rules=replace(state.rules, tie_rule="pk"))
        state = resolve_night(state, 15, 14)
        seen = []

        class RecordingAPI:
            choose_inspection = staticmethod(decisions.choose_inspection)
            choose_kill = staticmethod(decisions.choose_kill)
            message = staticmethod(decisions.message)

            @staticmethod
            def vote(obs, policy, rng, candidates=None):
                if obs.day == 1:
                    seen.append((candidates, obs.player, obs.public_events,
                                 decisions.published_ballots(obs)))
                    # Public seat convention creates a first-round tie. No role
                    # information is used to choose either forced ballot.
                    return {0: 1, 1: 0, 2: 0, 3: 1}.get(obs.player)
                return decisions.vote(obs, policy, rng, candidates)

        result = continue_game(state, decisions.GoodPolicyV4(),
                               decisions.MafiaPolicyV4(), 29000100,
                               decision_api=RecordingAPI)
        self.assertIn(result.good_win, (0, 1))
        first = [row for row in seen if row[0] is None]
        pk = [row for row in seen if row[0] is not None]
        self.assertEqual(len(first), 15)
        self.assertEqual(len(pk), 15)
        self.assertTrue(all(row[2] == first[0][2] for row in first))
        self.assertTrue(all(row[3] == {} for row in first))
        self.assertTrue(all(row[2] == pk[0][2] for row in pk))
        expected = {p: {0: 1, 1: 0, 2: 0, 3: 1}.get(p) for p in range(15)}
        self.assertTrue(all(row[3] == {1: expected} for row in pk))
        self.assertTrue(all(row[0] == (0, 1) for row in pk))


if __name__ == "__main__":
    unittest.main()
