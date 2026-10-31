#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
from statistics import mean
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'results/v25'
f=json.loads((F/'freeze.json').read_text());manifest=json.loads((F/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((F/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((F/n).read_bytes()).hexdigest()==h
sys.path.insert(0,str(F/'source'))
from mafia_lab import strategies_v25 as d
from mafia_lab import strategies_v24 as old
from mafia_lab.source_advice_experiment_v25 import build_spec,evaluate,contrasts,HASH_KEYS
from mafia_lab.simulation import opening,continue_game
from mafia_lab.statistics import win_summary
r,gs,ms=build_spec(f['config']);gm={g.name:g for g in gs};mm={m.name:m for m in ms}
games=count=replays=compat=intervals=0
for phase in ('train','holdout'):
 report=json.loads((F/(phase+'.json')).read_text());assert report['contrasts']==contrasts(report['cells'])
 lookup={(c['good'],c['mafia']):c for c in report['cells']}
 for mn in mm:
  for pre in ('base','gate'):
   a=lookup[pre+'_q0',mn]
   for q in ('50','100'):
    b=lookup[pre+'_q'+q,mn]
    for i,active in enumerate(a['raw']['narrow_civilian']):
     if not active:assert a['raw']['day1_hash'][i]==b['raw']['day1_hash'][i] and a['raw']['win'][i]==b['raw']['win'][i]
 for c in report['cells']:
  count+=1;games+=c['n'];assert c['win']==win_summary(c['raw']['win'])
  assert c['means']=={k:mean(v) for k,v in c['raw'].items() if k not in HASH_KEYS}
  assert all(len(v)==c['n'] for v in c['raw'].values())
  for flag in ('orphan','stale','ignored_known','voted_good','illegal'):assert sum(c['raw'][flag+'_ballots'])==0
  if c['good'].startswith('base'):assert sum(c['raw']['blocked_advice_ballots'])==0
  for sample in c['samples']:
   g,m,seed=gm[c['good']],mm[c['mafia']],sample['seed'];s=opening(r,g,m,seed,d)
   o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
   assert sha256(repr(o.transcript).encode()).hexdigest()==sample['trace_hash']
   raw=evaluate((phase,r,g,m,seed,1))['raw']
   for k in c['raw']:assert raw[k][0]==c['raw'][k][sample['index']]
   if c['good'].startswith('base'):
    z=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
    assert z.transcript==o.transcript;compat+=1
   replays+=1
 for z in report['contrasts']:
  if z['primary']:
   v=z['win'];p=z['precision'];n=v['n'];t=p['tail_alpha'];aa=[]
   for count_key,prob_key in (('improved','p_plus'),('worsened','p_minus')):
    ci=binomtest(v[count_key],n).proportion_ci(confidence_level=1-2*t,method='exact')
    assert max(abs(ci.low-p[prob_key][0]),abs(ci.high-p[prob_key][1]))<1e-10;intervals+=1
assert games==manifest['games']
assert json.loads((F/'no_selection_before_holdout.json').read_text())['holdout_unread']
result=dict(status='pass',formal_games=games,cells_checked=count,sampled_unwrapped_replays=replays,
 baseline_v24_compatible_replays=compat,independent_binomial_intervals=intervals,assets_checked=len(f['assets']),
 scope='All hashes/arithmetic/invariants; three sampled full traces per cell plus archived API compatibility for base. Not all formal games independently rerun.')
(ROOT/'results/v25_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
