#!/usr/bin/env python3
"""Post-evaluation arithmetic and sampled archived-source replay audit."""
import sys,json
from pathlib import Path
from hashlib import sha256
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v19'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for name,digest in manifest['files'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
for name,digest in f['assets'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,str(folder/'source'))
from mafia_lab.reply_evaluation_v19 import build_spec,evaluate,contrasts,BRANCHES
from mafia_lab.statistics import win_summary
r,gs,ms=build_spec(f['config']);gm={p.name:p for p in gs};mm={p.name:p for p in ms};replays=0;cells=0
for block in f['config']['blocks']:
    report=json.loads((folder/(block['name']+'.json')).read_text())
    assert report['contrasts']==contrasts(report['cells'])
    for c in report['cells']:
        cells+=1
        assert c['means']=={k:mean(v) for k,v in c['raw'].items()}
        assert all(len(v)==c['n'] for v in c['raw'].values())
        assert c['branches']=={b:win_summary([v for i,v in enumerate(c['raw']['win']) if b=='all' or c['raw'][b][i]]) for b in BRANCHES}
        assert all(a<=b for a,b in zip(c['raw']['reply'],c['raw']['opportunity']))
        for sample in c['samples']:
            other=evaluate((block['name'],r,gm[c['good']],mm[c['mafia']],sample['seed'],1))
            for k in c['raw']:assert other['raw'][k][0]==c['raw'][k][sample['index']]
            assert other['samples'][0]['trace_hash']==sample['trace_hash'];replays+=1
result=dict(status='pass',cells_checked=cells,sampled_full_replays=replays,assets_checked=len(f['assets']),
            games_recorded=manifest['games'],scope='Arithmetic, hash integrity, common branch masks, and 3 sampled archived full replays per cell. Not all games independently rerun.')
(ROOT/'results/v19_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
