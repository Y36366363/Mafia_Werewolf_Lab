from dataclasses import replace
import json
from pathlib import Path

from mafia_lab.engine import Message, from_roles, observe, resolve_night
from mafia_lab.formal_source_conflict_v39 import formal_edges, prevent_formal_merge
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec


RULES, GOOD, _ = build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()))
POLICY = GOOD[-1]


def sample(player=15):
    state = resolve_night(from_roles(['police'] * 4 + ['mafia'] * 4 + ['civilian'] * 8, RULES), 8, 9)
    return replace(observe(state, player), day=2, messages=(
        Message(4, 'report', 10, False, 'day', 1),
        Message(0, 'report', 9, False, 'day', 2),
        Message(0, 'accuse', 4, context='day', day=2),
        Message(4, 'accuse', 11, context='day', day=2),
    ))


def test_live_formal_opposition_routes_to_legal_endpoints_without_identity_change():
    obs = sample()
    old = explain(obs, POLICY, retain=True)
    new = prevent_formal_merge(obs, POLICY, old)
    assert old['reason'] == 'compatible_sources_protocol'
    assert new['formal_edges'] == [(0, 4)]
    assert new['target'] in {0, 4}
    for key in ('known_bad', 'known_good', 'sources', 'proposals'):
        assert new[key] == old[key]


def test_soft_stale_relay_and_preclaim_calls_are_excluded():
    obs = sample()
    for kind in ('nominate', 'shortlist', 'relay'):
        messages = (*obs.messages[:2], replace(obs.messages[2], kind=kind), obs.messages[3])
        assert formal_edges(replace(obs, messages=messages), [0, 4]) == []
    messages = (*obs.messages[:2], replace(obs.messages[2], day=1), obs.messages[3])
    assert formal_edges(replace(obs, messages=messages), [0, 4]) == []
    assert formal_edges(replace(obs, messages=(obs.messages[2], *obs.messages[:2])), [0, 4]) == []
    assert formal_edges(replace(obs, alive=tuple(p for p in obs.alive if p != 4)), [0, 4]) == []


def test_superseded_call_does_not_create_conflict():
    obs = sample()
    obs = replace(obs, messages=(*obs.messages, Message(0, 'accuse', 12, context='day', day=2)))
    assert formal_edges(obs, [0, 4]) == []


def test_scope_preserves_pk_private_facts_and_first_day():
    for obs, candidates in [(sample(), (4, 11)), (sample(), (11, 12)),
                            (sample(0), None), (replace(sample(), day=1), None)]:
        old = explain(obs, POLICY, candidates, retain=True)
        new = prevent_formal_merge(obs, POLICY, old)
        assert new['target'] is None or new['target'] in old['legal']
        assert new['target'] not in old['known_good']
        if old['known_bad'] or obs.day == 1:
            assert new is old
