from dataclasses import replace

from mafia_lab.engine import PublicEvent
from mafia_lab.response_cost_v50 import loses_prefix_lead
from test_formal_source_conflict_v39 import sample


def test_cost_gate_reads_only_already_visible_first_ballots():
    live = PublicEvent('live_vote',1,player=6,ballots=((6,12),))
    obs = replace(sample(5),day=1,public_events=(live,))
    assert not loses_prefix_lead(obs,12,0)
    second = PublicEvent('live_vote',1,player=7,ballots=((7,0),))
    later = PublicEvent('vote',1,ballots=((15,12),(13,12)))
    pk = PublicEvent('live_pk_vote',1,player=9,ballots=((9,12),))
    obs = replace(obs,public_events=(live,second,later,pk))
    assert loses_prefix_lead(obs,12,0)
    assert not loses_prefix_lead(obs,0,0)
    assert not loses_prefix_lead(obs,None,0)
