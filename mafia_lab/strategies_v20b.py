"""v20b: add the omitted shared first-night inspection consistency constraint.

Frozen after reviewing v20; separate new-seed mechanism probe, no q retuning.
"""
from . import strategies_v20 as base
from .strategies_v20 import (Role,teammates,old,private_bad,impossible_sources,
    public_claims,_rank_choice,_recommendations)
GoodPolicyV20=base.GoodPolicyV20
MafiaPolicyV20=base.MafiaPolicyV20
choose_inspection=base.choose_inspection
choose_kill=base.choose_kill
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
final_call=base.final_call
preference=base.preference
final_selection=base.final_selection
message=base.message
after_speech=base.after_speech

def route(obs, policy, candidates=None):
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None, 'no_legal_candidate'
    known_good = {obs.player}
    if obs.role == Role.POLICE:
        known_good |= teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
        pool = [p for p in pool if p not in known_good]
    if not pool:
        return None, 'private_good_only'
    known_bad = private_bad(obs, policy.remember).intersection(pool)
    if known_bad:
        return _rank_choice(obs, policy, known_bad), 'private_refutation_or_check'
    pool = old.constraints._clear_priority(obs, pool)
    bad = impossible_sources(obs, policy)
    sources = sorted({m.speaker for m in public_claims(obs)} - bad)
    if not sources:
        return _rank_choice(obs, policy, pool), 'position_fallback'
    recs = {s: _recommendations(obs, s, pool) for s in sources}
    if len(sources) == 1:
        if recs[sources[0]]:
            return _rank_choice(obs, policy, recs[sources[0]]), 'single_source_protocol'
        return _rank_choice(obs, policy, pool), 'single_source_no_legal_proposal'
    # Incompatible claimants cannot both be genuine; this does NOT prove
    # either is genuine. Resolve among live conflicting sources, not latest.
    reports = [m for m in obs.messages if m.kind == 'report' and m.speaker in sources]
    conflicts = set()
    for i, a in enumerate(reports):
        if a.verdict and a.target in sources and a.target != a.speaker:
            conflicts.update((a.speaker, a.target))
        for b in reports[i+1:]:
            # This first-night-only check assumes one shared real inspection
            # and truthful reporting of that actual result, not teammate cover.
            if (a.speaker != b.speaker and a.day == b.day == 1
                    and (a.target, a.verdict) != (b.target, b.verdict)):
                conflicts.update((a.speaker, b.speaker))
            if a.speaker != b.speaker and a.target == b.target and a.verdict != b.verdict:
                conflicts.update((a.speaker, b.speaker))
    common = set.intersection(*(recs[s] for s in sources))
    if common:
        return _rank_choice(obs, policy, common), 'common_recommendation_protocol'
    live_conflicts = [p for p in pool if p in conflicts]
    if live_conflicts:
        return _rank_choice(obs, policy, live_conflicts), 'compare_conflicting_sources'
    union = set.union(*(recs[s] for s in sources))
    if union:
        return _rank_choice(obs, policy, union), 'compatible_sources_protocol'
    return _rank_choice(obs, policy, pool), 'position_fallback'


def vote(obs,policy,rng,candidates=None):
    if not isinstance(policy,GoodPolicyV20) or policy.routing=='credit':
        return base.vote(obs,policy,rng,candidates)
    return route(obs,policy,candidates)[0]
