#!/usr/bin/env python3
"""Predeclared first-case selection; descriptive traces, no policy selection."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.gold_relay_experiment_v27 import build_spec,simulate
from mafia_lab import strategies_v27 as d
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


def run():
    root=ROOT/'results/v27';config=json.loads((root/'freeze.json').read_text())['config']
    held=json.loads((root/'holdout.json').read_text());D={(c['good'],c['mafia']):c for c in held['cells']}
    rules,gs,ms=build_spec(config);G={g.name:g for g in gs};M={m.name:m for m in ms};selected=[]
    for knife in ('late','decoy'):
        for mode in ('restate','claim'):
            names=sorted(m for m in M if m.startswith(knife+'_') and '_'+mode+'_' in m)
            for kind in ('gain','loss','changed'):
                candidates=[]
                for mn in names:
                    a,b=D['base_q50',mn]['raw'],D['local_q50',mn]['raw']
                    for i,(x,y) in enumerate(zip(a['win'],b['win'])):
                        ok=(not x and y) if kind=='gain' else (x and not y) if kind=='loss' else b['relay_changed_ballots'][i]>0
                        if ok:candidates.append((config['holdout']['seed_start']+i,mn));break
                if candidates:
                    seed,mn=min(candidates);selected.append(dict(kind=kind,seed=seed,mafia=mn))
                else:selected.append(dict(kind=kind,seed=None,mafia=knife+'_'+mode))
    cache={};replays=0
    for case in selected:
        if case['seed'] is None:continue
        for gn in ('base_q50','fixed_q50','local_q50'):
            key=(gn,case['mafia'],case['seed'])
            if key in cache:continue
            row=simulate(rules,G[gn],M[key[1]],key[2],details=True)
            s=opening(rules,G[gn],M[key[1]],key[2],d)
            o=continue_game(s,G[gn],M[key[1]],key[2],trace=True,decision_api=d,public_ballots=True)
            assert hash_events(o.transcript)==row['trace_hash'];replays+=1
            cell=D[gn,key[1]];i=key[2]-cell['seed_start']
            assert all(row['raw'][k]==v[i] for k,v in cell['raw'].items())
            cache[key]=row
    output=dict(selection='first ascending seed then mafia name, each knife × succession mode × gain/loss/vote-change; no filtering',
                selected=selected,cases=[dict(good=k[0],mafia=k[1],**v) for k,v in cache.items()],
                audited_detail_runs=len(cache),independent_direct_replays=replays,
                limitations='Examples reused from already evaluated holdout; descriptive only, not new validation data.')
    save(ROOT/'results/v27_examples.json',output)
    print(json.dumps(dict(cases=len(cache),direct_replays=replays,selection=selected)))


if __name__=='__main__':run()
