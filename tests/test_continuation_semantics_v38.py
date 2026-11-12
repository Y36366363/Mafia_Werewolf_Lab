"""Read-only checks of discovered graph and action-timing limitations."""
from dataclasses import replace
from pathlib import Path
import json
from mafia_lab.continuation_forensics_v38 import local_view
from mafia_lab.engine import from_roles,resolve_night,observe,Message
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
R,GS,_=build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()));G=GS[-1]


def test_live_formal_call_against_report_backed_source_is_not_a_current_graph_edge():
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),8,9)
    obs=replace(observe(s,15),day=2,messages=(
        Message(4,'report',10,False,'day',1),
        Message(0,'report',9,False,'day',2),
        Message(0,'accuse',4,context='day',day=2),
        Message(4,'accuse',11,context='day',day=2)))
    v=local_view(obs,G)
    assert 0 in v['sources'] and 4 in v['sources']
    assert [0,4] not in [list(e) for e in v['active_edges']]
    assert v['proposals']['0']==[4] and v['proposals']['4']==[11]
    assert v['reason']=='compatible_sources_protocol'


def test_new_claim_after_police_speech_changes_private_knowledge_at_ballot():
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,R),8,9)
    before=replace(observe(s,0),day=2,messages=(Message(0,'report',9,False,'day',2),))
    after=replace(before,messages=before.messages+(Message(4,'police',context='day',day=2),))
    assert local_view(before,G)['known_bad']==[]
    assert local_view(after,G)['known_bad']==[4]
    assert local_view(after,G)['target']==4
    assert local_view(after,G)['team_call'] is None
