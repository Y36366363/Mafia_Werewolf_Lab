"""A two-factor receiver ablation: statement semantics and source compatibility.

Only day-one observations with a locally admissible deceased-source grant are
changed. Facts, actions, randomization, and later continuation remain v28.
No claim type, compatibility edge, or consensus is an identity certificate.
"""
from dataclasses import dataclass
from . import strategies_v28 as base
from . import strategies_v20 as evidence
from .engine import Role


@dataclass(frozen=True)
class GoodPolicyV29(base.GoodPolicyV28):
    typed_advice: bool = False
    conflict_guard: bool = False


MafiaPolicyV29 = base.MafiaPolicyV28
choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
preference = base.preference
final_selection = base.final_selection
message = base.message
after_speech = base.after_speech
after_last_words = base.after_last_words
final_call = base.final_call


def statement_kind(obs, policy, source, targets):
    """Identify the actual active proposal; do not upgrade an identity belief.

    A report hit is a purported fact; an execution call is an intent. Both
    specify a target, unlike a shortlist. Same-source explicit calls retain
    priority over that source's reported hit, as in the inherited protocol.
    """
    if not targets:return 'none'
    for origin, relay, _ in reversed(base.admitted_dead_relays(obs, policy)):
        if origin.speaker == source and relay.target in targets:
            return 'execution'
    rows = [m for m in obs.messages if m.speaker == source and m.day == obs.day]
    if any(m.kind == 'accuse' and m.target in targets for m in rows):
        return 'execution'
    if any(m.kind == 'report' and m.verdict and m.target in targets for m in rows):
        return 'claimed_hit'
    if any(m.kind == 'shortlist' and set(m.targets).intersection(targets) for m in rows):
        return 'shortlist'
    return 'none'


def explain(obs, policy, candidates=None):
    original = base.explain(obs, policy, candidates)
    meta = dict(receiver_scope=False, receiver_changed=False, proposal_kinds={}, common_targets=[],
                contributors_conflict=False, blocked_by_type=False, blocked_by_conflict=False,
                early_common_accepted=False)
    original = dict(original, **meta)
    if obs.day != 1 or not base.dead_offers(obs, policy):
        return original
    original['receiver_scope'] = True
    # Private facts and legality precede every public consensus rule.
    if not original['legal'] or original['known_bad']:
        return original
    pool = [p for p in original['legal'] if p not in original['known_good']]
    if not pool:return original
    guarded = evidence.old.constraints._clear_priority(obs, pool)
    # Day-one legacy routing uses every unrefuted source, including sources
    # without a proposal. Preserve that choice: an empty set prevents consensus.
    sources = original['sources']
    recs = {s:set(original['proposals'].get(str(s),[])).intersection(guarded) for s in sources}
    kinds = {s:statement_kind(obs,policy,s,recs[s]) for s in sources}
    common = set.intersection(*(recs[s] for s in sources)) if sources else set()
    incompatible = any(a in sources and b in sources for a,b in original['history_edges'])
    explicit = bool(sources) and all(kinds[s] in {'execution','claimed_hit'} for s in sources)
    block_type = bool(common and policy.typed_advice and not explicit)
    block_conflict = bool(common and policy.conflict_guard and incompatible)
    info = dict(original, proposal_kinds={str(s):k for s,k in kinds.items()},
                common_targets=sorted(common), contributors_conflict=incompatible,
                blocked_by_type=block_type, blocked_by_conflict=block_conflict)
    if not (policy.typed_advice or policy.conflict_guard):
        return dict(info,early_common_accepted=bool(common and original['reason']=='common_recommendation_protocol'))

    def choose(choices, reason, early=False):
        target=evidence._rank_choice(obs,policy,choices)
        return dict(info,target=target,reason=reason,receiver_changed=target!=original['target'],
                    early_common_accepted=early)

    if not sources:return choose(guarded,'position_fallback')
    if len(sources)==1:
        s=sources[0]
        return choose(recs[s] or guarded,'single_source_protocol' if recs[s] else 'single_source_no_legal_proposal')
    if common and not block_type and not block_conflict:
        return choose(common,'explicit_common_protocol' if policy.typed_advice else 'common_recommendation_protocol',True)
    # The inherited comparison policy is retained, not a proof that the live
    # member of a dead/live conflict is mafia. No source is authenticated.
    if original['conflict_targets']:
        return choose(original['conflict_targets'],'compare_conflicting_sources')
    if common and policy.typed_advice and not block_conflict:
        # An overlap of suggestions may break an unresolved tie only AFTER
        # source conflicts have been considered; it never becomes a hard fact.
        return choose(common,'soft_overlap_fallback')
    union=set.union(*(recs[s] for s in sources)) if sources else set()
    if union:return choose(union,'compatible_sources_protocol')
    return choose(guarded,'position_fallback')


def vote(obs,policy,rng,candidates=None):
    if obs.role==Role.MAFIA:return base.vote(obs,policy,rng,candidates)
    return explain(obs,policy,candidates)['target']
