"""Read frozen risk experiment, verify invariants, report coverage not rare wins."""
import sys,json,gzip
from pathlib import Path
from hashlib import sha256
from dataclasses import replace
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_day1_risk_v34 import spec,simulate
from mafia_lab.day1_risk_v34 import RiskAPI,public_context,explain
from mafia_lab.source_generation_v33 import GenerationAPI
from mafia_lab.source_hypotheses_v32 import role_support
from analyze_source_hypotheses_v32 import read_obs
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save
from mafia_lab import strategies_v31 as base
from mafia_lab.engine import Role


def read_phase(out,phase):return json.loads(gzip.decompress((out/(phase+'.json.gz')).read_bytes()))

class VerifyAPI(RiskAPI):
 def __init__(self,*args):super().__init__(*args);self.next_day_checks=0;self.ballots=0
 def vote(self,obs,policy,rng,candidates=None):
  target=super().vote(obs,policy,rng,candidates)
  if obs.role!=Role.MAFIA:
   v=explain(obs,policy,self.receiver,candidates)
   assert target is None or target in v['legal']
   assert not v['known_bad'] or target in v['known_bad']
   assert target not in v['known_good'];self.ballots+=1
   if obs.day>=2:
    old=base.explain(obs,policy,candidates);assert target==old['target'] and v['reason']==old['reason'];self.next_day_checks+=1
  return target


