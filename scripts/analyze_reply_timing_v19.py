#!/usr/bin/env python3
"""Exploratory PRE-intervention opening strata; no new strategies or seed search."""
import sys,json
from pathlib import Path
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v19';sys.path.insert(0,str(folder/'source'))
from mafia_lab.reply_evaluation_v19 import build_spec
from mafia_lab.simulation import opening
from mafia_lab.engine import Role,speech_order
from mafia_lab.statistics import paired_summary,win_summary
from mafia_lab import strategies_v19 as d

def analyze(job):
    phase,rules,g,m,start,cells=job;lookup={c['good']:c for c in cells}
    base=lookup['guard_keep'];early=[]
    for i in range(base['n']):
        s=opening(rules,g,m,start+i,d);order=list(speech_order(s));fake=base['raw']['fake_speaker'][i]
        first=next(p for p in order if s.roles[p]==Role.POLICE)
        early.append(fake!=-1 and order.index(first)<order.index(fake))
    result=[]
    for branch in ('eligible','civilian_target','police_target'):
        for existing in (False,True):
            mask=[bool(v) and x==existing for v,x in zip(base['raw'][branch],early)]
            row=dict(phase=phase,mafia=m.name,branch=branch,police_already_spoke=existing,n=sum(mask),policies={})
            for name in ('guard_keep','guard_answer','guard_selective'):
                row['policies'][name]=win_summary([v for v,k in zip(lookup[name]['raw']['win'],mask) if k])
            for metric in ('win','day1_mafia_exile','day1_police_exile','police_claims'):
                row[metric]=paired_summary([v for v,k in zip(base['raw'][metric],mask) if k],
                    [v for v,k in zip(lookup['guard_answer']['raw'][metric],mask) if k])
            result.append(row)
    return result
if __name__=='__main__':
    f=json.loads((folder/'freeze.json').read_text());rules,good,mafia=build_spec(f['config']);g=next(p for p in good if p.name=='guard_keep');jobs=[]
    for b in f['config']['blocks']:
        r=json.loads((folder/(b['name']+'.json')).read_text())
        for m in mafia:jobs.append((b['name'],rules,g,m,b['seed_start'],[c for c in r['cells'] if c['mafia']==m.name]))
    with ProcessPoolExecutor(max_workers=4) as pool:rows=[r for chunk in pool.map(analyze,jobs) for r in chunk]
    result=dict(scope='Exploratory opening-based stratification added after reading A, before reading B. No policy modification or new outcome simulation. Distinguishes first cop reply from exposing another cop.',
                analyzer_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),rows=rows)
    (ROOT/'results/v19_timing_diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('timing diagnostic written')
