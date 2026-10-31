"""Explicit police execution calls, then an isolated provenance-conditioned vote pilot.

All decisions use Observation. Vote-history counts are weak within-pool ordering,
never identity probabilities or substitutes for private facts / singleton calls.
"""
from collections import Counter
from dataclasses import dataclass, replace
from . import strategies_v25 as base
from . import strategies_v20 as evidence
from .engine import Message, Role, speech_order
from .policies import teammates


@dataclass(frozen=True)
class GoodPolicyV26(base.GoodPolicyV25):
    execution_call: bool = False
    vote_history: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.vote_history and not self.execution_call:
            raise ValueError('history pilot follows explicit-call baseline')


@dataclass(frozen=True)
class MafiaPolicyV26(base.MafiaPolicyV25):
    vote_mode: str = 'team'

    def __post_init__(self):
        super().__post_init__()
        if self.vote_mode not in {'team', 'costless_bus'}:
            raise ValueError('unknown mafia ballot mode')


choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
final_call = base.final_call
preference = base.preference
final_selection = base.final_selection
message = base.message


def team_execution_call(obs):
    team = teammates(obs)
    return next((m for m in obs.messages if m.day == obs.day and m.context == 'day'
                 and m.kind == 'accuse' and m.speaker in team
                 and any(r.day == obs.day and r.context == 'day' and r.kind == 'report'
                         and r.speaker == m.speaker for r in obs.messages)), None)


def after_speech(obs, policy, rng):
    if (obs.role == Role.POLICE and isinstance(policy, GoodPolicyV26)
            and policy.execution_call and obs.day >= 2):
        own_report = any(m.speaker == obs.player and m.day == obs.day and m.context == 'day'
                         and m.kind == 'report' for m in obs.messages)
        if own_report:
            info = base.explain(obs, policy)
            if info['target'] in info['known_bad']:
                # Keep the original shortlist/extension and add an explicit execution
                # field in the existing ordinary speech slot. Extra content is
                # part of the tested protocol, not a zero-budget voting repair.
                original = base.after_speech(obs, policy, rng)
                call = Message(obs.player, 'accuse', info['target'], context='day', day=obs.day)
                parts = original if isinstance(original, tuple) else (original,)
                parts = tuple(m for m in parts if m is not None)
                return (*parts, call)
    return base.after_speech(obs, policy, rng)


def observation_before_ballot(obs, event, event_index):
    """Conservative public prefix, excluding post-exile last words and later checks."""
    day = event.day
    night_dead = {d.player for d in obs.deaths if d.day == day and d.cause == 'night'}
    messages = tuple(m for m in obs.messages if m.day < day or (m.day == day and (
        m.context == 'day' or (m.context == 'last_words' and m.speaker in night_dead)
        or (m.context == 'pk' and event.kind == 'pk_vote'))))
    deaths = tuple(d for d in obs.deaths if d.day < day or (d.day == day and d.cause == 'night'))
    dead = {d.player for d in deaths}
    return replace(obs, day=day, messages=messages, investigations=tuple(r for r in obs.investigations if r.day <= day),
                   alive=tuple(p for p in range(obs.rules.n_players) if p not in dead), deaths=deaths,
                   public_events=obs.public_events[:event_index], pending_pk=())


