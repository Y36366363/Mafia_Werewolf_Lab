#!/usr/bin/env python3
"""Secondary exact bound when a frozen paired counter shows zero win flips."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
h=json.loads((ROOT/'results/v23/holdout.json').read_text());lookup={(c['good'],c['mafia']):c for c in h['cells']}
rows=[];family=8;alpha=.05
for g in ('legacy_q50','repair_q50'):
    for base in ('late_near','late_far','decoy_near','decoy_far'):
        a,b=lookup[g,base+'_quiet'],lookup[g,base+'_restate'];n=a['n']
        k=sum(x!=y for x,y in zip(a['raw']['win'],b['raw']['win']))
        upper=-math.expm1(math.log(alpha/family)/n) if k==0 else 1.0
        rows.append(dict(good=g,base=base,n=n,win_flips=k,absolute_population_win_effect_bound=upper,
            method='If K=0: 1-(alpha/8)^(1/n); otherwise trivial bound 1. |E[D]| <= P(D != 0).'))
result=dict(scope='Secondary procedure specified after viewing train but before viewing holdout. Simultaneous 95% bound for 8 frozen paired comparisons under independent-seed game sampling per comparison; union bound needs no independence across columns. Bounds overall terminal win effect only, not local harm or exploitability against other policies.',
    family=family,alpha=alpha,rows=rows)
(ROOT/'results/v23_zero_counter_bound.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(rows))
