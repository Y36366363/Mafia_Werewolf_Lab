"""Frozen matched-budget first-day risk-control comparison."""
import sys,json,gzip,shutil,time,platform
from pathlib import Path
from dataclasses import replace,asdict
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.day1_risk_v34 import RiskAPI,public_context
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.source_hypotheses_v32 import source_prefix,role_support
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save


def spec(cfg):
 bc=json.loads((ROOT/cfg['base_config']).read_text());r,gs,ms=build_spec(bc);M={m.name:m for m in ms}
 plans=[(name,M[name],'ordinary',False) for name in cfg['ordinary']]
 for name in cfg['self_plans']:
  coop='copy_team' if name.startswith('copy_team_') else name
  plans.append(('self_'+name,replace(M['false_grant'],name='self_'+name),coop,name=='copy_team_relay'))
 return r,gs[-1],plans,bc


def simulate(r,g,plan,mode,receiver,seed,logic=False,details=False):
 name,m,coop,fake=plan;api=RiskAPI(mode,coop,receiver,fake);s=opening(r,g,m,seed,api)
 o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
 first_exile=[e['payload']['victim'] for e in o.transcript if e['day']==1 and e['event']=='day_death']
 cops=[e['payload']['speaker'] for e in o.transcript if e['day']==1 and e['event']=='message'
       and e['payload']['context']=='day' and e['payload']['kind'] in {'report','police'} and s.roles[e['payload']['speaker']]==Role.POLICE]
 assert len(cops)<=1
 night2=next((a['target'] for a in api.nights if a['day']==2),None)
 prefix=[]
 for e in o.transcript:
  if e['day']==1 and e['event']=='votes':break
  if e['event'] in {'night_death','message','speech_extension','last_words_extension'}:prefix.append(e)
 raw=dict(seed=seed,win=o.good_win,day1_mafia_exile=int(bool(first_exile) and s.roles[first_exile[0]]==Role.MAFIA),
   day1_police_exile=int(bool(first_exile) and s.roles[first_exile[0]]==Role.POLICE),
   day1_police_reports=len(cops),night2_police_death=int(night2 is not None and s.roles[night2]==Role.POLICE),
   opening_hash=hash_events((s.roles,s.deaths,s.investigations)),ordinary_hash=hash_events(prefix),trace_hash=hash_events(o.transcript),
   risk_votes=sum(v['applied'] for v in api.risk_votes),first_round_risk_votes=sum(v['applied'] and v['round']=='first' for v in api.risk_votes),
   day2_overrides=sum(v['day']>=2 and v['reason'].startswith('day1_') for v in api.risk_votes),
   own_relay_first_mismatches=sum(v['own_relay_mismatch'] and v['round']=='first' for v in api.risk_votes),
   fake_calls=sum(c['kind']=='fake' for c in api.final_calls),real_calls=sum(c['kind']=='civilian' for c in api.final_calls),
   context=api.end_public,
   live_police_report=bool(cops),opportunities=api.opportunities)
 c=api.end_public
 if c:
  raw['context_evaluation_only']=dict(dead_role=s.roles[c['origin']].value,gold_role=s.roles[c['gold']].value,
       first_live_role=s.roles[c['first_live']].value,public_police=bool(cops))
 p=source_prefix(api.focal) if api.focal else None
 if p and logic:
  obs,dead,live,event=p;raw['logic_sample']=dict(event=event,observation=asdict(obs),support=role_support(obs,dead.speaker,live.speaker if live else None),
        dead_source=dead.speaker,live_source=live.speaker if live else None)
 if details:raw.update(roles_evaluation_only=[x.value for x in s.roles],transcript=o.transcript,
                        votes=api.risk_votes,calls=api.final_calls,nights=api.nights,inspections=api.inspections)
 return raw


