from random import Random
from mafia_lab import strategies_v20 as a,strategies_v20b as b
from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message,Rules


def make_case(messages):
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,Rules(tie_rule='pk')),15,14)
    for m in messages:s=add_message(s,m)
    p=a.GoodPolicyV20(name='test',leadership='nominate',position_model='posterior',source_credit=True)
    return observe(s,9),p


def test_different_first_checks_cannot_both_be_real_shared_check():
    obs,p=make_case([Message(0,'report',14,False,'day',1),Message(4,'report',8,True,'day',1)])
    assert a.route(obs,p)[1]=='compatible_sources_protocol'
    target,reason=b.route(obs,p)
    assert reason=='compare_conflicting_sources' and target in {0,4}


def test_same_check_not_automatically_a_conflict():
    obs,p=make_case([Message(0,'report',14,False,'day',1),Message(4,'report',14,False,'day',1)])
    assert b.route(obs,p)==a.route(obs,p)


def test_different_days_do_not_imply_shared_first_check_conflict():
    obs,p=make_case([Message(0,'report',14,False,'day',1),Message(4,'report',8,True,'day',2)])
    assert b.route(obs,p)==a.route(obs,p)
