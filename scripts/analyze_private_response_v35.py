"""Fixed-data coverage, legality and interval audit for private q experiment."""
import sys,json,gzip
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_private_response_v35 import spec,simulate
from mafia_lab.private_response_v35 import PrivateResponseAPI
from mafia_lab.day1_risk_v34 import RiskAPI,explain
from mafia_lab import strategies_v31 as base
from mafia_lab.source_hypotheses_v32 import role_support
from analyze_source_hypotheses_v32 import read_obs
from mafia_lab.engine import Role
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


def read_phase(out,phase):return json.loads(gzip.decompress((out/(phase+'.json.gz')).read_bytes()))

class VerifyAPI(PrivateResponseAPI):
 def __init__(self,*args):super().__init__(*args);self.ballots=0;self.normal_next_day=0
 def vote(self,obs,policy,rng,candidates=None):
  target=super().vote(obs,policy,rng,candidates)
  if obs.role!=Role.MAFIA:
   v=explain(obs,policy,self.receiver,candidates)
   assert target is None or target in v['legal']
   assert not v['known_bad'] or target in v['known_bad']
   assert target not in v['known_good'];self.ballots+=1
   if obs.day>=2:assert target==base.explain(obs,policy,candidates)['target'];self.normal_next_day+=1
  return target


