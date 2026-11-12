from dataclasses import replace
from random import Random
from pathlib import Path
import json
from mafia_lab.continuation_forensics_v38 import ContinuationForensicsAPI,local_view,follow_reason,daily_counts
from mafia_lab.hit_candidates_v37 import HitCandidatesAPI
from mafia_lab.engine import from_roles,resolve_night,observe,Message
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
R,GS,MS=build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()));G=GS[-1];M=next(m for m in MS if m.name=='late_copy')


def scenario(player=1):
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),8,9)
    return replace(observe(s,player),day=2,messages=(Message(4,'police',context='day',day=2),))


def test_private_false_source_never_copied_to_civilian():
    cop=local_view(scenario(),G);civil=local_view(scenario(15),G)
    assert cop['known_false_sources']==[4] and cop['target']==4
    assert civil['known_false_sources']==[] and civil['known_bad']==[]


def test_private_fact_priority_and_current_call():
    o=scenario();o=replace(o,messages=o.messages+(Message(0,'report',9,False,'day',2),Message(0,'accuse',4,context='day',day=2)))
    v=local_view(o,G)
    assert v['team_call']==dict(source=0,target=4) and v['target']==4


def test_pk_does_not_invent_vote_opportunity():
    v=local_view(scenario(),G,(10,11))
    assert v['known_false_sources']==[4] and v['known_bad']==[]
    assert v['target'] in (10,11)


def test_counts_include_terminal_night_without_night_death_event():
    roles=['police','mafia','civilian']
    transcript=[dict(day=1,event='votes',payload={}),dict(day=2,event='terminal',payload={'winner':'mafia'})]
    d=daily_counts(roles,[dict(day=1,target=2),dict(day=2,target=0)],transcript,False)
    assert d[0]['end']==dict(police=1,mafia=1,civilian=0)
    assert d[1]['end']==dict(police=0,mafia=1,civilian=0) and not d[1]['day_played']


def test_same_counts_can_hide_different_claim_information():
    a=scenario();b=replace(a,messages=())
    assert a.alive==b.alive and local_view(a,G)['known_bad']!=local_view(b,G)['known_bad']


def test_reason_separates_relay_refutation_and_no_admission():
    v=dict(legal=[4,5],target=5,known_bad=[],known_good=[],excluded_sources=[],guarded=[4,5],
           proposals={'0':[5]},accepted_relays=[dict(source=0,target=5)],reason='single_source_protocol')
    assert follow_reason(v,0,4)=='relay_replaced_call'
    assert follow_reason(dict(v,excluded_sources=[0]),0,4)=='privately_refuted_source'
    assert follow_reason(v,0,5)=='followed'


def test_nonintervention_preserves_random_state_and_speech():
    a=ContinuationForensicsAPI();b=HitCandidatesAPI();x,y=Random(7),Random(7)
    assert a.after_speech(scenario(),G,x)==b.after_speech(scenario(),G,y)
    assert x.getstate()==y.getstate()


def test_complete_traces_identical_to_original_api():
    for retain in (False,True):
        for seed in (211000017,211000079):
            a=ContinuationForensicsAPI(retain=retain);s=opening(R,G,M,seed,a)
            x=continue_game(s,G,M,seed,trace=True,decision_api=a,public_ballots=True)
            b=HitCandidatesAPI(retain=retain);s=opening(R,G,M,seed,b)
            y=continue_game(s,G,M,seed,trace=True,decision_api=b,public_ballots=True)
            assert hash_events(x.transcript)==hash_events(y.transcript)
