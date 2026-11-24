"""Compare a rival call with a third target backed by today's public speech."""
from dataclasses import replace

from .engine import Role, speech_order
from .policies import teammates
from .strategies_v18 import _clear_priority


def current_alternative(obs, pair, clear):
    """Return a legal alternative supported more than the rival in this prefix."""
    if (obs.role != Role.MAFIA or obs.day != 2 or obs.pending_pk
            or len(pair) != 2 or obs.player not in pair):
        return None
    rival = next(p for p in pair if p != obs.player)
    team = teammates(obs)
    nonteam = [p for p in obs.alive if p not in team]
    if rival not in nonteam:
        return None
    legal = set(_clear_priority(obs, nonteam)) - set(pair) - {clear}
    order = {p: i for i, p in enumerate(speech_order(obs))}
    supporters = set(nonteam) - set(pair)
    latest = {
        m.speaker: m.target for m in obs.messages
        if m.day == 2 and m.context == 'day' and m.kind in {'nominate', 'accuse'}
        and m.speaker in supporters and order[m.speaker] < order[obs.player]
    }
    support = {target: sorted(p for p, choice in latest.items() if choice == target)
               for target in legal | {rival}}
    eligible = [p for p in legal if len(support[p]) >= 2 and len(support[p]) > len(support[rival])]
    if not eligible:
        return None
    target = min(eligible, key=lambda p: (-len(support[p]), order[p]))
    return dict(target=target, voters=support[target], rival=rival, rival_voters=support[rival])


class CurrentSupportMixin:
    """Leave the overnight report intact and specify the actual call in speech."""

    live_alternative = None
    live_redirect = False

    def after_speech(self, obs, policy, rng):
        inherited = super().after_speech(obs, policy, rng)
        plan = self.bluff_plan
        if (obs.role != Role.MAFIA or obs.day != 2 or obs.pending_pk or not plan
                or plan['hit'] or obs.player != plan['source'] or inherited is None
                or inherited.kind != 'accuse'):
            return inherited
        self.live_alternative = current_alternative(obs, self.pair, plan['target'])
        if self.live_redirect and self.live_alternative is not None:
            return replace(inherited, target=self.live_alternative['target'])
        return inherited
