"""Frozen-data diagnosis and observation-local grant invariance checks."""
import sys,json
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab import strategies_v31 as d
from mafia_lab import strategies_v30 as old
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec,simulate,AuditAPI,PAIRS
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save
from mafia_lab.engine import Role

class GrantAudit(AuditAPI):
 def __init__(self):super().__init__();self.grant_checks=0;self.orphan_choices=[];self.defensive_reports=0
 def message(self,obs,policy,rng,context='day',override=None):
  result=d.message(obs,policy,rng,context,override)
  if obs.role==Role.POLICE and obs.day==1 and context=='day' and obs.deaths[0].player in d.teammates(obs) and result.kind=='report':
   assert any(m.kind=='report' and m.verdict and m.target in d.teammates(obs) for m in d.evidence.old.threats(obs))
   self.defensive_reports+=1
  return result
 def vote(self,obs,policy,rng,candidates=None):
  if obs.role!=Role.MAFIA and policy.neutral_conflicts and obs.day==1:
   view=d.explain(obs,policy,candidates)
   assert not (view['reason'] in {'compare_conflicting_sources','compare_live_conflicting_sources'} and view['history_edges'] and not view['live_edges'])
   if any(m.kind=='delegate' for m in obs.messages) and not any(m.kind=='relay' for m in obs.messages):
    without=replace(obs,messages=tuple(m for m in obs.messages if m.kind!='delegate'))
    a,b=d.explain(obs,policy,candidates),d.explain(without,policy,candidates)
    assert a['target']==b['target'] and a['reason']==b['reason'] and a['history_edges']==b['history_edges']
    self.grant_checks+=1
  return super().vote(obs,policy,rng,candidates)


def run():
 f=json.loads((ROOT/'results/v31/freeze.json').read_text());cfg=f['config'];data=json.loads((ROOT/'results/v31/holdout.json').read_text())
 r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms};D={(c['good'],c['mafia']):c for c in data['cells']}
 selected=[];keys=set()
 for mn in M:
  for a,b in PAIRS:
   x,y=D[a,mn],D[b,mn];mask=[1]*x['n'] if mn.startswith('false_') else x['raw']['dead_clear']
   for kind in ('gain','loss','same_terminal_process_change'):
    seed=None
    for i,k in enumerate(mask):
     if not k:continue
     p,q=x['raw']['win'][i],y['raw']['win'][i]
     yes=(p==0 and q==1) if kind=='gain' else (p==1 and q==0) if kind=='loss' else p==q and x['raw']['process_hash'][i]!=y['raw']['process_hash'][i]
     if yes:seed=x['seed_start']+i;break
    selected.append(dict(mafia=mn,pair=[a,b],event=kind,seed=seed))
    if seed is not None:keys|={(seed,a,mn),(seed,b,mn)}
  for field in ('relay_own_first_mismatch_ballots','police_own_first_mismatch_ballots'):
   candidates=[]
   for gn in G:
    c=D[gn,mn]
    for i,v in enumerate(c['raw'][field]):
     if v:candidates.append((c['seed_start']+i,gn,mn));break
   key=min(candidates) if candidates else None;selected.append(dict(event=field,mafia=mn,key=key))
   if key:keys.add(key)
 cases=[];grant_checks=0;defensive_reports=0
 for seed,gn,mn in sorted(keys):
  row=simulate(r,G[gn],M[mn],seed,True);cell=D[gn,mn];i=seed-cell['seed_start']
  assert all(v==cell['raw'][k][i] for k,v in row['raw'].items())
  s=opening(r,G[gn],M[mn],seed,d);o=continue_game(s,G[gn],M[mn],seed,trace=True,decision_api=d,public_ballots=True)
  assert hash_events(o.transcript)==row['trace_hash'];cases.append(dict(good=gn,mafia=mn,**row))
 # Three declared samples per row/column: selective mutation of observations,
 # not an altered full game and not an extra outcome comparison.
 for gn in ('neutral','aligned'):
  for mn in M:
   for sample in D[gn,mn]['samples']:
    api=GrantAudit();s=opening(r,G[gn],M[mn],sample['seed'],api)
    o=continue_game(s,G[gn],M[mn],sample['seed'],trace=True,decision_api=api,public_ballots=True)
    assert hash_events(o.transcript)==sample['trace_hash'];grant_checks+=api.grant_checks;defensive_reports+=api.defensive_reports
 historical=[]
 for seed,mn in [(192000016,'false_notice'),(192000016,'false_grant'),(192000073,'decoy_old'),(192000073,'decoy_copy')]:
  for gn in G:
   row=simulate(r,G[gn],M[mn],seed,True)
   if gn=='legacy':
    s=opening(r,G[gn],M[mn],seed,old);o=continue_game(s,G[gn],M[mn],seed,trace=True,decision_api=old,public_ballots=True)
    assert hash_events(o.transcript)==row['trace_hash']
   historical.append(dict(good=gn,mafia=mn,**row))
 # Half-sample directions and whole-team mixtures are fixed descriptive tables.
 blocks=[];mixtures=[]
 for gn in G:
  for knife in ('late','decoy'):
   for mode in ('copy','quiet'):
    x,y=D[gn,knife+'_old']['raw'],D[gn,knife+'_'+mode]['raw']
    for lo,hi in ((0,1024),(1024,2048)):
     ids=[i for i in range(lo,hi) if x['dead_clear'][i]]
     blocks.append(dict(good=gn,knife=knife,mode=mode,block=[lo,hi],n=len(ids),delta=sum(y['win'][i]-x['win'][i] for i in ids)/len(ids)))
    if gn=='aligned':
     for frac in (0,.25,.5,.75,1):
      mixtures.append(dict(knife=knife,mode=mode,opponent_share=frac,good_win=(1-frac)*sum(x['win'])/2048+frac*sum(y['win'])/2048,
         interpretation='Entire mafia team selects one frozen plan at opening with shared randomization; arithmetic expected payoff, no new simulation or equilibrium.'))
 result=dict(selected=selected,cases=cases,detail_runs=len(cases),direct_replays=len(cases),
   grant_prefix_checks=grant_checks,defensive_report_checks=defensive_reports,grant_audit_games=48,historical_cases=historical,historical_runs=len(historical),
   historical_legacy_direct_replays=4,blocks=blocks,mixtures=mixtures,new_validation_samples=0,
   limitation='Descriptive cases from existing evaluation; old cases reused. Half blocks and mixtures not additional independent confirmations.')
 save(ROOT/'results/v31_examples.json',result);print(json.dumps({k:result[k] for k in ('detail_runs','direct_replays','grant_prefix_checks','grant_audit_games','historical_runs','historical_legacy_direct_replays')}))

if __name__=='__main__':run()