def main():
 out=ROOT/'results/v34';f=json.loads((out/'freeze.json').read_text());cfg=f['config'];r,g,plans,bc=spec(cfg);P={p[0]:p for p in plans}
 for rel,h in f['assets'].items():assert sha256((ROOT/rel).read_bytes()).hexdigest()==h and sha256((out/'source'/rel).read_bytes()).hexdigest()==h
 for rel,h in json.loads((out/'manifest.json').read_text())['files'].items():assert sha256((out/rel).read_bytes()).hexdigest()==h
 counts=dict(replays=0,baseline_replays=0,ballot_checks=0,next_day_checks=0,logic_prefixes=0,interval_crosschecks=0)
 summaries=[];coverage=[];examples=[]
 for phase in ('train','holdout'):
  data=read_phase(out,phase);D={(c['mode'],c['receiver'],c['mafia']):c['rows'] for c in data['cells']}
  for cell in data['cells']:
   mode,receiver,mn=cell['mode'],cell['receiver'],cell['mafia'];rows=cell['rows'];plan=P[mn];_,m,coop,fake=plan
   assert [x['seed'] for x in rows]==list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
   assert all(x['day2_overrides']==0 for x in rows)
   for index in (0,len(rows)//2,len(rows)-1):
    row=rows[index];api=VerifyAPI(mode,coop,receiver,fake);s=opening(r,g,m,row['seed'],api);o=continue_game(s,g,m,row['seed'],trace=True,decision_api=api,public_ballots=True)
    assert hash_events(o.transcript)==row['trace_hash']
    assert all(not v['own_relay_mismatch'] for v in api.risk_votes if v['day']==1 and v['round']=='first')
    counts['replays']+=1;counts['ballot_checks']+=api.ballots;counts['next_day_checks']+=api.next_day_checks
    if receiver=='original' and not fake:
     api=GenerationAPI(mode,coop);s=opening(r,g,m,row['seed'],api);o=continue_game(s,g,m,row['seed'],trace=True,decision_api=api,public_ballots=True)
     assert hash_events(o.transcript)==row['trace_hash'];counts['baseline_replays']+=1
   for row in rows:
    if 'logic_sample' not in row:continue
    q=row['logic_sample'];obs=read_obs(q['observation']);support=role_support(obs,q['dead_source'],q['live_source']);assert support==q['support'];counts['logic_prefixes']+=1
   context=[x for x in rows if x['context']];eligible=[x for x in context if x['context']['eligible']]
   cc=dict(phase=phase,mode=mode,receiver=receiver,mafia=mn,n=len(rows),context_n=len(context),eligible_n=len(eligible),
     eligible_mafia_gold=sum(x['context_evaluation_only']['gold_role']=='mafia' for x in eligible),
     eligible_police_report=sum(x['live_police_report'] for x in eligible),
     false_gold_context=sum(x['context_evaluation_only']['gold_role']=='mafia' for x in context),
     false_gold_with_police=sum(x['context_evaluation_only']['gold_role']=='mafia' and x['live_police_report'] for x in context),
     false_gold_eligible_with_police=sum(x['context_evaluation_only']['gold_role']=='mafia' and x['live_police_report'] for x in eligible),
     false_gold_eligible_with_opportunity=sum(x['context_evaluation_only']['gold_role']=='mafia' and any(p['prior_outsider'] and not p['prior_live_team'] for p in x['opportunities']) for x in eligible),
     false_gold_eligible_four_opportunities=sum(x['context_evaluation_only']['gold_role']=='mafia' and sum(p['prior_outsider'] and not p['prior_live_team'] for p in x['opportunities'])==4 for x in eligible),
     different_report=sum('different_report' in x['context']['blocks'] for x in context),
     source_challenge=sum('source_challenge' in x['context']['blocks'] for x in context),
     risk_games=sum(bool(x['first_round_risk_votes']) for x in rows),fake_call_games=sum(bool(x['fake_calls']) for x in rows),
     fake_calls_qualified=sum(bool(x['fake_calls']) and bool(x['context']) and x['context']['eligible'] for x in rows))
   coverage.append(cc)
   summaries.append(dict(phase=phase,mode=mode,receiver=receiver,mafia=mn,n=len(rows),wins=sum(x['win'] for x in rows),
      mafia_exiles=sum(x['day1_mafia_exile'] for x in rows),police_exiles=sum(x['day1_police_exile'] for x in rows),
      all_day_own_relay_first_mismatches=sum(x['own_relay_first_mismatches'] for x in rows),public_police=sum(x['day1_police_reports'] for x in rows)/len(rows),night2_cop_death=sum(x['night2_police_death'] for x in rows)/len(rows),
      eligible_wins=sum(x['win'] for x in eligible),context_wins=sum(x['win'] for x in context)))
  for mode in cfg['police_modes']:
   for mn in P:
    reference=D[mode,'original',mn]
    for receiver in ('first_live','conditional_gold'):
     assert [x['context'] for x in reference]==[x['context'] for x in D[mode,receiver,mn]]
  for c in data['contrasts']:
   a,b=D[tuple(c['control'])],D[tuple(c['treatment'])]
   assert all(x['opening_hash']==y['opening_hash'] and x['ordinary_hash']==y['ordinary_hash'] for x,y in zip(a,b))
   for metric in ('win','day1_mafia_exile'):
    v=c[metric];assert v['counts']==[sum(x[metric] for x in a),sum(y[metric] for y in b)]
    for label,k in [('p_plus',v['gains']),('p_minus',v['losses'])]:
     ci=binomtest(k,c['n']).proportion_ci(confidence_level=1-2*v['precision']['tail_alpha'],method='exact')
     assert abs(ci.low-v['precision'][label][0])<1e-9 and abs(ci.high-v['precision'][label][1])<1e-9;counts['interval_crosschecks']+=1
  if phase=='holdout':
   # First qualifying examples from fixed acceptance, never new seed searches.
   selectors=[('self','original','self_copy_team_relay','fake_gold_uncontested',lambda x:bool(x['context']) and x['context']['eligible'] and x['context_evaluation_only']['gold_role']=='mafia'),
]
   for mode,receiver,mn,label,pred in selectors:
    row=next((x for x in D[mode,receiver,mn] if pred(x)),None)
    if row:
     detail=simulate(r,g,P[mn],mode,receiver,row['seed'],True,True);assert detail['trace_hash']==row['trace_hash'];examples.append(dict(mode=mode,receiver=receiver,mafia=mn,label=label,**detail))
   if examples:
    start=next((e for e in examples if e['label']=='fake_gold_uncontested'),None)
    if start:
     mn='self_copy_team_relay';index=start['seed']-cfg['holdout']['seed_start'];row=D['available','original',mn][index]
     detail=simulate(r,g,P[mn],'available','original',row['seed'],True,True);assert detail['trace_hash']==row['trace_hash']
     assert detail['context'] and not detail['context']['eligible'] and detail['live_police_report']
     examples.append(dict(mode='available',receiver='original',mafia=mn,label='same_deal_police_breaks_false_consensus',**detail))
   for mode in cfg['police_modes']:
    for receiver in ('first_live','conditional_gold'):
     for label,condition in [('gain',lambda a,b:a['win']==0 and b['win']==1),('loss',lambda a,b:a['win']==1 and b['win']==0)]:
      pair=None
      for mn in sorted(P):
       found=next(((mn,a,b) for a,b in zip(D[mode,'original',mn],D[mode,receiver,mn]) if condition(a,b)),None)
       if found:pair=found;break
      if pair:
       mn,a,b=pair
       for recv,row in [('original',a),(receiver,b)]:
        detail=simulate(r,g,P[mn],mode,recv,row['seed'],True,True);assert detail['trace_hash']==row['trace_hash'];examples.append(dict(mode=mode,receiver=recv,mafia=mn,label=receiver+'_'+label,**detail))
 # Additional descriptive types, always first qualifying acceptance seed.
   extra=[('self','original','self_quiet','self','first_live','self_quiet','balance_exiles_real_source',lambda u,v:u['win']==1 and v['win']==0 and v['day1_police_exile']==1),
     ('self','original','late_copy','self','conditional_gold','late_copy','gold_process_change_same_terminal',lambda u,v:u['trace_hash']!=v['trace_hash'] and u['win']==v['win']),
     ('self','original','self_copy_team_pass','self','original','self_copy_team_relay','fake_relay_gain',lambda u,v:u['win']==0 and v['win']==1),
     ('self','original','self_copy_team_pass','self','original','self_copy_team_relay','fake_relay_loss',lambda u,v:u['win']==1 and v['win']==0)]
   for am,ar,an,bm,br,bn,label,predicate in extra:
    pair=next(((u,v) for u,v in zip(D[am,ar,an],D[bm,br,bn]) if predicate(u,v)),None)
    if pair:
     for mode,receiver,mn,row in [(am,ar,an,pair[0]),(bm,br,bn,pair[1])]:
      detail=simulate(r,g,P[mn],mode,receiver,row['seed'],True,True);assert detail['trace_hash']==row['trace_hash'];examples.append(dict(mode=mode,receiver=receiver,mafia=mn,label=label,**detail))
 result=dict(**counts,coverage=coverage,summaries=summaries,examples=examples,case_replays=len(examples),
   limitation='Coverage is unconditional and role-stratified offline; examples are post-hoc descriptions, no new acceptance seeds.')
 save(ROOT/'results/v34_diagnostics.json',result);print(json.dumps(counts))

if __name__=='__main__':main()
