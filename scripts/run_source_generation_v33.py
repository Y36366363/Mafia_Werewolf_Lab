"""Frozen complete-game source generator experiment; no fitted receiver."""
import sys,json,shutil,time,platform
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict,replace
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.source_generation_v33 import GenerationAPI
from mafia_lab.source_hypotheses_v32 import source_prefix,role_support
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save


def spec(cfg):
 bc=json.loads((ROOT/cfg['base_config']).read_text());r,gs,ms=build_spec(bc);M={m.name:m for m in ms}
 plans=[(name,M[name],'ordinary') for name in cfg['ordinary']]
 plans += [('self_'+plan,replace(M['false_grant'],name='self_'+plan),plan) for plan in cfg['self_plans']]
 return r,gs[-1],plans,bc


def simulate(r,g,m,cooperation,mode,seed,logic=False,details=False):
 api=GenerationAPI(mode,cooperation);s=opening(r,g,m,seed,api)
 o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
 day1=[e['payload']['victim'] for e in o.transcript if e['day']==1 and e['event']=='day_death']
 reports=[e['payload'] for e in o.transcript if e['day']==1 and e['event']=='message' and e['payload']['context']=='day' and e['payload']['kind'] in {'report','police'}]
 cop_reports=[x for x in reports if s.roles[x['speaker']]==Role.POLICE]
 day2kill=next((x['target'] for x in api.nights if x['day']==2),None)
 dead=s.deaths[0].player
 livepolice=4-int(s.roles[dead]==Role.POLICE)-sum(s.roles[p]==Role.POLICE for p in day1)
 if day2kill is not None:livepolice-=int(s.roles[day2kill]==Role.POLICE)
 row=dict(seed=seed,win=o.good_win,day1_mafia_exile=int(bool(day1) and s.roles[day1[0]]==Role.MAFIA),
   dead_clear=int(s.roles[dead]==Role.POLICE and not s.investigations[0].is_mafia),
   first_dead_role=s.roles[dead].value,day1_live_police_reports=len(cop_reports),
   night2_police_death=int(day2kill is not None and s.roles[day2kill]==Role.POLICE),police_at_day2=livepolice,
   opening_hash=hash_events((s.roles,s.deaths,s.investigations)),trace_hash=hash_events(o.transcript),
   opportunities=api.opportunities)
 if mode!='hide':assert len(cop_reports)<=1
 prefix=source_prefix(api.focal) if api.focal else None
 if prefix:
  obs,dc,lc,event=prefix
  end=api.focal
  all_sources=sorted({m.speaker for m in end.messages if m.context=='day' and m.kind in {'report','police'}})
  d=dict(event=event,dead_source=dead,live_source=lc.speaker if lc else None,
    dead_role=s.roles[dead].value,live_role=s.roles[lc.speaker].value if lc else None,
    gold=dc.target,gold_role=s.roles[dc.target].value,
    end_live_sources=len(all_sources),end_live_police=sum(s.roles[x]==Role.POLICE for x in all_sources))
  if logic:d.update(observation=asdict(obs),support=role_support(obs,dead,lc.speaker if lc else None))
  row['diagnostic']=d
 if details:row.update(roles_evaluation_only=[x.value for x in s.roles],transcript=o.transcript,nights=api.nights,inspections=api.inspections)
 return row


def job(args):
 phase,r,g,plan,cfg=args;name,m,coop=plan;cells=[]
 for mode in cfg['police_modes']:
  rows=[];sample=0
  for seed in range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']):
   row=simulate(r,g,m,coop,mode,seed,sample<cfg['logic_samples_per_cell'])
   if 'support' in row.get('diagnostic',{}):sample+=1
   rows.append(row)
  cells.append(dict(phase=phase,mafia=name,mode=mode,rows=rows))
 return cells


def contrasts(cells,cfg):
 D={(x['mode'],x['mafia']):x['rows'] for x in cells};result=[]
 for name in sorted({x['mafia'] for x in cells}):
  for a,b in [('hide','self'),('self','available')]:
   x,y=D[a,name],D[b,name];assert all(u['opening_hash']==v['opening_hash'] for u,v in zip(x,y))
   c=dict(mafia=name,control=a,treatment=b,n=len(x),process_different=sum(u['trace_hash']!=v['trace_hash'] for u,v in zip(x,y)))
   for metric in ('win','day1_mafia_exile'):
    xx=[u[metric] for u in x];yy=[v[metric] for v in y]
    c[metric]=dict(counts=[sum(xx),sum(yy)],gains=sum(u<v for u,v in zip(xx,yy)),losses=sum(u>v for u,v in zip(xx,yy)),precision=exact_paired_interval(xx,yy,cfg['family']))
   result.append(c)
 return result


def main(smoke=False):
 cfg=json.loads((ROOT/'configs/source_generation_v33.json').read_text());r,g,plans,bc=spec(cfg)
 out=ROOT/('results/v33_smoke' if smoke else 'results/v33')
 if out.exists():raise ValueError('new output required')
 out.mkdir();assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v33.py'))+list((ROOT/'tests').glob('*v33.py'))+[ROOT/'configs/source_generation_v33.json',ROOT/cfg['base_config'],ROOT/'docs/source_generation_protocol_v33.md']
 hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
 for p in assets:
  dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 save(out/'freeze.json',dict(config=cfg,base_config=bc,good=asdict(g),plans=[dict(name=n,policy=asdict(m),cooperation=c) for n,m,c in plans],assets=hashes,python=platform.python_version()))
 started=time.monotonic();total=0
 for phase in (('smoke',) if smoke else ('train','holdout')):
  cells=[]
  with ProcessPoolExecutor(max_workers=4) as pool:
   futures=[pool.submit(job,(phase,r,g,p,cfg)) for p in plans]
   for future in as_completed(futures):cells.extend(future.result());print(phase,len(cells),'/27',flush=True)
  cells.sort(key=lambda c:(c['mode'],c['mafia']));save(out/(phase+'.json'),dict(cells=cells,contrasts=contrasts(cells,cfg)))
  total+=sum(len(c['rows']) for c in cells)
  assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
  if phase=='train':save(out/'no_selection.json',dict(selection=False,note='All generators and diagnostic features frozen; no trained receiver.'))
 save(out/'manifest.json',dict(games=total,elapsed_seconds=time.monotonic()-started,files={p.name:sha256(p.read_bytes()).hexdigest() for p in out.glob('*.json')}))
 print('complete',total,flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