def vote_history_counts(obs, policy):
    """One signed count per voter/day, latest completed round supersedes first.

    +1: voted private-good; or supported a privately/publicly refuted source's
    current target with no unrefuted claimant recommending that same target.
    -1: voted private-bad. Abstentions / other targets: zero. No death labels.
    """
    last = {}
    for index, event in enumerate(obs.public_events):
        if event.kind in {'vote', 'pk_vote'}:
            last[event.day] = (index, event)
    scores = Counter(); details = []
    for day, (index, event) in sorted(last.items()):
        past = observation_before_ballot(obs, event, index)
        good = {obs.player}
        if obs.role == Role.POLICE:
            good |= teammates(obs) | {r.target for r in past.investigations if not r.is_mafia}
        bad = evidence.private_bad(past, True)
        refuted = evidence.impossible_sources(past, policy)
        sources = {m.speaker for m in evidence.public_claims(past)}
        calls = {}
        for m in past.messages:
            if m.day == day and (m.kind == 'accuse' or (m.kind == 'report' and m.verdict)):
                calls[m.speaker] = m.target
        for voter, target in event.ballots:
            value = 0; reason = 'uninformative_or_abstention'
            if target in bad:
                value, reason = -1, 'voted_private_bad'
            elif target in good:
                value, reason = 1, 'voted_private_good'
            elif target is not None:
                false_support = any(s in refuted and t == target for s, t in calls.items())
                alternate = any(s not in refuted and calls.get(s) == target for s in sources)
                if false_support and not alternate:
                    value, reason = 1, 'followed_refuted_source_without_other_claimant'
            scores[voter] += value
            if value:
                details.append(dict(day=day, round=event.kind, voter=voter, target=target,
                                    value=value, reason=reason))
    return dict(scores), details


def explain(obs, policy, candidates=None):
    info = base.explain(obs, policy, candidates)
    info = dict(info, call_target=None, followed_team_call=False, history_changed=False,
                history_pool=[], history_scores={}, history_evidence=[])
    if obs.day < 2:
        return info
    if obs.role == Role.POLICE and policy.execution_call:
        call = team_execution_call(obs)
        if call is not None:
            info['call_target'] = call.target
            if call.target in info['known_bad']:
                return dict(info, target=call.target, reason='private_bad_team_execution_call', followed_team_call=True)
    if not policy.vote_history or info['known_bad']:
        return info
    pool = [p for p in info['legal'] if p not in info['known_good']]
    guarded = evidence.old.constraints._clear_priority(obs, pool) if pool else []
    recs = {s: set(info['proposals'][str(s)]) for s in info['proposal_sources']}
    reason = info['reason']
    if reason in {'position_fallback', 'single_source_no_legal_proposal'}:
        choices = set(guarded)
    elif reason == 'compare_conflicting_sources':
        choices = set(info['conflict_targets'])
    elif reason == 'compatible_sources_protocol':
        choices = set.union(*recs.values()) if recs else set()
    elif reason == 'single_source_protocol':
        choices = next(iter(recs.values())) if len(recs) == 1 else set()
    elif reason == 'common_recommendation_protocol':
        choices = set.intersection(*recs.values()) if recs else set()
    else:
        choices = set()
    if len(choices) < 2:
        return info
    scores, facts = vote_history_counts(obs, policy)
    high = max(scores.get(p, 0) for p in choices)
    tied = [p for p in choices if scores.get(p, 0) == high]
    target = evidence._rank_choice(obs, policy, tied)
    return dict(info, target=target, history_changed=target != info['target'],
                history_pool=sorted(choices), history_scores=scores, history_evidence=facts)


def costless_bus_target(obs, policy, candidates=None):
    if obs.role != Role.MAFIA or policy.vote_mode != 'costless_bus':
        return None
    team = teammates(obs)
    last = next((p for p in reversed(speech_order(obs)) if p in team), None)
    if obs.player != last:
        return None
    kind = 'live_pk_vote' if candidates is not None else 'live_vote'
    published = {voter: target for e in obs.public_events if e.kind == kind and e.day == obs.day
                 for voter, target in e.ballots}
    # Before this vote, include own and all future votes in the worst-case bound.
    remaining = len(obs.alive) - len(published)
    counts = Counter(t for t in published.values() if t is not None)
    legal = [p for p in (obs.alive if candidates is None else candidates) if p != obs.player]
    for target in legal:
        if target not in team:
            continue
        rival = max((counts[p] for p in obs.alive if p != target), default=0)
        if counts[target] > rival + remaining:
            return target
    return None


def vote(obs, policy, rng, candidates=None):
    if obs.role == Role.MAFIA:
        target = costless_bus_target(obs, policy, candidates)
        return target if target is not None else base.vote(obs, policy, rng, candidates)
    return explain(obs, policy, candidates)['target']
