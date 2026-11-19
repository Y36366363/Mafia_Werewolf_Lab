from dataclasses import replace

from mafia_lab.continuation_audit_v45 import ContinuationAuditAPI, replace_public_report
from mafia_lab.engine import Investigation, Message, Role
from test_formal_source_conflict_v39 import POLICY, sample


def test_public_replacement_preserves_observer_private_information_and_calls():
    old = Message(0, 'report', 9, True, 'day', 2)
    new = replace(old, target=11, verdict=False)
    call = Message(0, 'accuse', 9, context='day', day=2)
    obs = replace(sample(15), messages=(old, call))
    changed = replace_public_report(obs, old, new)
    assert changed.messages == (new, call)
    assert changed.investigations == obs.investigations == ()
    assert changed.teammates == obs.teammates == ()
    assert changed.public_events == obs.public_events
    assert obs.messages == (old, call)


def test_shadow_retains_private_refutation_and_excludes_pk_intervention():
    old = Message(0, 'report', 9, True, 'day', 2)
    call = Message(0, 'accuse', 9, context='day', day=2)
    refuted = Message(4, 'report', 15, True, 'day', 2)
    voter = replace(sample(15), messages=(old, call, refuted))
    police = replace(sample(0), role=Role.POLICE,
                     investigations=(Investigation(1, 9, True), Investigation(2, 11, False)))
    api = ContinuationAuditAPI('ordinary', False, '1/2', True, True, True)
    api._message_records = [(police, old)]
    api._vote_records = [(voter, POLICY, None, 4),
                         (voter, POLICY, (9, 11), 9),
                         (replace(police, messages=voter.messages), POLICY, None, 9)]
    shadows = api.latest_report_shadow(2)
    assert len(shadows) == 1
    assert shadows[0]['ballots'] == [dict(player=15, role='civilian', before=4, after=4),
                                      dict(player=0, role='police', before=9, after=9)]
    assert api._vote_records[0][0].messages == (old, call, refuted)
    assert api.latest_report_shadow(3) == []
