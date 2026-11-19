"""Passive observation audit and a same-ballot public-report diagnostic.

No referee role array is accepted by the decision recorder or shadow receiver.
The shadow calculation changes no actual game and samples no randomness.
"""
from collections import Counter
from dataclasses import asdict, replace

from .corroborated_hit_v44 import CorroboratedHitAPI, civilian_vote, common_hit
from .engine import Role
from .hit_candidates_v37 import explain
from .source_evidence_pilot_v42 import agreement_choice


def ballot_details(obs, policy, candidates, target):
    info = explain(obs, policy, candidates, retain=True)
    return dict(observation=asdict(obs), candidates=candidates, target=target,
                info=info, common_hit=common_hit(obs, info),
                agreement=agreement_choice(obs, info))


def replace_public_report(obs, old, new):
    """One public message replacement; all observer-private fields unchanged."""
    assert old.speaker == new.speaker and old.kind == new.kind == 'report'
    assert old.day == new.day == obs.day and old.context == new.context == 'day'
    assert sum(message == old for message in obs.messages) == 1
    return replace(obs, messages=tuple(new if message == old else message
                                       for message in obs.messages))


class ContinuationAuditAPI(CorroboratedHitAPI):
    def __init__(self, cooperation, fake_relay, q, copy, common_first, coordinate):
        super().__init__(cooperation, fake_relay, q, copy, common_first, coordinate)
        self.audit_messages = []
        self.audit_votes = []
        self._message_records = []
        self._vote_records = []

    def message(self, obs, policy, rng, context='day', override=None):
        message = super().message(obs, policy, rng, context, override)
        self.audit_messages.append(dict(observation=asdict(obs), output=asdict(message)))
        self._message_records.append((obs, message))
        return message

    def vote(self, obs, policy, rng, candidates=None):
        target = super().vote(obs, policy, rng, candidates)
        row = (ballot_details(obs, policy, candidates, target)
               if obs.role != Role.MAFIA else
               dict(observation=asdict(obs), candidates=candidates, target=target))
        self.audit_votes.append(row)
        self._vote_records.append((obs, policy, candidates, target))
        # Check information permissions independently of the referee role array.
        assert all(check.day <= obs.day for check in obs.investigations)
        if obs.role != Role.POLICE:
            assert not obs.investigations
        if obs.role == Role.CIVILIAN:
            assert not obs.teammates
        return target

    def latest_report_shadow(self, day):
        replacements = []
        for obs, report in self._message_records:
            if (obs.day != day or obs.role != Role.POLICE or report.context != 'day'
                    or report.kind != 'report' or not obs.investigations):
                continue
            latest = obs.investigations[-1]
            if (latest.day != day or latest.target not in obs.alive
                    or (report.target, report.verdict) == (latest.target, latest.is_mafia)):
                continue
            new = replace(report, target=latest.target, verdict=latest.is_mafia)
            replacements.append((report, new, latest))
        shadows = []
        for old, new, latest in replacements:
            ballots = []
            for obs, policy, candidates, actual in self._vote_records:
                if obs.day != day or candidates is not None:
                    continue
                altered = replace_public_report(obs, old, new)
                target = (civilian_vote(altered, policy, self.common_first)
                          if obs.role == Role.CIVILIAN else actual)
                if obs.role == Role.CIVILIAN:
                    assert civilian_vote(obs, policy, self.common_first) == actual
                    info = explain(altered, policy, retain=True)
                    assert target is None or target in info['legal']
                    assert target not in info['known_good']
                    assert not info['known_bad'] or target in info['known_bad']
                ballots.append(dict(player=obs.player, role=obs.role.value,
                                    before=actual, after=target))
            before = Counter(row['before'] for row in ballots if row['before'] is not None)
            after = Counter(row['after'] for row in ballots if row['after'] is not None)
            leaders = lambda counts: sorted(p for p, n in counts.items() if n == max(counts.values())) if counts else []
            shadows.append(dict(old=asdict(old), new=asdict(new), latest=asdict(latest),
                                ballots=ballots, before=dict(before), after=dict(after),
                                before_leaders=leaders(before), after_leaders=leaders(after)))
        return shadows
