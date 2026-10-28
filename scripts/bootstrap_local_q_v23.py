#!/usr/bin/env python3
"""Post-train sensitivity, not a calibrated CI or policy reselection."""
import json,random
from pathlib import Path
from fractions import Fraction
from collections import Counter
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v23'
train=json.loads((folder/'train.json').read_text());freeze=json.loads((folder/'freeze.json').read_text())
cols=[m['name'] for m in freeze['mafia']];lookup={(c['good'],c['mafia']):c for c in train['cells']}
n=freeze['config']['train']['n']
arrays=[[lookup[g,m]['raw']['win'] for m in cols] for g in ('repair_q0','repair_q100')]

def solve_counts(a,b):
    slopes=[y-x for x,y in zip(a,b)];candidates={Fraction(0),Fraction(1)}
    for i in range(len(a)):
        for j in range(i):
            if slopes[i]!=slopes[j]:
                q=Fraction(a[j]-a[i],slopes[i]-slopes[j])
                if 0<=q<=1:candidates.add(q)
    scored={q:min(Fraction(x)+q*s for x,s in zip(a,slopes)) for q in candidates}
    v=max(scored.values());qs=[q for q in candidates if scored[q]==v]
    return min(qs),max(qs),v

a=[sum(v) for v in arrays[0]];b=[sum(v) for v in arrays[1]];lo,hi,v=solve_counts(a,b)
assert str(v/n)==train['certificate']['value_exact']
rng=random.Random(172000000);replicates=[]
for _ in range(500):
    weights=Counter(rng.randrange(n) for _ in range(n))
    ac=[sum(arr[i]*k for i,k in weights.items()) for arr in arrays[0]]
    bc=[sum(arr[i]*k for i,k in weights.items()) for arr in arrays[1]]
    l,h,value=solve_counts(ac,bc)
    replicates.append(dict(optimal_q_low=str(l),optimal_q_high=str(h),value=str(value/n)))
result=dict(scope='Post-train paired-seed bootstrap sensitivity, planned before reading holdout; not a confidence interval, not equilibrium uncertainty certificate, not used to change frozen q. Same seed resample across all endpoints/columns; optimal intervals retained for ties.',
    bootstrap_seed=172000000,replicates=500,training_n=n,base_optimal_interval=[str(lo),str(hi)],
    optimal_set_includes_zero=sum(Fraction(r['optimal_q_low'])==0 for r in replicates),
    optimal_set_includes_one=sum(Fraction(r['optimal_q_high'])==1 for r in replicates),
    uniquely_interior=sum(0<Fraction(r['optimal_q_low'])==Fraction(r['optimal_q_high'])<1 for r in replicates),
    raw=replicates,script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
(ROOT/'results/v23_q_sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'raw','scope','script_sha256'}}))
