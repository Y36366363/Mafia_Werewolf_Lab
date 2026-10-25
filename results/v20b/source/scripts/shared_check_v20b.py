#!/usr/bin/env python3
"""Fresh-seed constraint-only probe and archived-source sampled replay."""
import sys,json,shutil,time,argparse
from pathlib import Path
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v20b'
if '--verify' in sys.argv:sys.path.insert(0,str(folder/'source'))
else:sys.path.insert(0,str(ROOT))
from mafia_lab import strategies_v20 as original,strategies_v20b as corrected
from mafia_lab.evidence_experiment_v20 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.reply_evaluation_v19 import metrics
from mafia_lab.statistics import win_summary,paired_summary

def save(p,value):
    p.write_text(json.dumps(value,ensure_ascii=False,indent=None if 'cells' in value else 2)+'\n')

def evaluate(job):
    mode,rules,g,m,start,n=job;api=original if mode=='original' else corrected
    raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        s=opening(rules,g,m,seed,api);o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
        for k,v in metrics(s,o).items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=sha256(repr(o.transcript).encode()).hexdigest()))
    return dict(mode=mode,mafia=m.name,n=n,seed_start=start,raw=raw,means={k:mean(v) for k,v in raw.items()},samples=samples)

def contrasts(cells):
    lookup={(c['mode'],c['mafia']):c for c in cells};out=[]
    for m in sorted({c['mafia'] for c in cells}):
        a,b=lookup['original',m],lookup['corrected',m]
        for key in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
            assert a['raw'][key]==b['raw'][key]
        row=dict(mafia=m,original=win_summary(a['raw']['win']),corrected=win_summary(b['raw']['win']))
        for k in ('win','day1_mafia_exile','day1_police_exile'):
            row[k]=paired_summary(a['raw'][k],b['raw'][k])
        out.append(row)
    return out

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:
        f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
        for n,h in f['assets'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
        for n,h in manifest['files'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
        r,gs,ms=build_spec(f['config']);g=next(p for p in gs if p.name=='evidence_q50');mm={m.name:m for m in ms}
        data=json.loads((folder/'probe.json').read_text());assert data['contrasts']==contrasts(data['cells']);replays=0
        for c in data['cells']:
            assert c['means']=={k:mean(v) for k,v in c['raw'].items()}
            assert all(len(v)==c['n'] for v in c['raw'].values())
            for sample in c['samples']:
                replay=evaluate((c['mode'],r,g,mm[c['mafia']],sample['seed'],1))
                for k in c['raw']:assert replay['raw'][k][0]==c['raw'][k][sample['index']]
                assert replay['samples'][0]['trace_hash']==sample['trace_hash'];replays+=1
        result=dict(status='pass',cells_checked=len(data['cells']),sampled_full_replays=replays,assets_checked=len(f['assets']),games_recorded=manifest['games'],scope='Fresh exploratory constraint probe; no independent replication, no q retuning; sampled full replay only.')
        save(ROOT/'results/v20b_integrity_audit.json',result);print(json.dumps(result));sys.exit()
    if folder.exists():raise ValueError('use fresh output')
    folder.mkdir();config=json.loads((ROOT/'configs/evidence_memory_v20.json').read_text());rules,gs,mafia=build_spec(config)
    good=next(p for p in gs if p.name=='evidence_q50')
    assets=list((ROOT/'mafia_lab').glob('*.py'))+[Path(__file__).resolve(),ROOT/'docs/shared_check_protocol_v20b.md',ROOT/'tests/test_shared_check_v20b.py']
    for src in assets:
        dst=folder/'source'/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    save(folder/'freeze.json',dict(config=config,seed_start=163000000,n=2048,assets={str(p.relative_to(folder)):sha256(p.read_bytes()).hexdigest() for p in (folder/'source').rglob('*') if p.is_file()}))
    started=time.monotonic()
    with ProcessPoolExecutor(max_workers=4) as pool:
        cells=list(pool.map(evaluate,[(mode,rules,good,m,163000000,2048) for mode in ('original','corrected') for m in mafia]))
    save(folder/'probe.json',dict(cells=cells,contrasts=contrasts(cells)))
    save(folder/'manifest.json',dict(games=sum(c['n'] for c in cells),elapsed_seconds=time.monotonic()-started,files={n:sha256((folder/n).read_bytes()).hexdigest() for n in ['freeze.json','probe.json']}))
    print(json.dumps(dict(games=sum(c['n'] for c in cells),status='complete')))
