"""Reconnect gold relays to the v29 receiver; frozen local mafia controls.

No role oracle, new credit weights, authenticated death, or new shared signal.
The new mafia choices use only own team and messages already observed.
"""
from dataclasses import dataclass
from . import strategies_v29 as base
from . import strategies_v28 as gold
from . import strategies_v20 as evidence
from .engine import Message, Role, speech_order
from .policies import teammates

GoodPolicyV30 = base.GoodPolicyV29

@dataclass(frozen=True)
class MafiaPolicyV30(base.MafiaPolicyV29):
    opening_control: str = 'old'
    def __post_init__(self):
        super().__post_init__()
        if self.opening_control not in {'old','copy','quiet','false_notice','false_grant'}:
            raise ValueError('unknown frozen opening control')

choose_inspection=base.choose_inspection
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
preference=base.preference
final_selection=base.final_selection
final_call=base.final_call
explain=base.explain
vote=base.vote


def choose_kill(obs, policy, rng):
    if obs.day==0 and policy.opening_control in {'false_notice','false_grant'}:
        return min(teammates(obs))
    return base.choose_kill(obs,policy,rng)


def dead_clear(obs):
    if not obs.deaths:return None
    victim=obs.deaths[0].player
    return next((m for m in obs.messages if m.speaker==victim and m.day==1
                 and m.context=='last_words' and m.kind=='report' and m.verdict is False),None)


def first_mafia(obs):
    return next((p for p in speech_order(obs) if p in teammates(obs)),None)


def copy_target(obs, clear):
    # Public far target excluding own team and the copied clear. A mafia actor
    # knows the target is nonmafia, not whether it is police or civilian.
    team=teammates(obs);order=list(speech_order(obs));index=order.index(obs.player)
    pool=[p for p in order[index+1:] if p not in team and p!=clear.target]
    pool=pool or [p for p in order if p not in team and p!=clear.target]
    return pool[-1] if pool else None


def false_gold(obs):
    return next((p for p in speech_order(obs) if p not in teammates(obs)),None)


def message(obs,policy,rng,context='day',override=None):
    if obs.role==Role.MAFIA:
        mode=policy.opening_control
        if obs.day==1 and context=='last_words' and mode in {'false_notice','false_grant'}:
            return Message(obs.player,'report',false_gold(obs),False,context,1)
        if obs.day==1 and context=='day':
            if mode in {'quiet','false_notice','false_grant'}:
                return Message(obs.player,'pass',context=context,day=1)
            clear=dead_clear(obs)
            if mode=='copy' and clear and obs.player==first_mafia(obs):
                return Message(obs.player,'report',clear.target,False,context,1)
    return base.message(obs,policy,rng,context,override)


def after_speech(obs,policy,rng):
    if obs.role==Role.MAFIA and obs.day==1:
        if policy.opening_control in {'quiet','false_notice','false_grant'}:return None
        clear=dead_clear(obs)
        if policy.opening_control=='copy' and clear and obs.player==first_mafia(obs):
            target=copy_target(obs,clear)
            return Message(obs.player,'accuse',target,context='day',day=1) if target is not None else None
    return base.after_speech(obs,policy,rng)


def after_last_words(obs,policy,rng):
    if obs.role==Role.MAFIA and obs.day==1 and policy.opening_control in {'false_notice','false_grant'}:
        recipient=false_gold(obs)
        pool=tuple(p for p in speech_order(obs) if p not in teammates(obs) and p!=recipient)[:2]
        parts=(Message(obs.player,'shortlist',context='last_words',day=1,targets=pool),)
        if policy.opening_control=='false_grant':
            parts+= (Message(obs.player,'delegate',recipient,context='last_words',day=1,targets=pool),)
        return parts
    return base.after_last_words(obs,policy,rng)
