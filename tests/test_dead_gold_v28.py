import json
from dataclasses import replace
from pathlib import Path
from random import Random
from mafia_lab import strategies_v28 as d
from mafia_lab import strategies_v27 as old
from mafia_lab.dead_gold_experiment_v28 import build_spec,simulate
from mafia_lab.engine import Message,Role,add_message,add_last_words_component,from_roles,observe,resolve_night
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
C=json.loads(Path('configs/dead_gold_v28.json').read_text())


def case(origin=0,recipient=8):
    r,gs,ms=build_spec(C);G={g.name:g for g in gs}
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),origin,8)
    s=add_message(s,Message(origin,'report',recipient,False,'last_words',1))
    return s,G,ms


def grant(s,origin=0,recipient=8,pool=(9,10)):
    s=add_last_words_component(s,Message(origin,'shortlist',context='last_words',day=1,targets=pool))
    return add_last_words_component(s,Message(origin,'delegate',recipient,context='last_words',day=1,targets=pool))


def test_last_words_grant_preserves_truth_and_uses_only_police_observation():
    s,G,_=case();g=G['list_q50'];o=observe(s,0)
    parts=d.after_last_words(o,g,Random(1))
    assert parts[0].kind=='shortlist' and parts[1].kind=='delegate'
    assert parts[1].target==8 and not(set(parts[1].targets)&{0,1,2,3,8})
    assert d.after_last_words(o,G['reference_q50'],Random(1)) is None
    roles=list(s.roles);roles[5],roles[10]=roles[10],roles[5]
    t=replace(s,roles=tuple(roles));assert observe(t,0)==o
    assert d.after_last_words(observe(t,0),g,Random(1))==parts
    hit=replace(o,messages=(Message(0,'report',4,True,'last_words',1),))
    assert d.after_last_words(hit,g,Random(1)) is None


def test_list_stays_inside_but_evidence_can_name_conditional_rival():
    s,G,_=case();s=grant(s)
    s=add_message(s,Message(4,'report',9,True,'day',1))
    a=d.gold_final_decision(observe(s,8),G['list_q50'])
    b=d.gold_final_decision(observe(s,8),G['evidence_q50'])
    assert a.target in (9,10) and b.target==4
    assert d.reroute_witnesses(observe(s,8),d.dead_offers(observe(s,8),G['evidence_q50'])[0][1])[4]['conditional']
    assert not observe(s,8).investigations and not observe(s,8).teammates


def test_future_evidence_not_seen_before_it_occurs_and_can_be_used_at_final_slot():
    s,G,_=case();s=grant(s);g=G['evidence_q50']
    before=d.gold_final_decision(observe(s,8),g)
    assert before.target in (9,10)
    later=add_message(s,Message(4,'report',9,True,'day',1))
    assert d.gold_final_decision(observe(later,8),g).target==4
    # A forged outside relay without its witness is never retroactively justified.
    forged=add_message(s,Message(8,'relay',4,context='day',day=1,targets=(0,)))
    forged=add_message(forged,Message(4,'report',9,True,'day',1))
    assert not d.admitted_dead_relays(observe(forged,11),g)


def test_private_false_hit_outside_list_causes_refusal_or_justified_reroute():
    s,G,_=case();s=grant(s);s=add_message(s,Message(4,'report',8,True,'day',1))
    assert d.gold_final_decision(observe(s,8),G['list_q50']) is None
    assert d.gold_final_decision(observe(s,8),G['evidence_q50']).target==4


def test_outside_permission_not_arbitrary_and_pk_and_private_facts_still_hold():
    s,G,_=case();s=grant(s);g=G['evidence_q50']
    forged=add_message(s,Message(8,'relay',5,context='day',day=1,targets=(0,)))
    assert not d.explain(observe(forged,11),g)['dead_relay_admitted']
    s=add_message(s,Message(4,'report',9,True,'day',1));relay=d.gold_final_decision(observe(s,8),g)
    s=add_message(s,relay);info=d.explain(observe(s,11),g)
    assert info['dead_relay_admitted'] and info['dead_relay_outside'] and info['dead_relay_conditional']
    assert 8 not in info['sources'] and 8 not in info['known_good']
    assert d.explain(observe(s,11),g,[9,10])['target'] in (9,10)
    assert d.explain(observe(s,1),g)['target']==4


