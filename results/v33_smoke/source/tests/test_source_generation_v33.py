import json
from pathlib import Path
from dataclasses import replace
from random import Random
from mafia_lab.engine import Role,Message,from_roles,resolve_night,observe
from mafia_lab.source_generation_v33 import GenerationAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.source_hypotheses_v32 import ResponseAPI

C=json.loads(Path('configs/unresolved_conflict_v31.json').read_text())
R,GS,MS=build_spec(C);G=GS[-1];M=next(m for m in MS if m.name=='false_grant')

def scene(dead=0,player=1,threat=True,target=1):
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),dead,8)
 rows=[Message(dead,'report',8,False,'last_words',1)]
 if threat:rows.append(Message(5,'report',target,True,'day',1))
 return replace(observe(s,player),messages=tuple(rows))


def test_dead_team_self_hit_response_is_truthful_and_optional_mode_differs():
 o=scene()
 assert GenerationAPI('hide').message(o,G,Random(0)).kind=='pass'
 for mode in ('self','available'):
  m=GenerationAPI(mode).message(o,G,Random(0));assert (m.kind,m.target,m.verdict)==('report',8,False)


def test_team_hit_does_not_recruit_other_police_in_self_mode():
 o=scene(target=3)
 assert GenerationAPI('self').message(o,G,Random(0)).kind=='pass'
 assert GenerationAPI('available').message(o,G,Random(0)).kind=='report'


def test_prior_live_team_report_prevents_second_ordinary_spokesperson():
 o=scene();o=replace(o,messages=o.messages+(Message(2,'report',8,False,'day',1),))
 for mode in ('self','available'):assert GenerationAPI(mode).message(o,G,Random(0)).kind=='pass'


def test_without_prior_threat_no_forced_response_after_dead_team_report():
 o=scene(threat=False)
 for mode in ('hide','self','available'):assert GenerationAPI(mode).message(o,G,Random(0)).kind not in {'report','police'}


def test_later_false_claim_not_available_to_earlier_police():
 o=scene(threat=False)
 assert GenerationAPI('available').message(o,G,Random(0)).kind=='pass'
 later=replace(o,player=2,teammates=(0,1,3),messages=o.messages+(Message(5,'report',3,True,'day',1),))
 assert GenerationAPI('available').message(later,G,Random(0)).kind=='report'


def test_hide_exactly_preserves_v32_message():
 for dead in (0,4):
  for target in (1,3,9):
   o=scene(dead=dead,target=target)
   assert GenerationAPI('hide').message(o,G,Random(9))==ResponseAPI(True).message(o,G,Random(9))


def test_early_late_cooperation_uses_own_team_order_and_no_extra_claimants():
 o=scene(dead=4,player=5);o=replace(o,messages=o.messages[:1])
 for plan in ('copy_early','copy_late','hit_early','hit_late'):
  api=GenerationAPI('hide',plan);speaker=api.collaborator(o)
  assert speaker==(7 if plan.endswith('late') else 5)
  m=api.message(replace(o,player=speaker,teammates=tuple(p for p in (4,5,6,7) if p!=speaker)),M,Random(1))
  assert m.kind=='report' and m.verdict==plan.startswith('hit_')
  if m.verdict:assert m.target not in {4,5,6,7,8}
  else:assert m.target==8
  for other in {5,6,7}-{speaker}:assert api.message(replace(o,player=other,teammates=tuple(p for p in (4,5,6,7) if p!=other)),M,Random(1)).kind=='pass'


def test_two_mafia_can_fabricate_shared_mafia_gold():
 o=scene(dead=4,player=4);api=GenerationAPI('hide','copy_team')
 dead=api.message(o,M,Random(1),'last_words');assert dead.target==5 and not dead.verdict
 liveobs=replace(o,player=6,teammates=(4,5,7),messages=(dead,));speaker=api.collaborator(liveobs)
 assert speaker!=dead.target
 live=api.message(replace(liveobs,player=speaker,teammates=tuple(p for p in (4,5,6,7) if p!=speaker)),M,Random(1))
 assert live.target==dead.target and not live.verdict
 assert api.after_last_words(o,M,Random(1))[1].target==dead.target


def test_votes_keep_private_refutation_and_pk_legality():
 from mafia_lab import strategies_v31 as base
 for role_player in (1,9):
  o=scene(player=role_player,target=role_player)
  for mode in ('hide','self','available'):
   for candidates in (None,(5,10),(8,10)):
    assert GenerationAPI(mode).vote(o,G,Random(2),candidates)==base.vote(o,G,Random(2),candidates)
