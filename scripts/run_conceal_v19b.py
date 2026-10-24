#!/usr/bin/env python3
"""Exploratory follow-up chosen after A/B, with frozen fresh seeds C/D."""
import sys,json,shutil,time
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
from statistics import mean
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab import strategies_v19_hide as d
from mafia_lab.reply_evaluation_v19 import metrics,BRANCHES
from mafia_lab.statistics import paired_summary,win_summary
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import speech_order,Role

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        s=opening(rules,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
        v=metrics(s,o);order=list(speech_order(s));fake=v['fake_speaker'];first=next(p for p in order if s.roles[p]==Role.POLICE)
        no_prior=fake!=-1 and order.index(first)>order.index(fake)
        v['narrow_civilian']=int(v['civilian_target'] and no_prior)
        v['narrow_police']=int(v['police_target'] and no_prior)
        v['no_prior_police_claim']=int(no_prior)
        for k,x in v.items():raw.setdefault(k,[]).append(x)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=sha256(repr(o.transcript).encode()).hexdigest()))
    return dict(phase=phase,good=g.name,mafia=m.name,seed_start=start,n=n,raw=raw,means={k:mean(v) for k,v in raw.items()},samples=samples)

def analyze(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for m in sorted({c['mafia'] for c in cells}):
        a,b=lookup['conceal',m],lookup['answer',m]
        for key in ('fake_speaker','fake_target','first_dead','first_check','opportunity','narrow_civilian','narrow_police'):
            assert a['raw'][key]==b['raw'][key]
        for branch in ('narrow_civilian','narrow_police','eligible','dead_police'):
            mask=[bool(v) for v in a['raw'][branch]];row=dict(mafia=m,branch=branch,n=sum(mask))
            for g in ('conceal','answer'):
                row[g]=win_summary([v for v,k in zip(lookup[g,m]['raw']['win'],mask) if k])
            for metric in ('win','police_claims','day1_mafia_exile','day1_police_exile'):
                row[metric]=paired_summary([v for v,k in zip(a['raw'][metric],mask) if k],[v for v,k in zip(b['raw'][metric],mask) if k])
            out.append(row)
    return out
if __name__=='__main__':
    from mafia_lab.reply_evaluation_v19 import build_spec
    original=json.loads((ROOT/'configs/reply_v19.json').read_text());rules,gs,ms=build_spec(original)
    template=asdict(next(p for p in gs if p.name=='guard_answer'))
    answer=d.GoodPolicyV19(**dict(template,name='answer'))
    conceal=d.GoodPolicyV19(**dict(template,name='conceal',reply='keep'),conceal_wrong_hit=True)
    mafia=[m for m in ms if m.response=='forward'];good=[conceal,answer]
    config=dict(blocks=[dict(name='evaluation_C',seed_start=158000000,n=4096),dict(name='replication_D',seed_start=159000000,n=4096)],
                rules=asdict(rules),good=[asdict(p) for p in good],mafia=[asdict(p) for p in mafia])
    folder=ROOT/'results/v19b'
    if folder.exists():raise ValueError('use fresh output')
    folder.mkdir();assets=list((ROOT/'mafia_lab').glob('*.py'))+[Path(__file__).resolve(),ROOT/'docs/conceal_protocol_v19b.md']
    for src in assets:
        dst=folder/'source'/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    save(folder/'freeze.json',dict(config=config,assets={str(p.relative_to(folder)):sha256(p.read_bytes()).hexdigest() for p in (folder/'source').rglob('*') if p.is_file()}))
    started=time.monotonic()
    for b in config['blocks']:
        with ProcessPoolExecutor(max_workers=4) as pool:cells=list(pool.map(evaluate,[(b['name'],rules,g,m,b['seed_start'],b['n']) for g in good for m in mafia]))
        save(folder/(b['name']+'.json'),dict(cells=cells,contrasts=analyze(cells)));print(b['name']+' completed',flush=True)
    names=['freeze.json']+[b['name']+'.json' for b in config['blocks']]
    save(folder/'manifest.json',dict(games=32768,elapsed_seconds=time.monotonic()-started,files={n:sha256((folder/n).read_bytes()).hexdigest() for n in names}))
