import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from random import Random
from mafia_lab import strategies_v26 as d
from mafia_lab import strategies_v25 as previous
from mafia_lab.engine import Message,PublicEvent,Role,add_message,from_roles,observe,resolve_night
from mafia_lab.police_execution_experiment_v26 import build_spec,evaluate,contrasts,simulate
from mafia_lab.simulation import opening,continue_game
C=json.loads(Path('configs/police_execution_v26.json').read_text())


def case():
 r,gs,ms=build_spec(C)
 s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,4)
 s=resolve_night(s,14,5)
 s=add_message(s,Message(0,'report',5,True,'day',2))
 return s,{g.name:g for g in gs},ms


def test_execution_preserves_report_and_shortlist_and_calls_intended_known_mafia():
 s,gs,_=case();g=gs['aligned_q50'];o=observe(s,0)
 old=previous.after_speech(o,g,Random(1));parts=d.after_speech(o,g,Random(1))
 assert isinstance(parts,tuple) and parts[:-1]==(old,)
 assert old.kind=='shortlist' and parts[-1].kind=='accuse'
 assert s.messages[-1]==Message(0,'report',5,True,'day',2)
 assert parts[-1].target in previous.explain(o,g)['known_bad']
 for part in parts:s=add_message(s,part)
 for p in (0,1,2,3):
  info=d.explain(observe(s,p),g)
  assert info['target']==parts[-1].target and info['followed_team_call']
 assert d.explain(observe(s,9),g)['target']==parts[-1].target


def test_call_cannot_override_private_fact_or_pk_legality_or_recruit_second_reporter():
 s,gs,_=case();g=gs['aligned_q50'];o=observe(s,0)
 for msg in d.after_speech(o,g,Random(1)):s=add_message(s,msg)
 called=d.team_execution_call(observe(s,1)).target
 other=next(p for p in (4,5) if p!=called)
 assert d.explain(observe(s,1),g,[other])['target']==other
 bogus=replace(s,messages=(Message(0,'report',5,True,'day',2),Message(0,'accuse',8,context='day',day=2)))
 assert d.explain(observe(bogus,1),g)['target'] in {4,5}
 assert not d.explain(observe(bogus,1),g)['followed_team_call']
 assert d.message(observe(s,1),g,Random(2))==previous.message(observe(s,1),g,Random(2))


def test_vote_history_uses_only_completed_round_and_evidence_before_vote():
 s,gs,_=case();g=gs['history_q50']
 # Civilian8 was falsely checked by mafia4 in day1. First completed day1 vote.
 msgs=(Message(4,'report',8,True,'day',1),)
 vote=PublicEvent('vote',1,ballots=((5,8),(6,4),(7,None)))
 partial=PublicEvent('live_vote',2,player=5,ballots=((5,8),))
 o=replace(observe(s,8),messages=msgs,public_events=(vote,partial))
 scores,details=d.vote_history_counts(o,g)
 assert scores[5]==1 and scores[6]==-1 and scores[7]==0
 assert len(details)==2
 # Later inspections and post-vote last words must not leak into old vote.
 later=replace(o,investigations=s.investigations,messages=msgs+(Message(6,'report',8,True,'last_words',1),))
 assert d.vote_history_counts(later,g)==(scores,details)
 pk=PublicEvent('pk_vote',1,ballots=((5,4),(6,4),(7,None)))
 score2,_=d.vote_history_counts(replace(o,public_events=(vote,pk)),g)
 assert score2[5]==-1 and score2[6]==-1  # one day, not first+PK sum


def test_public_report_unproved_good_is_not_private_good_and_death_is_not_identity():
 s,gs,_=case();o=replace(observe(s,9),messages=(Message(0,'report',8,False,'day',1),),
 public_events=(PublicEvent('vote',1,ballots=((5,8),(6,4))),))
 scores,_=d.vote_history_counts(o,gs['history_q50'])
 assert scores[5]==scores[6]==0
 # A death of a target alone does not assign a side or change these counts.
 assert d.vote_history_counts(replace(o,day=3),gs['history_q50'])[0]==scores


def test_history_cannot_override_known_bad_single_call_or_clear_protection():
 s,gs,_=case();g=gs['history_q50'];o=observe(s,0)
 parts=d.after_speech(o,g,Random(1))
 for p in parts:s=add_message(s,p)
 o=observe(s,1);info=d.explain(o,g)
 assert info['target'] in info['known_bad'] and not info['history_changed']
 civilian=d.explain(observe(s,9),g)
 assert civilian['target']==parts[-1].target and not civilian['history_changed']


def test_unknown_roles_do_not_change_civilian_observation_or_history_action():
 s,gs,_=case();roles=list(s.roles);roles[1],roles[10]=roles[10],roles[1]
 t=replace(s,roles=tuple(roles));a,b=observe(s,9),observe(t,9)
 assert a==b
 assert d.vote(a,gs['history_q50'],Random(1))==d.vote(b,gs['history_q50'],Random(1))


def test_costless_bus_requires_worst_case_irreversible_teammate_exile():
 s,_,ms=case();m=next(m for m in ms if m.vote_mode=='costless_bus');o=observe(s,7)
 o=replace(o,last_anchor=7)
 # Voting order from8, actor7 is last overall; legal prior ballots force mafia4 out.
 voters=[p for p in o.alive if p!=7]
 events=tuple(PublicEvent('live_vote',2,player=p,ballots=((p,4 if p!=4 else 8),)) for p in voters)
 ready=replace(o,public_events=events)
 assert d.costless_bus_target(ready,m)==4
 assert d.costless_bus_target(replace(o,public_events=events[:1]),m) is None
 assert d.costless_bus_target(ready,replace(m,vote_mode='team')) is None
 # There is no permission to vote self or to bus outside PK candidates.
 assert d.costless_bus_target(ready,m,[8,9]) is None


def test_control_and_unwrapped_execution_replay_and_smoke_contracts():
 r,gs,ms=build_spec(C);G={g.name:g for g in gs};M={m.name:m for m in ms}
 for gn in ('legacy_q50','aligned_q50','history_q50'):
  mn='late_far_claim_team';g,m=G[gn],M[mn];seed=181000000
  s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
  assert sha256(repr(o.transcript).encode()).hexdigest()==simulate(r,g,m,seed)['trace_hash']
  if gn=='legacy_q50':
   old=continue_game(s,g,m,seed,trace=True,decision_api=previous,public_ballots=True)
   assert old.transcript==o.transcript
 rows=[evaluate(('smoke',r,G[gn],M[mn],181000000,2)) for gn,mn in C['cells']]
 assert sum(v['primary'] for v in contrasts(rows))==8
 for row in rows:
  for flag in ('orphan','stale','ignored_known','voted_good','illegal','call_mismatch'):assert sum(row['raw'][flag+'_ballots'])==0
