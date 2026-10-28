#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v23'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
sys.path.insert(0,str(folder/'source'))
from mafia_lab import strategies_v23 as d
from mafia_lab.restatement_experiment_v23 import build_spec,evaluate,contrasts,matrix,ENDPOINTS
from mafia_lab.position_repair_experiment_v14 import _solution,_frozen
from mafia_lab.simulation import opening,continue_game
from mafia_lab.statistics import win_summary
r,gs,ms=build_spec(f['config']);gm={g.name:g for g in gs};mm={m.name:m for m in ms};names=list(mm)
s=json.loads((folder/'selection_before_holdout.json').read_text());gm['trained_local_q']=d.GoodPolicyV23(**s['policy'])
replays=cells_count=0;actual_games=0
for phase in ('train','holdout'):
    report=json.loads((folder/(phase+'.json')).read_text());assert report['contrasts']==contrasts(report['cells'])
    mat=matrix(report['cells'],names);assert report['matrix']==[[str(x) for x in row] for row in mat]
    if phase=='train':
        cert=_solution(mat,list(ENDPOINTS),names);assert cert==report['certificate']==s['certificate']
        assert cert['gap_exact']=='0' and Fraction(s['q_exact'])==Fraction(cert['good_mixture'].get('repair_q100','0'))
    else:
        assert report['frozen_bounds']==_frozen(mat,list(ENDPOINTS),names,s['certificate'])
        evaluated=s['alias_of'] or 'trained_local_q'
        selected={c['mafia']:c['win'] for c in report['cells'] if c['good']==evaluated}
        assert report['local_q_evaluation']['rates']==selected
        if s['alias_of']:assert Fraction(gm[s['alias_of']].response_probability)==Fraction(s['q_exact'])
    for c in report['cells']:
        cells_count+=1;actual_games+=c['n']
        assert c['win']==win_summary(c['raw']['win'])
        assert c['means']=={k:mean(v) for k,v in c['raw'].items() if k!='pre_day2_vote_hash'}
        assert all(len(v)==c['n'] for v in c['raw'].values())
        for flag in ('ignored_known','voted_good','illegal'):assert sum(c['raw'][flag+'_ballots'])==0
        if c['good']!='legacy_q50':
            assert sum(c['raw']['orphan_ballots'])==sum(c['raw']['stale_ballots'])==0
        if not mm[c['mafia']].restate:assert sum(c['raw']['repeat_count'])==0
        for sample in c['samples']:
            api=d;g=gm[c['good']];m=mm[c['mafia']];seed=sample['seed']
            initial=opening(r,g,m,seed,api)
            outcome=continue_game(initial,g,m,seed,trace=True,decision_api=api,public_ballots=True)
            assert sha256(repr(outcome.transcript).encode()).hexdigest()==sample['trace_hash']
            repeated=evaluate((phase,r,g,m,seed,1))
            for k in c['raw']:assert repeated['raw'][k][0]==c['raw'][k][sample['index']]
            replays+=1
assert actual_games==manifest['games']
result=dict(status='pass',actual_games=actual_games,cells_checked=cells_count,sampled_full_traces=replays,assets_checked=len(f['assets']),
    alias_reused=s['alias_of'],scope='Frozen-source hashes, all arithmetic, paired prefix/branch consistency, flags and 3 sampled unwrapped full traces per cell. Not all games independently rerun.')
(ROOT/'results/v23_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
