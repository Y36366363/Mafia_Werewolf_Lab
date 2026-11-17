"""Same-slot succession copying and observation-only agreement diagnostics."""

from dataclasses import replace

from .engine import Role
from .hit_candidates_v37 import explain
from .paired_source_routing_v40 import current_calls
from .policies import teammates
from .source_evidence_pilot_v42 import AMBIGUOUS, SourceEvidencePilotAPI


def death_night_reports(obs):
    victims = {death.player for death in obs.deaths
               if death.day == obs.day and death.cause == 'night'}
    return [(m.target, m.verdict) for m in obs.messages
            if m.day == obs.day and m.context == 'last_words' and m.kind == 'report'
            and m.speaker in victims]


def copyable_report(obs):
    """Choose a currently visible night-last-words result at a legal slot."""
    if obs.role != Role.MAFIA or obs.day < 2:
        return None
    reports = set(death_night_reports(obs))
    if len(reports) != 1:
        return None
    target, verdict = next(iter(reports))
    if target not in obs.alive or target == obs.player:
        return None
    return target, verdict


def match_diagnostics(obs, info):
    """Reconstruct v42's public match set after its normal ballot guards."""
    if info['known_bad'] or info['reason'] not in AMBIGUOUS:
        return None
    reports = set(death_night_reports(obs))
    if len(reports) != 1:
        return None
    calls = current_calls(obs)
    eligible = {source: calls[source] for source in info['proposal_sources']
                if source in obs.alive and source in calls
                and calls[source] in info['proposals'].get(str(source), ())}
    if len(set(eligible.values())) < 2:
        return None
    claims = {m.speaker: (m.target, m.verdict) for m in obs.messages
              if m.day == obs.day and m.context == 'day' and m.kind == 'report'}
    return sorted(source for source in eligible if claims.get(source) in reports)


class SuccessionCopyAPI(SourceEvidencePilotAPI):
    def __init__(self, cooperation, fake_relay, q, agreement=False, copy=False):
        super().__init__(cooperation, fake_relay, q, 'succession_report', agreement)
        self.copy = copy
        self.copy_events = []
        self.match_events = []

    def message(self, obs, policy, rng, context='day', override=None):
        count = len(self.successions)
        report = super().message(obs, policy, rng, context, override)
        if len(self.successions) == count:
            return report
        possible = copyable_report(obs)
        if possible is None:
            return report
        target, verdict = possible
        changed = (report.target, report.verdict) != possible
        self.copy_events.append(dict(day=obs.day, speaker=obs.player, target=target,
            verdict=verdict, call=report.target, changes_report=changed,
            copied=self.copy, hit_teammate=verdict and target in teammates(obs)))
        if self.copy:
            return replace(report, target=target, verdict=verdict)
        return report

    def vote(self, obs, policy, rng, candidates=None):
        before = len(self.pilot_ballots)
        target = super().vote(obs, policy, rng, candidates)
        if len(self.pilot_ballots) == before:
            return target
        ballot = self.pilot_ballots[-1]
        details = explain(obs, policy, candidates, retain=True)
        matches = match_diagnostics(obs, details)
        if matches is not None and len(matches) == 1:
            assert ballot['supported'] is not None and ballot['supported'][0] == matches[0]
        else:
            assert ballot['supported'] is None
        latest = next((e for e in reversed(self.copy_events) if e['day'] == obs.day), None)
        self.match_events.append(dict(day=obs.day, first=candidates is None,
            player=obs.player, matches=matches, eligible=details['proposal_sources'],
            copier=None if latest is None else latest['speaker']))
        return target
