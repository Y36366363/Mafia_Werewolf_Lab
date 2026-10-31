"""Surviving day-one false claimant can restate its old target at its own turn.

No fabricated new check, new target, extra turn, or referee identity access.
The v22 continuation repair stays frozen; only its local response q is reopened.
"""
from dataclasses import dataclass
from . import strategies_v20 as base
from . import strategies_v22 as repaired
from .engine import Message,Role


@dataclass(frozen=True)
class GoodPolicyV23(base.GoodPolicyV20):
    live_conflicts_only: bool = True
    current_advice_only: bool = True

    def __post_init__(self):
        super().__post_init__()
        if self.routing!='evidence' or not self.remember:
            raise ValueError('v23 fixes evidence routing and private memory')


@dataclass(frozen=True)
class MafiaPolicyV23(base.MafiaPolicyV20):
    restate: bool = False


choose_inspection=base.choose_inspection
choose_kill=base.choose_kill
turn_extensions=base.turn_extensions
post_preferences=base.post_preferences
final_call=base.final_call
preference=base.preference
final_selection=base.final_selection
message=base.message
explain=repaired.explain
route=repaired.route


def restatement_target(obs,policy):
    if obs.role!=Role.MAFIA or not isinstance(policy,MafiaPolicyV23) or not policy.restate or obs.day<2:
        return None
    original=next((m for m in obs.messages if m.day==1 and m.context=='day'
                   and m.kind=='report' and m.verdict and m.speaker==obs.player),None)
    if original is not None and original.target in obs.alive:
        return original.target
    return None


def after_speech(obs,policy,rng):
    target=restatement_target(obs,policy)
    if target is not None:
        return Message(obs.player,'accuse',target,context='day',day=obs.day)
    return base.after_speech(obs,policy,rng)


def vote(obs,policy,rng,candidates=None):
    if isinstance(policy,GoodPolicyV23):
        return route(obs,policy,candidates)[0]
    return base.vote(obs,policy,rng,candidates)
