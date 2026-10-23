"""v18 one available police response and truthful-good claim constraints.

Civilian claim reasoning counts uniformly dealt role assignments satisfying
truthful real police and no civilian police impersonation. It is a reference
belief model, not a calibrated posterior of strategic statement likelihoods.
"""
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, chain
from math import comb
from fractions import Fraction
from .engine import Role, Message, speech_order
from .policies import teammates
from . import strategies_v17 as v17

@dataclass(frozen=True)
class GoodPolicyV18(v17.GoodPolicyV17):
    response_rule: str = 'keep'
    claim_model: str = 'fixed'
    def __post_init__(self):
        super().__post_init__()
        if self.response_rule not in {'keep','answer','self'}:
            raise ValueError('invalid response rule')
        if self.claim_model not in {'fixed','logical'}:
            raise ValueError('invalid claim model')

@dataclass(frozen=True)
class MafiaPolicyV18(v17.MafiaPolicyV17):
    def __post_init__(self):
        v17.v16.MafiaPolicyV16.__post_init__(self)
        if self.response not in {'quiet','counter','early'}:
            raise ValueError('invalid mafia response')
choose_inspection=v17.choose_inspection
choose_kill=v17.choose_kill
turn_extensions=v17.turn_extensions
post_preferences=v17.post_preferences
final_call=v17.final_call
preference=v17.preference
final_selection=v17.final_selection


def _false_claims(obs):
    allies=teammates(obs)
    return [m for m in obs.messages if m.day==obs.day and m.context=='day'
            and m.kind in {'report','police'} and m.speaker not in allies]


def response_target(obs, policy):
    if obs.role!=Role.POLICE or policy.response_rule=='keep':
        return None
    rows=_false_claims(obs)
    if policy.response_rule=='self':
        rows=[m for m in rows if m.kind=='report' and m.verdict and m.target==obs.player]
    if not rows:
        return None
    threat=rows[-1]
    # One responder per visible outsider claim episode; no hidden collective
    # out-of-turn response. Only statements already seen by this actor count.
    index=max(i for i,m in enumerate(obs.messages) if m is threat)
    if any(m.speaker in teammates(obs) and m.kind in {'police','report'}
           and m.context=='day' for m in obs.messages[index+1:]):
        return None
    return threat.speaker


def message(obs, policy, rng, context='day', override=None):
    if isinstance(policy,GoodPolicyV18) and context=='day':
        target=response_target(obs,policy)
        if target is not None:
            # A role counterclaim is distinct from a fabricated inspection.
            return Message(obs.player,'police',context='day',day=obs.day)
    if isinstance(policy,MafiaPolicyV18) and policy.response=='early' and context=='day':
        first=next(p for p in speech_order(obs) if p in teammates(obs))
        if obs.player==first:
            pool=[p for p in speech_order(obs) if p not in teammates(obs)]
            if pool:
                return Message(obs.player,'report',pool[0],True,'day',obs.day)
    return v17.message(obs,policy,rng,context,override)


def after_speech(obs,policy,rng):
    if isinstance(policy,GoodPolicyV18) and obs.role==Role.POLICE:
        own=next((m for m in reversed(obs.messages) if m.speaker==obs.player
                  and m.day==obs.day and m.context=='day'),None)
        if own is not None and own.kind=='police':
            threats=_false_claims(obs)
            if threats:
                return Message(obs.player,'accuse',threats[-1].speaker,
                               context='day',day=obs.day)
    return v17.after_speech(obs,policy,rng)


def public_constraints(obs):
    claims=set()
    reports=set()
    for m in obs.messages:
        if m.kind in {'report','police'}:
            claims.add(m.speaker)
        if m.kind=='report':
            reports.add((m.speaker,m.target,bool(m.verdict)))
    return tuple(sorted(claims)),tuple(sorted(reports))


def _choose(n,k):
    return comb(n,k) if n>=0 and 0<=k<=n else 0


