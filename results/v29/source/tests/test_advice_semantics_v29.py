import json
from dataclasses import replace
from pathlib import Path
from random import Random
from mafia_lab import strategies_v29 as d
from mafia_lab import strategies_v28 as old
from mafia_lab.advice_semantics_experiment_v29 import build_spec,simulate,column_job,contrasts
from mafia_lab.engine import Message,Role,add_message,add_last_words_component,from_roles,observe,resolve_night
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
C=json.loads(Path('configs/advice_semantics_v29.json').read_text())


def case(fake=True,pool=(9,10)):
    r,gs,ms=build_spec(C);G={g.name:g for g in gs}
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),0,8)
    s=add_message(s,Message(0,'report',8,False,'last_words',1))
    s=add_last_words_component(s,Message(0,'shortlist',context='last_words',day=1,targets=pool))
    s=add_last_words_component(s,Message(0,'delegate',8,context='last_words',day=1,targets=pool))
    if fake:s=add_message(s,Message(4,'report',9,True,'day',1))
    return s,G,ms


def test_shortlist_and_claimed_hit_overlap_is_not_a_hard_joint_execution():
    s,G,_=case();o=observe(s,11)
    plain=d.explain(o,G['plain']);typed=d.explain(o,G['typed'])
    assert plain['target']==9 and plain['early_common_accepted']
    assert plain['proposal_kinds']=={'0':'shortlist','4':'claimed_hit'}
    assert typed['target']==4 and typed['blocked_by_type'] and not typed['blocked_by_conflict']
    assert typed['known_bad']==[] and 4 not in typed['known_good']


def test_source_conflict_is_a_separate_factor_even_when_every_proposal_is_explicit():
    s,G,_=case();s=add_message(s,Message(8,'relay',9,context='day',day=1,targets=(0,)))
    typed=replace(G['typed'],dead_gold='list');guard=replace(G['guard'],dead_gold='list')
    a=d.explain(observe(s,11),typed);b=d.explain(observe(s,11),guard)
    assert a['proposal_kinds']=={'0':'execution','4':'claimed_hit'}
    assert not a['blocked_by_type'] and a['target']==9
    assert b['blocked_by_conflict'] and b['target']==4


def test_compatible_explicit_calls_can_still_agree_without_identity_authentication():
    s,G,_=case(fake=False);s=add_message(s,Message(4,'report',8,False,'day',1))
    s=add_message(s,Message(4,'accuse',9,context='day',day=1))
    s=add_message(s,Message(8,'relay',9,context='day',day=1,targets=(0,)))
    g=replace(G['both'],dead_gold='list');v=d.explain(observe(s,11),g)
    assert v['proposal_kinds']=={'0':'execution','4':'execution'}
    assert not v['contributors_conflict'] and v['early_common_accepted'] and v['target']==9
    assert v['known_bad']==[]


def test_compatible_soft_lists_remain_usable_as_fallback_not_new_facts():
    s,G,_=case(fake=False);s=add_message(s,Message(4,'report',8,False,'day',1))
    s=add_message(s,Message(4,'shortlist',context='day',day=1,targets=(9,12)))
    v=d.explain(observe(s,11),G['both'])
    assert v['blocked_by_type'] and not v['blocked_by_conflict']
    assert v['reason']=='soft_overlap_fallback' and v['target']==9 and v['known_bad']==[]


def test_execution_call_remains_distinct_from_reported_hit_and_has_same_source_priority():
    s,G,_=case(fake=False);s=add_message(s,Message(4,'report',5,True,'day',1))
    s=add_message(s,Message(4,'accuse',6,context='day',day=1))
    assert d.statement_kind(observe(s,11),G['both'],4,{6})=='execution'
    assert d.statement_kind(observe(s,11),G['both'],4,{5})=='claimed_hit'
    assert s.messages[-2].target==5 and s.messages[-1].target==6


def test_private_facts_and_pk_legality_precede_public_merging():
    s,G,_=case()
    for g in G.values():
        v=d.explain(observe(s,1),g)
        assert v['target']==4 and v['known_bad']==[4]
        assert d.explain(observe(s,11),g,[9,10])['target'] in (9,10)
    # A civilian falsely hit by4 has its own independent refutation.
    assert d.explain(observe(s,9),G['both'])['target']==4


def test_future_claim_cannot_change_earlier_decision_and_death_never_certifies_source():
    s,G,_=case(fake=False);o=observe(s,11)
    first=d.explain(o,G['both'])
    assert not first['contributors_conflict'] and first['target'] in (9,10)
    later=add_message(s,Message(4,'report',9,True,'day',1))
    v=d.explain(observe(later,11),G['both'])
    assert v['contributors_conflict'] and v['target']==4 and v['known_bad']==[]
    assert 8 not in v['known_good']  # even the named gold is not authenticated


def test_hidden_role_swap_does_not_change_civilian_observation_or_decision():
    s,G,_=case();roles=list(s.roles);roles[1],roles[12]=roles[12],roles[1]
    t=replace(s,roles=tuple(roles));a,b=observe(s,11),observe(t,11)
    assert a==b
    for g in G.values():assert d.vote(a,g,Random(1))==d.vote(b,g,Random(1))


def test_no_scope_or_later_day_keeps_inherited_actions_and_gold_mechanism_exists():
    s,G,_=case();g=G['both'];o=replace(observe(s,11),day=2)
    assert d.explain(o,g)['target']==old.explain(o,g)['target']
    plain=replace(observe(s,11),messages=tuple(m for m in s.messages if m.kind!='delegate'))
    assert d.explain(plain,g)['target']==old.explain(plain,g)['target']
    assert not d.explain(plain,g)['receiver_scope']
    retained=replace(g,dead_gold='evidence')
    assert d.final_call(observe(s,8),retained,Random(1)).kind=='relay'


def test_old_failure_is_fixed_without_relabeling_the_victim_or_adding_messages():
    r,gs,ms=build_spec(C);G={g.name:g for g in gs};m=next(m for m in ms if m.name=='late_far_claim_team')
    rows={g.name:simulate(r,g,m,186000016,details=True) for g in gs}
    assert rows['plain']['raw']['win']==0 and rows['anchor']['raw']['win']==1
    assert rows['typed']['raw']['process_hash']==rows['guard']['raw']['process_hash']==rows['both']['raw']['process_hash']==rows['anchor']['raw']['process_hash']
    assert len({rows[n]['raw']['speech_prefix_hash'] for n in ('plain','typed','guard','both')})==1


def test_direct_api_legacy_compatibility_and_grouped_runner_give_identical_games():
    r,gs,ms=build_spec(C);m=ms[0];seed=C['smoke']['seed_start']
    rows=column_job(('smoke',r,gs,m,seed,1));D={c['good']:c for c in rows}
    for g in gs:
        s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
        row=simulate(r,g,m,seed)
        assert row['trace_hash']==hash_events(o.transcript)==D[g.name]['samples'][0]['trace_hash']
        if g.name in ('anchor','plain'):
            prior=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
            assert prior.transcript==o.transcript


def test_optional_q_node_is_absent_in_dead_police_clear_branch():
    r,gs,ms=build_spec(C);g=next(g for g in gs if g.name=='both')
    initial=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),0,8)
    results=[]
    for q in ('0','1/2','1'):
        results.append(continue_game(initial,replace(g,response_probability=q),ms[0],190000001,trace=True,decision_api=d,public_ballots=True).transcript)
    assert results[0]==results[1]==results[2]
