"""Explicit, scoped gold delegation; no role authentication by the referee.

The relay is interpreted as a replacement for its source's own proposal, not
an independent supporting source. All authority tests use the observer's data.
"""
from dataclasses import dataclass, replace
from . import strategies_v26 as base
from . import strategies_v20 as evidence
from .engine import Message, Role, speech_order
from .policies import teammates


@dataclass(frozen=True)
class GoodPolicyV27(base.GoodPolicyV26):
    relay_mode: str = 'none'

    def __post_init__(self):
        super().__post_init__()
        if self.relay_mode not in {'none', 'fixed', 'local'}:
            raise ValueError('unknown gold relay mode')
        if not self.execution_call or self.vote_history:
            raise ValueError('relay isolates the explicit-call baseline without history learning')


MafiaPolicyV27 = base.MafiaPolicyV26
choose_inspection = base.choose_inspection
choose_kill = base.choose_kill
turn_extensions = base.turn_extensions
post_preferences = base.post_preferences
final_call = base.final_call
preference = base.preference
final_selection = base.final_selection
message = base.message


def public_clear_before(obs, source, recipient, stop):
    return any(m.kind == 'report' and m.speaker == source and m.target == recipient
               and m.verdict is False for m in obs.messages[:stop])


def valid_delegations(obs, policy):
    """Current-day, same-source clear; later own instructions revoke delegation.

    The named source need not be genuine. A privately refuted source cannot
    confer authority in this observer's eyes. Absence of refutation is not proof.
    """
    bad = evidence.impossible_sources(obs, policy)
    order = list(speech_order(obs))
    rows = []
    for i, m in enumerate(obs.messages):
        if m.kind != 'delegate' or m.day != obs.day or m.context != 'day':
            continue
        if m.speaker in bad or m.target not in obs.alive:
            continue
        if m.speaker not in order or order.index(m.speaker) >= order.index(m.target):
            continue
        if not public_clear_before(obs, m.speaker, m.target, i):
            continue
        if not any(r.speaker == m.speaker and r.kind == 'report' and r.day == obs.day
                   and r.context == 'day' for r in obs.messages[:i]):
            continue
        later = obs.messages[i+1:]
        if any(r.speaker == m.speaker and r.day == obs.day and r.kind in
               {'accuse', 'shortlist', 'delegate'} for r in later):
            continue
        rows.append((i, m))
    return rows


def relay_decision(obs, policy):
    if obs.role != Role.CIVILIAN or obs.day < 2 or policy.relay_mode == 'none':
        return None
    offers = [(i, m) for i, m in valid_delegations(obs, policy) if m.target == obs.player]
    # Multiple distinct sources are a real decision problem, not automatically
    # solved by taking the latest. This initial pilot declines ambiguous offers.
    if len(offers) != 1:
        return None
    i, offer = offers[0]
    pool = [p for p in offer.targets if p in obs.alive and p != obs.player]
    guarded = evidence.old.constraints._clear_priority(obs, pool) if pool else []
    known = evidence.private_bad(obs, policy.remember).intersection(obs.alive)
    if not guarded or (known and not known.intersection(guarded)):
        return None
    if policy.relay_mode == 'fixed':
        # Never knowingly endorse someone else while holding a live private hit.
        target = next((p for p in guarded if p in known), guarded[0])
    else:
        target = base.explain(obs, policy, guarded)['target']
    if target is None:
        return None
    return Message(obs.player, 'relay', target, context='day', day=obs.day,
                   targets=(offer.speaker,))


def delegation_offer(obs, policy, original):
    if obs.role != Role.POLICE or obs.day < 2 or policy.relay_mode == 'none':
        return None
    if not any(m.speaker == obs.player and m.kind == 'report' and m.day == obs.day
               and m.context == 'day' for m in obs.messages):
        return None
    # A direct known-mafia execution call remains authoritative; this pilot is
    # about delegating an unresolved shortlist, not undoing private facts.
    if any(m is not None and m.kind == 'accuse' for m in original):
        return None
    shortlist = next((m for m in reversed(original) if m is not None and m.kind == 'shortlist'), None)
    if shortlist is None:
        return None
    pool = tuple(p for p in shortlist.targets if p in obs.alive and p != shortlist.target)
    if not pool:
        return None
    order = list(speech_order(obs)); after = order[order.index(obs.player)+1:]
    clear = {r.target for r in obs.investigations if not r.is_mafia} - teammates(obs)
    recipient = next((p for p in after if p in clear and p not in pool
                      and public_clear_before(obs, obs.player, p, len(obs.messages))), None)
    if recipient is None:
        return None
    return Message(obs.player, 'delegate', recipient, context='day', day=obs.day, targets=pool)


def after_speech(obs, policy, rng):
    original = base.after_speech(obs, policy, rng)
    if obs.role == Role.MAFIA or policy.relay_mode == 'none':
        return original
    parts = original if isinstance(original, tuple) else (original,)
    extra = delegation_offer(obs, policy, parts) if obs.role == Role.POLICE else relay_decision(obs, policy)
    return (*tuple(m for m in parts if m is not None), extra) if extra else original


def admitted_relays(obs, policy):
    accepted = []
    for i, offer in valid_delegations(obs, policy):
        replies = [r for r in obs.messages[i+1:] if r.kind == 'relay' and r.day == obs.day
                   and r.context == 'day' and r.speaker == offer.target
                   and r.targets == (offer.speaker,) and r.target in offer.targets
                   and r.target in obs.alive]
        if replies:
            accepted.append((offer, replies[-1]))
    return accepted


def explain(obs, policy, candidates=None):
    original = base.explain(obs, policy, candidates)
    original = dict(original, relay_admitted=0, relay_changed=False, relay_sources=[], relay_targets=[])
    if policy.relay_mode == 'none' or obs.day < 2:
        return original
    accepted = admitted_relays(obs, policy)
    if not accepted:
        return original
    # Interpret a valid relay as the delegator's updated proposal. Do not give
    # its speaker a report/identity, and do not count it as another vote/source.
    virtual = tuple(Message(a.speaker, 'accuse', r.target, context='day', day=obs.day)
                    for a, r in accepted)
    info = base.explain(replace(obs, messages=obs.messages+virtual), policy, candidates)
    return dict(info, relay_admitted=len(accepted), relay_changed=info['target'] != original['target'],
                relay_sources=[a.speaker for a, _ in accepted], relay_targets=[r.target for _, r in accepted])


def vote(obs, policy, rng, candidates=None):
    if obs.role == Role.MAFIA:
        return base.vote(obs, policy, rng, candidates)
    return explain(obs, policy, candidates)['target']
