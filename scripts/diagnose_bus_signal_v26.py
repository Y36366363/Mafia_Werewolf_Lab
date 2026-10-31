#!/usr/bin/env python3
"""Post-held paired explanation at the already selected first history-change seed."""
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'results/v26'
sys.path.insert(0,str(F/'source'))
from mafia_lab import strategies_v26 as d
from mafia_lab.police_execution_experiment_v26 import build_spec,simulate
from mafia_lab.simulation import opening,continue_game
f=json.loads((F/'freeze.json').read_text());h=json.loads((F/'holdout.json').read_text());examples=json.loads((ROOT/'results/v26_examples.json').read_text())
selected=next(r for r in examples['rows'] if r['kind']=='history_first_change' and r['mafia']=='decoy_far_claim_team');seed=selected['seed']
r,gs,ms=build_spec(f['config']);g=next(g for g in gs if g.name=='history_q50');runs={}
for mode in ('team','bus'):
 m=next(m for m in ms if m.name=='decoy_far_claim_'+mode);cell=next(c for c in h['cells'] if c['good']==g.name and c['mafia']==m.name);i=seed-cell['seed_start']
 run=simulate(r,g,m,seed,True)
 for k,v in cell['raw'].items():assert run['raw'][k]==v[i]
 s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
 assert sha256(repr(o.transcript).encode()).hexdigest()==run['trace_hash'];runs[mode]=run
out=dict(scope='Post-held explanation, selected from the already prespecified first history-change example; same held seed replayed under declared bus counterpart. Not a new statistical comparison or policy change.',seed=seed,runs=runs,detailed_replays=2,unwrapped_replays=2,
 input_sha256={'holdout':sha256((F/'holdout.json').read_bytes()).hexdigest(),'selected_examples':sha256((ROOT/'results/v26_examples.json').read_bytes()).hexdigest()})
(ROOT/'results/v26_bus_signal_example.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for mode,run in runs.items():
 v=next(v for v in run['votes'] if v['day']==2 and v['player']==12)
 print(mode,dict(target=v['target'],changed=v['history_changed'],scores=v['history_scores'],buses=run['buses'],win=run['raw']['win']))
