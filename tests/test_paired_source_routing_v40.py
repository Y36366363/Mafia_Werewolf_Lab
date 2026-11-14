from dataclasses import replace

from mafia_lab.engine import Message
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.paired_source_routing_v40 import paired_targets
from test_formal_source_conflict_v39 import POLICY, sample


def test_mapping_uses_the_same_source_comparison_then_follows_opposite_call():
    obs = sample()
    info = explain(obs, POLICY, retain=True)
    pair = paired_targets(obs, POLICY, info)
    assert pair['source_exile'] == 0
    assert pair['backing'] == 4
    assert pair['mapped'] == 11
    assert pair['calls'] == {0: 4, 4: 11}


def test_mapping_requires_both_actions_legal_and_ignores_soft_lists():
    obs = sample()
    assert paired_targets(obs, POLICY, explain(obs, POLICY, (0, 4), True)) is None
    assert paired_targets(obs, POLICY, explain(obs, POLICY, retain=True) | {'known_bad': [4]}) is None
    soft = replace(obs, messages=(*obs.messages[:2],
        Message(0, 'shortlist', context='day', day=2, targets=(4,)), obs.messages[-1]))
    assert paired_targets(soft, POLICY, explain(soft, POLICY, retain=True)) is None


def test_successor_report_replaces_claim_and_keeps_same_formal_target():
    from random import Random
    from mafia_lab.paired_source_routing_v40 import SourceRoutingAPI
    from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
    import json
    from pathlib import Path

    _, _, policies = build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()))
    mafia = next(policy for policy in policies if policy.name == 'late_copy')
    obs = sample(5)
    obs = replace(obs, alive=tuple(p for p in obs.alive if p != 4),
                  messages=(Message(4, 'report', 11, True, 'day', 1),))
    control = SourceRoutingAPI('ordinary', False, '1/2', 'merge_control')
    treatment = SourceRoutingAPI('ordinary', False, '1/2', 'succession_report')
    claim = control.message(obs, mafia, Random(1))
    report = treatment.message(obs, mafia, Random(1))
    assert claim.kind == 'police'
    assert report == Message(5, 'report', 11, True, 'day', 2)
    a = control.after_speech(replace(obs, messages=(*obs.messages, claim)), mafia, Random(1))
    b = treatment.after_speech(replace(obs, messages=(*obs.messages, report)), mafia, Random(1))
    assert a == b == Message(5, 'accuse', 11, context='day', day=2)
