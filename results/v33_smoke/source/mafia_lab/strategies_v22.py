"""Separate persistent claim incompatibility from today's voting instruction.

Truth assumptions and all non-voting policies are inherited unchanged from v20b.
Repairs begin on day two, keeping the complete day-one trajectory identical.
"""
from dataclasses import dataclass
from . import strategies_v20b as legacy
from . import strategies_v20 as base
from .engine import Role
from .policies import teammates


@dataclass(frozen=True)
class GoodPolicyV22(base.GoodPolicyV20):
    live_conflicts_only: bool = True
    current_advice_only: bool = True

    def __post_init__(self):
        super().__post_init__()
        if self.routing != 'evidence' or not self.remember or self.response_probability != '1/2':
            raise ValueError('v22 fixes evidence routing, memory and q50')


MafiaPolicyV22 = base.MafiaPolicyV20
choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
final_call = base.final_call
preference = base.preference
final_selection = base.final_selection
message = base.message
after_speech = base.after_speech


def conflict_edges(obs, sources):
    """Observable incompatibilities, retained even after sources die."""
    reports = [m for m in obs.messages if m.kind == 'report' and m.speaker in sources]
    edges = set()
    for i, a in enumerate(reports):
        if a.verdict and a.target in sources and a.target != a.speaker:
            edges.add(tuple(sorted((a.speaker, a.target))))
        for b in reports[i+1:]:
            if a.speaker == b.speaker:
                continue
            shared = a.day == b.day == 1 and (a.target, a.verdict) != (b.target, b.verdict)
            contradictory = a.target == b.target and a.verdict != b.verdict
            if shared or contradictory:
                edges.add(tuple(sorted((a.speaker, b.speaker))))
    return sorted(edges)


def current_recommendations(obs, source, pool):
    """Today's repeat or new proposal, including today's unverified last words.

    Reading history is unrestricted; the date filter changes action eligibility,
    not the public history, source identity, or private remembered facts.
    """
    rows = [m for m in obs.messages if m.speaker == source and m.day == obs.day]
    calls = [m.target for m in rows if m.kind == 'accuse' and m.target in pool]
    if calls:
        return {calls[-1]}
    hits = [m.target for m in rows if m.kind == 'report' and m.verdict and m.target in pool]
    if hits:
        return {hits[-1]}
    lists = [m for m in rows if m.kind == 'shortlist']
    return set(lists[-1].targets).intersection(pool) if lists else set()


def explain(obs, policy, candidates=None):
    legal = [p for p in (obs.alive if candidates is None else candidates)
             if p in obs.alive and p != obs.player]
    known_good = {obs.player}
    if obs.role == Role.POLICE:
        known_good |= teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
    pool = [p for p in legal if p not in known_good]
    known_bad = base.private_bad(obs, True).intersection(pool)
    sources = sorted({m.speaker for m in base.public_claims(obs)} - base.impossible_sources(obs, policy))
    edges = conflict_edges(obs, sources)
    repair_live = obs.day >= 2 and policy.live_conflicts_only
    repair_advice = obs.day >= 2 and policy.current_advice_only
    active_edges = [e for e in edges if not repair_live or all(p in obs.alive for p in e)]
    # Public clear-order guard is unchanged. It does not supersede private facts.
    guarded = base.old.constraints._clear_priority(obs, pool) if pool else []
    recommendations = current_recommendations if repair_advice else base._recommendations
    recs = {s: recommendations(obs, s, guarded) for s in sources}
    proposal_sources = [s for s in sources if recs[s]] if repair_advice else sources
    live_targets = [p for p in guarded if any(p in edge for edge in active_edges)]
    details = dict(legal=legal,known_good=sorted(known_good.intersection(obs.alive)),
                   known_bad=sorted(known_bad),sources=sources,history_edges=edges,
                   active_edges=active_edges,conflict_targets=live_targets,
                   proposals={str(s): sorted(recs[s]) for s in sources},
                   proposal_sources=proposal_sources)

    def result(target, reason):
        return dict(details, target=target, reason=reason)

    if obs.day == 1 or not (repair_live or repair_advice):
        target, reason = legacy.route(obs, policy, candidates)
        return result(target, reason)
    if not legal:
        return result(None, 'no_legal_candidate')
    if not pool:
        return result(None, 'private_good_only')
    if known_bad:
        return result(base._rank_choice(obs, policy, known_bad), 'private_refutation_or_check')
    if not sources:
        return result(base._rank_choice(obs, policy, guarded), 'position_fallback')
    if len(proposal_sources) == 1:
        proposals = recs[proposal_sources[0]]
        if proposals:
            return result(base._rank_choice(obs, policy, proposals), 'single_source_protocol')
        return result(base._rank_choice(obs, policy, guarded), 'single_source_no_legal_proposal')
    common = set.intersection(*(recs[s] for s in proposal_sources)) if proposal_sources else set()
    if common:
        return result(base._rank_choice(obs, policy, common), 'common_recommendation_protocol')
    if live_targets:
        return result(base._rank_choice(obs, policy, live_targets), 'compare_conflicting_sources')
    union = set.union(*(recs[s] for s in proposal_sources)) if proposal_sources else set()
    if union:
        return result(base._rank_choice(obs, policy, union), 'compatible_sources_protocol')
    return result(base._rank_choice(obs, policy, guarded), 'position_fallback')


def route(obs, policy, candidates=None):
    details = explain(obs, policy, candidates)
    return details['target'], details['reason']


def vote(obs, policy, rng, candidates=None):
    if not isinstance(policy, GoodPolicyV22):
        return base.vote(obs, policy, rng, candidates)
    return route(obs, policy, candidates)[0]
