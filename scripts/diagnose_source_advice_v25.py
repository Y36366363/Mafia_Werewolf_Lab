#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'results/v25'
sys.path.insert(0,str(F/'source'))
from mafia_lab import strategies_v25 as d
from mafia_lab.source_advice_experiment_v25 import build_spec,simulate,BASES
from mafia_lab.simulation import opening,continue_game


def main():
    freeze=json.loads((F/'freeze.json').read_text());held=json.loads((F/'holdout.json').read_text());rules,gs,ms=build_spec(freeze['config'])
    lookup={(c['good'],c['mafia']):c for c in held['cells']};gm={g.name:g for g in gs};mm={m.name:m for m in ms};rows=[];replays=0
    for base in BASES:
        a,b=lookup['base_q50',base+'_claim'],lookup['gate_q50',base+'_claim']
        for category in ('gain','loss','blocked_but_still_loss'):
            def eligible(i):
                x,y=a['raw']['win'][i],b['raw']['win'][i]
                return (not x and y) if category=='gain' else (x and not y) if category=='loss' else (not x and not y and b['raw']['blocked_advice_game'][i])
            index=next((i for i in range(a['n']) if eligible(i)),None)
            if index is None:rows.append(dict(base=base,category=category,status='no_case'));continue
            seed=a['seed_start']+index;runs={}
            for gn in ('base_q50','gate_q50'):
                g,m=gm[gn],mm[base+'_claim'];row=simulate(rules,g,m,seed,True);cell=lookup[gn,m.name]
                for k,v in cell['raw'].items():assert row['raw'][k]==v[index]
                s=opening(rules,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
                assert sha256(repr(o.transcript).encode()).hexdigest()==row['trace_hash'];replays+=1
                runs[gn]=row
            first=None
            for x,y in zip(runs['base_q50']['votes'],runs['gate_q50']['votes']):
                if (x['day'],x['round'],x['player'])!=(y['day'],y['round'],y['player']):break
                if x['target']!=y['target']:
                    first=dict(base=x,gate=y);break
            rows.append(dict(base=base,category=category,status='replayed',seed=seed,index=index,first_vote_difference=first,runs=runs))
    out=dict(scope='Post-held explanatory first seed per prespecified category; reused held data, not new independent evidence or policy selection.',
             selection_rule='q50 claim in each base: ascending first gain, loss, blocked-but-still-loss.',
             held_sha256=sha256((F/'holdout.json').read_bytes()).hexdigest(),detailed_replays=replays,unwrapped_replays=replays,rows=rows)
    (ROOT/'results/v25_examples.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status='pass',replays=replays,selected=sum(r['status']=='replayed' for r in rows))))


if __name__=='__main__':main()
