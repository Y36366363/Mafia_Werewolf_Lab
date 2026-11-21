from dataclasses import replace
from random import Random

from mafia_lab.engine import Message, PublicEvent, Role
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.returning_sources_v47 import ReturningSourcesAPI, compare_sources, original_pair
from test_formal_source_conflict_v39 import POLICY, sample


def test_only_completed_prior_first_ballot_can_affect_consistency_priority():
    reports = (Message(0,'report',9,True,'day',1),Message(4,'report',11,True,'day',1),
               Message(0,'accuse',9,context='day',day=1),Message(4,'accuse',11,context='day',day=1),
               Message(0,'report',10,False,'day',2),Message(4,'report',12,True,'day',2),
               Message(0,'accuse',9,context='day',day=2),Message(4,'accuse',12,context='day',day=2))
    obs = replace(sample(),messages=reports,public_events=(PublicEvent('vote',1,ballots=((0,9),(4,11))),))
    pair = original_pair(obs)
    old = compare_sources(obs,explain(obs,POLICY,retain=True),pair)
    assert old['fresh'] == [0,4] and old['preferred'] is None
    changed = replace(obs,public_events=(PublicEvent('vote',1,ballots=((0,9),(4,13))),
                PublicEvent('pk_vote',1,ballots=((0,11),(4,11))),
                PublicEvent('live_vote',2,player=4,ballots=((4,12),))))
    new = compare_sources(changed,explain(changed,POLICY,retain=True),pair)
    assert new['preferred'] == 0 and new['flags'][4] == ['prior_call_ballot_mismatch']
    assert original_pair(replace(obs,alive=tuple(p for p in obs.alive if p!=4))) == ()


def test_night_plan_does_not_change_after_true_report_becomes_public():
    api = ReturningSourcesAPI('ordinary',False,'1/2','prepared','consistency')
    api.pair = (0,4)
    first = (Message(0,'report',9,True,'day',1),Message(4,'report',11,True,'day',1))
    night = replace(sample(4),day=1,messages=first)
    api.prepare_bluff(night,4,10,Random(3))
    obs = replace(night,day=2,alive=tuple(p for p in night.alive if p!=10))
    plan = api.message(obs,POLICY,Random(8))
    assert obs.role == Role.MAFIA and plan.target not in {4,5,6,7,9,10,11}
    changed = replace(obs,messages=first+(Message(0,'report',plan.target,not plan.verdict,'day',2),))
    assert api.message(changed,POLICY,Random(12)) == plan
