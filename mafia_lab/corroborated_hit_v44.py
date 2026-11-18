"""Public common hits and police execution choices made from local observations."""

from dataclasses import replace

from .engine import Role, speech_order
from .hit_candidates_v37 import explain
from .policies import teammates
from .source_evidence_pilot_v42 import agreement_choice
from .strategies_v18 import _clear_priority
from .strategies_v26 import team_execution_call
from .succession_copy_v43 import SuccessionCopyAPI


def common_hit(obs, info):
    """Return the unanimous current hit among at least two live report sources."""
    if obs.role != Role.CIVILIAN or obs.day < 2 or info['known_bad']:
        return None
    sources = set(info['sources'])
    reports = {m.speaker: m for m in obs.messages
               if m.kind == 'report' and m.day == obs.day and m.context == 'day'
               and m.speaker in sources and m.speaker in obs.alive}
    if len(reports) < 2:
        return None
    claims = {(m.target, m.verdict) for m in reports.values()}
    if len(claims) != 1:
        return None
    target, verdict = next(iter(claims))
    if not verdict or any(m.kind == 'report' and m.speaker in sources
                          and m.target == target and m.verdict is False for m in obs.messages):
        return None
    guarded = _clear_priority(obs, [p for p in info['legal'] if p not in info['known_good']])
    return target if target in guarded else None


def civilian_vote(obs, policy, common_first, candidates=None):
    info = explain(obs, policy, candidates, retain=True)
    shared = common_hit(obs, info)
    supported = agreement_choice(obs, info)
    baseline = supported[1] if supported else info['target']
    return shared if common_first and shared is not None else baseline


def projected_support(obs, policy, parts, call_index, known_bad, common_first):
    """Predict unconditional civilian-type choices using only the current prefix."""
    original = parts[call_index]
    voters = [p for p in obs.alive if p not in teammates(obs) and p not in known_bad]
    support = {}
    for target in sorted(known_bad):
        proposed = (*parts[:call_index], replace(original, target=target), *parts[call_index+1:])
        prefix = replace(obs, messages=obs.messages + proposed, public_events=(),
                         role=Role.CIVILIAN, teammates=(), investigations=())
        support[target] = sum(
            civilian_vote(replace(prefix, player=p), policy, common_first) == target
            for p in voters if p != target)
    return support


class CorroboratedHitAPI(SuccessionCopyAPI):
    def __init__(self, cooperation, fake_relay, q, copy, common_first, coordinate):
        super().__init__(cooperation, fake_relay, q, agreement=True, copy=copy)
        self.common_first = common_first
        self.coordinate = coordinate
        self.common_events = []
        self.call_events = []
        self.police_checks = []

    def after_speech(self, obs, policy, rng):
        parts = super().after_speech(obs, policy, rng)
        if (obs.role != Role.POLICE or obs.day < 2 or team_execution_call(obs) is not None
                or not any(m.speaker == obs.player and m.day == obs.day and m.context == 'day'
                           and m.kind == 'report' for m in obs.messages)):
            return parts
        messages = tuple(m for m in (parts if isinstance(parts, tuple) else (parts,)) if m is not None)
        indexes = [i for i, m in enumerate(messages) if m.kind == 'accuse']
        if len(indexes) != 1:
            return parts
        index = indexes[0]
        original = messages[index].target
        known_bad = set(explain(obs, policy, retain=True)['known_bad'])
        if original not in known_bad or len(known_bad) < 2:
            return parts
        predicted = projected_support(obs, policy, messages, index, known_bad, self.common_first)
        order = {p: i for i, p in enumerate(speech_order(obs))}
        preferred = max(known_bad, key=lambda p: (predicted[p], p == original, -order[p]))
        target = preferred if self.coordinate else original
        self.call_events.append(dict(day=obs.day, speaker=obs.player, original=original,
            preferred=preferred, target=target, predicted=predicted, known_bad=sorted(known_bad)))
        return (*messages[:index], replace(messages[index], target=target), *messages[index+1:]) if target != original else parts

    def vote(self, obs, policy, rng, candidates=None):
        target = super().vote(obs, policy, rng, candidates)
        if obs.day < 2:
            return target
        if obs.role == Role.CIVILIAN:
            info = explain(obs, policy, candidates, retain=True)
            shared = common_hit(obs, info)
            if shared is not None:
                actual = shared if self.common_first else target
                self.common_events.append(dict(day=obs.day, first=candidates is None, player=obs.player,
                                               target=shared, baseline=target, actual=actual))
                self.pilot_ballots[-1]['target'] = actual
                return actual
        if obs.role == Role.POLICE:
            call = next((row for row in self.call_events if row['day'] == obs.day), None)
            if call is not None:
                known_bad = explain(obs, policy, candidates, retain=True)['known_bad']
                if call['target'] in known_bad:
                    assert target == call['target']
                    self.police_checks.append(dict(day=obs.day, pk=candidates is not None, target=target))
        return target
