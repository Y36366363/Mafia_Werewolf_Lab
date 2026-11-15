"""Observation-only role compatibility, not a calibrated posterior or agent."""
from dataclasses import replace
from itertools import combinations
from math import comb
from .engine import Role, Message, speech_order
from . import strategies_v31 as base
from .policies import teammates


def suppress_redundant(obs, context):
    """Private police-team knowledge; no referee labels or inferred death identity."""
    return (obs.role == Role.POLICE and obs.day == 1 and context == 'day'
            and any(m.kind == 'report' and m.context == 'last_words' and m.day == 1
                    and m.speaker in teammates(obs) for m in obs.messages))


class ResponseAPI:
    def __init__(self, restrained=False):
        self.restrained = restrained
        self.suppressed = 0
        self.focal = None
    def __getattr__(self, name):
        return getattr(base, name)
    def message(self, obs, policy, rng, context='day', override=None):
        result = base.message(obs, policy, rng, context, override)
        if self.restrained and suppress_redundant(obs, context) and result.kind in {'report', 'police'}:
            self.suppressed += 1
            return Message(obs.player, 'pass', context=context, day=obs.day)
        return result
    def vote(self, obs, policy, rng, candidates=None):
        if obs.day == 1 and candidates is None and obs.player == 0 and obs.role == Role.CIVILIAN:
            # Only this observer's private role is supplied. Earlier live ballots
            # are intentionally discarded: the diagnostic is about pre-vote speech.
            self.focal = replace(obs, public_events=(), pending_pk=())
        return base.vote(obs, policy, rng, candidates)


def source_prefix(obs):
    """First living claim snapshot; absence is observable only after all speeches."""
    victim = obs.deaths[0].player
    dead = next((m for m in obs.messages if m.speaker == victim and m.context == 'last_words'
                 and m.day == 1 and m.kind == 'report' and m.verdict is False), None)
    if dead is None:
        return None
    index = next((i for i, m in enumerate(obs.messages) if m.context == 'day' and m.day == 1
                  and m.kind == 'report'), None)
    live = obs.messages[index] if index is not None else None
    messages = obs.messages[:index+1] if index is not None else obs.messages
    snapshot = replace(obs, messages=messages, public_events=(), pending_pk=())
    if live is None:
        event = 'no_live_at_end'
    else:
        position = list(speech_order(obs)).index(live.speaker) + 1
        timing = 'early' if position <= 7 else 'late'
        kind = 'hit' if live.verdict else 'copy' if live.target == dead.target else 'other_clear'
        event = kind + '_' + timing
    return snapshot, dead, live, event


def role_support(obs, dead_source, live_source=None):
    """Count role assignments satisfying role-truth constraints only.

    Police report truthful mafia/nonmafia status; civilians cannot claim police.
    Mafia reports may be arbitrary. Death, grants, lists, rank and votes do NOT
    certify anyone. These are a SUPERSET of strategy-generated histories. In
    particular common inspection choice, likelihood of speaking, and kill-policy
    likelihood are not supplied. Counts must never be called posterior weights.
    """
    if obs.role != Role.CIVILIAN or obs.day != 1:
        raise ValueError('first-day civilian diagnostic only')
    n = obs.rules.n_players
    claims = [m for m in obs.messages if m.kind in {'report', 'police'}]
    reports = [m for m in claims if m.kind == 'report']
    seats = set(range(n)); possible = sorted(seats - {obs.player})
    counts = {}; witnesses = {}
    for police_tuple in combinations(possible, obs.rules.police):
        police = set(police_tuple)
        bad = {m.speaker for m in claims if m.speaker not in police}
        clean = police | {obs.player}
        for m in reports:
            if m.speaker in police:
                (bad if m.verdict else clean).add(m.target)
        if bad & clean or len(bad) > obs.rules.mafia:
            continue
        free = sorted(seats - bad - clean); need = obs.rules.mafia - len(bad)
        if not 0 <= need <= len(free):
            continue
        # Sources in this diagnostic are claimants, hence non-police => mafia.
        key = ('P' if dead_source in police else 'M') + '/' + (
            '-' if live_source is None else 'P' if live_source in police else 'M')
        count = comb(len(free), need)
        counts[key] = counts.get(key, 0) + count
        if key not in witnesses:
            mafia = bad | set(free[:need])
            witnesses[key] = ['police' if p in police else 'mafia' if p in mafia else 'civilian' for p in range(n)]
    return dict(counts=counts, witnesses=witnesses,
                interpretation='logical role compatibility superset; NOT posterior probabilities')
