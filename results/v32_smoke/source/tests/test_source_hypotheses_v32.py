from dataclasses import replace
from random import Random
import json
from pathlib import Path
import pytest
from mafia_lab.source_hypotheses_v32 import role_support, source_prefix, ResponseAPI, suppress_redundant
from mafia_lab.engine import from_roles, resolve_night, observe, Message, Role
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec


def obs(dead=0,live=4,hit=False,target=9,player=15):
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8),dead,8)
    messages=(Message(dead,'report',8,False,'last_words',1),Message(live,'report',target,hit,'day',1))
    return replace(observe(s,player),messages=messages)


def test_compatible_dead_live_sources_not_certified():
    o=obs(target=8);d=role_support(o,0,4)
    assert set(d['counts'])=={'P/P','P/M','M/P','M/M'}
    for k,roles in d['witnesses'].items():
        assert roles.count('police')==4 and roles.count('mafia')==4 and roles[15]=='civilian'
        assert replace(o,teammates=(),investigations=())==o
        for m in o.messages:
            if roles[m.speaker]=='police':assert (roles[m.target]=='mafia')==m.verdict


def test_private_false_hit_rules_out_live_police_not_dead_authentication():
    d=role_support(obs(hit=True,target=15),0,4)
    assert set(d['counts'])=={'P/M','M/M'}


def test_contradiction_removes_both_police_not_one_fixed_endpoint():
    d=role_support(obs(hit=True,target=8),0,4)
    assert set(d['counts'])=={'P/M','M/P','M/M'}


def test_grant_and_shortlist_and_timing_not_identity_evidence():
    o=obs();a=role_support(o,0,4)
    extras=(Message(0,'delegate',8,context='last_words',day=1,targets=(9,10)),Message(8,'relay',9,day=1,targets=(0,)))
    assert role_support(replace(o,messages=o.messages+extras),0,4)==a
    assert role_support(replace(o,messages=o.messages[::-1]),0,4)==a


def test_future_report_excluded_from_first_source_snapshot():
    o=obs(target=8);bad=Message(5,'report',15,True,day=1)
    a=source_prefix(o);b=source_prefix(replace(o,messages=o.messages+(bad,)))
    assert a==b


def test_absence_only_at_end():
    o=obs();o=replace(o,messages=o.messages[:1]);p=source_prefix(o)
    assert p[2] is None and p[3]=='no_live_at_end'


def test_restrained_uses_private_team_not_reporter_death_as_truth():
    assert suppress_redundant(obs(player=1),'day')
    assert not suppress_redundant(obs(dead=4,live=0,player=1),'day')
    assert not suppress_redundant(obs(player=15),'day')
    assert not suppress_redundant(obs(player=1),'pk')


def test_no_non_civilian_inference():
    with pytest.raises(ValueError):role_support(obs(player=1),0,4)


def test_restrained_vote_preserves_private_and_pk_constraints():
    from mafia_lab import strategies_v31 as base
    cfg=json.loads(Path('configs/unresolved_conflict_v31.json').read_text());r,gs,ms=build_spec(cfg)
    g=gs[-1];o=obs(player=1)
    for candidates in (None,(4,9),(8,9)):
        assert ResponseAPI(True).vote(o,g,Random(7),candidates)==base.vote(o,g,Random(7),candidates)
