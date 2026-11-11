"""Single ballot-receiver ablation: retain public hit targets in live conflicts."""
from .private_response_v35 import PrivateResponseAPI
from . import strategies_v31 as base
from .engine import Role


def explain(obs, policy, candidates=None, retain=False):
    old = base.explain(obs, policy, candidates)
    info = dict(old, hit_scope=False, admitted_hits=[], old_conflict_pool=[],
                expanded_pool=[], receiver_changed=False)
    # Only the old live-source conflict branch changes. Private facts, the
    # clear-before-source order, ballot legality and other branches come first.
    if obs.day != 1 or old['reason'] != 'compare_live_conflicting_sources':
        return info
    pool = [p for p in old['legal'] if p not in old['known_good']]
    pool = base.evidence.old.constraints._clear_priority(obs, pool)
    sources = set(old['sources']) - base.evidence.impossible_sources(obs, policy)
    hits = sorted({m.target for m in obs.messages
                   if m.day == obs.day and m.context in {'day', 'pk'}
                   and m.kind == 'report' and m.verdict is True
                   and m.speaker in sources and m.speaker in obs.alive
                   and m.target in pool})
    prior = sorted(set(old['conflict_targets']).intersection(pool))
    expanded = sorted(set(prior).union(hits))
    info.update(hit_scope=True, admitted_hits=hits, old_conflict_pool=prior,
                expanded_pool=expanded)
    if retain and expanded:
        target = base.evidence._rank_choice(obs, policy, expanded)
        info.update(target=target, reason='compare_sources_and_hit_targets',
                    receiver_changed=target != old['target'])
    return info


class HitCandidatesAPI(PrivateResponseAPI):
    def __init__(self, cooperation='ordinary', fake_relay=False, q='1/2', retain=False):
        super().__init__(cooperation, 'original', fake_relay, q)
        self.retain = retain
        self.candidate_votes = []

    def vote(self, obs, policy, rng, candidates=None):
        if obs.role == Role.MAFIA:
            return super().vote(obs, policy, rng, candidates)
        info = explain(obs, policy, candidates, self.retain)
        target = info['target']
        assert target is None or target in info['legal']
        assert not info['known_bad'] or target in info['known_bad']
        assert target not in info['known_good']
        self.candidate_votes.append(dict(day=obs.day, player=obs.player,
            role=obs.role.value, round='first' if candidates is None else 'pk',
            target=target, reason=info['reason'], legal=info['legal'],
            known_bad=info['known_bad'], known_good=info['known_good'],
            hit_scope=info['hit_scope'], admitted_hits=info['admitted_hits'],
            old_pool=info['old_conflict_pool'], expanded_pool=info['expanded_pool'],
            changed=info['receiver_changed']))
        return target
