"""Targeted v18 diagnostic: forward accusation and information-preserving reply."""
from dataclasses import replace
from .engine import Message,Role,speech_order
from .policies import teammates
from . import strategies_v18 as base

GoodPolicyV18=base.GoodPolicyV18
MafiaPolicyV18=base.MafiaPolicyV18
choose_inspection=base.choose_inspection
choose_kill=base.choose_kill
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
final_call=base.final_call
preference=base.preference
final_selection=base.final_selection
vote=base.vote

def message(obs,policy,rng,context='day',override=None):
    if context=='day' and isinstance(policy,GoodPolicyV18):
        threat=base.response_target(obs,policy)
        if threat is not None:
            record=base.v17.v16._latest_report(obs)
            if record is not None:
                return Message(obs.player,'report',record.target,record.is_mafia,'day',obs.day)
    if context=='day' and isinstance(policy,MafiaPolicyV18) and policy.response=='early':
        order=list(speech_order(obs));allies=teammates(obs)
        first=next(p for p in order if p in allies)
        if obs.player==first:
            future=[p for p in order[order.index(first)+1:] if p not in allies]
            pool=future or [p for p in order if p not in allies]
            if pool:
                return Message(obs.player,'report',pool[0],True,'day',obs.day)
    return base.message(obs,policy,rng,context,override)

def after_speech(obs,policy,rng):
    if isinstance(policy,GoodPolicyV18) and obs.role==Role.POLICE:
        index=next((i for i in range(len(obs.messages)-1,-1,-1)
                    if obs.messages[i].speaker==obs.player
                    and obs.messages[i].context=='day' and obs.messages[i].day==obs.day),None)
        if index is not None:
            before=replace(obs,messages=obs.messages[:index])
            target=base.response_target(before,policy)
            if target is not None:
                return Message(obs.player,'accuse',target,context='day',day=obs.day)
    return base.after_speech(obs,policy,rng)
