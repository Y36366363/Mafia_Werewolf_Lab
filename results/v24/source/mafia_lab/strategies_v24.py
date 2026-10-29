"""A surviving teammate can support an old target or openly take over the claim.

No new investigation is asserted. Support and claim use the same accusation
channel and ordinary-turn budget; only claim changes the speaker's own status.
"""
from dataclasses import dataclass
from . import strategies_v23 as base
from .engine import Message, Role, speech_order
from .policies import teammates

GoodPolicyV24 = base.GoodPolicyV23


@dataclass(frozen=True)
class MafiaPolicyV24(base.MafiaPolicyV23):
    succession: str = 'none'

    def __post_init__(self):
        super().__post_init__()
        if self.succession not in {'none', 'support', 'claim'}:
            raise ValueError('unknown succession mode')
        if self.succession != 'none' and not self.restate:
            raise ValueError('succession modes retain the surviving-origin response')


choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
final_call = base.final_call
preference = base.preference
final_selection = base.final_selection
explain = base.explain
route = base.route
vote = base.vote


def succession_opportunity(obs):
    """A shadow eligibility test also usable in the unchanged control world.

    Role knowledge is only this mafia actor's own team. The old target must
    still be alive; the original claimant must be dead, not merely quiet.
    """
    if obs.role != Role.MAFIA or obs.day < 2:
        return None
    team = teammates(obs)
    original = next((m for m in obs.messages if m.day == 1 and m.context == 'day'
                     and m.kind == 'report' and m.verdict and m.speaker in team), None)
    if original is None or original.speaker in obs.alive or original.target not in obs.alive:
        return None
    first = next((p for p in speech_order(obs) if p in team), None)
    if obs.player != first:
        return None
    if any(m.speaker == obs.player and m.day == obs.day and m.context == 'day'
           and m.kind == 'accuse' and m.target == original.target for m in obs.messages):
        return None
    return dict(origin=original.speaker, target=original.target, speaker=obs.player)


def succession_event(obs, policy):
    if not isinstance(policy, MafiaPolicyV24) or policy.succession == 'none':
        return None
    return succession_opportunity(obs)


def message(obs, policy, rng, context='day', override=None):
    event = succession_event(obs, policy) if context == 'day' else None
    if event is not None and policy.succession == 'claim':
        return Message(obs.player, 'police', context='day', day=obs.day)
    return base.message(obs, policy, rng, context, override)


def after_speech(obs, policy, rng):
    event = succession_event(obs, policy)
    if event is not None:
        return Message(obs.player, 'accuse', event['target'], context='day', day=obs.day)
    return base.after_speech(obs, policy, rng)
