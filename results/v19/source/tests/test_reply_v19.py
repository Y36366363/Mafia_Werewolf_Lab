import json
from pathlib import Path
from random import Random
from dataclasses import replace
from mafia_lab.engine import Rules,from_roles,resolve_night,observe,add_message,Message,Role
from mafia_lab import strategies_v19 as d
from mafia_lab.reply_evaluation_v19 import build_spec,evaluate,contrasts

C=json.loads(Path('configs/reply_v19.json').read_text())
def setup():
    r,g,m=build_spec(C)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,14)
    return s,{p.name:p for p in g},m

def test_real_inspection_shortlist_denial_all_preserved():
    s,g,_=setup();p=g['guard_answer']
    s=add_message(s,Message(4,'report',8,True,'day',1))
    msg=d.message(observe(s,0),p,Random(1));r=s.investigations[-1]
    assert (msg.kind,msg.target,msg.verdict)==('report',r.target,r.is_mafia)
    s=add_message(s,msg);extra=d.after_speech(observe(s,0),p,Random(1))
    assert isinstance(extra,tuple) and [m.kind for m in extra]==['shortlist','accuse']
    for m in extra:s=add_message(s,m)
    assert extra[-1].target==4 and d.reply_target(observe(s,1),p) is None
    assert d.vote(observe(s,0),p,Random(1))==4

def test_selective_uses_police_team_only():
    s,g,_=setup();p=g['guard_selective']
    civilian=add_message(s,Message(4,'report',8,True,'day',1))
    cop=add_message(s,Message(4,'report',1,True,'day',1))
    assert d.reply_target(observe(civilian,0),p) is None
    assert d.reply_target(observe(cop,0),p)==4

def test_civilian_private_denial_not_public_authentication():
    s,g,_=setup();s=add_message(s,Message(4,'report',8,True,'day',1))
    assert d.vote(observe(s,8),g['guard_keep'],Random(1))==4
    assert d.own_false_accusers(observe(s,9))==[]
    assert d.source_credit(observe(s,9),g['guard_keep'])[8]==d.old.Fraction(1,2)

def test_clear_relational_credit_even_when_accused():
    s,g,_=setup()
    for m in [Message(0,'report',8,False,'day',1),Message(4,'report',8,True,'day',1)]:s=add_message(s,m)
    v=d.source_credit(observe(s,8),g['guard_keep']);assert v[8]>=v[0]
    obs=observe(s,9);assert d.constraints._clear_priority(obs,[0,8])==[0]

def test_unobserved_role_permutation_no_leak():
    s,g,_=setup();s=add_message(s,Message(4,'report',8,True,'day',1))
    roles=list(s.roles);roles[5],roles[9]=roles[9],roles[5];other=replace(s,roles=tuple(roles))
    for observer in (0,8,10):
        assert observe(s,observer)==observe(other,observer)
        assert d.vote(observe(s,observer),g['guard_answer'],Random(1))==d.vote(observe(other,observer),g['guard_answer'],Random(1))

def test_survival_cap_symmetric_and_not_identity_probability():
    s,g,_=setup()
    for m in [Message(0,'report',8,False,'day',1),Message(4,'report',9,False,'day',1)]:s=add_message(s,m)
    obs=replace(observe(s,10),day=2)
    v=d.source_credit(obs,g['guard_bait']);assert v[0]==v[4]==d.old.Fraction(1,2)

def test_pair_masks_all_policies_and_actual_turns():
    rules,good,mafia=build_spec(C)
    cells=[evaluate(('smoke',rules,g,m,155000000,16)) for g in good for m in mafia]
    assert contrasts(cells)
    for c in cells:
        assert all(r<=o for r,o in zip(c['raw']['reply'],c['raw']['opportunity']))
