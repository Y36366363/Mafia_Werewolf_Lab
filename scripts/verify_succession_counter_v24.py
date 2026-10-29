#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v24'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
sys.path.insert(0,str(folder/'source'))
from mafia_lab import strategies_v24 as d
from mafia_lab.succession_experiment_v24 import build_spec,evaluate,contrasts,coverage,matrix,ENDPOINTS,HASH_KEYS
from mafia_lab.position_repair_experiment_v14 import _solution,_frozen
from mafia_lab.simulation import opening,continue_game
from mafia_lab.statistics import win_summary
r,gs,ms=build_spec(f['config']);gm={g.name:g for g in gs};mm={m.name:m for m in ms};names=list(mm)
s=json.loads((folder/'selection_before_holdout.json').read_text());gm['trained_local_q']=d.GoodPolicyV24(**s['policy'])
replays=count=games=0
for phase in ('train','holdout'):
    report=json.loads((folder/(phase+'.json')).read_text())
    assert report['contrasts']==contrasts(report['cells'])
    assert report['coverage']==coverage(report['cells'])
    mat=matrix(report['cells'],names);assert report['matrix']==[[str(x) for x in row] for row in mat]
    by_key={(c['good'],c['mafia']):c for c in report['cells']}
    for mn in names:
        reference=by_key['repair_q0',mn]
        for gn in ('repair_q50','repair_q100'):
            for key in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
                assert reference['raw'][key]==by_key[gn,mn]['raw'][key]
            other=by_key[gn,mn]
            assert reference['raw']['narrow_civilian']==other['raw']['narrow_civilian']
            for i,active in enumerate(reference['raw']['narrow_civilian']):
                if not active:
                    assert reference['raw']['day1_hash'][i]==other['raw']['day1_hash'][i]
                    assert reference['raw']['win'][i]==other['raw']['win'][i]
    if phase=='train':
        cert=_solution(mat,list(ENDPOINTS),names)
        assert cert==report['certificate']==s['certificate'] and cert['gap_exact']=='0'
        assert Fraction(s['q_exact'])==Fraction(cert['good_mixture'].get('repair_q100','0'))
    else:assert report['frozen_bounds']==_frozen(mat,list(ENDPOINTS),names,s['certificate'])
    for c in report['cells']:
        count+=1;games+=c['n']
        assert c['win']==win_summary(c['raw']['win'])
        assert c['means']=={k:mean(v) for k,v in c['raw'].items() if k not in HASH_KEYS}
        assert all(len(v)==c['n'] for v in c['raw'].values())
        for flag in ('orphan','stale','ignored_known','voted_good','illegal'):assert sum(c['raw'][flag+'_ballots'])==0
        if mm[c['mafia']].succession=='none':assert sum(c['raw']['succession_count'])==0
        for sample in c['samples']:
            g=gm[c['good']];m=mm[c['mafia']];seed=sample['seed']
            initial=opening(r,g,m,seed,d)
            outcome=continue_game(initial,g,m,seed,trace=True,decision_api=d,public_ballots=True)
            assert sha256(repr(outcome.transcript).encode()).hexdigest()==sample['trace_hash']
            repeated=evaluate((phase,r,g,m,seed,1))
            for k in c['raw']:assert repeated['raw'][k][0]==c['raw'][k][sample['index']]
            replays+=1
assert games==manifest['games']
result=dict(status='pass',actual_games=games,cells_checked=count,sampled_full_traces=replays,
            assets_checked=len(f['assets']),alias_reused=s['alias_of'],
            scope='All hashes/arithmetic/paired prefixes and mechanism flags; 3 sampled independent unwrapped traces per cell, not all games rerun.')
(ROOT/'results/v24_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
