#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'results/v26'
sys.path.insert(0,str(F/'source'))
from mafia_lab import strategies_v26 as d
from mafia_lab.police_execution_experiment_v26 import build_spec,simulate
from mafia_lab.simulation import opening,continue_game


class NightAPI:
 def __init__(self):self.actions=[];self.bus_witness=[]
 def __getattr__(self,k):return getattr(d,k)
 def choose_inspection(self,o,p,rng):
  t=d.choose_inspection(o,p,rng);self.actions.append(dict(day=o.day+1,action='inspection',actor=o.player,target=t));return t
 def choose_kill(self,o,p,rng):
  t=d.choose_kill(o,p,rng);self.actions.append(dict(day=o.day+1,action='kill',actor=o.player,target=t));return t
 def vote(self,o,p,rng,candidates=None):
  if o.role.value=='mafia':
   t=d.costless_bus_target(o,p,candidates)
   if t is not None:
    from collections import Counter
    kind='live_pk_vote' if candidates is not None else 'live_vote'
    votes={v:t for e in o.public_events if e.kind==kind and e.day==o.day for v,t in e.ballots}
    c=Counter(t for t in votes.values() if t is not None);remaining=len(o.alive)-len(votes)
    rival=max((c[q] for q in o.alive if q!=t),default=0);assert c[t]>rival+remaining
    self.bus_witness.append(dict(day=o.day,player=o.player,target=t,count=c[t],rival=rival,remaining=remaining))
  return d.vote(o,p,rng,candidates)


def main():
 f=json.loads((F/'freeze.json').read_text());held=json.loads((F/'holdout.json').read_text());r,gs,ms=build_spec(f['config']);G={g.name:g for g in gs};M={m.name:m for m in ms};D={(c['good'],c['mafia']):c for c in held['cells']};rows=[];count=0
 def replay(gn,mn,seed,index=None):
  nonlocal count
  g,m=G[gn],M[mn];row=simulate(r,g,m,seed,True)
  if index is not None:
   for k,v in D[gn,mn]['raw'].items():assert row['raw'][k]==v[index]
  s=opening(r,g,m,seed,d);o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
  assert sha256(repr(o.transcript).encode()).hexdigest()==row['trace_hash']
  api=NightAPI();s=opening(r,g,m,seed,api);z=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
  assert o==z and len(api.actions)==2*o.nights
  row['night_actions_evaluation_only']=api.actions;row['bus_witness']=api.bus_witness;count+=1;return row
 def pair(gn1,gn2,mn,kind,index):
  if index is None:return dict(kind=kind,mafia=mn,status='no_case')
  seed=D[gn1,mn]['seed_start']+index;runs={gn:replay(gn,mn,seed,index) for gn in (gn1,gn2)}
  first=None
  for x,y in zip(runs[gn1]['votes'],runs[gn2]['votes']):
   if (x['day'],x['round'],x['player'])!=(y['day'],y['round'],y['player']):break
   if x['target']!=y['target']:first=dict(control=x,treatment=y);break
  return dict(kind=kind,mafia=mn,status='replayed',seed=seed,index=index,runs=runs,first_vote_difference=first)
 for mn in ('late_far_claim_team','decoy_far_claim_team'):
  a,b=D['legacy_q50',mn],D['aligned_q50',mn]
  for kind in ('alignment_gain','alignment_loss','called_still_loss'):
   def test(i):
    x,y=a['raw']['win'][i],b['raw']['win'][i]
    return (not x and y) if kind=='alignment_gain' else (x and not y) if kind=='alignment_loss' else (not x and not y and b['raw']['call_count'][i]>0)
   idx=next((i for i in range(a['n']) if test(i)),None);rows.append(pair('legacy_q50','aligned_q50',mn,kind,idx))
 for mn in ('late_far_claim_team','late_far_claim_bus','decoy_far_claim_team','decoy_far_claim_bus'):
  c=D['history_q50',mn];idx=next((i for i,v in enumerate(c['raw']['history_changed_game']) if v),None)
  rows.append(pair('aligned_q50','history_q50',mn,'history_first_change',idx))
 old=[]
 for mn in ('late_near_restate_team','late_far_restate_team'):
  old.append(dict(seed=174000033,mafia=mn,runs={gn:replay(gn,mn,174000033) for gn in ('legacy_q50','aligned_q50')}))
 out=dict(scope='Prespecified first examples, reused held data; four old development replays are not fresh evidence.',held_sha256=sha256((F/'holdout.json').read_bytes()).hexdigest(),
  detailed_replays=count,unwrapped_replays=count,night_audited_replays=count,rows=rows,old_development=old)
 (ROOT/'results/v26_examples.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status='pass',detailed_replays=count,unwrapped_replays=count,night_audited_replays=count)))


if __name__=='__main__':main()
