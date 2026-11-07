"""Frozen diagnostics and deterministic replays; no receiver fitting."""
import sys,json,gzip
from pathlib import Path
from hashlib import sha256
from dataclasses import replace
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_source_generation_v33 import spec,simulate
from analyze_source_hypotheses_v32 import read_obs
from mafia_lab.source_generation_v33 import GenerationAPI
from mafia_lab.source_hypotheses_v32 import ResponseAPI,role_support
from mafia_lab import strategies_v31 as base
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save

def result_bytes(out,name):
 path=out/name
 return path.read_bytes() if path.exists() else gzip.decompress((out/(name+'.gz')).read_bytes())

class CheckAPI(GenerationAPI):
 def __init__(self,mode,cooperation):super().__init__(mode,cooperation);self.checks=0
 def vote(self,obs,policy,rng,candidates=None):
  target=super().vote(obs,policy,rng,candidates)
  if obs.role!=Role.MAFIA:
   v=base.explain(obs,policy,candidates)
   assert target is None or target in v['legal']
   assert not v['known_bad'] or target in v['known_bad']
   assert target not in v['known_good'];self.checks+=1
  return target


def main():
 out=ROOT/'results/v33';f=json.loads((out/'freeze.json').read_text());cfg=f['config'];r,g,plans,bc=spec(cfg);P={p[0]:p for p in plans}
 for rel,h in f['assets'].items():
  assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
  assert sha256((out/'source'/rel).read_bytes()).hexdigest()==h
 for rel,h in json.loads((out/'manifest.json').read_text())['files'].items():assert sha256(result_bytes(out,rel)).hexdigest()==h
 counts=dict(replays=0,baseline_replays=0,ballot_checks=0,logic_prefixes=0,interval_crosschecks=0)
 summaries=[];events=[];examples=[]
 for phase in ('train','holdout'):
  data=json.loads(result_bytes(out,phase+'.json'))
  for cell in data['cells']:
   mode=cell['mode'];name=cell['mafia'];_,m,coop=P[name];rows=cell['rows']
   assert [x['seed'] for x in rows]==list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
   for index in (0,len(rows)//2,len(rows)-1):
    raw=rows[index];api=CheckAPI(mode,coop);s=opening(r,g,m,raw['seed'],api);o=continue_game(s,g,m,raw['seed'],trace=True,decision_api=api,public_ballots=True)
    assert hash_events(o.transcript)==raw['trace_hash'];counts['replays']+=1;counts['ballot_checks']+=api.checks
    if mode=='hide' and coop=='ordinary':
     api=ResponseAPI(True);s=opening(r,g,m,raw['seed'],api);o=continue_game(s,g,m,raw['seed'],trace=True,decision_api=api,public_ballots=True)
     assert hash_events(o.transcript)==raw['trace_hash'];counts['baseline_replays']+=1
   if mode!='hide':assert all(x['day1_live_police_reports']<=1 for x in rows)
   for row in rows:
    for opp in row['opportunities']:
     if mode!='hide' and opp['prior_live_team']:assert not opp['reported']
     if mode=='self' and opp['dead_team_report'] and not opp['self_hit']:assert not opp['reported']
    d=row.get('diagnostic')
    if d and 'support' in d:
     obs=read_obs(d['observation']);z=role_support(obs,d['dead_source'],d['live_source']);assert z==d['support']
     without=replace(obs,messages=tuple(m for m in obs.messages if m.kind!='delegate'));assert role_support(without,d['dead_source'],d['live_source'])==z
     key=('P' if d['dead_role']=='police' else 'M')+'/'+('-' if d['live_role'] is None else 'P' if d['live_role']=='police' else 'M')
     assert key in z['counts'];counts['logic_prefixes']+=1
   branch=[x for x in rows if x['dead_clear']]
   summaries.append(dict(phase=phase,mode=mode,mafia=name,n=len(rows),wins=sum(x['win'] for x in rows),exiles=sum(x['day1_mafia_exile'] for x in rows),
     day1_police_reports=sum(x['day1_live_police_reports'] for x in rows)/len(rows),night2_cop_deaths=sum(x['night2_police_death'] for x in rows)/len(rows),
     cops_at_day2=sum(x['police_at_day2'] for x in rows)/len(rows),
     opportunity_games=sum(any(a['prior_outsider'] and not a['prior_live_team'] for a in x['opportunities']) for x in rows),no_later_opportunity_games=sum(not any(a['prior_outsider'] for a in x['opportunities']) for x in rows),dead_clear_n=len(branch),dead_clear_wins=sum(x['win'] for x in branch),dead_clear_exiles=sum(x['day1_mafia_exile'] for x in branch)))
   tags=sorted({x['diagnostic']['event'] for x in rows if 'diagnostic' in x})
   for tag in tags:
    sample=[x['diagnostic'] for x in rows if x.get('diagnostic',{}).get('event')==tag]
    types={}
    for d in sample:
     key=('P' if d['dead_role']=='police' else 'M')+'/'+('-' if d['live_role'] is None else 'P' if d['live_role']=='police' else 'M')
     types[key]=types.get(key,0)+1
    events.append(dict(phase=phase,mode=mode,mafia=name,event=tag,n=len(sample),source_types=types,
      mafia_gold=sum(d['gold_role']=='mafia' for d in sample),two_live_sources=sum(d['end_live_sources']>=2 for d in sample)))
  for c in data['contrasts']:
   for metric in ('win','day1_mafia_exile'):
    v=c[metric];n=c['n'];tail=v['precision']['tail_alpha']
    for key,k in [('p_plus',v['gains']),('p_minus',v['losses'])]:
     ci=binomtest(k,n).proportion_ci(confidence_level=1-2*tail,method='exact')
     assert abs(ci.low-v['precision'][key][0])<1e-9 and abs(ci.high-v['precision'][key][1])<1e-9;counts['interval_crosschecks']+=1
  if phase=='holdout':
   D={(c['mode'],c['mafia']):c['rows'] for c in data['cells']}
   selections=[('self_copy_team','hide','mafia_gold',lambda x:'diagnostic' in x and x['diagnostic']['gold_role']=='mafia'),
               ('self_hit_late','available','no_opportunity',lambda x:'diagnostic' in x and not any(a['prior_outsider'] for a in x['opportunities'])),
               ('late_old','self','self_defense',lambda x:any(a['self_hit'] and a['reported'] for a in x['opportunities']))]
   for name,mode,label,pred in selections:
    row=next((x for x in D[mode,name] if pred(x)),None)
    if row:
     _,m,coop=P[name];detail=simulate(r,g,m,coop,mode,row['seed'],True,True);assert detail['trace_hash']==row['trace_hash']
     examples.append(dict(mafia=name,mode=mode,label=label,**detail))
 # Descriptive paired loss: first accepted seed where both versions exile
 # mafia on day one but the more responsive version loses the terminal game.
   a,b=D['self','late_copy'],D['available','late_copy']
   pair=next(((u,v) for u,v in zip(a,b) if u['win']==1 and v['win']==0 and u['day1_mafia_exile']==v['day1_mafia_exile']==1),None)
   if pair:
    _,m,coop=P['late_copy']
    for mode,row in zip(('self','available'),pair):
     detail=simulate(r,g,m,coop,mode,row['seed'],True,True);assert detail['trace_hash']==row['trace_hash']
     examples.append(dict(mafia='late_copy',mode=mode,label='paired_terminal_loss_after_day1_mafia_exile',**detail))
 save(ROOT/'results/v33_diagnostics.json',dict(**counts,summaries=summaries,events=events,examples=examples,case_replays=len(examples),
   limitation='No new acceptance seeds; frequencies are descriptive, logical support a necessary-constraint superset. Source probabilities and civilian policies not fitted.'))
 print(json.dumps(counts))

if __name__=='__main__':main()
