"""Day-one unresolved conflicts without grant-triggered source conviction.

Conflict is evidence of incompatibility, not a mandate against its surviving
endpoint. All choices consume only the acting player's Observation.
"""
from dataclasses import dataclass,replace
from . import strategies_v30 as base
from . import strategies_v28 as gold
from . import strategies_v29 as semantics
from . import strategies_v20 as evidence
from . import strategies_v26 as execution
from .engine import Message,Role
from .policies import teammates

@dataclass(frozen=True)
class GoodPolicyV31(base.GoodPolicyV30):
    neutral_conflicts: bool = False
    align_intent: bool = False
    def __post_init__(self):
        super().__post_init__()
        if self.align_intent and not self.neutral_conflicts:
            raise ValueError('intent pilot requires the neutral receiver')
        if self.dead_gold!='evidence' or not self.conflict_guard or not self.typed_advice:
            raise ValueError('retain v30 evidence_guard control')

MafiaPolicyV31=base.MafiaPolicyV30
choose_inspection=base.choose_inspection
choose_kill=base.choose_kill
message=base.message
after_last_words=base.after_last_words
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
preference=base.preference
final_selection=base.final_selection


def accepted_relays(obs,policy):
    # Same public offer validation as v28, with explicit full live-target
    # delegation scope for both repaired rows. No authenticity claim.
    accepted=[]
    for i,offer in gold.dead_offers(obs,policy):
        for r in obs.messages[i+1:]:
            if (r.kind=='relay' and r.day==1 and r.context=='day' and r.speaker==offer.target
                    and r.targets==(offer.speaker,) and r.target in obs.alive
                    and r.target!=r.speaker):
                accepted.append((offer,r))
    return accepted


def explain(obs,policy,candidates=None):
    old=base.explain(obs,policy,candidates)
    info=dict(old,neutral_scope=False,orphan_not_actionable=False,live_edges=[],
              intent_team_applicable=False,intent_team_mismatch=False)
    if not policy.neutral_conflicts or obs.day!=1:return info
    # Start from the pre-v29 public proposal extraction, independent of whether
    # the victim appended a grant. Reconstruct relays as source replacements.
    # For one's own intent, do not let one's newly posted relay validate itself.
    accepted=[(a,r) for a,r in accepted_relays(obs,policy) if r.speaker!=obs.player or not policy.align_intent]
    virtual=tuple(Message(a.speaker,'accuse',r.target,context='day',day=1) for a,r in accepted)
    prepared=replace(obs,messages=obs.messages+virtual)
    v=gold.base.explain(prepared,policy,candidates)
    info=dict(v,receiver_scope=True,receiver_changed=False,proposal_kinds={},common_targets=[],
        contributors_conflict=False,blocked_by_type=False,blocked_by_conflict=False,early_common_accepted=False,
        dead_relay_admitted=len(accepted),dead_relay_changed=False,dead_relay_outside=False,
        dead_relay_target=accepted[-1][1].target if accepted else None,dead_relay_conditional=False,
        neutral_scope=True,orphan_not_actionable=False,live_edges=[],intent_team_applicable=False,intent_team_mismatch=False)
    if not v['legal']:return info
    if v['known_bad']:
        # One public police spokesperson's explicit call coordinates the team;
        # only if the target is already privately known bad AND ballot-legal.
        call=execution.team_execution_call(obs) if policy.align_intent and obs.role==Role.POLICE else None
        if call is not None and call.target in v['known_bad']:
            return dict(info,target=call.target,reason='private_bad_team_execution_call',intent_team_applicable=True)
        return info
    pool=[p for p in v['legal'] if p not in v['known_good']]
    if not pool:return info
    pool=evidence.old.constraints._clear_priority(obs,pool)
    sources=v['sources'];recs={s:set(v['proposals'].get(str(s),())).intersection(pool) for s in sources}
    kinds={s:semantics.statement_kind(prepared,policy,s,recs[s]) for s in sources}
    edges=v['history_edges'];live=[e for e in edges if all(p in obs.alive for p in e)]
    conflicts=any(a in sources and b in sources for a,b in edges)
    common=set.intersection(*(recs[s] for s in sources)) if sources else set()
    explicit=bool(sources) and all(k in {'execution','claimed_hit'} for k in kinds.values())
    live_targets=[p for p in pool if any(p in e for e in live)]
    info.update(proposal_kinds={str(s):k for s,k in kinds.items()},common_targets=sorted(common),
        contributors_conflict=conflicts,blocked_by_type=bool(common and not explicit),
        blocked_by_conflict=bool(common and conflicts),live_edges=live,
        orphan_not_actionable=bool(edges and not live),conflict_targets=live_targets,active_edges=live)
    def choose(choices,reason,early=False):
        target=evidence._rank_choice(obs,policy,choices)
        return dict(info,target=target,reason=reason,receiver_changed=target!=old['target'],early_common_accepted=early)
    if not sources:return choose(pool,'position_fallback')
    if len(sources)==1:return choose(recs[sources[0]] or pool,'single_source_protocol')
    if common and explicit and not conflicts:return choose(common,'explicit_common_protocol',True)
    if live_targets:return choose(live_targets,'compare_live_conflicting_sources')
    if common and not conflicts:return choose(common,'soft_overlap_fallback')
    union=set.union(*(recs[s] for s in sources)) if sources else set()
    return choose(union or pool,'unresolved_conflict_proposals' if conflicts else 'compatible_sources_protocol')


def after_speech(obs,policy,rng):
    original=base.after_speech(obs,policy,rng)
    if (obs.role!=Role.POLICE or not policy.align_intent or obs.day!=1 or not any(
            m.speaker==obs.player and m.kind=='report' and m.day==1 and m.context=='day' for m in obs.messages)):
        return original
    v=explain(obs,policy);parts=original if isinstance(original,tuple) else (original,)
    parts=tuple(m for m in parts if m is not None and m.kind!='accuse')
    if v['target'] in v['known_bad']:
        parts+=(Message(obs.player,'accuse',v['target'],context='day',day=1),)
    return parts or None


def final_call(obs,policy,rng):
    if obs.role==Role.CIVILIAN and obs.day==1 and policy.align_intent:
        offers=gold.dead_offers(obs,policy)
        if len(offers)==1 and offers[0][1].target==obs.player:
            target=explain(obs,policy)['target']
            if target is not None:return Message(obs.player,'relay',target,context='day',day=1,targets=(offers[0][1].speaker,))
    return base.final_call(obs,policy,rng)


def vote(obs,policy,rng,candidates=None):
    return base.vote(obs,policy,rng,candidates) if obs.role==Role.MAFIA else explain(obs,policy,candidates)['target']
