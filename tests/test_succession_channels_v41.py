from dataclasses import replace

from mafia_lab.engine import Message
from mafia_lab.succession_channels_v41 import masked_explain
from test_formal_source_conflict_v39 import POLICY, sample


def test_same_report_can_admit_source_without_adding_its_edge_and_vice_versa():
    obs = sample()
    report = Message(4, 'report', 9, True, 'day', 2)
    obs = replace(obs, messages=(obs.messages[1], report, obs.messages[2], obs.messages[3]))
    for gate in (False, True):
        for conflict in (False, True):
            info = masked_explain(obs, POLICY, None, {report}, gate, conflict)
            assert (4 in info['proposal_sources']) == gate
            assert ((0, 4) in info['active_edges']) == conflict
            assert info['target'] in info['legal']


def test_private_rebuttal_survives_both_masks():
    obs = sample()
    report = Message(4, 'report', obs.player, True, 'day', 2)
    obs = replace(obs, messages=(*obs.messages, report))
    info = masked_explain(obs, POLICY, None, {report}, False, False)
    assert info['known_bad'] == [4]
    assert info['target'] == 4
