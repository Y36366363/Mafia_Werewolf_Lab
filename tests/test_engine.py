"""Referee invariants with paired hidden worlds, not strategy-performance tests."""

from dataclasses import FrozenInstanceError, replace
import random
import unittest

from mafia_lab.engine import (
    Message, Role, Rules, add_message, deal, from_roles, last_words_eligible,
    night_targets, observe, resolve_night, resolve_votes, speech_order, winner,
)


class ObservationTests(unittest.TestCase):
    def test_civilian_cannot_distinguish_hidden_role_permutation(self):
        first = from_roles(["civilian", "police", "mafia", "civilian"])
        second = from_roles(["civilian", "mafia", "police", "civilian"])
        self.assertEqual(observe(first, 0), observe(second, 0))
        self.assertFalse(hasattr(observe(first, 0), "roles"))
        self.assertEqual(observe(first, 0).teammates, ())

    def test_factions_only_know_their_own_teammates(self):
        a = from_roles(["police", "police", "mafia", "mafia", "civilian", "civilian"])
        b = from_roles(["police", "police", "civilian", "mafia", "mafia", "civilian"])
        self.assertEqual(observe(a, 0), observe(b, 0))
        self.assertEqual(observe(a, 0).teammates, (1,))
        self.assertEqual(observe(a, 2).teammates, (3,))

    def test_night_death_does_not_flip_role(self):
        a = from_roles(["civilian", "police", "police", "mafia", "civilian"])
        b = from_roles(["civilian", "civilian", "police", "mafia", "police"])
        a = resolve_night(a, 1, 3)
        b = resolve_night(b, 1, 3)
        self.assertEqual(observe(a, 0), observe(b, 0))
        self.assertEqual(a.public_events, b.public_events)

    def test_inspection_is_private_and_dying_police_receives_it(self):
        state = from_roles(["police", "police", "mafia", "civilian", "civilian"])
        state = resolve_night(state, 0, 2)
        self.assertEqual(observe(state, 0).investigations, observe(state, 1).investigations)
        self.assertEqual(observe(state, 0).investigations[0].target, 2)
        self.assertTrue(observe(state, 0).investigations[0].is_mafia)
        self.assertEqual(observe(state, 2).investigations, ())
        self.assertEqual(observe(state, 3).investigations, ())
        self.assertTrue(last_words_eligible(state, 0))
        state = resolve_night(state, 3, 4)
        self.assertEqual(len(observe(state, 0).investigations), 1)
        self.assertEqual(len(observe(state, 1).investigations), 2)

    def test_inspection_choice_not_public_and_cannot_change_mafia_observation(self):
        state = from_roles(["police", "police", "mafia", "civilian", "civilian"])
        a = resolve_night(state, 3, 2)
        b = resolve_night(state, 3, 4)
        self.assertEqual(observe(a, 2), observe(b, 2))
        self.assertEqual(observe(a, 4), observe(b, 4))
        self.assertNotEqual(observe(a, 0), observe(b, 0))


class TerminalAndNightTests(unittest.TestCase):
    def test_last_police_death_ends_before_last_words(self):
        state = from_roles(["police", "mafia", "civilian", "civilian"])
        state = resolve_night(state, 0, 1)
        self.assertEqual(winner(state), "mafia")
        self.assertTrue(observe(state, 0).investigations[0].is_mafia)
        self.assertFalse(last_words_eligible(state, 0))
        with self.assertRaises(ValueError):
            add_message(state, Message(0, "report", 1, True, "last_words", 1))
        with self.assertRaises(ValueError):
            resolve_votes(state, {1: 2, 2: 1, 3: 1})

    def test_last_mafia_self_kill_is_immediate_good_win(self):
        state = from_roles(["police", "mafia", "civilian", "civilian"])
        state = resolve_night(state, 1, 1)
        self.assertEqual(winner(state), "good")
        self.assertFalse(last_words_eligible(state, 1))

    def test_parity_and_no_civilians_do_not_end_game(self):
        state = from_roles(["police", "mafia", "mafia"])
        self.assertIsNone(winner(state))

    def test_police_can_inspect_self_and_teammates(self):
        state = from_roles(["police", "police", "mafia", "civilian"])
        self.assertEqual(night_targets(state, Role.POLICE), (0, 1, 2, 3))
        for target in (0, 1):
            after = resolve_night(state, 3, target)
            self.assertFalse(after.investigations[0].is_mafia)

    def test_self_kill_switch_covers_all_mafia_teammates(self):
        state = from_roles(["police", "police", "mafia", "mafia", "civilian"])
        self.assertEqual(night_targets(state, "mafia"), state.alive)
        state = replace(state, rules=replace(state.rules, allow_self_kill=False))
        self.assertEqual(night_targets(state, "mafia"), (0, 1, 4))
        for target in (2, 3):
            with self.assertRaises(ValueError):
                resolve_night(state, target, 4)

    def test_dead_targets_rejected_and_input_state_unchanged(self):
        before = from_roles(["police", "police", "mafia", "civilian", "civilian"])
        after = resolve_night(before, 3, 3)
        self.assertEqual(before.alive, (0, 1, 2, 3, 4))
        with self.assertRaises(FrozenInstanceError):
            after.day = 9
        for kill, inspect in ((3, 4), (4, 3)):
            with self.assertRaises(ValueError):
                resolve_night(after, kill, inspect)


