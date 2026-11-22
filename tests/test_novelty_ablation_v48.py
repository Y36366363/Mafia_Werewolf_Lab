from dataclasses import replace

from mafia_lab.engine import Message, PublicEvent
from mafia_lab.novelty_ablation_v48 import corroborated_challenges
from test_formal_source_conflict_v39 import sample


def test_challenge_requires_post_claim_speech_and_a_completed_first_ballot():
    hit = Message(4,'report',11,True,'day',1)
    challenge = Message(11,'nominate',4,context='day',day=1)
    first = PublicEvent('vote',1,ballots=((11,4),))
    obs = replace(sample(),messages=(hit,challenge),public_events=(first,))
    assert corroborated_challenges(obs,(0,4)) == {0:[],4:[11]}
    prefix = replace(obs,messages=(challenge,hit))
    assert corroborated_challenges(prefix,(0,4)) == {0:[],4:[]}
    pk = PublicEvent('pk_vote',1,ballots=((11,4),))
    unclosed = PublicEvent('live_vote',1,player=11,ballots=((11,4),))
    future = PublicEvent('vote',2,ballots=((11,4),))
    assert corroborated_challenges(replace(obs,public_events=(pk,unclosed,future)),(0,4)) == {0:[],4:[]}


def test_criticizing_both_claimants_does_not_make_either_witness_more_independent():
    reports = (Message(0,'report',11,True,'day',1),Message(4,'report',12,True,'day',1))
    replies = (Message(11,'nominate',0,context='day',day=1),
               Message(12,'nominate',4,context='day',day=1))
    first = PublicEvent('vote',1,ballots=((11,0),(12,4)))
    obs = replace(sample(),messages=(*reports,*replies),public_events=(first,))
    assert corroborated_challenges(obs,(0,4)) == {0:[11],4:[12]}
