import json
from pathlib import Path
from dataclasses import replace
from random import Random
from mafia_lab.engine import from_roles,resolve_night,observe,Message,Role
from mafia_lab.day1_risk_v34 import RiskAPI,explain,public_context
from mafia_lab.source_generation_v33 import GenerationAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab import strategies_v31 as base

C=json.loads(Path('configs/unresolved_conflict_v31.json').read_text());R,GS,MS=build_spec(C);G=GS[-1];M=next(m for m in MS if m.name=='false_grant')

def scenario(fake=False,player=15):
 dead=4 if fake else 0
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),dead,8)
 rows=(Message(dead,'report',8,False,'last_words',1),Message(dead,'delegate',8,context='last_words',day=1,targets=(9,10)),Message(5,'report',8,False,'day',1))
 return replace(observe(s,player),messages=rows)


def test_public_gold_conditions_use_entire_current_prefix():
 o=scenario();assert public_context(o)['eligible']
 for m,reason in [(Message(6,'report',9,False,'day',1),'different_report'),(Message(6,'report',8,True,'day',1),'different_report'),(Message(6,'police',day=1),'unresolved_bare_claim')]:
  c=public_context(replace(o,messages=o.messages+(m,)));assert not c['eligible'] and reason in c['blocks']


def test_true_police_can_challenge_sources_even_while_confirming_same_gold():
 o=scenario();o=replace(o,messages=o.messages+(Message(1,'report',8,False,'day',1),Message(1,'accuse',5,day=1)))
 assert 'source_challenge' in public_context(o)['blocks']


def test_conditional_gold_requires_actual_matching_relay_and_checks_issue_prefix():
 o=scenario();assert not explain(o,G,'conditional_gold')['risk_applied']
 relay=Message(8,'relay',10,day=1,targets=(0,))
 a=replace(o,messages=o.messages+(relay,));v=explain(a,G,'conditional_gold');assert v['target']==10 and v['risk_applied']
 b=replace(a,messages=a.messages+(Message(6,'report',9,False,'day',1),))
 assert not explain(b,G,'conditional_gold')['risk_applied']
 # Grant after relay cannot authorize that earlier call.
 late=replace(o,messages=(o.messages[0],o.messages[2],relay,o.messages[1]));assert not explain(late,G,'conditional_gold')['risk_applied']


def test_first_live_does_not_mean_last_responder():
 o=scenario();o=replace(o,messages=o.messages+(Message(6,'report',9,True,'day',1),))
 assert explain(o,G,'first_live')['target']==5


def test_private_refutation_overrides_both_public_controls():
 o=scenario(player=15);o=replace(o,messages=o.messages+(Message(6,'report',15,True,'day',1),Message(8,'relay',10,day=1,targets=(0,))))
 for receiver in ('first_live','conditional_gold'):
  v=explain(o,G,receiver);assert v['target']==6 and v['risk_block']=='private_refutation'


def test_pk_and_clear_protection_are_retained():
 o=scenario();assert not explain(o,G,'first_live',(9,10))['risk_applied']
 o=replace(o,messages=o.messages+(Message(6,'report',5,False,'day',1),))
 assert not explain(o,G,'first_live')['risk_applied']


def test_no_day_two_priority_and_police_keep_private_selector():
 for player in (1,15):
  o=scenario(player=player)
  for day in (1,2):
   p=replace(o,day=day)
   if player==15 and day==1:continue
   for receiver in ('first_live','conditional_gold'):
    a,b=explain(p,G,receiver),base.explain(p,G);assert a['target']==b['target'] and a['reason']==b['reason']


def test_gold_own_choice_does_not_validate_its_own_relay():
 o=scenario(player=8);o=replace(o,messages=o.messages+(Message(8,'relay',10,day=1,targets=(0,)),))
 assert not explain(o,G,'conditional_gold')['risk_applied']


def test_false_gold_has_same_relay_message_shape_and_can_decline():
 o=scenario(True,player=5)
 # In copy_team: dead4 -> gold5, another mafia6 copies it; choose nonmafia9.
 o=replace(o,messages=(Message(4,'report',5,False,'last_words',1),Message(4,'delegate',5,context='last_words',day=1,targets=(9,10)),Message(6,'report',5,False,'day',1),Message(6,'accuse',9,day=1)))
 assert RiskAPI('self','copy_team','original',False).final_call(o,M,Random(0)) is None
 call=RiskAPI('self','copy_team','original',True).final_call(o,M,Random(0));assert call==Message(5,'relay',9,day=1,targets=(4,))


def test_public_conditions_do_not_authenticate_hidden_roles():
 o=scenario();c=public_context(o);other=replace(o,teammates=())
 assert public_context(other)==c
 # The gate is a public function, independent of observer role and team.
 assert public_context(replace(o,role=Role.POLICE,teammates=(0,1,2)))==c


def test_original_preserves_v33_votes_and_final_call():
 for p in (1,8,15):
  o=scenario(player=p)
  a=RiskAPI('self','ordinary','original');b=GenerationAPI('self','ordinary')
  assert a.vote(o,G,Random(9))==b.vote(o,G,Random(9))
  assert a.final_call(o,G,Random(9))==b.final_call(o,G,Random(9))


def test_new_pk_report_revokes_gold_priority_without_changing_first_source():
 o=scenario();o=replace(o,messages=o.messages+(Message(8,'relay',10,day=1,targets=(0,)),Message(6,'report',9,False,'pk',1)))
 c=public_context(o);assert not c['eligible'] and c['first_live']==5
 assert not explain(o,G,'conditional_gold',(5,10))['risk_applied']
