#!/usr/bin/env python3
"""Bookkeeping and provenance checks; no fresh performance evidence."""
import json
from pathlib import Path
from hashlib import sha256
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
def digest(p):return sha256((ROOT/p).read_bytes()).hexdigest()
plan=load('results/v26_diagnostic_before_holdout.json');assert not plan['holdout_exists'] and not plan['train_numbers_read']
for p,h in plan['files'].items():assert digest(p)==h
held=load('results/v26/holdout.json');D={(c['good'],c['mafia']):c for c in held['cells']};ex=load('results/v26_examples.json');assert ex['held_sha256']==digest('results/v26/holdout.json')
count=history_votes=bus=0
for row in ex['rows']:
 mn=row['mafia'];kind=row['kind']
 if kind.startswith('history'):
  names=('aligned_q50','history_q50');b=D[names[1],mn]
  ix=next((i for i,v in enumerate(b['raw']['history_changed_game']) if v),None)
 else:
  names=('legacy_q50','aligned_q50');a,b=D[names[0],mn],D[names[1],mn]
  def pred(i):
   x,y=a['raw']['win'][i],b['raw']['win'][i]
   return (not x and y) if kind=='alignment_gain' else (x and not y) if kind=='alignment_loss' else (not x and not y and b['raw']['call_count'][i]>0)
  ix=next((i for i in range(a['n']) if pred(i)),None)
 if ix is None:assert row['status']=='no_case';continue
 assert row['status']=='replayed' and row['index']==ix and row['seed']==b['seed_start']+ix
 for name,run in row['runs'].items():
  c=D[name,mn]
  for k,v in run['raw'].items():assert v==c['raw'][k][ix]
  count+=1
  for v in run['votes']:
   assert not v['call_mismatch'] and not v['illegal'] and not v['voted_good'] and not v['ignored_known']
   if v['history_changed']:assert v['target'] in v['history_pool'] and not v['known_bad']
   scores=Counter();seen=set()
   for e in v['history_evidence']:
    assert e['day']<=v['day'] and (e['day'],e['voter']) not in seen
    seen.add((e['day'],e['voter']));assert e['value'] in (-1,1);scores[e['voter']]+=e['value']
   for p,value in v['history_scores'].items():assert value==scores[int(p)] and abs(value)<=v['day']
   history_votes+=bool(v['history_evidence'])
  for w in run['bus_witness']:
   assert w['count']>w['rival']+w['remaining']
   events=[e for e in run['transcript'] if e['day']==w['day'] and e['event'] in ('votes','pk_votes')]
   tallies=[Counter(t for t in e['payload'].values() if t is not None) for e in events]
   assert any(c[w['target']]>max((n for p,n in c.items() if p!=w['target']),default=0) for c in tallies)
   bus+=1
# Four development trajectories are explicitly excluded from new held evidence.
assert len(ex['old_development'])==2
for row in ex['old_development']:
 assert row['seed']==174000033 and set(row['runs'])=={'legacy_q50','aligned_q50'}
 count+=2
assert count==ex['detailed_replays']==ex['unwrapped_replays']==ex['night_audited_replays']
extra=load('results/v26_bus_signal_example.json')
assert extra['input_sha256']['holdout']==digest('results/v26/holdout.json')
assert extra['input_sha256']['selected_examples']==digest('results/v26_examples.json')
selected=next(r for r in ex['rows'] if r['kind']=='history_first_change' and r['mafia']=='decoy_far_claim_team')
assert extra['seed']==selected['seed']
for mode,run in extra['runs'].items():
 c=D['history_q50','decoy_far_claim_'+mode];i=extra['seed']-c['seed_start']
 for k,v in run['raw'].items():assert v==c['raw'][k][i]
out=dict(status='pass',case_replays_checked=count,history_evidence_ballots_checked=history_votes,bus_witnesses_checked=bus,posthoc_bus_runs_checked=len(extra['runs']),
         scope='Checks stored provenance, first-seed selection, raw equality, count bounds and bus winner witnesses. No additional simulations or general robustness claim.')
(ROOT/'results/v26_aux_integrity_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
