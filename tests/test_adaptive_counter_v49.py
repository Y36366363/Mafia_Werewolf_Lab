from dataclasses import replace
from random import Random

from mafia_lab.adaptive_counter_v49 import AdaptiveCounterAPI, backed_alternative, counter_options
from mafia_lab.engine import Message, PublicEvent
from mafia_lab.strategies_v30 import MafiaPolicyV30
from test_formal_source_conflict_v39 import sample


def test_countervote_needs_a_visible_hit_before_the_players_nomination():
    hit = Message(0,'report',5,True,'day',1)
    nomination = Message(5,'nominate',0,context='day',day=1)
    obs = replace(sample(5),day=1,messages=(hit,))
    assert counter_options(obs)==(0,)
    api = AdaptiveCounterAPI('ordinary',False,'1/2',True,'neutral',False)
    policy = MafiaPolicyV30(name='test',response='forward')
    parts = api.after_speech(obs,policy,Random(1))
    assert nomination in parts
    assert api.vote(replace(obs,messages=(hit,nomination)),policy,Random(2))==0
    before = len(api.counter_ballots)
    api.vote(replace(obs,messages=(nomination,hit)),policy,Random(2))
    assert len(api.counter_ballots)==before


def test_backed_target_excludes_mafia_votes_planned_night_victim_and_this_clear():
    votes = PublicEvent('vote',1,ballots=((1,12),(2,12),(3,0),(5,13),(6,13),
                                         (9,14),(10,14),(11,14)))
    obs = replace(sample(4),day=1,messages=(),public_events=(votes,))
    result = backed_alternative(obs,(0,4),4,14,15)
    assert result==dict(target=12,voters=[1,2],rival=0,rival_voters=[3])
    assert backed_alternative(obs,(0,4),4,14,12) is None
    assert backed_alternative(replace(obs,public_events=(replace(votes,kind='pk_vote'),)),(0,4),4,14,15) is None
