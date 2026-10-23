#!/usr/bin/env python3
import json,sys,importlib.util
from pathlib import Path
from hashlib import sha256
from statistics import mean
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'results/v18_probe'
rd=lambda n:json.loads((folder/n).read_text())
manifest,freeze,result=map(rd,['manifest.json','freeze.json','probe.json'])
for name,digest in manifest['files'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
for name,digest in freeze['assets'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,str(folder/'source'))
spec=importlib.util.spec_from_file_location('archived_probe',folder/'source/scripts/run_police_response_probe_v18.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from mafia_lab.police_response_experiment_v18 import build_spec,_branches,_contrasts
config=json.loads((folder/'source/configs/police_response_v18.json').read_text())
rules,good,mafia,cal=build_spec(config);mafia=[m for m in mafia if m.response=='early']
gm,mm={p.name:p for p in good},{p.name:p for p in mafia}
replays=0
for c in result['cells']:
    assert c['means']=={k:mean(v) for k,v in c['raw'].items()}
    assert all(len(v)==c['n'] for v in c['raw'].values())
    assert c['branches']==_branches(c['raw'])
    for sample in c['samples']:
        other=module.evaluate((rules,gm[c['good']],mm[c['mafia']],sample['seed'],1))
        for k in c['raw']:assert other['raw'][k][0]==c['raw'][k][sample['index']]
        assert other['samples'][0]['trace_hash']==sample['trace_hash']
        replays+=1
assert result['contrasts']==_contrasts(result['cells'],good,mafia)
audit={'status':'pass','cells_checked':len(result['cells']),'assets_checked':len(freeze['assets']),'sampled_full_replays':replays,'scope':'Posthoc diagnostic, sampled replay and arithmetic audit, not new equilibrium evidence.'}
(ROOT/'results/v18_probe_integrity_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit))
