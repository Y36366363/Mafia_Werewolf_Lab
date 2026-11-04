import json
from dataclasses import replace
from pathlib import Path
from random import Random
from mafia_lab import strategies_v30 as d
from mafia_lab import strategies_v29 as old
from mafia_lab.relay_receiver_experiment_v30 import build_spec,simulate,column_job
from mafia_lab.engine import Message,Role,from_roles,resolve_night,observe,add_message,add_last_words_component
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events

C=json.loads(Path('configs/relay_receiver_v30.json').read_text())

def case():
 r,gs,ms=build_spec(C)
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),0,8)
 s=add_message(s,Message(0,'report',8,False,'last_words',1))
 for m in (Message(0,'shortlist',context='last_words',day=1,targets=(9,10)),Message(0,'delegate',8,context='last_words',day=1,targets=(9,10))):
  s=add_last_words_component(s,m)
 return s,{g.name:g for g in gs},{m.name:m for m in ms}


def test_relay_can_turn_soft_list_into_explicit_agreement_but_conflict_guard_survives():
 s,G,M=case();s=add_message(s,Message(4,'report',9,True,'day',1))
 call=d.final_call(observe(s,8),G['relay_guard'],Random(1));assert call.target==9
 s=add_message(s,call)
 a=d.explain(observe(s,11),G['relay_typed']);b=d.explain(observe(s,11),G['relay_guard'])
 assert a['kinds'] if 'kinds' in a else a['proposal_kinds']=={'0':'execution','4':'claimed_hit'}
 assert a['target']==9 and a['early_common_accepted'] and a['contributors_conflict']
 assert b['target']==4 and b['blocked_by_conflict'] and not b['early_common_accepted']
 assert 4 not in b['known_bad']


def test_guard_does_not_authenticate_a_copied_clear_and_wrong_execution():
 s,G,M=case();o=observe(s,4);m=M['late_copy']
 report=d.message(o,m,Random(1));assert report.verdict is False and report.target==8
 s=add_message(s,report);call=d.after_speech(observe(s,4),m,Random(1));assert call.kind=='accuse' and call.target not in (4,5,6,7,8)
 s=add_message(s,call)
 v=d.explain(observe(s,11),G['notice']);assert not v['contributors_conflict']
 assert v['known_bad']==[]  # agreement is not a police identity proof


def test_copy_uses_only_already_visible_dead_clear_and_own_team():
 s,G,M=case();o=observe(s,4);m=M['late_copy']
 roles=list(s.roles);roles[1],roles[12]=roles[12],roles[1]
 other=observe(replace(s,roles=tuple(roles)),4);assert o==other
 assert d.message(o,m,Random(1))==d.message(other,m,Random(1))
 assert d.after_speech(o,m,Random(1))==d.after_speech(other,m,Random(1))
 earlier=replace(o,messages=())
 assert d.message(earlier,m,Random(1))==old.message(earlier,m,Random(1))


def test_quiet_has_no_initial_fake_report_or_extra_accusation():
 s,G,M=case();m=M['late_quiet'];o=observe(s,4)
 assert d.message(o,m,Random(1)).kind=='pass'
 assert d.after_speech(o,m,Random(1)) is None


def test_fake_last_words_grant_is_admitted_without_referee_authentication():
 s,G,M=case();r=s.rules
 t=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),4,8)
 m=M['false_grant'];msg=d.message(observe(t,4),m,Random(1),'last_words');t=add_message(t,msg)
 parts=d.after_last_words(observe(t,4),m,Random(1))
 for part in parts:t=add_last_words_component(t,part)
 # This public recipient happens to be civilian8; no policy queried that label.
 recipient=msg.target;assert recipient==8
 obs=observe(t,recipient);offers=d.gold.dead_offers(obs,G['relay_guard'])
 assert len(offers)==1 and offers[0][1].speaker==4
 call=d.final_call(obs,G['relay_guard'],Random(1));assert call is not None
 v=d.explain(observe(add_message(t,call),9),G['relay_guard']);assert v['known_bad']==[]
 assert not d.gold.dead_offers(observe(t,0),G['relay_guard'])  # police privately refutes fake


def test_selfkill_variants_have_same_opening_and_differ_only_by_authorization():
 r,gs,ms=build_spec(C);M={m.name:m for m in ms};g=gs[2]
 a=opening(r,g,M['false_notice'],193000001,d);b=opening(r,g,M['false_grant'],193000001,d)
 assert a==b and a.roles[a.deaths[0].player]==Role.MAFIA
 for mode in ['false_notice','false_grant']:
  m=M[mode];msg=d.message(observe(a,a.deaths[0].player),m,Random(1),'last_words')
  t=add_message(a,msg);parts=d.after_last_words(observe(t,msg.speaker),m,Random(1))
  assert [p.kind for p in parts]==(['shortlist'] if mode=='false_notice' else ['shortlist','delegate'])


def test_private_facts_and_pk_legality_override_any_gold_instruction():
 s,G,M=case();s=add_message(s,Message(4,'report',9,True,'day',1))
 s=add_message(s,Message(8,'relay',9,context='day',day=1,targets=(0,)))
 for g in G.values():
  v=d.explain(observe(s,1),g);assert v['target']==4 and v['known_bad']==[4]
  assert d.explain(observe(s,11),g,(9,10))['target'] in (9,10)


def test_old_column_and_notice_exactly_reproduce_v29_and_direct_runner():
 r,gs,ms=build_spec(C);g=gs[0];m=ms[0];seed=193000000
 s=opening(r,g,m,seed,d);a=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
 b=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
 assert a.transcript==b.transcript
 row=simulate(r,g,m,seed);assert row['trace_hash']==hash_events(a.transcript)
 grouped=column_job(('smoke',r,(g,),m,seed,1))[0]
 assert grouped['samples'][0]['trace_hash']==row['trace_hash']


def test_q_remains_configurable_but_has_no_optional_node_after_police_died():
 s,G,M=case();g=G['relay_guard'];m=M['late_old'];out=[]
 for q in ['0','1/2','1']:
  out.append(continue_game(s,replace(g,response_probability=q),m,193000001,trace=True,decision_api=d,public_ballots=True).transcript)
 assert out[0]==out[1]==out[2]
