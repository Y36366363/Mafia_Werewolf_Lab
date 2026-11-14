"""Paired source actions and a separate succession-report intervention."""

from .engine import Message, Role
from .formal_source_conflict_v39 import MERGE_REASONS, formal_edges
from .hit_candidates_v37 import HitCandidatesAPI, explain
from .strategies_v20 import _rank_choice, old
from .strategies_v24 import succession_event


def current_calls(obs):
    """Last direct ordinary execution call by each live player."""
    return {m.speaker: m.target for m in obs.messages
            if m.day == obs.day and m.context == 'day'
            and m.kind == 'accuse' and m.speaker in obs.alive}


def paired_targets(obs, policy, info):
    """Return the source-exile and mapped targets on the same observation."""
    if (obs.role != Role.CIVILIAN or obs.day < 2 or info['known_bad']
            or info['reason'] not in MERGE_REASONS):
        return None
    edges = formal_edges(obs, info['proposal_sources'])
    if len(edges) != 1:
        return None
    pair = edges[0]
    other_edges = [edge for edge in info['active_edges'] if tuple(edge) != pair]
    if other_edges:
        return None
    calls = current_calls(obs)
    pool = [p for p in info['legal'] if p not in info['known_good']]
    guarded = old.constraints._clear_priority(obs, pool)
    if any(s not in guarded or calls.get(s) not in guarded
           or calls[s] not in info['proposals'].get(str(s), ())
           or calls[s] == s for s in pair):
        return None
    if calls[pair[0]] == calls[pair[1]]:
        return None
    exile = _rank_choice(obs, policy, pair)
    other = next(s for s in pair if s != exile)
    return dict(sources=pair, calls={s: calls[s] for s in pair},
                source_exile=exile, backing=other, mapped=calls[other])


class SourceRoutingAPI(HitCandidatesAPI):
    def __init__(self, cooperation, fake_relay, q, mode):
        super().__init__(cooperation, fake_relay, q, retain=True)
        self.mode = mode
        self.ballots = []
        self.successions = []

    def message(self, obs, policy, rng, context='day', override=None):
        message = super().message(obs, policy, rng, context, override)
        if message.kind == 'police' and context == 'day':
            event = succession_event(obs, policy)
            if event:
                self.successions.append(dict(day=obs.day, **event))
                if self.mode == 'succession_report':
                    # The inherited continuation already calls to exile this same
                    # living target. The report replaces the bare claim slot.
                    return Message(obs.player, 'report', event['target'], True, 'day', obs.day)
        return message

    def vote(self, obs, policy, rng, candidates=None):
        if obs.day == 1 or obs.role != Role.CIVILIAN:
            return super().vote(obs, policy, rng, candidates)
        info = explain(obs, policy, candidates, retain=True)
        pair = paired_targets(obs, policy, info)
        target = info['target']
        if pair and self.mode in {'source_exile', 'call_mapping'}:
            key = 'source_exile' if self.mode == 'source_exile' else 'mapped'
            target = pair[key]
        assert target is None or target in info['legal']
        assert target not in info['known_good']
        assert not info['known_bad'] or target in info['known_bad']
        self.ballots.append(dict(day=obs.day, player=obs.player,
            round='first' if candidates is None else 'pk', target=target,
            original=info['target'], reason=info['reason'], pair=pair,
            calls=[(p, t) for p, t in current_calls(obs).items() if t in info['legal']],
            proposal_sources=info['proposal_sources']))
        return target