def main():
 out=ROOT/'results/v35';f=json.loads((out/'freeze.json').read_text());cfg=f['config'];r,g,plans,bc=spec(cfg);P={p[0]:p for p in plans};G={p['name']:p for p in cfg['profiles']}
 for rel,h in f['assets'].items():assert sha256((ROOT/rel).read_bytes()).hexdigest()==h and sha256((out/'source'/rel).read_bytes()).hexdigest()==h
 for rel,h in json.loads((out/'manifest.json').read_text())['files'].items():assert sha256((out/rel).read_bytes()).hexdigest()==h
 counts=dict(replays=0,baseline_replays=0,ballots=0,next_day_checks=0,logic_prefixes=0,interval_crosschecks=0,
             ordinary_trace_equalities=0)
 summaries=[];examples=[];dose=[]
 for phase in ('train','holdout'):
  data=read_phase(out,phase);D={(c['profile'],c['mafia']):c['rows'] for c in data['cells']}
  for cell in data['cells']:
   gn,mn=cell['profile'],cell['mafia'];profile=G[gn];rows=cell['rows'];plan=P[mn];_,m,coop,fake=plan
   assert [x['seed'] for x in rows]==list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
   for row in rows:
    assert row['draw_count']<=1 and row['day2_overrides']==0 and row['own_relay_first_mismatches']==0
    decisions=row['response_audit']
    assert sum(x['reported'] for x in decisions)<=1
    for z in decisions:
     if z['reason']=='single_local_draw':assert z['reported']==(z['draw']<float(Fraction(z['q'])))
     elif z['reason']=='mandatory_self_defense':assert z['reported'] and z['draw'] is None
     else:assert not z['reported'] and z['draw'] is None
    if 'logic_sample' in row:
     q=row['logic_sample'];obs=read_obs(q['observation']);assert role_support(obs,q['dead_source'],q['live_source'])==q['support'];counts['logic_prefixes']+=1
   for index in (0,len(rows)//2,len(rows)-1):
    row=rows[index];api=VerifyAPI(coop,profile['receiver'],fake,profile['q']);s=opening(r,g,m,row['seed'],api);o=continue_game(s,g,m,row['seed'],trace=True,decision_api=api,public_ballots=True)
    assert hash_events(o.transcript)==row['trace_hash'];counts['replays']+=1;counts['ballots']+=api.ballots;counts['next_day_checks']+=api.normal_next_day
    if gn=='legacy':
     old=RiskAPI('self',coop,'original',fake);s=opening(r,g,m,row['seed'],old);o=continue_game(s,g,m,row['seed'],trace=True,decision_api=old,public_ballots=True)
     assert hash_events(o.transcript)==row['trace_hash'];counts['baseline_replays']+=1
   contexts=[x for x in rows if x['context']];eligible=[x for x in contexts if x['context']['eligible']]
   scope=[x for x in rows if x['private_scope']]
   summaries.append(dict(phase=phase,profile=gn,mafia=mn,n=len(rows),wins=sum(x['win'] for x in rows),
     exiles=sum(x['day1_mafia_exile'] for x in rows),police_exiles=sum(x['day1_police_exile'] for x in rows),
     public_cops=sum(x['day1_police_reports'] for x in rows)/len(rows),night2_cop_death=sum(x['night2_police_death'] for x in rows)/len(rows),
     private_scope=len(scope),draw_games=sum(bool(x['draw_count']) for x in rows),
     first_draw_reports=sum(any(z['reason']=='single_local_draw' and z['reported'] for z in x['response_audit']) for x in rows),
     self_defense_reports=sum(any(z['reason']=='mandatory_self_defense' and z['reported'] for z in x['response_audit']) for x in rows),
     context_n=len(contexts),eligible_n=len(eligible),fake_gold_eligible=sum(x['context_evaluation_only']['gold_role']=='mafia' for x in eligible),
     live_report_games=sum(x['live_police_report'] for x in rows)))
  for mn in P:
   reference=D['legacy',mn]
   for gn in ('dead_q0','dead_q50','dead_q100'):
    for x,y in zip(reference,D[gn,mn]):
     if mn.startswith('late_'):
      assert x['trace_hash']==y['trace_hash'] and not y['private_scope'];counts['ordinary_trace_equalities']+=1
   qrows=[D[gn,mn] for gn in ('dead_q0','dead_q50','dead_q100')]
   for triplet in zip(*qrows):
    first=[next((z for z in x['response_audit'] if z['draw'] is not None),None) for x in triplet]
    if all(first):
     assert len({(z['player'],z['draw']) for z in first})==1
     assert not first[0]['reported'] and first[2]['reported']
   if phase=='holdout':
    for lo,hi in ((0,1024),(1024,2048)):
     a,b=D['dead_q50',mn][lo:hi],D['dead_q100',mn][lo:hi]
     dose.append(dict(mafia=mn,seed_offsets=[lo,hi],n=len(a),delta_wins=sum(y['win']-x['win'] for x,y in zip(a,b))))
  for c in data['contrasts']:
   x,y=D[tuple(c['control'])],D[tuple(c['treatment'])]
   assert all(a['opening_hash']==b['opening_hash'] for a,b in zip(x,y))
   for metric in ('win','day1_mafia_exile'):
    v=c[metric];assert v['counts']==[sum(a[metric] for a in x),sum(b[metric] for b in y)]
    for key,k in [('p_plus',v['gains']),('p_minus',v['losses'])]:
     ci=binomtest(k,c['n']).proportion_ci(confidence_level=1-2*v['precision']['tail_alpha'],method='exact')
     assert abs(ci.low-v['precision'][key][0])<1e-9 and abs(ci.high-v['precision'][key][1])<1e-9;counts['interval_crosschecks']+=1
  if phase=='holdout':
   # Select descriptive response gains/losses, not new seed batches.
   for aa,bb in [('legacy','dead_q50'),('dead_q0','dead_q50'),('dead_q50','dead_q100'),('dead_q50','dead_q50_balance')]:
    for kind,condition in [('gain',lambda a,b:a['win']==0 and b['win']==1),('loss',lambda a,b:a['win']==1 and b['win']==0)]:
     chosen=None
     for mn in sorted(P):
      found=next(((mn,a,b) for a,b in zip(D[aa,mn],D[bb,mn]) if condition(a,b)),None)
      if found:chosen=found;break
     if chosen:
      mn,a,b=chosen
      for gn,row in [(aa,a),(bb,b)]:
       detail=simulate(r,g,P[mn],G[gn],row['seed'],True,True);assert detail['trace_hash']==row['trace_hash'];examples.append(dict(profile=gn,mafia=mn,label=aa+'_to_'+bb+'_'+kind,**detail))
 save(ROOT/'results/v35_diagnostics.json',dict(**counts,summaries=summaries,half_blocks=dose,examples=examples,case_replays=len(examples),
      note='All simulations complete to terminal; half blocks and cases descriptive, not additional independent confirmations. No probability selected or civilian belief retrained.'))
 print(json.dumps(counts))

if __name__=='__main__':main()
