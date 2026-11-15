"""Independent receiver masks for two uses of the v40 succession report."""

from dataclasses import replace

from .engine import Message, Role
from .hit_candidates_v37 import explain
from .paired_source_routing_v40 import SourceRoutingAPI, current_calls
from .strategies_v20 import _rank_choice, old
from .strategies_v22 import conflict_edges
from .strategies_v24 import explain as pre_gate
from .strategies_v27 import admitted_relays


def masked_explain(obs, policy, candidates, injected, gate, conflict):
    """Keep other uses of the public report intact, including private rebuttal."""
    if gate and conflict or not injected:
        return explain(obs, policy, candidates, retain=True)

    virtual = tuple(Message(offer.speaker, 'accuse', reply.target, context='day', day=obs.day)
                    for offer, reply in admitted_relays(obs, policy))
    prepared = replace(obs, messages=obs.messages + virtual)
    info = pre_gate(prepared, policy, candidates)
    backed = {m.speaker for m in obs.messages if m.kind == 'report' and (gate or m not in injected)}
    eligible = [s for s in info['proposal_sources'] if s in backed]
    proposals = {s: targets if int(s) in backed else [] for s, targets in info['proposals'].items()}
    info = dict(info, proposals=proposals, proposal_sources=eligible)

    if not info['legal'] or info['known_bad']:
        return info
    legal = [p for p in info['legal'] if p not in info['known_good']]
    if not legal:
        return dict(info, target=None, reason='private_good_only')
    guarded = old.constraints._clear_priority(obs, legal)
    if not conflict:
        graph_view = replace(prepared, messages=tuple(m for m in prepared.messages if m not in injected))
        history = conflict_edges(graph_view, info['sources'])
        active = [edge for edge in history if all(p in obs.alive for p in edge)]
        endpoints = {p for edge in active for p in edge}
        info = dict(info, history_edges=history, active_edges=active,
                    conflict_targets=[p for p in guarded if p in endpoints])

    recs = [set(proposals[str(s)]) for s in eligible]
    common = set.intersection(*recs) if recs else set()
    union = set.union(*recs) if recs else set()
    if not info['sources']:
        choices, reason = guarded, 'position_fallback'
    elif len(recs) == 1:
        choices, reason = recs[0], 'single_source_protocol'
    elif common:
        choices, reason = common, 'common_recommendation_protocol'
    elif info['conflict_targets']:
        choices, reason = info['conflict_targets'], 'compare_conflicting_sources'
    elif union:
        choices, reason = union, 'compatible_sources_protocol'
    else:
        choices, reason = guarded, 'position_fallback'
    return dict(info, target=_rank_choice(obs, policy, choices), reason=reason)


MODES = {
    'bare': (False, False),
    'report_neither': (False, False),
    'report_gate': (True, False),
    'report_conflict': (False, True),
    'report_both': (True, True),
}


class SuccessionChannelsAPI(SourceRoutingAPI):
    def __init__(self, cooperation, fake_relay, q, arm):
        super().__init__(cooperation, fake_relay, q,
                         'merge_control' if arm == 'bare' else 'succession_report')
        self.arm = arm
        self.injected = set()
        self.channel_votes = []

    def message(self, obs, policy, rng, context='day', override=None):
        prior = len(self.successions)
        result = super().message(obs, policy, rng, context, override)
        if self.arm != 'bare' and len(self.successions) != prior:
            self.injected.add(result)
        return result

    def vote(self, obs, policy, rng, candidates=None):
        if obs.day < 2 or obs.role != Role.CIVILIAN:
            return super().vote(obs, policy, rng, candidates)

        injected = self.injected.intersection(obs.messages)
        info = masked_explain(obs, policy, candidates, injected, *MODES[self.arm])
        target = info['target']
        assert target is None or target in info['legal']
        assert target not in info['known_good']
        assert not info['known_bad'] or target in info['known_bad']
        row = dict(day=obs.day, player=obs.player, first=candidates is None,
                   target=target, reason=info['reason'], known_bad=info['known_bad'],
                   proposals=info['proposals'], sources=info['proposal_sources'],
                   edges=info['active_edges'],
                   calls=[(s, t) for s, t in current_calls(obs).items() if t in info['legal']])
        if injected and self.arm == 'report_both' and candidates is None and obs.day == self.successions[0]['day']:
            row['shadow'] = {}
            for arm, switches in MODES.items():
                if arm == 'bare':
                    continue
                view = info if arm == self.arm else masked_explain(obs, policy, candidates, injected, *switches)
                row['shadow'][arm] = dict(target=view['target'], reason=view['reason'],
                                          edges=view['active_edges'], sources=view['proposal_sources'])
        self.channel_votes.append(row)
        return target
