"""Dead-source gold delegation, evidence-conditioned rerouting, no authentication.

All four variants retain v27 ordinary live-gold relays. New day-one authority
is scoped to a first-night victim's public last-words clear and grant. A false
source is still possible: delegation transfers advice, never a role certificate.
"""
from dataclasses import dataclass, replace
from . import strategies_v27 as base
from . import strategies_v16 as positions
from . import strategies_v20 as evidence
from .engine import Message, Role


@dataclass(frozen=True)
class GoodPolicyV28(base.GoodPolicyV27):
    dead_gold: str = 'reference'

    def __post_init__(self):
        super().__post_init__()
        if self.dead_gold not in {'reference','notice','list','evidence'}:
            raise ValueError('unknown dead-gold protocol')
        if self.relay_mode != 'local':
            raise ValueError('retain existing live-gold local relay in every variant')


MafiaPolicyV28 = base.MafiaPolicyV27
choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
preference = base.preference
final_selection = base.final_selection
message = base.message
after_speech = base.after_speech


def after_last_words(obs, policy, rng):
    if (obs.role != Role.POLICE or policy.dead_gold == 'reference' or obs.day != 1
            or not obs.deaths or obs.deaths[0].cause != 'night'
            or obs.player != obs.deaths[0].player):
        return None
    report = next((m for m in reversed(obs.messages) if m.speaker == obs.player
        and m.kind == 'report' and m.context == 'last_words' and m.day == 1), None)
    if report is None or report.verdict or report.target not in obs.alive:
        return None
    ranked, scores = positions._ranked_candidates(obs, policy)
    pool = tuple(ranked[:positions._list_size(policy, ranked, scores)])
    if not pool or report.target in pool:
        return None
    return (Message(obs.player,'shortlist',context='last_words',day=1,targets=pool),
            Message(obs.player,'delegate',report.target,context='last_words',day=1,targets=pool))


def dead_offers(obs, policy):
    if obs.day != 1 or not obs.deaths or obs.deaths[0].cause != 'night':
        return []
    origin = obs.deaths[0].player
    bad = evidence.impossible_sources(obs,policy)
    if origin in bad:
        return []
    offers=[]
    for i,m in enumerate(obs.messages):
        if (m.kind != 'delegate' or m.speaker != origin or m.day != 1
                or m.context != 'last_words' or m.target not in obs.alive):
            continue
        clear = any(r.speaker == origin and r.kind == 'report' and r.verdict is False
                    and r.target == m.target and r.context == 'last_words' and r.day == 1
                    for r in obs.messages[:i])
        if clear:offers.append((i,m))
    return offers if len(offers)==1 else []


def reroute_witnesses(obs, offer):
    """Public reasons, with conditional and unconditional logic kept distinct.

    A different first-night result conflicts with the origin's shared check
    ONLY IF the origin is genuine. It does not prove the rival mafia outright.
    A self-hit or inconsistent own report is intrinsically false under the
    truthful-police/no-civilian-impostor restricted candidate assumptions.
    """
    seen={}; witnesses={}
    for i,m in enumerate(obs.messages):
        if m.kind!='report' or m.speaker not in obs.alive or m.speaker==offer.target:
            continue
        key=(m.speaker,m.target)
        if m.verdict and m.speaker==m.target:
            witnesses[m.speaker]=dict(reason='public_self_hit',index=i,conditional=False)
        elif key in seen and seen[key]!=m.verdict:
            witnesses[m.speaker]=dict(reason='same_source_contradiction',index=i,conditional=False)
        elif (m.day==1 and m.context=='day' and m.speaker!=offer.speaker
                and (m.target,m.verdict)!=(offer.target,False)):
            witnesses.setdefault(m.speaker,dict(reason='shared_check_conflict_if_origin_true',
                                                index=i,conditional=True))
        seen[key]=m.verdict
    return witnesses


def gold_final_decision(obs,policy):
    if obs.role!=Role.CIVILIAN or policy.dead_gold not in {'list','evidence'}:
        return None
    offers=dead_offers(obs,policy)
    if len(offers)!=1 or offers[0][1].target!=obs.player:
        return None
    _,offer=offers[0]
    live=[p for p in offer.targets if p in obs.alive and p!=obs.player]
    known=evidence.private_bad(obs,policy.remember).intersection(obs.alive)
    witnesses=reroute_witnesses(obs,offer)
    if policy.dead_gold=='evidence' and witnesses:
        # Prefer genuinely public logical contradictions to conditional shared-
        # check conflicts. This is a discrete protocol priority, not a score.
        hard=[p for p,w in witnesses.items() if not w['conditional']]
        target=evidence._rank_choice(obs,policy,hard or list(witnesses))
    else:
        if not live or (known and not known.intersection(live)):
            return None
        target=base.explain(obs,policy,live)['target']
    if target is None:return None
    return Message(obs.player,'relay',target,context='day',day=1,targets=(offer.speaker,))


def final_call(obs,policy,rng):
    if obs.role!=Role.MAFIA:
        call=gold_final_decision(obs,policy)
        if call is not None:return call
    return base.final_call(obs,policy,rng)


def admitted_dead_relays(obs,policy):
    if policy.dead_gold not in {'list','evidence'}:return []
    accepted=[]
    for i,offer in dead_offers(obs,policy):
        for j,r in enumerate(obs.messages[i+1:],i+1):
            if (r.kind!='relay' or r.day!=1 or r.context!='day' or r.speaker!=offer.target
                    or r.targets!=(offer.speaker,) or r.target not in obs.alive):continue
            # Check the witness at the actual relay prefix, not later speech.
            prefix=replace(obs,messages=obs.messages[:j])
            within=r.target in offer.targets
            witness=reroute_witnesses(prefix,offer).get(r.target)
            if within or (policy.dead_gold=='evidence' and witness):
                accepted.append((offer,r,witness))
    return accepted


def explain(obs,policy,candidates=None):
    info=base.explain(obs,policy,candidates)
    info=dict(info,dead_relay_admitted=0,dead_relay_changed=False,dead_relay_outside=False,
              dead_relay_target=None,dead_relay_conditional=False)
    if policy.dead_gold=='reference' or obs.day!=1:return info
    relays=admitted_dead_relays(obs,policy)
    if not relays:return info
    # Interpretation of a delegated proposal, not fabricated new speech or a
    # new police identity. Conflicting other sources and private facts remain.
    virtual=tuple(Message(a.speaker,'accuse',r.target,context='day',day=1) for a,r,w in relays)
    updated=base.explain(replace(obs,messages=obs.messages+virtual),policy,candidates)
    a,r,w=relays[-1]
    return dict(updated,dead_relay_admitted=len(relays),dead_relay_changed=updated['target']!=info['target'],
                dead_relay_outside=r.target not in a.targets,dead_relay_target=r.target,
                dead_relay_conditional=bool(w and w['conditional']))


def vote(obs,policy,rng,candidates=None):
    if obs.role==Role.MAFIA:return base.vote(obs,policy,rng,candidates)
    return explain(obs,policy,candidates)['target']
