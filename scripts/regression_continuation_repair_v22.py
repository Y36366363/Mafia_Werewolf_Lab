#!/usr/bin/env python3
"""Six known-case regression games; not independent performance evidence."""
import json,sys
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v22'
sys.path.insert(0,str(folder/'source'))
from mafia_lab.continuation_repair_v22 import build_spec,AuditAPI
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab import strategies_v22 as d

class DetailedAPI(AuditAPI):
    def __init__(self):super().__init__();self.details=[];self.nights=[]
    def choose_inspection(self,obs,policy,rng):
        target=d.choose_inspection(obs,policy,rng)
        self.nights.append(dict(night=obs.day+1,kind='inspection',target=target))
        return target
    def choose_kill(self,obs,policy,rng):
        target=d.choose_kill(obs,policy,rng)
        self.nights.append(dict(night=obs.day+1,kind='kill',target=target))
        return target
    def vote(self,obs,policy,rng,candidates=None):
        target=super().vote(obs,policy,rng,candidates)
        if obs.role!=Role.MAFIA:
            self.details.append(dict(observation=asdict(obs),decision=d.explain(obs,policy,candidates),round='pk' if candidates is not None else 'first'))
        return target

f=json.loads((folder/'freeze.json').read_text());rules,gs,ms=build_spec(f['config']);gm={g.name:g for g in gs};mm={m.name:m for m in ms}
cases=[('late_near',163000010,'lost_despite_day1_mafia'),('decoy_far',163000018,'gained_win'),('late_near',163000001,'sole_surviving_conflict_police')]
examples=[]
for mafia,seed,kind in cases:
    row=dict(mafia=mafia,seed=seed,kind=kind,runs={})
    for name in ('legacy','both'):
        api=DetailedAPI();s=opening(rules,gm[name],mm[mafia],seed,api)
        o=continue_game(s,gm[name],mm[mafia],seed,trace=True,decision_api=api,public_ballots=True)
        row['runs'][name]=dict(win=o.good_win,roles_evaluation_only=[r.value for r in s.roles],
            transcript=o.transcript,votes=api.details,nights=api.nights,trace_hash=sha256(repr(o.transcript).encode()).hexdigest())
    examples.append(row)
result=dict(scope='Three preidentified v21 regression examples, six games. Reused development seeds, excluded from new-seed win estimates and all confidence intervals. No policy changes.',
    script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),examples=examples)
(ROOT/'results/v22_regression_examples.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([dict(seed=e['seed'],mafia=e['mafia'],old_win=e['runs']['legacy']['win'],new_win=e['runs']['both']['win']) for e in examples]))
