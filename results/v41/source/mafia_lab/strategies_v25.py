"""One mechanism ablation: advice admission, not authenticated source identity.

Bare police claims remain in history/conflicts and private reasoning. The gate
only withholds their current voting advice until that speaker has made an
explicit (still unverified) inspection statement. Mafia policies are unchanged.
"""
from dataclasses import dataclass
from . import strategies_v24 as base
from . import strategies_v20 as evidence
from .engine import Role


@dataclass(frozen=True)
class GoodPolicyV25(base.GoodPolicyV24):
    report_advice_gate: bool = False


MafiaPolicyV25 = base.MafiaPolicyV24
choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
final_call = base.final_call
preference = base.preference
final_selection = base.final_selection
message = base.message
after_speech = base.after_speech


def explain(obs, policy, candidates=None):
    info = base.explain(obs, policy, candidates)
    backed = {m.speaker for m in obs.messages if m.kind == 'report'}
    blocked = [s for s in info['proposal_sources'] if s not in backed]
    enabled = policy.report_advice_gate and obs.day >= 2
    info = dict(info, blocked_advice_sources=blocked if enabled else [],
                report_backed_sources=sorted(backed), gate_active=enabled)
    if not enabled:
        return info
    # Keep every source and every conflict edge; only proposals lose admission.
    info['proposals'] = {s: targets if int(s) in backed else []
                         for s, targets in info['proposals'].items()}
    eligible = [s for s in info['proposal_sources'] if s in backed]
    info['proposal_sources'] = eligible
    if not info['legal'] or info['known_bad']:
        return info
    pool = [p for p in info['legal'] if p not in info['known_good']]
    if not pool:
        return dict(info, target=None, reason='private_good_only')
    guarded = evidence.old.constraints._clear_priority(obs, pool)
    recs = {s: set(info['proposals'][str(s)]) for s in eligible}
    if not info['sources']:
        target, reason = evidence._rank_choice(obs, policy, guarded), 'position_fallback'
    elif len(eligible) == 1:
        target, reason = evidence._rank_choice(obs, policy, recs[eligible[0]]), 'single_source_protocol'
    else:
        common = set.intersection(*(recs[s] for s in eligible)) if eligible else set()
        union = set.union(*(recs[s] for s in eligible)) if eligible else set()
        if common:
            target, reason = evidence._rank_choice(obs, policy, common), 'common_recommendation_protocol'
        elif info['conflict_targets']:
            target, reason = evidence._rank_choice(obs, policy, info['conflict_targets']), 'compare_conflicting_sources'
        elif union:
            target, reason = evidence._rank_choice(obs, policy, union), 'compatible_sources_protocol'
        else:
            target, reason = evidence._rank_choice(obs, policy, guarded), 'position_fallback'
    return dict(info, target=target, reason=reason)


def route(obs, policy, candidates=None):
    info = explain(obs, policy, candidates)
    return info['target'], info['reason']


def vote(obs, policy, rng, candidates=None):
    if obs.role == Role.MAFIA:
        return base.vote(obs, policy, rng, candidates)
    return route(obs, policy, candidates)[0]
