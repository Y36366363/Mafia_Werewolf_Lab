from dataclasses import replace
from random import Random
import json
from pathlib import Path
from mafia_lab.engine import from_roles,resolve_night,observe,Message
from mafia_lab.continuation_audit_v36 import ContinuationAuditAPI,observation_view,public_gold_links,classify_hit_vote
from mafia_lab.private_response_v35 import PrivateResponseAPI
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
C=json.loads(Path('configs/unresolved_conflict_v31.json').read_text());R,GS,MS=build_spec(C);G=GS[-1];M=next(m for m in MS if m.name=='false_grant')


def scenario():
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),4,5)
 rows=(Message(4,'report',8,False,'last_words',1),Message(0,'report',5,True,'day',1))
 return replace(observe(s,10),messages=rows)


def test_ledger_retains_dead_sources_without_authentication():
 o=scenario();links=public_gold_links(o)
 assert links==[dict(source=4,target=8,day=1,context='last_words',source_alive=False,target_alive=True)]
 assert public_gold_links(replace(o,day=3))==links


def test_view_uses_only_same_civilian_observation():
 o=scenario();a=observation_view(o,G);b=observation_view(replace(o,teammates=(),investigations=()),G)
 assert a==b and a['known_bad']==[]


def test_no_automatic_dead_source_authentication():
 v=observation_view(scenario(),G)
 assert v['known_bad']==[] and 8 not in v['known_good']


def test_classification_separates_legality_and_private_facts():
 v=dict(legal=[5,6],target=6,known_bad=[6],known_good=[],excluded_sources=[],guarded=[5,6],proposal_sources=[0],proposals={'0':[5]},reason='private_refutation_or_check')
 assert classify_hit_vote(v,0,5)=='other_private_bad'
 assert classify_hit_vote(v,0,8)=='target_not_legal'
 assert classify_hit_vote(dict(v,target=5),0,5)=='aligned_with_hit'


def test_old_history_is_not_current_instruction():
 v=dict(legal=[5,6],target=6,known_bad=[],known_good=[],excluded_sources=[],guarded=[5,6],proposal_sources=[],proposals={'0':[]},reason='position_fallback')
 assert classify_hit_vote(v,0,5)=='no_current_proposal_from_source'
 assert classify_hit_vote(dict(v,proposals={'0':[6]},proposal_sources=[0]),0,5)=='source_proposes_other_target'


def test_instrumentation_preserves_random_stream_and_action():
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),4,5)
 o=replace(observe(s,0),messages=scenario().messages[:1]);a,b=Random(1),Random(1)
 assert ContinuationAuditAPI('copy_early',q='1/2').message(o,G,a)==PrivateResponseAPI('copy_early',q='1/2').message(o,G,b)
 assert a.getstate()==b.getstate()


def test_full_replay_shadow_does_not_change_trace():
 for q in ('0','1/2'):
  seed=207000002;api=ContinuationAuditAPI('copy_early',q=q);s=opening(R,G,M,seed,api)
  a=continue_game(s,G,M,seed,trace=True,decision_api=api,public_ballots=True)
  baseline=PrivateResponseAPI('copy_early',q=q);s=opening(R,G,M,seed,baseline)
  b=continue_game(s,G,M,seed,trace=True,decision_api=baseline,public_ballots=True)
  assert hash_events(a.transcript)==hash_events(b.transcript)
  assert api.audit_rounds and api.audit_votes
