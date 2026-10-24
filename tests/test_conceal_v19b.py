import json
from pathlib import Path
from random import Random
from dataclasses import asdict
from mafia_lab.reply_evaluation_v19 import build_spec
from mafia_lab import strategies_v19_hide as d
from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message

def make_case(target):
    r,gs,_=build_spec(json.loads(Path('configs/reply_v19.json').read_text()))
    p=d.GoodPolicyV19(**dict(asdict(gs[1]),name='conceal'),conceal_wrong_hit=True)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,14)
    return add_message(s,Message(4,'report',target,True,'day',1)),p

def test_actual_first_cop_can_conceal_without_losing_check():
    s,p=make_case(8);o=observe(s,0)
    assert d.conceal(o,p) and o.investigations
    assert d.message(o,p,Random(1)).kind=='pass'
    assert d.after_speech(o,p,Random(1)).kind=='nominate'

def test_police_target_or_prior_claim_does_not_trigger_concealment():
    s,p=make_case(1);assert not d.conceal(observe(s,0),p)
    s,p=make_case(8);s=add_message(s,Message(1,'report',14,False,'day',1))
    assert not d.conceal(observe(s,0),p)

def test_concealment_stops_after_day_one():
    from dataclasses import replace
    s,p=make_case(8);assert not d.conceal(replace(observe(s,0),day=2),p)
