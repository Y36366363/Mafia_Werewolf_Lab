"""Continuation ballot policy for explicit opposition between live claimants."""

from . import strategies_v20 as evidence
from .engine import Role
from .hit_candidates_v37 import HitCandidatesAPI, explain


MERGE_REASONS = {'common_recommendation_protocol', 'compatible_sources_protocol'}


def formal_edges(obs, sources):
    """Read current ordinary formal calls between already declared live sources."""
    declared = set()
    latest = {}
    live_sources = set(sources).intersection(obs.alive)
    for message in obs.messages:
        if message.speaker not in live_sources:
            continue
        if message.kind in {'police', 'report'}:
            declared.add(message.speaker)
        if message.kind == 'accuse' and message.context == 'day' and message.day == obs.day:
            target = message.target
            latest[message.speaker] = (
                target if message.speaker in declared and target in declared
                and target != message.speaker else None
            )
    return sorted({tuple(sorted((speaker, target))) for speaker, target in latest.items()
                   if target is not None})


def prevent_formal_merge(obs, policy, original):
    """Replace a merge by the established comparison among legal live sources."""
    if obs.role != Role.CIVILIAN or obs.day < 2 or original['known_bad']:
        return original
    if original['reason'] not in MERGE_REASONS:
        return original
    edges = formal_edges(obs, original['proposal_sources'])
    prior = {tuple(edge) for edge in original['active_edges']}
    added = [edge for edge in edges if edge not in prior]
    if not added:
        return original
    pool = [p for p in original['legal'] if p not in original['known_good']]
    guarded = evidence.old.constraints._clear_priority(obs, pool)
    active = sorted(prior.union(added))
    endpoints = {p for edge in active for p in edge}
    targets = [p for p in guarded if p in endpoints]
    return dict(original,
                target=evidence._rank_choice(obs, policy, targets or guarded),
                reason='formal_source_comparison' if targets else 'formal_source_fallback',
                formal_edges=added, active_edges=active, conflict_targets=targets)


class FormalSourceConflictAPI(HitCandidatesAPI):
    """Both arms inherit the v37 retain-hits opening and fixed v35 response."""

    def __init__(self, cooperation, fake_relay, q, enabled):
        super().__init__(cooperation, fake_relay, q, retain=True)
        self.enabled = enabled
        self.continuation_ballots = []

    def vote(self, obs, policy, rng, candidates=None):
        if obs.day == 1 or obs.role == Role.MAFIA:
            return super().vote(obs, policy, rng, candidates)
        original = explain(obs, policy, candidates, retain=True)
        revised = prevent_formal_merge(obs, policy, original)
        chosen = revised if self.enabled else original
        target = chosen['target']
        assert target is None or target in chosen['legal']
        assert target not in chosen['known_good']
        assert not chosen['known_bad'] or target in chosen['known_bad']
        if obs.role == Role.CIVILIAN:
            calls = {}
            for message in obs.messages:
                if (message.day == obs.day and message.kind == 'accuse'
                        and message.context == 'day' and message.speaker in obs.alive):
                    calls[message.speaker] = message.target
            self.continuation_ballots.append(dict(
                day=obs.day, round='first' if candidates is None else 'pk',
                player=obs.player, target=target, original_target=original['target'],
                revised_target=revised['target'], original_reason=original['reason'],
                reason=chosen['reason'], eligible_calls=sorted(
                    (source, value) for source, value in calls.items() if value in chosen['legal']),
                formal_edges=revised.get('formal_edges', []),
                proposals=original['proposals'] if revised is not original else {},
            ))
        return target
