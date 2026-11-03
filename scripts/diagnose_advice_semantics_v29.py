#!/usr/bin/env python3
"""First predeclared win/loss/process cases; no new validation samples."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.advice_semantics_experiment_v29 import build_spec,simulate,PAIRS,PROFILES
from mafia_lab import strategies_v29 as d
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


def run():
    cfg=json.loads((ROOT/'results/v29/freeze.json').read_text())['config']
    held=json.loads((ROOT/'results/v29/holdout.json').read_text());D={(c['good'],c['mafia']):c for c in held['cells']}
    r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms};selected=[]
    for a,b in PAIRS:
        for knife in ('late','decoy'):
            for mode in ('restate','claim'):
                names=sorted(m for m in M if m.startswith(knife+'_') and '_'+mode+'_' in m)
                for kind in ('gain','loss','same_terminal_different_process'):
                    choices=[]
                    for mn in names:
                        x,y=D[a,mn]['raw'],D[b,mn]['raw']
                        for i,k in enumerate(x['dead_clear']):
                            if not k:continue
                            p,q=x['win'][i],y['win'][i]
                            match=(not p and q) if kind=='gain' else (p and not q) if kind=='loss' else p==q and x['process_hash'][i]!=y['process_hash'][i]
                            if match:choices.append((cfg['holdout']['seed_start']+i,mn));break
                    seed,mn=min(choices) if choices else (None,knife+'_'+mode)
                    selected.append(dict(comparison=a+'->'+b,kind=kind,seed=seed,mafia=mn))
    cache={}
    for item in selected:
        if item['seed'] is None:continue
        for gn in PROFILES:
            key=gn,item['mafia'],item['seed']
            if key in cache:continue
            row=simulate(r,G[gn],M[key[1]],key[2],details=True)
            s=opening(r,G[gn],M[key[1]],key[2],d)
            o=continue_game(s,G[gn],M[key[1]],key[2],trace=True,decision_api=d,public_ballots=True)
            assert hash_events(o.transcript)==row['trace_hash']
            cell=D[gn,key[1]];i=key[2]-cell['seed_start']
            assert all(v==cell['raw'][k][i] for k,v in row['raw'].items())
            cache[key]=row
    out=dict(selection='First ascending seed then column name; each predeclared contrast × knife × succession × gain/loss/same-terminal-process-change.',
        selected=selected,cases=[dict(good=k[0],mafia=k[1],**v) for k,v in cache.items()],
        detail_runs=len(cache),direct_replays=len(cache),new_validation_samples=0,
        limitation='Descriptive replay of already evaluated held-out cases, not additional independent evidence.')
    save(ROOT/'results/v29_examples.json',out)
    print(json.dumps(dict(cases=len(cache),direct_replays=len(cache),selected=selected)))


if __name__=='__main__':run()
