from dataclasses import replace
from random import Random
import json
from pathlib import Path
from mafia_lab.engine import from_roles, resolve_night, observe, Message
from mafia_lab.hit_candidates_v37 import explain, HitCandidatesAPI
from mafia_lab.private_response_v35 import PrivateResponseAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening, continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events

R, GS, MS = build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()))
G = GS[-1]
M = next(m for m in MS if m.name == 'false_grant')


def scenario(player=15):
    s = resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8, R), 4, 6)
    return replace(observe(s, player), messages=(
        Message(0, 'report', 6, True, 'day', 1),
        Message(5, 'report', 8, False, 'day', 1)))


def test_hit_added_to_source_conflict_not_forced():
    o = scenario(); old = explain(o, G); new = explain(o, G, retain=True)
    assert old['reason'] == 'compare_live_conflicting_sources'
    assert new['admitted_hits'] == [6]
    assert set(new['expanded_pool']) == {0, 5, 6}
    assert new['target'] in new['expanded_pool']
    assert set(old['old_conflict_pool']) == {0, 5}


def test_private_refutation_beats_public_hit():
    o = scenario(15)
    o = replace(o, messages=(Message(0,'report',15,True,'day',1),o.messages[1]))
    v = explain(o, G, retain=True)
    assert not v['hit_scope'] and v['target'] == 0


def test_police_known_bad_and_teammates_take_priority():
    o = scenario(1); v = explain(o, G, retain=True)
    assert v['known_bad'] and v['target'] in v['known_bad'] and not v['hit_scope']


def test_pk_limits_candidates():
    for candidates in ((0, 5), (5, 6), (8,)):
        v = explain(scenario(), G, candidates, True)
        assert v['target'] is None or v['target'] in candidates
        assert set(v['expanded_pool']).issubset(candidates)


def test_no_day_two_extension():
    o = replace(scenario(), day=2)
    assert explain(o, G)['target'] == explain(o, G, retain=True)['target']
    assert not explain(o, G, retain=True)['hit_scope']


def test_history_and_post_vote_context_do_not_add_hits():
    o = scenario()
    for m in (Message(5,'report',9,True,'last_words',1), Message(5,'report',10,True,'day',0)):
        v = explain(replace(o,messages=o.messages+(m,)),G,retain=True)
        assert m.target not in v['admitted_hits']


def test_clear_order_guard_is_retained():
    o = scenario(); o = replace(o,messages=o.messages+(Message(5,'report',6,False,'pk',1),))
    # If the inherited guard protects 6, expansion cannot restore it.
    from mafia_lab import strategies_v31 as base
    guarded = base.evidence.old.constraints._clear_priority(o,[p for p in observe_pool(o) if p!=o.player])
    v = explain(o,G,retain=True)
    assert 6 not in guarded and 6 not in v['expanded_pool']


def observe_pool(o): return list(o.alive)


def test_civilian_choice_has_no_hidden_team_input():
    o=scenario()
    assert explain(o,G,retain=True)==explain(replace(o,teammates=(),investigations=()),G,retain=True)


def test_shadow_receiver_exact_replay_and_randomness():
    seed=207000002
    a=HitCandidatesAPI('copy_early',q='1/2'); s=opening(R,G,M,seed,a)
    x=continue_game(s,G,M,seed,trace=True,decision_api=a,public_ballots=True)
    b=PrivateResponseAPI('copy_early',q='1/2'); s=opening(R,G,M,seed,b)
    y=continue_game(s,G,M,seed,trace=True,decision_api=b,public_ballots=True)
    assert hash_events(x.transcript)==hash_events(y.transcript)
