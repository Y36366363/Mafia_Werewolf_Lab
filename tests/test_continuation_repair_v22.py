import json
from dataclasses import replace
from pathlib import Path
from random import Random
from mafia_lab.engine import Rules,from_roles,resolve_night,resolve_votes,observe,add_message,Message,Role
from mafia_lab import strategies_v22 as d
from mafia_lab.continuation_repair_v22 import build_spec,restore_observation,evaluate,contrasts

CONFIG=json.loads(Path('configs/continuation_repair_v22.json').read_text())


def make_case(fresh=True):
    rules,gs,_=build_spec(CONFIG)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,6)
    s=add_message(s,Message(0,'report',6,True,'day',1))
    s=add_message(s,Message(4,'report',8,True,'day',1))
    s=resolve_votes(s,{p:(4 if p!=4 else None) for p in s.alive})
    s=resolve_night(s,13,12)
    if fresh:s=add_message(s,Message(0,'report',6,True,'day',2))
    return s,{g.name:g for g in gs}


def test_no_automatic_survivor_and_current_check_is_used():
    s,g=make_case();obs=observe(s,9)
    assert d.route(obs,g['legacy'])==(0,'compare_conflicting_sources')
    detail=d.explain(obs,g['both'])
    assert detail['target']==6 and detail['active_edges']==[]
    assert detail['history_edges']==[(0,4)]
    assert detail['proposals']['4']==[]
    assert 4 in detail['sources']  # no identity certification by death


def test_live_only_does_not_silently_remove_stale_hit_advice():
    s,g=make_case();obs=observe(s,9)
    detail=d.explain(obs,g['live_pair'])
    assert detail['active_edges']==[]
    assert detail['proposals']['4']==[8]
    # Documents why the separate stale-advice ablation is needed.
    assert d.explain(obs,g['current_day'])['history_edges']==[(0,4)]


def test_history_is_preserved_when_no_current_proposals_exist():
    s,g=make_case(False);obs=observe(s,9);r=d.explain(obs,g['both'])
    assert r['reason']=='position_fallback'
    assert any(m.speaker==4 and m.verdict for m in obs.messages)
    assert r['sources']==[0,4] and r['proposal_sources']==[]


def test_todays_dead_police_report_is_still_eligible():
    rules,gs,_=build_spec(CONFIG);p=next(g for g in gs if g.name=='both')
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,14)
    s=add_message(s,Message(0,'report',14,False,'day',1))
    s=resolve_votes(s,{i:(4 if i!=4 else None) for i in s.alive})
    s=resolve_night(s,0,6)
    s=add_message(s,Message(0,'report',6,True,'last_words',2))
    r=d.explain(observe(s,9),p)
    assert 0 not in s.alive and r['proposals']['0']==[6] and r['target']==6


def test_private_memory_and_pk_legality_take_priority():
    s,g=make_case();s=add_message(s,Message(5,'report',9,True,'day',2));p=g['both']
    assert d.vote(observe(s,9),p,Random(1))==5
    assert d.vote(observe(s,9),p,Random(1),[0,1]) in {0,1}
    assert d.vote(observe(s,0),p,Random(1),[1,2]) is None
    assert d.vote(observe(s,0),p,Random(1))==6


def test_unseen_roles_cannot_change_civilian_or_mafia_action():
    s,g=make_case();roles=list(s.roles);roles[5],roles[10]=roles[10],roles[5]
    other=replace(s,roles=tuple(roles));a,b=observe(s,9),observe(other,9)
    assert a==b and d.route(a,g['both'])==d.route(b,g['both'])


def test_three_real_case_categories_and_legacy_observation_equivalence():
    data=json.loads(Path('results/v21_verified/examples.json').read_text())['examples']
    _,gs,_=build_spec(CONFIG);gm={g.name:g for g in gs};checked=0
    for case in data:
        for mode in ('original','corrected'):
            for ballot in case[mode]['votes']:
                obs=restore_observation(ballot['observation'])
                candidates=tuple(obs.pending_pk) if ballot['round']=='pk' else None
                assert d.route(obs,gm['legacy'],candidates)==d.legacy.route(obs,gm['legacy'],candidates)
                if obs.day==1:
                    for g in gs:assert d.route(obs,g,candidates)==d.route(obs,gm['legacy'],candidates)
                checked+=1
    assert checked>100
    ex=next(e for e in data if e['mafia']=='late_near' and e['kind']=='lost_despite_day1_mafia')
    v=next(v for v in ex['corrected']['votes'] if v['day']==2 and v['role']=='civilian')
    obs=restore_observation(v['observation'])
    assert v['target']==15 and d.vote(obs,gm['both'],Random(1))==6


def test_existing_live_opposition_can_still_be_compared():
    s,g=make_case();s=add_message(s,Message(5,'report',0,True,'day',2))
    info=d.explain(observe(s,9),g['both'])
    assert (0,5) in info['active_edges']
    # Survivor gets no automatic truth certificate or immunity.
    assert 0 in info['conflict_targets']


def test_smoke_prefix_invariance_and_disabled_flags_match_old_runner():
    from hashlib import sha256
    from mafia_lab.simulation import opening,continue_game
    rules,gs,ms=build_spec(CONFIG)
    cells=[evaluate(('smoke',rules,g,m,168000000,8)) for g in gs for m in ms]
    assert contrasts(cells)
    g=next(g for g in gs if g.name=='legacy')
    for m in ms:
        s=opening(rules,g,m,168000000,d.legacy)
        old=continue_game(s,g,m,168000000,trace=True,decision_api=d.legacy,public_ballots=True)
        c=next(c for c in cells if c['good']=='legacy' and c['mafia']==m.name)
        assert c['samples'][0]['trace_hash']==sha256(repr(old.transcript).encode()).hexdigest()
