from dataclasses import replace

from mafia_lab.corroborated_hit_v44 import common_hit, projected_support
from mafia_lab.engine import Message
from test_formal_source_conflict_v39 import POLICY, sample


def test_common_report_survives_conflicting_calls_but_respects_private_and_pk():
    initial = sample(15)
    obs = replace(initial, messages=(
        Message(0, 'report', 9, True, 'day', 2),
        Message(4, 'report', 9, True, 'day', 2),
        Message(0, 'accuse', 9, context='day', day=2),
        Message(4, 'accuse', 11, context='day', day=2),
    ))
    info = dict(sources=[0, 4], legal=list(obs.alive), known_good=[15], known_bad=[])
    assert common_hit(obs, info) == 9
    assert common_hit(obs, dict(info, known_bad=[4])) is None
    assert common_hit(obs, dict(info, legal=[0, 4, 11])) is None
    assert common_hit(obs, dict(info, sources=[0])) is None
    disputed = replace(obs, messages=(*obs.messages, Message(4, 'report', 9, False, 'day', 1)))
    assert common_hit(disputed, info) is None


def test_projection_uses_only_public_history_and_current_hypothetical_call():
    obs = sample(0)
    call = Message(0, 'accuse', 4, context='day', day=2)
    result = projected_support(obs, POLICY, (call,), 0, {4, 5}, False)
    altered = replace(obs, investigations=())
    assert projected_support(altered, POLICY, (call,), 0, {4, 5}, False) == result
    assert set(result) == {4, 5}
