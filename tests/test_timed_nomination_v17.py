import json
from pathlib import Path
from random import Random
from dataclasses import replace
from fractions import Fraction
from mafia_lab.engine import Rules,from_roles,resolve_night,observe,add_message,Message,PublicEvent
from mafia_lab import strategies_v17 as d
from mafia_lab.timed_nomination_experiment_v17 import build_spec,evaluate_cell

CONFIG=json.loads(Path('configs/timed_nomination_v17.json').read_text())

def setup():
    rules,good,mafia,cal=build_spec(CONFIG)
    state=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,14)
    return state,{p.name:p for p in good},mafia

def test_shortlist_emitted_at_own_report_and_not_final_call():
    state,goods,mafia=setup();p=goods['timed2'];obs=observe(state,0)
    state=add_message(state,d.message(obs,p,Random(1)))
    m=d.after_speech(observe(state,0),p,Random(1))
    assert m.kind=='shortlist' and len(m.targets)==2
    assert d.final_call(observe(state,0),p,Random(1)) is None

def test_public_clear_can_propose_outside_list():
    state,goods,mafia=setup();p=goods['timed2']
    state=add_message(state,Message(0,'report',14,False,'day',1))
    state=add_message(state,Message(0,'shortlist',context='day',day=1,targets=(12,13)))
    m=d.after_speech(observe(state,14),p,Random(1))
    assert m.kind=='accuse' and m.target not in (12,13)

def test_unclaimed_hidden_police_cannot_issue_public_reroute():
    state,goods,mafia=setup();p=goods['timed2']
    state=add_message(state,Message(0,'report',14,False,'day',1))
    state=add_message(state,Message(0,'shortlist',context='day',day=1,targets=(12,13)))
    assert d.after_speech(observe(state,1),p,Random(1)).kind=='nominate'

def test_civilian_credit_has_no_referee_identity():
    state,goods,mafia=setup();p=goods['credit2']
    assert d._credit(observe(state,14),0,p)==Fraction(1,2)
    state=add_message(state,Message(4,'report',0,False,'day',1))
    assert d._credit(observe(state,14),0,p)==Fraction(3,4)
    # A mafia's false public clear gets the same fallible weight.
    state=add_message(state,Message(5,'report',4,False,'day',1))
    assert d._credit(observe(state,14),4,p)==Fraction(3,4)

def test_vote_history_needs_prior_public_mismatch():
    state,goods,mafia=setup()
    state=replace(state,day=2,messages=(Message(4,'nominate',12,None,'day',1),),
        public_events=(PublicEvent('vote',1,ballots=((4,None),(5,12))),))
    scores=d.history_scores(observe(state,14))
    assert scores[4]==Fraction(1,20) and scores[5]==0

def test_hidden_unknown_role_permutation_identical_action():
    state,goods,mafia=setup();p=goods['timed2']
    roles=list(state.roles);roles[4],roles[12]=roles[12],roles[4]
    alternative=replace(state,roles=tuple(roles))
    assert observe(state,0)==observe(alternative,0)
    assert d.after_speech(observe(state,0),p,Random(1))==d.after_speech(observe(alternative,0),p,Random(1))

def test_all_cells_smoke_and_pair_branches():
    rules,good,mafia,cal=build_spec(CONFIG)
    for m in mafia:
        cells=[evaluate_cell(('smoke',rules,g,m,148000000,4)) for g in good]
        assert all(c['raw']['eligible_clear']==cells[0]['raw']['eligible_clear'] for c in cells)

def test_history_only_changes_later_days():
    rules,good,mafia,cal=build_spec(CONFIG)
    gm={p.name:p for p in good}
    a=evaluate_cell(('smoke',rules,gm['credit2'],mafia[-1],148100000,16))
    b=evaluate_cell(('smoke',rules,gm['history2'],mafia[-1],148100000,16))
    for key in ('shortlist_size','day1_exile_mafia','day1_exile_police',
                'outside_reroute','outside_exile','day1_no_exile'):
        assert a['raw'][key]==b['raw'][key]