def test_false_dead_source_is_not_authenticated_and_cops_can_refute_it():
    s,G,_=case(origin=4,recipient=5);s=grant(s,4,5,pool=(8,9));g=G['list_q50']
    s=add_message(s,Message(5,'relay',9,context='day',day=1,targets=(4,)))
    civ=d.explain(observe(s,10),g)
    assert civ['dead_relay_admitted'] and 5 not in civ['known_good']
    assert not d.explain(observe(s,1),g)['dead_relay_admitted']
    # Dead alone plus a clear is not a delegation or a role flip.
    no_grant=replace(s,messages=s.messages[:1])
    assert not d.dead_offers(observe(no_grant,10),g)


def test_unknown_roles_do_not_change_gold_decision_and_old_authority_expires():
    s,G,_=case();s=grant(s);g=G['evidence_q50'];o=observe(s,8)
    roles=list(s.roles);roles[1],roles[11]=roles[11],roles[1]
    t=replace(s,roles=tuple(roles));assert observe(t,8)==o
    assert d.gold_final_decision(observe(t,8),g)==d.gold_final_decision(o,g)
    assert d.gold_final_decision(replace(o,day=2),g) is None


def test_public_self_contradiction_is_distinct_from_conditional_shared_check_conflict():
    s,G,_=case();s=grant(s);g=G['evidence_q50']
    s=add_message(s,Message(4,'report',9,True,'day',1))
    s=add_message(s,Message(5,'report',5,True,'day',1))
    offer=d.dead_offers(observe(s,8),g)[0][1]
    witnesses=d.reroute_witnesses(observe(s,8),offer)
    assert witnesses[4]['conditional'] and not witnesses[5]['conditional']
    assert d.gold_final_decision(observe(s,8),g).target==5


def test_reference_and_direct_api_replay_preserve_old_game_and_optional_q_node():
    r,gs,ms=build_spec(C);m=ms[0]
    for mode in ('reference','notice','list','evidence'):
        g=next(g for g in gs if g.dead_gold==mode and g.response_probability=='1/2');seed=187000000
        s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
        assert hash_events(o.transcript)==simulate(r,g,m,seed)['trace_hash']
        if mode=='reference':
            prior=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
            assert prior.transcript==o.transcript


def test_last_words_components_cannot_reopen_or_delay_the_dead_speakers_turn():
    import pytest
    from mafia_lab.engine import last_words_eligible
    s,G,_=case();complete=grant(s)
    assert not last_words_eligible(complete,0)
    with pytest.raises(ValueError):add_message(complete,Message(0,'report',8,False,'last_words',1))
    with pytest.raises(ValueError):add_last_words_component(complete,Message(0,'delegate',8,context='last_words',day=1,targets=(9,10)))
    delayed=add_message(s,Message(1,'pass',context='day',day=1))
    with pytest.raises(ValueError):add_last_words_component(delayed,Message(0,'shortlist',context='last_words',day=1,targets=(9,10)))


def test_dead_police_branch_has_no_optional_first_day_q_decision():
    r,gs,ms=build_spec(C)
    initial=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),0,8)
    transcripts=[]
    for g in gs:
        if g.dead_gold!='evidence':continue
        o=continue_game(initial,g,ms[0],187000001,trace=True,decision_api=d,public_ballots=True)
        transcripts.append(o.transcript)
    assert transcripts[0]==transcripts[1]==transcripts[2]
    assert any(e['event']=='final_call' and e['payload']['kind']=='relay' for e in transcripts[0])