class SpeechAndLastWordsTests(unittest.TestCase):
    def test_civilian_fake_report_is_public_claim_not_truth(self):
        state = from_roles(["police", "mafia", "civilian", "civilian"])
        state = add_message(state, Message(2, "report", 0, True))
        self.assertEqual(observe(state, 1).messages[-1].verdict, True)
        self.assertEqual(state.investigations, ())

    def test_last_words_budget_counts_night_and_day(self):
        roles = ["police", "police", "mafia", "mafia", "civilian", "civilian", "civilian", "civilian"]
        rules = Rules(2, 2, 4, last_words_limit=2)
        state = resolve_night(from_roles(roles, rules), 4, 2)
        self.assertTrue(last_words_eligible(state, 4))
        state = add_message(state, Message(4, "civilian", context="last_words", day=1))
        self.assertFalse(last_words_eligible(state, 4))
        state = resolve_votes(state, {i: (5 if i != 5 else None) for i in state.alive})
        self.assertTrue(last_words_eligible(state, 5))
        state = resolve_night(state, 6, 3)
        self.assertFalse(last_words_eligible(state, 6))
        self.assertEqual([d.ordinal for d in state.deaths], [1, 2, 3])

    def test_night_last_words_cannot_be_delayed_until_after_speech(self):
        state = resolve_night(from_roles(["police", "police", "mafia", "civilian"]), 3, 2)
        state = add_message(state, Message(0, "pass", day=1))
        self.assertFalse(last_words_eligible(state, 3))

    def test_speech_order_is_directional_and_skips_dead_seats(self):
        state = resolve_night(from_roles(["police", "police", "mafia", "civilian", "civilian"]), 3, 2)
        self.assertEqual(speech_order(state), (4, 0, 1, 2))
        self.assertEqual(speech_order(state, direction=-1), (2, 1, 0, 4))
        self.assertEqual(speech_order(observe(state, 4)), speech_order(state))


class VotingTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles(["police", "police", "mafia", "mafia", "civilian", "civilian"])

    def test_partial_ballot_is_rejected_without_publication(self):
        with self.assertRaises(ValueError):
            resolve_votes(self.state, {0: 2})
        self.assertEqual(self.state.public_events, ())

    def test_ballot_order_does_not_change_result_and_is_public_only_after(self):
        votes = {0: 2, 1: 2, 2: 0, 3: 0, 4: 2, 5: None}
        a = resolve_votes(self.state, votes)
        b = resolve_votes(self.state, dict(reversed(tuple(votes.items()))))
        self.assertEqual(a, b)
        self.assertNotIn(2, a.alive)
        self.assertEqual(a.public_events[0].ballots, tuple(sorted(votes.items())))
        self.assertEqual(observe(a, 5).public_events, a.public_events)

    def test_self_vote_and_dead_voter_and_invalid_seats_rejected(self):
        for votes in ({i: i for i in self.state.alive},
                      {**{i: None for i in self.state.alive}, 6: None},
                      {**{i: None for i in self.state.alive}, 0: True}):
            with self.assertRaises(ValueError):
                resolve_votes(self.state, votes)

    def test_all_abstain_does_not_start_pk(self):
        state = replace(self.state, rules=replace(self.state.rules, tie_rule="pk"))
        state = resolve_votes(state, {i: None for i in state.alive})
        self.assertEqual(state.alive, self.state.alive)
        self.assertEqual(state.pending_pk, ())

    def test_tie_passes_or_enters_pk_and_second_tie_passes(self):
        votes = {0: 2, 1: 2, 2: 0, 3: 0, 4: None, 5: None}
        passed = resolve_votes(self.state, votes)
        self.assertEqual(passed.alive, self.state.alive)
        self.assertEqual(passed.pending_pk, ())
        state = replace(self.state, rules=replace(self.state.rules, tie_rule="pk"))
        state = resolve_votes(state, votes)
        self.assertEqual(state.pending_pk, (0, 2))
        with self.assertRaises(ValueError):
            resolve_night(state, 5, 2)
        with self.assertRaises(ValueError):
            resolve_votes(state, votes)
        with self.assertRaises(ValueError):
            resolve_votes(state, {**votes, 4: 3}, pk=True)
        state = resolve_votes(state, votes, pk=True)
        self.assertEqual(state.alive, self.state.alive)
        self.assertEqual(state.pending_pk, ())

    def test_only_pk_candidates_get_pk_speech(self):
        state = replace(self.state, rules=replace(self.state.rules, tie_rule="pk"))
        state = resolve_votes(state, {0: 2, 1: 2, 2: 0, 3: 0, 4: None, 5: None})
        state = add_message(state, Message(0, "police", context="pk"))
        with self.assertRaises(ValueError):
            add_message(state, Message(1, "police", context="pk"))

    def test_last_mafia_day_vote_checks_terminal_immediately(self):
        state = from_roles(["police", "mafia", "civilian", "civilian"])
        state = resolve_votes(state, {0: 1, 1: 0, 2: 1, 3: 1})
        self.assertEqual(winner(state), "good")
        self.assertFalse(last_words_eligible(state, 1))


class SetupTests(unittest.TestCase):
    def test_deal_is_reproducible_and_preserves_counts(self):
        rules = Rules()
        a = deal(rules, random.Random(123))
        b = deal(rules, random.Random(123))
        self.assertEqual(a, b)
        self.assertEqual(a.roles.count(Role.POLICE), 4)
        self.assertEqual(a.roles.count(Role.MAFIA), 4)
        self.assertEqual(a.roles.count(Role.CIVILIAN), 8)

    def test_setup_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            from_roles(["police", "mafia", "civilian", "civilian"], Rules())
        with self.assertRaises(ValueError):
            Rules(police=0)


if __name__ == "__main__":
    unittest.main()
