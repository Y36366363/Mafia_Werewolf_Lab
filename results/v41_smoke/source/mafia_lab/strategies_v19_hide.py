"""Narrow v19b genuine concealment intervention, without changing credit."""
from dataclasses import dataclass
from . import strategies_v19 as base
from .engine import Message,Role
from .policies import teammates

@dataclass(frozen=True)
class GoodPolicyV19(base.GoodPolicyV19):
    conceal_wrong_hit: bool=False
MafiaPolicyV19=base.MafiaPolicyV19
choose_inspection=base.choose_inspection
choose_kill=base.choose_kill
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
final_call=base.final_call
preference=base.preference
final_selection=base.final_selection
after_speech=base.after_speech
vote=base.vote

def conceal(obs,policy):
    if obs.role!=Role.POLICE or obs.day!=1 or not policy.conceal_wrong_hit:return False
    team=teammates(obs)
    if any(m.day==1 and m.context=='day' and m.speaker in team and m.kind in {'police','report'} for m in obs.messages):return False
    threats=base.threats(obs)
    return bool(threats) and threats[-1].kind=='report' and threats[-1].verdict and threats[-1].target not in team

def message(obs,policy,rng,context='day',override=None):
    if isinstance(policy,GoodPolicyV19) and context=='day' and conceal(obs,policy):
        return Message(obs.player,'pass',context=context,day=obs.day)
    return base.message(obs,policy,rng,context,override)
