#!/usr/bin/env python3
"""Post-train, pre-held-specified marginal CP union bounds for 4 paired means."""
import json
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from scipy.stats import beta,binom
ROOT=Path(__file__).resolve().parents[1]


def cp(k,n,tail):
    lo=0. if k==0 else float(beta.ppf(tail,k,n-k+1))
    hi=1. if k==n else float(beta.ppf(1-tail,k+1,n-k))
    if k>0:assert abs(binom.sf(k-1,n,lo)-tail)<1e-9
    if k<n:assert abs(binom.cdf(k,n,hi)-tail)<1e-9
    return [lo,hi]


def main():
    p=ROOT/'results/v24/holdout.json';report=json.loads(p.read_text());out=[]
    for r in report['contrasts']:
        if not r['primary']:continue
        v=r['win'];plus=cp(v['improved'],v['n'],.05/16);minus=cp(v['worsened'],v['n'],.05/16)
        out.append(dict(base=r['base'],n=v['n'],improved=v['improved'],worsened=v['worsened'],
                        delta=v['delta'],p_plus=plus,p_minus=minus,simultaneous_ci=[plus[0]-minus[1],plus[1]-minus[0]]))
    assert len(out)==4
    q=ROOT/'results/v24_paired_precision.json'
    q.write_text(json.dumps(dict(scope='Training-informed method specified before held reading; marginal exact binomial CP plus union bound, 4 fixed q50 contrasts simultaneous 95% under iid simulation seeds.',
       tail_alpha=.05/16,input_sha256=sha256(p.read_bytes()).hexdigest(),rows=out),indent=2)+'\n')
    print(json.dumps(dict(status='pass',comparisons=len(out))))


if __name__=='__main__':main()
