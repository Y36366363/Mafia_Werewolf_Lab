"""Separate experiments for next-day succession and public report timing."""
from dataclasses import replace

from .corroborated_hit_v44 import CorroboratedHitAPI, common_hit
from .engine import Role, speech_order
from .hit_candidates_v37 import explain
from .paired_source_routing_v40 import current_calls
from .policies import teammates
from .source_evidence_pilot_v42 import AMBIGUOUS
from .strategies_v23 import restatement_target
from .succession_copy_v43 import copyable_report


def succession_warning(obs, call):
    """One-vote check using only the police caller's current observation."""
    original, target = call['original'], call['target']
    if (obs.role != Role.POLICE or obs.day != 2 or target == original
            or call['predicted'][target] - call['predicted'][original] != 1):
        return False
    team = teammates(obs)
    if not any(check.target == original and check.is_mafia for check in obs.investigations):
        return False
    reports = {m.speaker for m in obs.messages if m.day == 2 and m.kind == 'report'
               and m.target == original and m.verdict}
    if len(reports & team) < 2:
        return False
    return any(m.day == 1 and m.context == 'day' and m.speaker == target
               and m.kind == 'report' and m.verdict and m.target in obs.alive
               and m.target != original and m.target not in call['known_bad']
               for m in obs.messages)


def timing_choice(obs, info):
    """Resolve two distinct admissible calls using public reporting history."""
    if (obs.role != Role.CIVILIAN or obs.day < 2 or info['known_bad']
            or info['reason'] not in AMBIGUOUS or common_hit(obs, info) is not None):
        return None
    calls = current_calls(obs)
    eligible = [s for s in info['proposal_sources'] if s in calls
                and calls[s] in info['proposals'].get(str(s), ())]
    if len(eligible) != 2 or len(info['proposal_sources']) != 2 or calls[eligible[0]] == calls[eligible[1]]:
        return None
    current = {m.speaker: (i, m) for i, m in enumerate(obs.messages)
               if m.day == obs.day and m.context == 'day' and m.kind == 'report'
               and m.speaker in eligible}
    if len(current) == 2:
        (_, first), (index, later) = sorted(current.values())
        if (first.target, first.verdict) == (later.target, later.verdict):
            already_public = any(m.kind == 'report' and (m.target, m.verdict) == (later.target, later.verdict)
                                 for m in obs.messages[:current[first.speaker][0]])
            # Both could have seen a matching old or last-words report.
            if not already_public:
                return 'live_echo', first.speaker, calls[first.speaker]
    prior = [m for m in obs.messages if m.day < obs.day and m.kind in {'report', 'police'}]
    if all(any(m.speaker == s and m.context == 'day' for m in prior) for s in eligible):
        past_targets = {m.target for m in prior if m.kind == 'report'}
        fresh = [s for s, (_, m) in current.items() if m.target not in past_targets]
        if len(fresh) == 1:
            return 'returning_fresh', fresh[0], calls[fresh[0]]
    return None


class ReportTimingAPI(CorroboratedHitAPI):
    def __init__(self, cooperation, relay, q, risk, bluff, timing):
        super().__init__(cooperation, relay, q, copy=True, common_first=True, coordinate=True)
        self.risk = risk
        self.bluff = bluff
        self.timing = timing
        self.warnings = []
        self.reports = []
        self.choices = []

    def after_speech(self, obs, policy, rng):
        count = len(self.call_events)
        parts = super().after_speech(obs, policy, rng)
        if len(self.call_events) == count or not succession_warning(obs, self.call_events[-1]):
            return parts
        call = self.call_events[-1]
        self.warnings.append(dict(day=obs.day, kept_original=self.risk, original=call['original'],
                                  preferred=call['target']))
        if not self.risk:
            return parts
        call['target'] = call['original']
        return tuple(replace(m, target=call['target']) if m.kind == 'accuse' else m for m in parts)

    def message(self, obs, policy, rng, context='day', override=None):
        count = len(self.successions)
        report = super().message(obs, policy, rng, context, override)
        if self.bluff == 'inherited' or context != 'day' or obs.day < 2:
            return report
        if obs.role == Role.POLICE and report.kind == 'report' and obs.investigations:
            check = obs.investigations[-1]
            assert check.day == obs.day
            result = replace(report, target=check.target, verdict=check.is_mafia)
            self.reports.append(dict(day=obs.day, speaker=obs.player, target=result.target,
                                     verdict=result.verdict, reason='current_check'))
            return result
        if obs.role != Role.MAFIA:
            return report
        call = self.successions[-1]['target'] if len(self.successions) != count else restatement_target(obs, policy)
        if call is None:
            return report
        allies = teammates(obs)
        visible = [m for m in obs.messages if m.day == obs.day and m.kind == 'report'
                   and m.context == 'day' and m.speaker in obs.alive and m.speaker not in allies
                   and m.target in obs.alive and m.target != obs.player]
        occupied = {m.target for m in obs.messages if m.kind == 'report'}
        distinct = next((p for p in speech_order(obs) if p not in allies and p not in occupied), None)
        dead = copyable_report(obs)
        if self.bluff == 'distinct' and distinct is not None:
            target, verdict, reason = distinct, True, 'distinct'
        elif visible:
            target, verdict, reason = visible[0].target, visible[0].verdict, 'live_echo'
        elif dead is not None:
            target, verdict, reason = *dead, 'dead_echo'
        else:
            target, verdict, reason = call, True, 'legacy_repeat'
        self.reports.append(dict(day=obs.day, speaker=obs.player, target=target, verdict=verdict,
                                 reason=reason, call=call))
        return replace(report, kind='report', target=target, verdict=verdict)

    def vote(self, obs, policy, rng, candidates=None):
        target = super().vote(obs, policy, rng, candidates)
        if self.bluff == 'inherited' or obs.role != Role.CIVILIAN or obs.day < 2 or candidates is not None:
            return target
        info = explain(obs, policy, retain=True)
        proposed = timing_choice(obs, info)
        if proposed is None:
            return target
        reason, source, choice = proposed
        assert choice in info['legal'] and choice not in info['known_good'] and not info['known_bad']
        actual = choice if self.timing else target
        self.choices.append(dict(day=obs.day, player=obs.player, source=source, reason=reason,
                                 proposed=choice, baseline=target, actual=actual))
        self.pilot_ballots[-1]['target'] = actual
        return actual
