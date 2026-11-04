"""Declared first-occurrence cases; read-only, no new policy selection."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.relay_receiver_experiment_v30 import build_spec,simulate
from mafia_lab import strategies_v30 as d
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


def run():
 cfg=json.loads((ROOT/'results/v30/freeze.json').read_text())['config'];data=json.loads((ROOT/'results/v30/holdout.json').read_text())
 r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms};D={(c['good'],c['mafia']):c for c in data['cells']}
 chosen=[];keys=set()
 for mn in M:
  for field in ('relay_own_first_mismatch_ballots','incompatible_early_common_ballots','relay_false_source_count','police_own_first_mismatch_ballots'):
   options=[]
   for gn in G:
    c=D[gn,mn]
    for i,v in enumerate(c['raw'][field]):
     if v:options.append((c['seed_start']+i,gn,mn));break
   key=min(options) if options else None
   chosen.append(dict(mafia=mn,event=field,key=key))
   if key:keys.add(key)
  for a,b in [('notice','relay_guard'),('relay_typed','relay_guard'),('relay_guard','evidence_guard')]:
   options=[];x,y=D[a,mn],D[b,mn]
   for i,(v,w) in enumerate(zip(x['raw']['win'],y['raw']['win'])):
    if v!=w:
     options.append((x['seed_start']+i,mn));break
   key=options[0] if options else None;chosen.append(dict(mafia=mn,event=a+'->'+b+'_terminal_flip',key=key))
   if key:keys|={(key[0],a,mn),(key[0],b,mn)}
 # Earliest terminal flip for the declared opponent/false-authority contrasts.
 # Use receiver_guard for opponents and notice for false-authority, so a
 # no-relay effect can be explained without attributing it to gold voting.
 for pair in data['contrasts']:
  if not ((pair['kind']=='opponent' and pair['control'][0]=='relay_guard') or (pair['kind']=='false_authority' and pair['control'][0]=='notice')):continue
  a,b=tuple(pair['control']),tuple(pair['treatment']);x,y=D[a],D[b];key=None
  for i,(v,w) in enumerate(zip(x['raw']['win'],y['raw']['win'])):
   mask=True if pair['branch']=='selfkill' else x['raw']['dead_clear'][i]
   if mask and v!=w:key=x['seed_start']+i;break
  chosen.append(dict(event=pair['kind']+'_first_terminal_flip',control=a,treatment=b,seed=key))
  if key is not None:keys|={(key,a[0],a[1]),(key,b[0],b[1])}
 cases=[]
 for seed,gn,mn in sorted(keys):
  row=simulate(r,G[gn],M[mn],seed,details=True);cell=D[gn,mn];i=seed-cell['seed_start']
  assert all(v==cell['raw'][k][i] for k,v in row['raw'].items())
  s=opening(r,G[gn],M[mn],seed,d);o=continue_game(s,G[gn],M[mn],seed,trace=True,decision_api=d,public_ballots=True)
  assert row['trace_hash']==hash_events(o.transcript)
  cases.append(dict(good=gn,mafia=mn,**row))
 # Historical requested502-case audit: all 39 terminal gains, plus already
 # selected first gain and first same-terminal counterexample; no fresh sample.
 old=json.loads((ROOT/'results/v29/holdout.json').read_text());O={(c['good'],c['mafia']):c for c in old['cells']}
 x,y=O['plain','decoy_far_claim_team'],O['both','decoy_far_claim_team'];groups={}
 for i,k in enumerate(x['raw']['dead_clear']):
  if not k:continue
  label=f"{x['raw']['win'][i]}->{y['raw']['win'][i]}";g=groups.setdefault(label,dict(n=0,old_day1_mafia=0,new_day1_mafia=0,process_changed=0))
  g['n']+=1;g['old_day1_mafia']+=x['raw']['day1_mafia_exile'][i];g['new_day1_mafia']+=y['raw']['day1_mafia_exile'][i];g['process_changed']+=x['raw']['process_hash'][i]!=y['raw']['process_hash'][i]
 historical=json.loads((ROOT/'results/v29_examples.json').read_text());oldcases=[c for c in historical['cases'] if c['seed'] in {189000018,189000003} and c['mafia']=='decoy_far_claim_team' and c['good'] in {'plain','both'}]
 save(ROOT/'results/v30_examples.json',dict(selected=chosen,cases=cases,detail_runs=len(cases),direct_replays=len(cases),historical_v29_groups=groups,historical_cases=oldcases,new_validation_samples=0,
    limitation='Predeclared first occurrences in already evaluated data, descriptive only. Historical v29 cases and 502-case decomposition are reused evidence, not v30 confirmation.'))
 print(json.dumps(dict(detail_runs=len(cases),direct_replays=len(cases),historical_groups=groups)))

if __name__=='__main__':run()
