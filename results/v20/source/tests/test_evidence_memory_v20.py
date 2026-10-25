from dataclasses import replace
from random import Random
from fractions import Fraction
from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message,Role,Rules
from mafia_lab import strategies_v20 as d


def make_case():
    r=Rules(tie_rule='pk')
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,14)
    p=d.GoodPolicyV20(name='test',leadership='nominate',position_model='posterior',
        source_credit=True,shortlist_rule='list2',reveal='silent',trust='none',
        dead_police_message='truth',inspect_position='gap',dead_clear_plan='truth')
    return s,p


def test_private_refutation_persists_but_not_for_bystander():
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1))
    o=replace(observe(s,8),day=2)
    assert 4 in d.private_bad(o,True) and 4 not in d.private_bad(o,False)
    assert d.vote(o,p,Random(1))==4
    assert 4 not in d.private_bad(replace(observe(s,9),day=2),True)


def test_credit_memory_adds_same_private_fact_without_source_weights():
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1))
    o=replace(observe(s,8),day=2)
    assert d.vote(o,replace(p,routing='credit'),Random(1))==4


def test_single_claimant_advice_has_no_numeric_credit_gate():
    s,p=make_case()
    for m in [Message(0,'report',14,False,'day',1),Message(0,'accuse',4,context='day',day=1)]:s=add_message(s,m)
    assert d.old.source_credit(observe(s,9),p)[0]==Fraction(1,2)
    assert d.route(observe(s,9),p)==(4,'single_source_protocol')


def test_conflicting_claims_not_automatically_latest_wins():
    s,p=make_case()
    for m in [Message(0,'report',14,False,'day',1),Message(4,'report',0,True,'day',1)]:s=add_message(s,m)
    target,reason=d.route(observe(s,9),p)
    assert reason=='compare_conflicting_sources' and target in {0,4}


def test_gold_source_before_target_remains_protected():
    s,p=make_case();s=add_message(s,Message(4,'report',5,False,'day',1))
    assert d.vote(observe(s,9),p,Random(1),[4,5])==4


def test_hidden_roles_cannot_change_observer_action():
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1))
    roles=list(s.roles);roles[5],roles[9]=roles[9],roles[5];other=replace(s,roles=tuple(roles))
    for player in (0,8,10):
        a,b=observe(s,player),observe(other,player)
        assert a==b
        assert d.vote(a,p,Random(1))==d.vote(b,p,Random(1))
        assert d.message(a,p,Random(1))==d.message(b,p,Random(1))


def test_local_mix_has_real_hide_and_report_endpoints():
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1));o=observe(s,0)
    assert d.optional_response(o)
    assert d.message(o,replace(p,response_probability='0'),Random(1)).kind=='pass'
    msg=d.message(o,replace(p,response_probability='1'),Random(1));r=s.investigations[-1]
    assert (msg.kind,msg.target,msg.verdict)==('report',r.target,r.is_mafia)
    s=add_message(s,msg);extra=d.after_speech(observe(s,0),p,Random(1))
    assert [m.kind for m in extra]==['shortlist','accuse']


def test_targeting_police_does_not_use_optional_silence():
    s,p=make_case();s=add_message(s,Message(4,'report',1,True,'day',1));o=observe(s,0)
    assert not d.optional_response(o)
    assert d.message(o,replace(p,response_probability='0'),Random(1)).kind=='report'


def test_no_second_officer_and_no_repeated_sampling():
    s,p=make_case();s=add_message(s,Message(0,'report',14,False,'day',1))
    s=add_message(s,Message(4,'report',0,True,'day',1));o=observe(s,1)
    assert not d.optional_response(o)
    assert d.message(o,p,Random(1)).kind not in {'report','police'}
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1))
    s=add_message(s,Message(0,'pass',context='day',day=1))
    assert not d.optional_response(observe(s,1))


def test_pk_respects_legal_pool_and_never_private_good():
    s,p=make_case();s=add_message(s,Message(4,'report',8,True,'day',1))
    assert d.vote(observe(s,8),p,Random(1),[0,1]) in {0,1}
    assert d.vote(observe(s,0),p,Random(1),[1,2]) is None


def test_numeric_parameter_bounds_and_actual_sampling():
    import pytest
    s,p=make_case()
    with pytest.raises(ValueError):replace(p,response_probability='5/4')
    s=add_message(s,Message(4,'report',8,True,'day',1));o=observe(s,0)
    for seed in range(30):
        actions=[d.message(o,replace(p,response_probability=q),Random(seed)).kind=='report' for q in ['0','1/4','1/2','3/4','1']]
        assert actions==sorted(actions)


def test_experiment_smoke_pairing_and_no_extra_live_cop():
    import json
    from pathlib import Path
    from mafia_lab.evidence_experiment_v20 import build_spec,evaluate,contrasts
    config=json.loads(Path('configs/evidence_memory_v20.json').read_text())
    rules,good,mafia=build_spec(config)
    cells=[evaluate(('smoke',rules,g,m,162000000,8)) for g in good for m in mafia]
    assert contrasts(cells)
    assert all(max(c['raw']['police_claims'])<=1 for c in cells)
    # Pure endpoint exposure differs exactly by 1 in the designated branch.
    lookup={(c['good'],c['mafia']):c for c in cells}
    for m in mafia:
        a,b=lookup['evidence_q0',m.name],lookup['evidence_q100',m.name]
        for i,k in enumerate(a['raw']['narrow_civilian']):
            if k:assert b['raw']['police_claims'][i]-a['raw']['police_claims'][i]==1
