import json
from pathlib import Path
from itertools import permutations
from fractions import Fraction
from random import Random
from dataclasses import replace
from mafia_lab.engine import Rules,from_roles,resolve_night,observe,add_message,Message
from mafia_lab import strategies_v18 as d
from mafia_lab.police_response_experiment_v18 import build_spec,evaluate_cell

CONFIG=json.loads(Path('configs/police_response_v18.json').read_text())

def setup():
    rules,good,mafia,cal=build_spec(CONFIG)
    state=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,14)
    return state,{p.name:p for p in good},mafia

def test_clear_order_survives_extra_accusation():
    # A=0 clears B=1; C=2 accuses B; observer=3.
    r=d._claim_marginals(6,2,2,3,(0,2),((0,1,False),(2,1,True)))
    assert r[1]<=r[0]

def test_common_clear_is_good_if_one_source_must_be_real():
    # Only one mafia means the two distinct claimants cannot both be false.
    r=d._claim_marginals(6,1,2,5,(0,1),((0,2,False),(1,2,False)))
    assert r[2]==0

def test_double_false_common_clear_remains_possible():
    r=d._claim_marginals(6,3,2,5,(0,1),((0,2,False),(1,2,False)))
    assert r[2]>0

def test_combinatorial_marginals_match_full_role_enumeration():
    n,m,p,observer=5,1,2,4
    claims=(0,);reports=((0,1,False),)
    roles=set(permutations(['M']*m+['P']*p+['C']*(n-m-p)))
    worlds=[r for r in roles if r[observer]=='C'
            and all(r[s] in {'M','P'} for s in claims)
            and all(r[s]=='M' or ((r[t]=='M')==v) for s,t,v in reports)]
    expected=tuple(Fraction(sum(r[i]=='M' for r in worlds),len(worlds)) for i in range(n))
    assert d._claim_marginals(n,m,p,observer,claims,reports)==expected

def test_single_available_police_response_and_not_fake_inspection():
    state,gm,ms=setup();g=gm['logical_answer']
    state=add_message(state,Message(4,'report',0,True,'day',1))
    msg=d.message(observe(state,0),g,Random(1))
    assert msg.kind=='police' and msg.target is None
    state=add_message(state,msg)
    extra=d.after_speech(observe(state,0),g,Random(1))
    assert extra.kind=='accuse' and extra.target==4
    state=add_message(state,extra)
    assert d.response_target(observe(state,1),g) is None

def test_self_response_only_when_accused():
    state,gm,ms=setup()
    state=add_message(state,Message(4,'report',0,True,'day',1))
    assert d.response_target(observe(state,1),gm['logical_self']) is None
    assert d.response_target(observe(state,0),gm['logical_self'])==4
    assert d.response_target(observe(state,1),gm['logical_answer'])==4

def test_keep_does_not_respond():
    state,gm,ms=setup();state=add_message(state,Message(4,'report',0,True,'day',1))
    assert d.message(observe(state,1),gm['fixed_keep'],Random(1)).kind!='police'

def test_clear_protection_handles_cycles_without_empty_vote_pool():
    state,gm,ms=setup()
    for msg in [Message(4,'report',5,False,'day',1),Message(5,'report',4,False,'day',1)]:
        state=add_message(state,msg)
    assert d._clear_priority(observe(state,8),[4,5])==[4,5]

def test_private_opponent_role_permutation_is_invisible():
    state,gm,ms=setup()
    state=add_message(state,Message(4,'report',0,True,'day',1))
    roles=list(state.roles);roles[5],roles[8]=roles[8],roles[5]
    other=replace(state,roles=tuple(roles))
    assert observe(state,9)==observe(other,9)
    assert d.vote(observe(state,9),gm['logical_answer'],Random(1))==d.vote(observe(other,9),gm['logical_answer'],Random(1))

def test_smoke_all_cells_and_pair_opportunities():
    rules,good,mafia,cal=build_spec(CONFIG)
    for m in mafia:
        cells=[evaluate_cell(('smoke',rules,g,m,152000000,8)) for g in good]
        for key in ['response_opportunity','first_check_mafia','first_kill_police']:
            assert all(c['raw'][key]==cells[0]['raw'][key] for c in cells)
        assert all(c['means']['police_response_day1']<=c['means']['response_opportunity'] for c in cells)

def test_probe_forward_target_has_not_spoken_yet():
    from mafia_lab import strategies_v18_probe as probe
    from mafia_lab.engine import speech_order
    state,gm,mafia=setup();m=next(p for p in mafia if p.name=='safe_late_early')
    obs=observe(state,4);msg=probe.message(obs,m,Random(1))
    order=list(speech_order(state))
    assert order.index(msg.target)>order.index(4)

def test_probe_reply_preserves_actual_shared_inspection():
    from mafia_lab import strategies_v18_probe as probe
    state,gm,mafia=setup()
    state=add_message(state,Message(4,'report',0,True,'day',1))
    msg=probe.message(observe(state,0),gm['logical_answer'],Random(1))
    record=state.investigations[-1]
    assert msg.kind=='report' and (msg.target,msg.verdict)==(record.target,record.is_mafia)
    state=add_message(state,msg)
    assert probe.after_speech(observe(state,0),gm['logical_answer'],Random(1)).target==4

def test_probe_report_reply_retains_anti_false_claim_vote():
    from mafia_lab import strategies_v18_probe as probe
    state,gm,mafia=setup()
    state=add_message(state,Message(4,'report',0,True,'day',1))
    state=add_message(state,probe.message(observe(state,0),gm['logical_answer'],Random(1)))
    state=add_message(state,probe.after_speech(observe(state,0),gm['logical_answer'],Random(1)))
    assert probe.vote(observe(state,0),gm['logical_answer'],Random(1))==4
