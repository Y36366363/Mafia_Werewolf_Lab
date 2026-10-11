"""Independent referee replay of every tiny-model strategy/chance pairing.

Tiny policy functions are reused deliberately. Observation projection, terminal
timing, votes and complete continuation are evaluated by the general referee.
This validates cross-model consistency, not independent strategy optimality.
"""

from dataclasses import replace
from fractions import Fraction
from functools import lru_cache
from itertools import product
import unittest

from mafia_lab import tiny
from mafia_lab.engine import (
    Message, Role, Rules, add_message, from_roles, observe, resolve_night,
    resolve_votes, speech_order, winner,
)


ROLE_MAP = {"P": Role.POLICE, "M": Role.MAFIA,
            "C1": Role.CIVILIAN, "C2": Role.CIVILIAN}
TINY_RULES = Rules(1, 1, 2)


def observation_from_general_referee(state, seat):
    visible = observe(state, seat)
    inspection = None
    if visible.investigations:
        record = visible.investigations[-1]
        inspection = (record.target, record.is_mafia)
    claims = tuple(tiny.Claim(m.speaker, m.target, m.verdict)
                   for m in visible.messages)
    role = {Role.POLICE: "P", Role.MAFIA: "M", Role.CIVILIAN: "C"}[visible.role]
    return tiny.Observation(seat, role, speech_order(state),
                            visible.deaths[0].player, inspection, claims)


@lru_cache(maxsize=None)
def complete_silent_continuation(roles, alive):
    """Independent exact continuation, with at least one death each night.

    Histories can be discarded here because the declared continuation ignores
    all statements/inspection information and uses uniform kills and ballots.
    The check is fixed to a legal target because its unused result cannot alter
    this policy's actions or terminal payoff.
    """
    state = replace(from_roles(roles, TINY_RULES), alive=alive)
    result = winner(state)
    if result is not None:
        return Fraction(result == "good")
    kill_targets = tuple(p for p in alive if roles[p] != Role.MAFIA)
    value = Fraction(0)
    for target in kill_targets:
        after_night = resolve_night(state, target, alive[0])
        result = winner(after_night)
        if result is not None:
            value += Fraction(result == "good")
            continue
        choices = tuple(tuple(p for p in after_night.alive if p != voter)
                        for voter in after_night.alive)
        ballot_count = 1
        for targets in choices:
            ballot_count *= len(targets)
        day_value = Fraction(0)
        for votes in product(*choices):
            after_day = resolve_votes(after_night, dict(zip(after_night.alive, votes)))
            day_value += complete_silent_continuation(roles, after_day.alive)
        value += day_value / ballot_count
    return value / len(kill_targets)


def replay_scenario(roles, victim, check, good_plan, mafia_plan):
    converted = tuple(ROLE_MAP[role] for role in roles)
    state = resolve_night(from_roles(converted, TINY_RULES), victim, check)
    result = winner(state)
    if result is not None:
        return Fraction(result == "good")
    for seat in speech_order(state):
        obs = observation_from_general_referee(state, seat)
        claim = (tiny.mafia_speech(obs, mafia_plan) if obs.role == "M"
                 else tiny.good_speech(obs, good_plan))
        state = add_message(state, Message(
            claim.speaker, "report" if claim.claims_police else "pass",
            claim.target, claim.mafia, day=state.day,
        ))
    ballots = {}
    for seat in state.alive:
        obs = observation_from_general_referee(state, seat)
        ballots[seat] = (obs.targets[0] if obs.role == "M"
                         else tiny.good_vote(obs, good_plan))
    state = resolve_votes(state, ballots)
    return complete_silent_continuation(state.roles, state.alive)


class CrossModelTests(unittest.TestCase):
    def test_all_31104_paths_reproduce_every_exact_matrix_cell(self):
        reference = tiny.exact_matrix()
        scenarios = tuple(tiny.chance_scenarios())
        self.assertEqual(len(scenarios), 216)
        for gi, good_plan in enumerate(tiny.GOOD_PLANS):
            for mi, mafia_plan in enumerate(tiny.MAFIA_PLANS):
                with self.subTest(good=good_plan.name, mafia=mafia_plan):
                    value = sum((replay_scenario(*s, good_plan, mafia_plan)
                                 for s in scenarios), Fraction(0)) / len(scenarios)
                    self.assertEqual(value, reference[gi][mi])

    def test_frozen_continuation_reaches_correct_terminals(self):
        roles = tuple(ROLE_MAP[r] for r in ("P", "M", "C1", "C2"))
        self.assertEqual(complete_silent_continuation(roles, (0, 1, 2)), 0)
        self.assertEqual(complete_silent_continuation(roles, (0, 2)), 1)
        self.assertEqual(complete_silent_continuation(roles, (1, 2)), 0)


if __name__ == "__main__":
    unittest.main()
