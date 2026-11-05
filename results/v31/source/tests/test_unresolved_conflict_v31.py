import json
from pathlib import Path
from dataclasses import replace
from random import Random
from mafia_lab import strategies_v31 as d
from mafia_lab import strategies_v30 as old
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec,simulate,column_job
from mafia_lab.engine import Message,Role,from_roles,resolve_night,observe,add_message,add_last_words_component
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events

C=json.loads(Path('configs/unresolved_conflict_v31.json').read_text())

def case(fake_dead=False,grant=True):
 r,gs,ms=build_spec(C);victim=4 if fake_dead else 0
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),victim,8)
 s=add_message(s,Message(victim,'report',8,False,'last_words',1))
 s=add_last_words_component(s,Message(victim,'shortlist',context='last_words',day=1,targets=(9,10)))
 if grant:s=add_last_words_component(s,Message(victim,'delegate',8,context='last_words',day=1,targets=(9,10)))
 return s,{g.name:g for g in gs},{m.name:m for m in ms}


def test_dead_live_incompatibility_no_longer_is_a_directive_against_live_source():
 s,G,_=case();s=add_message(s,Message(4,'report',9,True,'day',1))
 a=d.explain(observe(s,11),G['legacy']);b=d.explain(observe(s,11),G['neutral'])
 assert a['target']==4 and a['reason']=='compare_conflicting_sources'
 assert b['orphan_not_actionable'] and b['conflict_targets']==[] and b['live_edges']==[]
 assert b['reason']=='unresolved_conflict_proposals' and b['target'] in (9,10)
 assert b['known_bad']==[] and 8 not in b['known_good']


def test_grant_alone_cannot_change_neutral_decision_without_actual_relay():
 for fake in (False,True):
  a,G,_=case(fake,False);b,_,_=case(fake,True)
  a=add_message(a,Message(5,'report',9,False,'day',1));b=add_message(b,Message(5,'report',9,False,'day',1))
  for name in ('neutral','aligned'):
   x,y=d.explain(observe(a,11),G[name]),d.explain(observe(b,11),G[name])
   assert x['target']==y['target'] and x['reason']==y['reason']
   assert x['history_edges']==y['history_edges']


def test_fake_dead_grant_is_not_authenticated_and_can_be_declined_by_police():
 s,G,_=case(True);o=observe(s,8)
 assert d.gold.dead_offers(o,G['aligned'])
 assert not d.gold.dead_offers(observe(s,1),G['aligned'])
 v=d.explain(o,G['neutral']);assert v['known_bad']==[]
 # Re-label hidden police/civilian seats; civilian sees exactly same data.
 roles=list(s.roles);roles[1],roles[12]=roles[12],roles[1]
 other=observe(replace(s,roles=tuple(roles)),8);assert o==other
 assert d.vote(o,G['aligned'],Random(1))==d.vote(other,G['aligned'],Random(1))


def test_all_live_conflicts_remain_comparable_without_identity_certificate():
 s,G,_=case(False,False)
 s=add_message(s,Message(4,'report',9,True,'day',1))
 s=add_message(s,Message(5,'report',10,False,'day',1))
 v=d.explain(observe(s,11),G['neutral'])
 assert (4,5) in v['live_edges'] and v['target'] in (4,5)
 assert v['reason']=='compare_live_conflicting_sources' and not v['known_bad']


def test_private_refutation_and_pk_legality_override_any_public_intent():
 s,G,_=case();s=add_message(s,Message(4,'report',9,True,'day',1))
 s=add_message(s,Message(8,'relay',10,context='day',day=1,targets=(0,)))
 for name in G:
  v=d.explain(observe(s,1),G[name]);assert v['target']==4 and v['known_bad']==[4]
  assert d.explain(observe(s,11),G[name],(9,10))['target'] in (9,10)
 assert d.explain(observe(s,9),G['aligned'])['target']==4


def test_aligned_gold_uses_same_prefix_selector_and_does_not_self_validate():
 s,G,_=case();s=add_message(s,Message(4,'report',9,True,'day',1))
 o=observe(s,8);g=G['aligned'];target=d.explain(o,g)['target']
 call=d.final_call(o,g,Random(1));assert call.target==target
 t=add_message(s,call);later=d.explain(observe(t,8),g)
 assert later['target']==target and not later['dead_relay_admitted']
 # Bystanders receive the advice under source0, not as a new police source8.
 v=d.explain(observe(t,11),g);assert v['dead_relay_admitted']==1 and 8 not in v['sources']


def test_unrestricted_relay_scope_is_same_in_both_repaired_rows():
 s,G,_=case();s=add_message(s,Message(8,'relay',12,context='day',day=1,targets=(0,)))
 for name in ('neutral','aligned'):
  v=d.explain(observe(s,11),G[name]);assert v['proposals']['0']==[12] and v['target']==12


def test_police_public_intent_preserves_report_and_follows_known_bad_team_call():
 s,G,M=case(fake_dead=True);s=add_message(s,Message(5,'report',9,True,'day',1))
 # Police1 publishes its own genuine first check8-good then explicitly calls.
 s=add_message(s,Message(1,'report',8,False,'day',1));g=G['aligned']
 parts=d.after_speech(observe(s,1),g,Random(1));parts=parts if isinstance(parts,tuple) else (parts,)
 calls=[m for m in parts if m is not None and m.kind=='accuse'];assert len(calls)==1
 for m in parts:
  if m is not None:s=add_message(s,m)
 for p in (1,2,3):
  v=d.explain(observe(s,p),g);assert v['target']==calls[0].target and v['target'] in v['known_bad']
 assert any(m.kind=='report' and m.speaker==1 for m in s.messages)
 # A PK excluding the announced target must not vote illegally.
 assert d.explain(observe(s,2),g,(9,10))['target'] in (9,10)


def test_true_dead_police_does_not_recruit_live_police_but_false_dead_may():
 for fake in (False,True):
  s,G,M=case(fake_dead=fake);g=G['aligned'];msgs=[]
  for p in ((0,1,2,3) if fake else (1,2,3)):msgs.append(d.message(observe(s,p),g,Random(1),'day').kind)
  if not fake:assert all(k!='report' for k in msgs)
  # This checks the existing selfkill scenario's ordinary spokesperson, not an
  # added permission to infer the victim's faction for civilian observers.
  else:assert 'report' in msgs


def test_future_messages_cannot_change_past_observation_and_day2_unchanged():
 s,G,_=case();o=observe(s,11);g=G['neutral'];before=d.explain(o,g)
 t=add_message(s,Message(4,'report',9,True,'day',1));assert d.explain(o,g)==before
 assert d.explain(observe(t,11),g)['history_edges']
 late=replace(o,day=2);assert d.explain(late,g)['target']==old.explain(late,g)['target']


def test_legacy_and_direct_grouped_runs_reproduce_previous_api():
 r,gs,ms=build_spec(C);g=gs[0];m=ms[0];seed=C['smoke']['seed_start']
 s=opening(r,g,m,seed,d);a=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
 b=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True);assert a.transcript==b.transcript
 row=simulate(r,g,m,seed);group=column_job(('smoke',r,(g,),m,seed,1))[0]
 assert row['trace_hash']==hash_events(a.transcript)==group['samples'][0]['trace_hash']


def test_q_still_available_and_absent_at_true_dead_police_optional_node():
 s,G,M=case();out=[]
 for q in ('0','1/2','1'):
  out.append(continue_game(s,replace(G['aligned'],response_probability=q),M['late_old'],196000001,trace=True,decision_api=d,public_ballots=True).transcript)
 assert out[0]==out[1]==out[2]
