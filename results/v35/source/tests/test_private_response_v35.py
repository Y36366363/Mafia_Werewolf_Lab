import json
from pathlib import Path
from random import Random
from dataclasses import replace
import pytest
from mafia_lab.engine import from_roles,resolve_night,observe,Message,Role
from mafia_lab.private_response_v35 import PrivateResponseAPI,private_branch
from mafia_lab.day1_risk_v34 import RiskAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec

C=json.loads(Path('configs/unresolved_conflict_v31.json').read_text());R,GS,MS=build_spec(C);G=GS[-1]


def observation(dead=4,player=0,claim=True):
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),dead,8)
 rows=(Message(dead,'report',8,False,'last_words',1),) if claim else ()
 return replace(observe(s,player),messages=rows)


def test_branch_uses_police_team_not_role_oracle():
 assert private_branch(observation())
 assert private_branch(observation(dead=0,player=1)) is None
 assert private_branch(observation(player=10)) is None
 assert private_branch(observation(claim=False)) is None
 assert private_branch(replace(observation(),day=2)) is None


def test_q_endpoints_after_dead_false_claim_without_live_threat():
 o=observation()
 assert PrivateResponseAPI(q='0').message(o,G,Random(1)).kind=='pass'
 m=PrivateResponseAPI(q='1').message(o,G,Random(1));assert (m.kind,m.target,m.verdict)==('report',8,False)


def test_only_first_police_turn_draws_even_after_failed_draw():
 o=observation();a=PrivateResponseAPI(q='1/2')
 first=a.message(o,G,Random(0));assert first.kind=='pass'
 nextobs=replace(o,player=1,teammates=(0,2,3),messages=o.messages+(first,))
 assert a.message(nextobs,G,Random(1)).kind=='pass'
 assert [x['reason'] for x in a.response_audit]==['single_local_draw','no_second_draw']
 assert sum(x['draw'] is not None for x in a.response_audit)==1


def test_self_hit_after_failed_draw_is_defense_not_retry():
 o=observation();a=PrivateResponseAPI(q='0');first=a.message(o,G,Random(0))
 later=replace(o,player=1,teammates=(0,2,3),messages=o.messages+(first,Message(5,'report',1,True,'day',1)))
 assert a.message(later,G,Random(3)).kind=='report'
 assert a.response_audit[-1]['reason']=='mandatory_self_defense' and a.response_audit[-1]['draw'] is None


def test_public_team_blocks_another_response_even_if_self_hit():
 o=observation(player=1);o=replace(o,messages=o.messages+(Message(0,'report',8,False,'day',1),Message(5,'report',1,True,'day',1)))
 assert PrivateResponseAPI(q='1').message(o,G,Random(0)).kind=='pass'


def test_no_tuning_true_dead_cop_branch_or_pk():
 for context in ('day','pk'):
  o=observation(dead=0,player=1)
  for q in ('0','1/2','1'):
   a=PrivateResponseAPI(q=q);b=RiskAPI('self')
   assert a.message(o,G,Random(3),context)==b.message(o,G,Random(3),context)
   assert not a.response_audit


def test_half_probability_is_actor_local_fixed_randomness():
 o=observation();reports=[]
 for seed in (0,1):
  a=PrivateResponseAPI(q='1/2');m=a.message(o,G,Random(seed));reports.append(m.kind)
  assert (m.kind=='report')==(a.response_audit[0]['draw']<.5)
 assert set(reports)=={'pass','report'}


def test_legacy_keeps_original_draw_consumption_and_action():
 for dead in (0,4):
  o=observation(dead=dead,player=1)
  a,b=Random(9),Random(9)
  assert PrivateResponseAPI(q=None).message(o,G,a)==RiskAPI('self').message(o,G,b)
  assert a.getstate()==b.getstate()


def test_votes_preserve_private_facts_and_pk_and_day_two():
 for player in (0,10):
  o=observation(player=player);o=replace(o,messages=o.messages+(Message(5,'report',player,True,'day',1),))
  for day in (1,2):
   for candidates in (None,(5,9),(8,9)):
    assert PrivateResponseAPI(q='1').vote(replace(o,day=day),G,Random(3),candidates)==RiskAPI('self').vote(replace(o,day=day),G,Random(3),candidates)


def test_civilian_observation_cannot_obtain_private_branch_from_same_history():
 o=observation();civil=replace(o,player=10,role=Role.CIVILIAN,teammates=(),investigations=())
 assert private_branch(civil) is None


def test_invalid_q_rejected():
 for q in ('-1/2','3/2'):
  with pytest.raises(ValueError):PrivateResponseAPI(q=q)
