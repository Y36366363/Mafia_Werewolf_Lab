import json
from pathlib import Path
from dataclasses import replace
from random import Random
from hashlib import sha256
from mafia_lab import strategies_v24 as previous
from mafia_lab import strategies_v25 as d
from mafia_lab.engine import from_roles,resolve_night,add_message,observe,Message
from mafia_lab.source_advice_experiment_v25 import build_spec,evaluate,contrasts,simulate,exact_paired_interval
from mafia_lab.simulation import opening,continue_game
C=json.loads(Path('configs/source_advice_v25.json').read_text())


def case():
    r,gs,ms=build_spec(C)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,r),15,6)
    s=add_message(s,Message(4,'report',8,True,'day',1))
    s=replace(s,day=2,alive=tuple(p for p in s.alive if p!=4),last_anchor=4)
    for msg in (Message(0,'report',6,True,'day',2),Message(5,'police',context='day',day=2),Message(5,'accuse',8,context='day',day=2)):
        s=add_message(s,msg)
    return s,{g.name:g for g in gs},ms


def test_gate_withholds_advice_but_preserves_source_history_and_private_facts():
    s,gs,_=case();o=observe(s,9)
    before=d.explain(o,gs['base_q50']);after=d.explain(o,gs['gate_q50'])
    assert 5 in before['proposal_sources'] and 5 not in after['proposal_sources']
    assert after['blocked_advice_sources']==[5]
    assert before['sources']==after['sources'] and 5 in after['sources']
    assert before['history_edges']==after['history_edges']
    assert after['proposals']['5']==[] and before['proposals']['5']==[8]
    assert o.messages==s.messages
    police=d.explain(observe(s,1),gs['gate_q50'])
    assert 5 in police['known_bad'] and police['target'] in police['known_bad']


def test_unverified_fake_inspection_bypasses_gate_no_truth_or_robustness_claim():
    s,gs,_=case();s=add_message(s,Message(5,'report',8,True,'day',2))
    o=observe(s,9);info=d.explain(o,gs['gate_q50'])
    assert 5 in info['proposal_sources'] and 5 not in info['blocked_advice_sources']
    # Making a report is admission, not proof the report is true.
    assert s.roles[5].value=='mafia' and info['proposals']['5']==[8]


def test_unknown_role_permutation_cannot_change_civilian_action():
    s,gs,_=case();roles=list(s.roles);roles[1],roles[10]=roles[10],roles[1]
    t=replace(s,roles=tuple(roles));a,b=observe(s,9),observe(t,9)
    assert a==b
    assert d.vote(a,gs['gate_q50'],Random(7))==d.vote(b,gs['gate_q50'],Random(7))


def test_day_one_unchanged_and_q_remains_variable():
    s,gs,ms=case();r=s.rules
    for q in ('0','50','100'):
        g=gs['gate_q'+q];b=gs['base_q'+q]
        initial=opening(r,g,ms[0],178000000,d)
        o=observe(initial,next(p for p in initial.alive if initial.roles[p].value=='police'))
        assert d.message(o,g,Random(2))==d.message(o,b,Random(2))
        assert d.vote(o,g,Random(2))==d.vote(o,b,Random(2))
        assert g.response_probability==b.response_probability


def test_control_full_trace_matches_previous_and_unwrapped_gate_matches_audit():
    r,gs,ms=build_spec(C);g=next(g for g in gs if g.name=='base_q50');m=next(m for m in ms if m.name=='late_far_claim')
    seed=178000000;s=opening(r,g,m,seed,d)
    a=continue_game(s,g,m,seed,trace=True,decision_api=previous,public_ballots=True)
    b=simulate(r,g,m,seed)
    assert sha256(repr(a.transcript).encode()).hexdigest()==b['trace_hash']
    g=replace(g,report_advice_gate=True)
    s=opening(r,g,m,seed,d);a=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
    assert sha256(repr(a.transcript).encode()).hexdigest()==simulate(r,g,m,seed)['trace_hash']


def test_smoke_design_prefixes_and_exact_precision_zero_is_not_zero_width():
    r,gs,ms=build_spec(C)
    rows=[evaluate(('smoke',r,g,m,178000000,2)) for g in gs for m in ms]
    cs=contrasts(rows);assert sum(c['primary'] for c in cs)==4
    for c in rows:
        assert all(sum(c['raw'][k+'_ballots'])==0 for k in ('orphan','stale','ignored_known','voted_good','illegal'))
    z=exact_paired_interval([0]*20,[0]*20)
    assert z['ci_simultaneous'][0]<0<z['ci_simultaneous'][1]
