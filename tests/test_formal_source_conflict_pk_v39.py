"""Post-freeze check with engine-validated statements and PK eligibility."""
from dataclasses import replace
import json
from pathlib import Path

from mafia_lab.engine import Message, add_message, from_roles, observe, resolve_night
from mafia_lab.formal_source_conflict_v39 import prevent_formal_merge
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec


def test_existing_formal_opposition_blocks_a_shared_pk_shortlist():
    rules, good, _ = build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()))
    state = from_roles(['police'] * 4 + ['mafia'] * 4 + ['civilian'] * 8, rules)
    state = resolve_night(state, 8, 9)
    state = add_message(state, Message(4, 'report', 10, False, 'day', 1))
    state = replace(state, day=2)
    for message in (
        Message(0, 'report', 4, True, 'day', 2),
        Message(0, 'shortlist', context='day', day=2, targets=(11,)),
        Message(0, 'accuse', 4, context='day', day=2),
        Message(4, 'shortlist', context='day', day=2, targets=(11,)),
    ):
        state = add_message(state, message)
    obs = observe(replace(state, pending_pk=(0, 11)), 15)
    old = explain(obs, good[-1], obs.pending_pk, retain=True)
    new = prevent_formal_merge(obs, good[-1], old)
    assert old['reason'] == 'common_recommendation_protocol'
    assert old['target'] == 11
    assert new['formal_edges'] == [(0, 4)]
    assert new['target'] == 0
