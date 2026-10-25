#!/usr/bin/env python3
"""Verify archived code, arithmetic, branch pairing and sampled full replays."""
import sys,json
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v20'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for name,digest in manifest['files'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
for name,digest in f['assets'].items():assert sha256((folder/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,str(folder/'source'))
from mafia_lab.evidence_experiment_v20 import build_spec,evaluate,contrasts,endpoint_matrix,ENDPOINTS,BRANCHES
from mafia_lab.position_repair_experiment_v14 import _solution,_frozen
from mafia_lab.statistics import win_summary
from mafia_lab import strategies_v20 as d
rules,good,mafia=build_spec(f['config']);gm={p.name:p for p in good};mm={p.name:p for p in mafia};names=list(mm)
selection=json.loads((folder/'selection_before_holdout.json').read_text());gm['trained_local_q']=d.GoodPolicyV20(**selection['policy'])
count=replays=0
for phase in ('train','holdout'):
    report=json.loads((folder/(phase+'.json')).read_text());assert report['contrasts']==contrasts(report['cells'])
    matrix=endpoint_matrix(report['cells'],names);assert report['endpoint_matrix']==[[str(x) for x in row] for row in matrix]
    if phase=='train':
        cert=_solution(matrix,list(ENDPOINTS),names);assert cert==report['certificate']==selection['certificate']
        assert cert['gap_exact']=='0'
        assert Fraction(selection['q_exact'])==Fraction(cert['good_mixture'].get('evidence_q100','0'))
    else:
        assert report['frozen_train_mixture_bounds']==_frozen(matrix,list(ENDPOINTS),names,selection['certificate'])
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    for c in report['cells']:
        count+=1
        assert c['means']=={k:mean(v) for k,v in c['raw'].items()}
        assert all(len(v)==c['n'] for v in c['raw'].values())
        assert c['branches']=={b:win_summary([v for i,v in enumerate(c['raw']['win']) if b=='all' or c['raw'][b][i]]) for b in BRANCHES}
        assert max(c['raw']['police_claims'])<=1
        if c['good'] in {'evidence_q0','evidence_q100','trained_local_q'}:
            ref=lookup['evidence_q50',c['mafia']]
            for k in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
                assert c['raw'][k]==ref['raw'][k]
        for sample in c['samples']:
            other=evaluate((phase,rules,gm[c['good']],mm[c['mafia']],sample['seed'],1))
            for k in c['raw']:assert other['raw'][k][0]==c['raw'][k][sample['index']]
            assert other['samples'][0]['trace_hash']==sample['trace_hash']
            assert other['samples'][0]['opening_hash']==sample['opening_hash'];replays+=1
    for m in mafia:
        a,b=lookup['evidence_q0',m.name],lookup['evidence_q100',m.name]
        for i,k in enumerate(a['raw']['narrow_civilian']):
            if k:assert b['raw']['police_claims'][i]-a['raw']['police_claims'][i]==1
result=dict(status='pass',cells_checked=count,sampled_full_replays=replays,assets_checked=len(f['assets']),games_recorded=manifest['games'],
    scope='Frozen-source hashes, arithmetic, branch invariance, single public police limit, endpoint exposure and sampled full replay; not all games rerun. Endpoint empirical certificate only.')
(ROOT/'results/v20_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
