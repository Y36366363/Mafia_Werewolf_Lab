"""A public agreement tie-break pilot under the v40 continuation model."""
from .engine import Role
from .hit_candidates_v37 import explain
from .paired_source_routing_v40 import SourceRoutingAPI, current_calls


AMBIGUOUS = {'compatible_sources_protocol', 'compare_conflicting_sources'}


def agreement_choice(obs, info):
    """Prefer one eligible live caller whose report matches a death-night report."""
    if (obs.day < 2 or obs.role != Role.CIVILIAN or info['known_bad']
            or info['reason'] not in AMBIGUOUS):
        return None
    victims = {death.player for death in obs.deaths
               if death.day == obs.day and death.cause == 'night'}
    last_words = {(m.target, m.verdict) for m in obs.messages
                  if m.day == obs.day and m.context == 'last_words'
                  and m.kind == 'report' and m.speaker in victims}
    if len(last_words) != 1:
        return None
    claims = {m.speaker: (m.target, m.verdict) for m in obs.messages
              if m.day == obs.day and m.context == 'day' and m.kind == 'report'}
    calls = current_calls(obs)
    eligible = {s: calls[s] for s in info['proposal_sources']
                if s in calls and s in obs.alive
                and calls[s] in info['proposals'].get(str(s), ())}
    if len(set(eligible.values())) < 2:
        return None
    supported = [source for source in eligible if claims.get(source) in last_words]
    if len(supported) != 1:
        return None
    source = supported[0]
    return source, eligible[source]


class SourceEvidencePilotAPI(SourceRoutingAPI):
    def __init__(self, cooperation, fake_relay, q, mode, agreement=False):
        super().__init__(cooperation, fake_relay, q, mode)
        self.agreement = agreement
        self.pilot_ballots = []

    def vote(self, obs, policy, rng, candidates=None):
        if obs.day < 2 or obs.role != Role.CIVILIAN:
            return super().vote(obs, policy, rng, candidates)
        info = explain(obs, policy, candidates, retain=True)
        supported = agreement_choice(obs, info)
        target = supported[1] if supported and self.agreement else info['target']
        assert target is None or target in info['legal']
        assert target not in info['known_good']
        assert not info['known_bad'] or target in info['known_bad']
        self.pilot_ballots.append(dict(
            day=obs.day, first=candidates is None, player=obs.player, baseline=info['target'],
            target=target, supported=supported, reason=info['reason'],
            calls=[(s, t) for s, t in current_calls(obs).items() if t in info['legal']]))
        return target