def column_job(args):
 phase,r,g,plan,cfg=args;cells=[]
 for mode in cfg['police_modes']:
  for receiver in cfg['receivers']:
   rows=[];nlogic=0
   for seed in range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']):
    row=simulate(r,g,plan,mode,receiver,seed,nlogic<cfg['logic_samples_per_cell'])
    nlogic+=int('logic_sample' in row);rows.append(row)
   cells.append(dict(phase=phase,mode=mode,receiver=receiver,mafia=plan[0],rows=rows))
 return cells


def contrasts(cells,cfg):
 D={(x['mode'],x['receiver'],x['mafia']):x['rows'] for x in cells};out=[]
 def pair(a,b,kind):
  x,y=D[a],D[b];assert all(u['opening_hash']==v['opening_hash'] and u['ordinary_hash']==v['ordinary_hash'] for u,v in zip(x,y))
  c=dict(control=list(a),treatment=list(b),kind=kind,n=len(x),process_changed=sum(u['trace_hash']!=v['trace_hash'] for u,v in zip(x,y)))
  for metric in ('win','day1_mafia_exile'):
   xx=[u[metric] for u in x];yy=[v[metric] for v in y]
   c[metric]=dict(counts=[sum(xx),sum(yy)],gains=sum(u<v for u,v in zip(xx,yy)),losses=sum(u>v for u,v in zip(xx,yy)),precision=exact_paired_interval(xx,yy,cfg['family']))
  out.append(c)
 for mode in cfg['police_modes']:
  for mn in sorted({x['mafia'] for x in cells}):
   for receiver in ('first_live','conditional_gold'):pair((mode,'original',mn),(mode,receiver,mn),'receiver')
  for receiver in cfg['receivers']:
   pair((mode,receiver,'self_copy_team_pass'),(mode,receiver,'self_copy_team_relay'),'fake_relay')
 assert len(out)*2==cfg['family'];return out


def main(smoke=False):
 cfg=json.loads((ROOT/'configs/day1_risk_v34.json').read_text());r,g,plans,bc=spec(cfg)
 out=ROOT/('results/v34_smoke' if smoke else 'results/v34')
 if out.exists():raise ValueError('new output required')
 out.mkdir();assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v34.py'))+list((ROOT/'tests').glob('*v34.py'))+[ROOT/'configs/day1_risk_v34.json',ROOT/cfg['base_config'],ROOT/'docs/day1_risk_protocol_v34.md']
 hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
 for p in assets:
  dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 save(out/'freeze.json',dict(config=cfg,base_config=bc,good=asdict(g),plans=[dict(name=n,policy=asdict(m),cooperation=c,fake_relay=v) for n,m,c,v in plans],assets=hashes,python=platform.python_version()))
 start=time.monotonic();total=0
 for phase in (('smoke',) if smoke else ('train','holdout')):
  cells=[]
  with ProcessPoolExecutor(max_workers=4) as pool:
   futures=[pool.submit(column_job,(phase,r,g,p,cfg)) for p in plans]
   for future in as_completed(futures):cells.extend(future.result());print(phase,len(cells),'/42',flush=True)
  cells.sort(key=lambda c:(c['mode'],c['receiver'],c['mafia']))
  data=dict(cells=cells,contrasts=contrasts(cells,cfg))
  # Exact raw outcomes in lossless gzip from the initial run, no later rewrite.
  blob=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
  (out/(phase+'.json.gz')).write_bytes(gzip.compress(blob,compresslevel=6,mtime=0))
  total+=sum(len(c['rows']) for c in cells)
  assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
  if phase=='train':save(out/'no_selection.json',dict(selection=False,note='All receivers, gates and plans frozen; no tuning from train or holdout.'))
 files=[p for p in out.iterdir() if p.is_file()]
 save(out/'manifest.json',dict(games=total,elapsed_seconds=time.monotonic()-start,files={p.name:sha256(p.read_bytes()).hexdigest() for p in files}))
 print('complete',total,flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
