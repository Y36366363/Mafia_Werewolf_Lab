import json
from pathlib import Path
from random import Random
from dataclasses import replace
from hashlib import sha256
from mafia_lab.engine import from_roles,resolve_night,observe,add_message,Message,Role
from mafia_lab import strategies_v23 as d
from mafia_lab.restatement_experiment_v23 import build_spec,evaluate,contrasts,simulate
C=json.loads(Path('configs/restatement_response_v23.json').read_text())


def make_case():
    r,gs,ms=build_spec(C)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,14)
    s=add_message(s,Message(4,'report',8,True,'day',1))
    return s,{g.name:g for g in gs},{m.name:m for m in ms}


def test_restate_is_same_target_accusation_not_new_inspection():
    s,_,ms=make_case();m=ms['late_near_restate'];o=replace(observe(s,4),day=2)
    msg=d.after_speech(o,m,Random(1))
    assert (msg.kind,msg.target,msg.verdict,msg.day)==('accuse',8,None,2)
    assert d.restatement_target(o,m)==8


def test_no_new_speaker_transfer_dead_target_or_day_one_repetition():
    s,_,ms=make_case();m=ms['late_near_restate']
    assert d.restatement_target(observe(s,4),m) is None
    assert d.restatement_target(replace(observe(s,5),day=2),m) is None
    o=replace(observe(s,4),day=2,alive=tuple(p for p in s.alive if p!=8))
    assert d.restatement_target(o,m) is None
    assert d.restatement_target(replace(observe(s,4),day=2),ms['late_near_quiet']) is None


def test_ordinary_claim_history_does_not_certify_source_to_bystander():
    s,gs,ms=make_case();o=replace(observe(s,4),day=2)
    msg=d.after_speech(o,ms['late_near_restate'],Random(1))
    # Evaluate actor-only observations at the next date without role labels.
    civil=replace(observe(s,9),day=2,messages=s.messages+(msg,))
    assert 4 in {m.speaker for m in d.base.public_claims(civil)}
    assert 4 not in d.base.private_bad(civil,True)
    victim=replace(civil,player=8)
    assert 4 in d.base.private_bad(victim,True)


def test_mafia_restatement_unchanged_by_unseen_police_civilian_permutation():
    s,_,ms=make_case();roles=list(s.roles);roles[0],roles[9]=roles[9],roles[0]
    other=replace(s,roles=tuple(roles));a=replace(observe(s,4),day=2);b=replace(observe(other,4),day=2)
    assert a==b
    assert d.after_speech(a,ms['late_near_restate'],Random(1))==d.after_speech(b,ms['late_near_restate'],Random(1))


def test_local_q_endpoints_and_no_second_responder():
    s,gs,_=make_case();o=observe(s,0)
    assert d.message(o,gs['repair_q0'],Random(1)).kind=='pass'
    assert d.message(o,gs['repair_q100'],Random(1)).kind=='report'
    s=add_message(s,Message(0,'report',14,False,'day',1))
    assert d.message(observe(s,1),gs['repair_q100'],Random(1)).kind not in {'report','police'}


def test_v22_fixed_q_route_and_quiet_trace_compatibility():
    from mafia_lab import strategies_v22 as old
    from mafia_lab.simulation import opening,continue_game
    r,gs,ms=build_spec(C);g=next(g for g in gs if g.name=='repair_q50');m=next(m for m in ms if m.name=='late_near_quiet')
    oldg=old.GoodPolicyV22(**{k:v for k,v in g.__dict__.items()})
    s=opening(r,g,m,171000000,d);before=continue_game(s,oldg,m,171000000,trace=True,decision_api=old,public_ballots=True)
    result=simulate(r,g,m,171000000)
    assert result['trace_hash']==sha256(repr(before.transcript).encode()).hexdigest()


def test_smoke_all_cells_branch_invariance_and_unwrapped_wrapper_equivalence():
    from mafia_lab.simulation import opening,continue_game
    r,gs,ms=build_spec(C)
    cells=[evaluate(('smoke',r,g,m,171000000,4)) for g in gs for m in ms]
    assert contrasts(cells)
    for name in ('repair_q0','repair_q50','repair_q100'):
        g=next(g for g in gs if g.name==name)
        for m in (ms[0],ms[1]):
            s=opening(r,g,m,171000000,d);o=continue_game(s,g,m,171000000,trace=True,decision_api=d,public_ballots=True)
            row=next(c for c in cells if c['good']==name and c['mafia']==m.name)
            assert row['samples'][0]['trace_hash']==sha256(repr(o.transcript).encode()).hexdigest()