@lru_cache(maxsize=100000)
def _claim_marginals(n, mafia_count, police_count, civilian, claims, reports):
    involved=tuple(sorted({civilian,*claims,*[t for _,t,_ in reports]}))
    total=0
    numerators=[0]*n
    uninvolved=n-len(involved)
    possible=[p for p in involved if p!=civilian]
    subsets=chain.from_iterable(combinations(possible,k)
        for k in range(max(0,mafia_count-uninvolved),min(mafia_count,len(possible))+1))
    for seats in subsets:
        mafia=set(seats)
        if civilian in mafia:
            continue
        true_claimants=set(claims)-mafia
        if civilian in true_claimants or len(true_claimants)>police_count:
            continue
        if any((t in mafia)!=verdict for source,t,verdict in reports
               if source in true_claimants):
            continue
        remaining=mafia_count-len(mafia)
        mafia_ways=_choose(uninvolved,remaining)
        # Genuine claimants are police, observing civilian cannot be police.
        police_ways=_choose(n-mafia_count-len(true_claimants)-1,
                            police_count-len(true_claimants))
        weight=mafia_ways*police_ways
        if not weight:
            continue
        total+=weight
        for p in mafia:
            numerators[p]+=weight
        if uninvolved:
            each=_choose(uninvolved-1,remaining-1)*police_ways
            for p in range(n):
                if p not in involved:
                    numerators[p]+=each
    if not total:
        raise ValueError('truthful-good declaration model inconsistent with observation')
    return tuple(Fraction(x,total) for x in numerators)


def claim_scores(obs):
    claims,reports=public_constraints(obs)
    return _claim_marginals(obs.rules.n_players,obs.rules.mafia,obs.rules.police,
                            obs.player,claims,reports)


def _clear_priority(obs, candidates):
    # A -> B means protect B until source A is considered first. Do not let
    # cycles of fabricated mutual clears eliminate all legal vote candidates.
    edges={(s,t) for s,t,v in public_constraints(obs)[1]
           if not v and s!=t and s in candidates and t in candidates}
    def reachable(start,goal):
        seen=set();stack=[start]
        while stack:
            p=stack.pop()
            if p==goal:return True
            if p in seen:continue
            seen.add(p);stack.extend(t for s,t in edges if s==p)
        return False
    protected={t for s,t in edges if not reachable(t,s)}
    return [p for p in candidates if p not in protected] or candidates


def vote(obs,policy,rng,candidates=None):
    if isinstance(policy,GoodPolicyV18):
        pool=[p for p in (obs.alive if candidates is None else candidates)
              if p in obs.alive and p!=obs.player]
        if not pool:return None
        if obs.role==Role.POLICE:
            hits=[r.target for r in obs.investigations if r.is_mafia and r.target in pool]
            if hits:return hits[-1]
            # Genuine available responders oppose the visible false claimant;
            # prior to responding, retain exactly the same baseline vote.
            own_counter=any(m.speaker==obs.player and m.kind=='police'
                            and m.day==obs.day and m.context=='day' for m in obs.messages)
            if own_counter:
                threats=[m.speaker for m in _false_claims(obs) if m.speaker in pool]
                if threats:return threats[-1]
        elif policy.claim_model=='logical':
            claims,reports=public_constraints(obs)
            if claims:
                risk=claim_scores(obs)
                # Keep the existing shortlist/private ranking as tie-break,
                # never let "latest speaker" override a higher logical risk.
                ranked,_=v17._rank(obs,policy)
                shortlist=v17._shortlist(obs)
                rank={p:i for i,p in enumerate(ranked)}
                pool=_clear_priority(obs,pool)
                return max(pool,key=lambda p:(risk[p],
                    int(shortlist is not None and p in shortlist.targets),
                    -rank.get(p,len(ranked))))
    return v17.vote(obs,policy,rng,candidates)
