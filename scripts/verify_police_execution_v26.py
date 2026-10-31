#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
from statistics import mean
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'results/v26'
f=json.loads((F/'freeze.json').read_text());manifest=json.loads((F/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((F/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((F/n).read_bytes()).hexdigest()==h
sys.path.insert(0,str(F/'source'))
from mafia_lab import strategies_v26 as d
from mafia_lab import strategies_v25 as old
from mafia_lab.police_execution_experiment_v26 import build_spec,evaluate,contrasts,HASH_KEYS
from mafia_lab.simulation import opening,continue_game
from mafia_lab.statistics import win_summary
r,gs,ms=build_spec(f['config']);G={g.name:g for g in gs};M={m.name:m for m in ms}
games=count=replays=compat=intervals=0
for phase in ('train','holdout'):
 report=json.loads((F/(phase+'.json')).read_text());assert report['contrasts']==contrasts(report['cells'])
 D={(c['good'],c['mafia']):c for c in report['cells']}
 assert set(D)=={tuple(k) for k in f['config']['cells']}
 for mn in {m for _,m in D if m.endswith('_team')}:
  for pre in ('legacy','aligned'):
   a=D[pre+'_q0',mn]
   for q in ('50','100'):
    b=D[pre+'_q'+q,mn]
    for i,active in enumerate(a['raw']['narrow_civilian']):
     if not active:assert a['raw']['day1_hash'][i]==b['raw']['day1_hash'][i] and a['raw']['win'][i]==b['raw']['win'][i]
 for c in report['cells']:
  count+=1;games+=c['n'];g=G[c['good']];m=M[c['mafia']]
  assert c['win']==win_summary(c['raw']['win'])
  assert c['means']=={k:mean(v) for k,v in c['raw'].items() if k not in HASH_KEYS}
  assert all(len(v)==c['n'] for v in c['raw'].values())
  for flag in ('orphan','stale','ignored_known','voted_good','illegal','call_mismatch'):assert sum(c['raw'][flag+'_ballots'])==0
  if not g.execution_call:assert sum(c['raw']['call_count'])==0
  if not g.vote_history:assert sum(c['raw']['history_changed_ballots'])==sum(c['raw']['history_available_ballots'])==0
  if m.vote_mode=='team':assert sum(c['raw']['bus_count'])==0
  for sample in c['samples']:
   seed=sample['seed'];s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
   assert sha256(repr(o.transcript).encode()).hexdigest()==sample['trace_hash']
   z=evaluate((phase,r,g,m,seed,1))['raw']
   for k in c['raw']:assert z[k][0]==c['raw'][k][sample['index']]
   if not g.execution_call and m.vote_mode=='team':
    other=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True);assert other.transcript==o.transcript;compat+=1
   replays+=1
 for z in report['contrasts']:
  if 'precision' in z:
   v=z['win'];p=z['precision'];tail=p['tail_alpha']
   for key,prob in [('improved','p_plus'),('worsened','p_minus')]:
    ci=binomtest(v[key],v['n']).proportion_ci(confidence_level=1-2*tail,method='exact')
    assert max(abs(ci.low-p[prob][0]),abs(ci.high-p[prob][1]))<1e-10;intervals+=1
assert games==manifest['games']
plan=json.loads((F/'no_selection_before_holdout.json').read_text());assert not plan['policy_selection'] and not plan['q_selection']
out=dict(status='pass',formal_games=games,cells_checked=count,sampled_unwrapped_replays=replays,legacy_v25_compatible_replays=compat,independent_binomial_intervals=intervals,assets_checked=len(f['assets']),scope='All archived arithmetic/hash/invariants and three sampled unwrapped trajectories per cell; not all games independently rerun.')
(ROOT/'results/v26_integrity_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
