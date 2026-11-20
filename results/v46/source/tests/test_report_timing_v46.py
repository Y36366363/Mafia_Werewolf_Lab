from dataclasses import replace

from mafia_lab.engine import Investigation, Message
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.report_timing_v46 import succession_warning, timing_choice
from test_formal_source_conflict_v39 import POLICY, sample


def test_later_live_echo_has_no_independent_priority_but_shared_hit_still_wins():
    a = Message(0, 'report', 10, False, 'day', 2)
    b = replace(a, speaker=4)
    calls = (Message(0, 'accuse', 4, context='day', day=2),
             Message(4, 'accuse', 11, context='day', day=2))
    obs = replace(sample(), messages=(a, b, *calls))
    assert timing_choice(obs, explain(obs,POLICY,retain=True)) == ('live_echo',0,4)
    shared = replace(obs, messages=(replace(a,verdict=True),replace(b,verdict=True),*calls))
    assert timing_choice(shared, explain(shared,POLICY,retain=True)) is None
    public_first = replace(obs, messages=(replace(a,speaker=8,context='last_words'),*obs.messages))
    assert timing_choice(public_first, explain(public_first,POLICY,retain=True)) is None
    refutation = replace(obs, messages=(Message(4,'report',15,True,'day',1),*obs.messages))
    assert timing_choice(refutation, explain(refutation,POLICY,retain=True)) is None


def test_returning_freshness_can_reward_a_distinct_false_report():
    history = (Message(0,'report',9,True,'day',1), Message(4,'report',11,True,'day',1))
    current = (replace(history[0], day=2), Message(4,'report',12,True,'day',2))
    calls = (Message(0,'accuse',9,context='day',day=2),
             Message(4,'accuse',11,context='day',day=2))
    obs = replace(sample(), messages=(*history,*current,*calls))
    assert timing_choice(obs, explain(obs,POLICY,retain=True)) == ('returning_fresh',4,11)


def test_risk_warning_needs_an_observed_old_threat_and_exactly_one_vote():
    messages = (Message(4,'report',11,True,'day',1),
                Message(0,'report',9,True,'day',2),
                Message(1,'report',9,True,'last_words',2))
    obs = replace(sample(0), messages=messages, investigations=(Investigation(2,9,True),))
    call = dict(original=9,target=4,predicted={9:7,4:8},known_bad=[4,9])
    assert succession_warning(obs, call)
    assert not succession_warning(replace(obs,messages=messages[1:]),call)
    assert not succession_warning(obs,dict(call,predicted={9:7,4:9}))
    assert not succession_warning(replace(obs,investigations=()),call)
