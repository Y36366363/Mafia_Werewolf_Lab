#!/usr/bin/env python3
import sys,json,importlib.util
from pathlib import Path
from hashlib import sha256
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v19b'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for name,digest in manifest['files'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
for name,digest in f['assets'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,str(folder/'source'))
spec=importlib.util.spec_from_file_location('archived_conceal',folder/'source/scripts/run_conceal_v19b.py');x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)
from mafia_lab.engine import Rules
from mafia_lab import strategies_v19_hide as d
r=Rules(**f['config']['rules']);gm={p['name']:d.GoodPolicyV19(**p) for p in f['config']['good']};mm={p['name']:d.MafiaPolicyV19(**p) for p in f['config']['mafia']}
replays=0;cells=0
for block in f['config']['blocks']:
    rep=json.loads((folder/(block['name']+'.json')).read_text());assert rep['contrasts']==x.analyze(rep['cells'])
    for c in rep['cells']:
        cells+=1;assert c['means']=={k:mean(v) for k,v in c['raw'].items()}
        assert all(len(v)==c['n'] for v in c['raw'].values())
        for s in c['samples']:
            other=x.evaluate((block['name'],r,gm[c['good']],mm[c['mafia']],s['seed'],1))
            for k in c['raw']:assert other['raw'][k][0]==c['raw'][k][s['index']]
            assert other['samples'][0]['trace_hash']==s['trace_hash'];replays+=1
    for row in rep['contrasts']:
        if row['branch']=='narrow_civilian' and row['n']:
            assert row['police_claims']['delta']==1
result=dict(status='pass',cells_checked=cells,sampled_full_replays=replays,assets_checked=len(f['assets']),games_recorded=manifest['games'],scope='Fresh exploratory concealment contrast; arithmetic, assets and 3 sampled full replays per cell. Not all games rerun.')
(ROOT/'results/v19b_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
