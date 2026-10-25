"""Extra independent implementation checks; no policy changes after freeze."""
from dataclasses import replace
from random import Random
from mafia_lab import strategies_v20 as d
from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message,Rules


def make_case():
    rules=Rules(tie_rule='pk')
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,14)
    p=d.GoodPolicyV20(name='evidence',leadership='nominate',position_model='posterior',source_credit=True,
        reveal='silent',trust='none',shortlist_rule='list2',dead_police_message='truth')
    return s,p


def test_evidence_actions_do_not_read_numeric_source_credit(monkeypatch):
    s,p=make_case()
    for m in [Message(0,'report',14,False,'day',1),Message(0,'accuse',4,context='day',day=1)]:s=add_message(s,m)
    def forbidden(*args,**kwargs):
        raise AssertionError('evidence mode used numeric source credit')
    monkeypatch.setattr(d.old,'source_credit',forbidden)
    monkeypatch.setattr(d.old.old,'_credit',forbidden)
    assert d.vote(observe(s,9),p,Random(1))==4
    d.message(observe(s,9),p,Random(1))
    d.after_speech(observe(s,9),p,Random(1))


def test_mafia_target_cannot_distinguish_police_and_civilian():
    s,_=make_case();roles=list(s.roles);roles[0],roles[8]=roles[8],roles[0]
    other=replace(s,roles=tuple(roles))
    a,b=observe(s,4),observe(other,4);assert a==b
    for target_rule in ('near','far'):
        m=d.MafiaPolicyV20(name='mafia',kill_mode='safe_late',response='forward',target_rule=target_rule)
        assert d.message(a,m,Random(1))==d.message(b,m,Random(1))
        assert d.choose_kill(a,m,Random(1))==d.choose_kill(b,m,Random(1))


def test_no_false_claim_is_publicly_authenticated_by_a_denial():
    s,p=make_case()
    s=add_message(s,Message(4,'report',8,True,'day',1))
    s=add_message(s,Message(8,'nominate',4,context='day',day=1))
    assert d.private_bad(observe(s,8),True)=={4}
    assert d.private_bad(observe(s,9),True)==set()
    assert 4 not in d.impossible_sources(observe(s,9),p)
