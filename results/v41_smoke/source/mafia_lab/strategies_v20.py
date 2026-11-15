"""Observer-local evidence routing and persistent private refutations.

No calibrated claim probabilities or numeric source credit in evidence mode.
Protocol choices among unresolved claims are policies, not logical theorems.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from .engine import Message, Role, speech_order
from .policies import teammates
from . import strategies_v19 as old

@dataclass(frozen=True)
class GoodPolicyV20(old.GoodPolicyV19):
    routing: str = 'evidence'
    remember: bool = True
    response_probability: str = '1/2'

    def __post_init__(self):
        super().__post_init__()
        if self.routing not in {'credit', 'evidence'}:
            raise ValueError('unknown information routing')
        if not 0 <= Fraction(self.response_probability) <= 1:
            raise ValueError('response probability outside [0,1]')
        if self.reply != 'keep' or self.survival_guard:
            raise ValueError('v20 supplies its own single-spokesperson response')

@dataclass(frozen=True)
class MafiaPolicyV20(old.MafiaPolicyV19):
    target_rule: str = 'near'

    def __post_init__(self):
        super().__post_init__()
        if self.response != 'forward' or self.target_rule not in {'near', 'far'}:
            raise ValueError('v20 fixes early bluff with near/far public target')

choose_inspection = old.choose_inspection
choose_kill = old.choose_kill
turn_extensions = old.turn_extensions
post_preferences = old.post_preferences
final_call = old.final_call
preference = old.preference
final_selection = old.final_selection


def public_claims(obs):
    return [m for m in obs.messages if m.kind in {'report', 'police'}]


def private_bad(obs, remember=True):
    """A private false-source fact; not authenticated for bystanders."""
    rows = public_claims(obs)
    if not remember:
        rows = [m for m in rows if m.day == obs.day]
    if obs.role == Role.POLICE:
        return ({r.target for r in obs.investigations if r.is_mafia}
                | {m.speaker for m in rows if m.speaker not in teammates(obs)})
    if obs.role == Role.CIVILIAN:
        return {m.speaker for m in rows if m.kind == 'report'
                and m.verdict and m.target == obs.player}
    return set()


def impossible_sources(obs, policy):
    bad = private_bad(obs, policy.remember)
    good = {obs.player}
    if obs.role == Role.POLICE:
        good |= teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
    reports = [m for m in obs.messages if m.kind == 'report']
    # Public self-accusation or contradictory checks cannot be genuine under
    # this experiment's truthful-police/no-civilian-impostor assumptions.
    seen = {}
    for m in reports:
        key = (m.speaker, m.target)
        if key in seen and seen[key] != m.verdict:
            bad.add(m.speaker)
        seen[key] = m.verdict
        if m.verdict and m.speaker == m.target:
            bad.add(m.speaker)
        if (policy.remember or m.day == obs.day) and m.verdict and m.target in good:
            bad.add(m.speaker)
    return bad


def _first_police(obs):
    team = teammates(obs)
    return next((p for p in speech_order(obs) if p in team), None)


def _prior_public_teammate(obs):
    team = teammates(obs)
    return any(m.speaker in team and m.day == 1 and m.context == 'day'
               and m.kind in {'report', 'police'} for m in obs.messages)


def optional_response(obs):
    """Only first living police's own ordinary turn can sample, once."""
    if obs.role != Role.POLICE or obs.day != 1 or obs.player != _first_police(obs):
        return False
    if obs.deaths[0].player in teammates(obs) or _prior_public_teammate(obs):
        return False
    threats = old.threats(obs)
    return bool(threats) and not any(
        m.kind == 'report' and m.verdict and m.target in teammates(obs)
        for m in threats)


def message(obs, policy, rng, context='day', override=None):
    if isinstance(policy, MafiaPolicyV20):
        if context == 'day' and obs.day == 1:
            order = list(speech_order(obs)); team = teammates(obs)
            first = next(p for p in order if p in team)
            if obs.player == first:
                future = [p for p in order[order.index(first)+1:] if p not in team]
                pool = future or [p for p in order if p not in team]
                if pool:
                    target = pool[0] if policy.target_rule == 'near' else pool[-1]
                    return Message(obs.player, 'report', target, True, 'day', obs.day)
        return old.old.v16.message(obs, policy, rng, context, override)
    if context == 'day' and obs.role == Role.POLICE and obs.day == 1:
        if optional_response(obs):
            q = Fraction(policy.response_probability)
            if rng.random() >= float(q):
                return Message(obs.player, 'pass', context='day', day=obs.day)
        threats = old.threats(obs)
        team = teammates(obs)
        if (obs.player == _first_police(obs) and not _prior_public_teammate(obs)
                and any(m.kind == 'report' and m.verdict and m.target in team for m in threats)):
            report = old.old.v16._latest_report(obs)
            if report is not None:
                return Message(obs.player, 'report', report.target, report.is_mafia, 'day', obs.day)
        # q never recruits a second officer. If the ordinary spokesperson is
        # accused, their own turn retains its truthful report with certainty.
        return old.old.message(obs, policy, rng, context, override)
    return old.old.message(obs, policy, rng, context, override)


def after_speech(obs, policy, rng):
    base = old.old.after_speech(obs, policy, rng)
    if not isinstance(policy, GoodPolicyV20):
        return base
    if obs.role == Role.POLICE and obs.day == 1:
        own_report = next((m for m in reversed(obs.messages)
                           if m.speaker == obs.player and m.day == 1
                           and m.context == 'day' and m.kind == 'report'), None)
        if own_report is not None:
            threats = old.threats(obs)
            if threats:
                denial = Message(obs.player, 'accuse', threats[-1].speaker,
                                 context='day', day=obs.day)
                return (base, denial) if base is not None and base.kind == 'shortlist' else denial
    if obs.role == Role.CIVILIAN:
        known = private_bad(obs, policy.remember).intersection(obs.alive)
        if known:
            target = next(p for p in speech_order(obs) if p in known)
            return Message(obs.player, 'nominate', target, context='day', day=obs.day)
    return base


def _rank_choice(obs, policy, pool):
    ranked, _ = old.old._rank(obs, policy)
    return next((p for p in ranked if p in pool), next(iter(pool), None))


def _recommendations(obs, source, pool):
    # Current same-source reroutes may legitimately supersede that source's
    # earlier suggestion. Historical hits remain useful if target is alive.
    calls = [m.target for m in obs.messages if m.speaker == source
             and m.day == obs.day and m.kind == 'accuse' and m.target in pool]
    if calls:
        return {calls[-1]}
    hits = [m.target for m in obs.messages if m.speaker == source
            and m.kind == 'report' and m.verdict and m.target in pool]
    if hits:
        return {hits[-1]}
    lists = [m for m in obs.messages if m.speaker == source
             and m.kind == 'shortlist' and m.day == obs.day]
    return set(lists[-1].targets).intersection(pool) if lists else set()


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


def vote(obs, policy, rng, candidates=None):
    if not isinstance(policy, GoodPolicyV20):
        return old.vote(obs, policy, rng, candidates)
    if policy.routing == 'credit':
        pool = [p for p in (obs.alive if candidates is None else candidates)
                if p in obs.alive and p != obs.player]
        known = private_bad(obs, True).intersection(pool) if policy.remember else set()
        if known:
            return _rank_choice(obs, policy, known)
        return old.vote(obs, policy, rng, candidates)
    return route(obs, policy, candidates)[0]
