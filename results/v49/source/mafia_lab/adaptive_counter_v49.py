"""Test a time-legal countervote and a vote-backed alternative to exiling the rival."""
from dataclasses import replace

from .engine import Message, Role, speech_order
from .novelty_ablation_v48 import NoveltyAblationAPI
from .policies import teammates
from .strategies_v18 import _clear_priority


def counter_options(obs):
    """A non-spokesperson may dispute a visible ordinary hit on their own seat."""
    if obs.role != Role.MAFIA or obs.day != 1:
        return ()
    team = teammates(obs)
    first = next(p for p in speech_order(obs) if p in team)
    if obs.player == first:
        return ()
    return tuple(m.speaker for m in obs.messages if m.kind == 'report' and m.verdict
                 and m.day == 1 and m.context == 'day' and m.target == obs.player
                 and m.speaker in obs.alive and m.speaker not in team)


def backed_alternative(obs, pair, source, victim, clear):
    """Require two actual prior votes from other surviving non-teammates."""
    rival = next(p for p in pair if p != source)
    team = teammates(obs)
    pool = [p for p in obs.alive if p not in team and p != victim]
    legal = set(_clear_priority(obs,pool)) - set(pair) - {clear}
    first = next((e for e in obs.public_events if e.kind == 'vote' and e.day == 1),None)
    if first is None:
        return None
    other_voters = set(pool) - set(pair)
    voters = {target: sorted(p for p,v in first.ballots if p in other_voters and v==target)
              for target in legal | {rival}}
    preferred = [p for p in legal if len(voters[p]) >= 2 and len(voters[p]) > len(voters[rival])]
    if not preferred:
        return None
    order = {p:i for i,p in enumerate(speech_order(obs))}
    target = min(preferred,key=lambda p:(-len(voters[p]),order[p]))
    return dict(target=target,voters=voters[target],rival=rival,rival_voters=voters[rival])


class AdaptiveCounterAPI(NoveltyAblationAPI):
    def __init__(self, cooperation, relay, q, counter, receiver, alternate):
        super().__init__(cooperation,relay,q,'prepared',receiver)
        self.counter = counter
        self.alternate = alternate
        self.counter_speeches = []
        self.counter_ballots = []
        self.alternative = None

    def after_speech(self, obs, policy, rng):
        inherited = super().after_speech(obs,policy,rng)
        eligible = counter_options(obs) if self.counter else ()
        if not eligible:
            return inherited
        source = eligible[-1]
        parts = inherited if isinstance(inherited,tuple) else (inherited,)
        # Reuse the player's own after-speech nomination slot.
        parts = tuple(m for m in parts if m is not None and m.kind != 'nominate')
        self.counter_speeches.append(dict(voter=obs.player,source=source))
        return (*parts,Message(obs.player,'nominate',source,context='day',day=1))

    def vote(self, obs, policy, rng, candidates=None):
        ordinary = super().vote(obs,policy,rng,candidates)
        eligible = counter_options(obs) if self.counter and candidates is None else ()
        if not eligible:
            return ordinary
        # A later report after our turn cannot turn a silent ballot into a promise.
        public = [m.target for i,m in enumerate(obs.messages) if m.speaker == obs.player and m.day == 1
                  and m.context == 'day' and m.kind == 'nominate' and m.target in eligible
                  and m.target in counter_options(replace(obs,messages=obs.messages[:i]))]
        if not public:
            return ordinary
        target = public[-1]
        self.counter_ballots.append(dict(voter=obs.player,source=target,baseline=ordinary))
        return target

    def prepare_bluff(self, obs, source, victim, rng):
        super().prepare_bluff(obs,source,victim,rng)
        plan = self.bluff_plan
        if plan['hit']:
            return
        self.alternative = backed_alternative(obs,self.pair,source,victim,plan['target'])
        if self.alternate and self.alternative is not None:
            self.bluff_plan = dict(plan,call=self.alternative['target'])
