"""Information and action-budget checks for the frozen succession counter."""
import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from random import Random

from mafia_lab import strategies_v23 as previous
from mafia_lab import strategies_v24 as d
from mafia_lab.engine import Message, Role, add_message, from_roles, observe, resolve_night
from mafia_lab.restatement_experiment_v23 import build_spec


C = json.loads(Path('configs/restatement_response_v23.json').read_text())


def case(mode='claim', *, dead_origin=True):
    rules, good, mafia = build_spec(C)
    policy = d.MafiaPolicyV24(**{**asdict(mafia[1]), 'succession': mode})
    state = resolve_night(from_roles(['police'] * 4 + ['mafia'] * 4 + ['civilian'] * 8, rules), 15, 14)
    state = add_message(state, Message(4, 'report', 8, True, 'day', 1))
    if dead_origin:
        state = replace(state, day=2, alive=tuple(p for p in state.alive if p != 4), last_anchor=4)
    else:
        state = replace(state, day=2, last_anchor=15)
    return state, good, policy


def test_claim_uses_one_ordinary_claim_and_same_one_current_accusation():
    state, _, policy = case()
    obs = observe(state, 5)
    assert d.succession_event(obs, policy) == {'origin': 4, 'target': 8, 'speaker': 5}
    claim = d.message(obs, policy, Random(1))
    assert (claim.speaker, claim.kind, claim.target, claim.verdict, claim.day) == (5, 'police', None, None, 2)
    after_claim = observe(add_message(state, claim), 5)
    # The normal-turn claim does not consume the one extension; no inspection is fabricated.
    assert d.succession_event(after_claim, policy) is not None
    extension = d.after_speech(after_claim, policy, Random(1))
    assert isinstance(extension, Message)
    assert (extension.kind, extension.target, extension.verdict, extension.day) == ('accuse', 8, None, 2)
    finished = add_message(add_message(state, claim), extension)
    assert d.succession_event(observe(finished, 5), policy) is None
    assert finished.messages[0] == Message(4, 'report', 8, True, 'day', 1)
    assert [m.kind for m in finished.messages] == ['report', 'police', 'accuse']


def test_support_and_claim_share_mafia_accusation_channel_but_not_source_status():
    state, _, claim_policy = case('claim')
    support_policy = replace(claim_policy, succession='support')
    obs = observe(state, 5)
    support = d.message(obs, support_policy, Random(1))
    assert support == previous.message(obs, support_policy, Random(1))
    assert support.kind not in {'police', 'report'}
    support_state = add_message(state, support)
    support_extension = d.after_speech(observe(support_state, 5), support_policy, Random(1))
    claim = d.message(obs, claim_policy, Random(1))
    claim_state = add_message(state, claim)
    claim_extension = d.after_speech(observe(claim_state, 5), claim_policy, Random(1))
    assert support_extension == claim_extension == Message(5, 'accuse', 8, context='day', day=2)
    support_state = add_message(support_state, support_extension)
    claim_state = add_message(claim_state, claim_extension)
    # An advocate does not automatically acquire police-source authority.
    support_sources = {m.speaker for m in previous.base.public_claims(observe(support_state, 9))}
    claim_sources = {m.speaker for m in previous.base.public_claims(observe(claim_state, 9))}
    assert support_sources == {4}
    assert claim_sources == {4, 5}
    assert 5 not in previous.base.private_bad(observe(claim_state, 9), True)
    assert 5 in previous.base.private_bad(observe(claim_state, 0), True)


def test_no_new_target_no_live_origin_succession_and_only_elected_live_actor():
    state, _, policy = case()
    obs = observe(state, 5)
    assert d.succession_event(replace(obs, day=1), policy) is None
    assert d.succession_event(replace(obs, alive=tuple(p for p in obs.alive if p != 8)), policy) is None
    assert d.succession_event(observe(state, 6), policy) is None
    assert d.succession_event(observe(state, 0), policy) is None
    assert d.succession_event(obs, replace(policy, succession='none')) is None
    live_state, _, _ = case(dead_origin=False)
    assert d.succession_event(observe(live_state, 5), policy) is None
    # A surviving original claimant still repeats its own accusation via v23.
    live_obs = observe(live_state, 4)
    assert d.after_speech(live_obs, policy, Random(1)) == previous.after_speech(live_obs, policy, Random(1))
    assert d.after_speech(live_obs, policy, Random(1)).target == 8


def test_succession_does_not_follow_an_unrelated_police_report():
    state, _, policy = case()
    # The only day-one report belongs to a known non-teammate, not the original impostor.
    unrelated = replace(state, messages=(Message(0, 'report', 8, True, 'day', 1),),
                        alive=tuple(p for p in state.alive if p != 0))
    assert d.succession_event(observe(unrelated, 5), policy) is None


def test_unknown_police_civilian_permutation_cannot_change_counter_action():
    state, _, policy = case()
    roles = list(state.roles)
    roles[0], roles[9] = roles[9], roles[0]
    other = replace(state, roles=tuple(roles))
    a, b = observe(state, 5), observe(other, 5)
    assert a == b
    assert d.succession_event(a, policy) == d.succession_event(b, policy)
    assert d.message(a, policy, Random(17)) == d.message(b, policy, Random(17))
    assert d.after_speech(a, policy, Random(17)) == d.after_speech(b, policy, Random(17))


def test_no_pk_recruitment_and_no_changed_day_one_local_q():
    state, good, policy = case()
    obs = observe(state, 5)
    assert d.message(obs, policy, Random(1), context='pk') == previous.message(obs, policy, Random(1), context='pk')
    first = replace(state, day=1, alive=tuple(p for p in range(15)), last_anchor=15)
    police = observe(first, 0)
    q0 = next(g for g in good if g.name == 'repair_q0')
    q1 = next(g for g in good if g.name == 'repair_q100')
    assert d.message(police, q0, Random(1)) == previous.message(police, q0, Random(1))
    assert d.message(police, q1, Random(1)) == previous.message(police, q1, Random(1))
    assert d.message(police, q0, Random(1)).kind == 'pass'
    assert d.message(police, q1, Random(1)).kind == 'report'


def test_none_counter_full_trace_matches_previous_version():
    from mafia_lab.simulation import continue_game, opening
    rules, good, mafia = build_spec(C)
    g = next(g for g in good if g.name == 'repair_q50')
    m = d.MafiaPolicyV24(**{**asdict(mafia[0]), 'succession': 'none'})
    seed = 171000000
    initial = opening(rules, g, m, seed, d)
    before = continue_game(initial, g, m, seed, trace=True, decision_api=previous, public_ballots=True)
    after = continue_game(initial, g, m, seed, trace=True, decision_api=d, public_ballots=True)
    assert sha256(repr(before.transcript).encode()).hexdigest() == sha256(repr(after.transcript).encode()).hexdigest()
