"""Predeclared source-generation audit. No receiver fit or seed selection."""
import sys, json, shutil, time, platform
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor, as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.source_hypotheses_v32 import ResponseAPI, source_prefix, role_support
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening, continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save
from mafia_lab.engine import Role
from mafia_lab import strategies_v31 as base


def simulate(r,g,m,seed,response,logic=False):
    api=ResponseAPI(response=='restrained');s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    exiles=[e['payload']['victim'] for e in o.transcript if e['day']==1 and e['event']=='day_death']
    reports=[e['payload'] for e in o.transcript if e['day']==1 and e['event']=='message'
             and e['payload']['context']=='day' and e['payload']['kind']=='report']
    dead=s.deaths[0].player
    row=dict(seed=seed,win=o.good_win,day1_mafia_exile=int(bool(exiles) and s.roles[exiles[0]]==Role.MAFIA),
        dead_clear=int(s.roles[dead]==Role.POLICE and not s.investigations[0].is_mafia),
        live_police_reports=sum(s.roles[x['speaker']]==Role.POLICE for x in reports),
        suppressed=api.suppressed,opening_hash=hash_events((s.roles,s.deaths,s.investigations)),
        trace_hash=hash_events(o.transcript))
    prefix=source_prefix(api.focal) if api.focal else None
    if prefix:
        obs,dead_claim,live,event=prefix
        diagnostic=dict(event=event,dead_police=int(s.roles[dead]==Role.POLICE),
            live_role=s.roles[live.speaker].value if live else None,
            observer=obs.player,dead_source=dead,live_source=live.speaker if live else None)
        if logic:
            diagnostic.update(observation=asdict(obs),support=role_support(obs,dead,live.speaker if live else None))
        row['diagnostic']=diagnostic
    return row


def job(args):
    phase,r,g,m,spec,cap=args;cells=[]
    for response in ('inherited','restrained'):
        rows=[];samples=0
        for seed in range(spec['seed_start'],spec['seed_start']+spec['n']):
            row=simulate(r,g,m,seed,response,samples<cap)
            if 'diagnostic' in row and 'support' in row['diagnostic']:samples+=1
            rows.append(row)
        cells.append(dict(phase=phase,mafia=m.name,response=response,n=len(rows),rows=rows))
    return cells


def contrasts(cells,family):
    D={(c['response'],c['mafia']):c for c in cells};out=[]
    for mn in sorted({c['mafia'] for c in cells}):
        a,b=D['inherited',mn]['rows'],D['restrained',mn]['rows']
        assert all(x['opening_hash']==y['opening_hash'] for x,y in zip(a,b))
        pairs=[(x,y) for x,y in zip(a,b) if x['dead_clear']]
        row=dict(mafia=mn,n=len(pairs),all_n=len(a),changed=sum(x['trace_hash']!=y['trace_hash'] for x,y in zip(a,b)),
                 suppressed=sum(y['suppressed'] for y in b),wins=[sum(x['win'] for x in a),sum(x['win'] for x in b)])
        for metric in ('win','day1_mafia_exile'):
            xx=[x[metric] for x,y in pairs];yy=[y[metric] for x,y in pairs]
            row[metric]=dict(counts=[sum(xx),sum(yy)],gains=sum(x<y for x,y in zip(xx,yy)),losses=sum(x>y for x,y in zip(xx,yy)),
                            precision=exact_paired_interval(xx,yy,family) if xx else None)
        out.append(row)
    return out


def main(smoke=False):
    cfg=json.loads((ROOT/'configs/source_hypotheses_v32.json').read_text())
    bc=json.loads((ROOT/cfg['base_config']).read_text());r,gs,ms=build_spec(bc);g=next(g for g in gs if g.name==cfg['good'])
    output=ROOT/('results/v32_smoke' if smoke else 'results/v32')
    if output.exists():raise ValueError('fresh output only')
    output.mkdir();assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v32.py'))+list((ROOT/'tests').glob('*v32.py'))+[ROOT/'configs/source_hypotheses_v32.json',ROOT/cfg['base_config'],ROOT/'docs/source_hypotheses_protocol_v32.md']
    for p in assets:
        dest=output/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    save(output/'freeze.json',dict(config=cfg,base_config=bc,good=asdict(g),mafia=[asdict(m) for m in ms],assets=hashes,python=platform.python_version()))
    started=time.monotonic();games=0
    for phase in (('smoke',) if smoke else ('train','holdout')):
        cells=[]
        with ProcessPoolExecutor(max_workers=4) as pool:
            jobs=[pool.submit(job,(phase,r,g,m,cfg[phase],cfg['logic_samples_per_cell'])) for m in ms]
            for f in as_completed(jobs):
                cells.extend(f.result());print(phase,len(cells),'/16',flush=True)
        cells.sort(key=lambda c:(c['response'],c['mafia']))
        save(output/(phase+'.json'),dict(cells=cells,contrasts=contrasts(cells,cfg['family'])))
        games+=sum(c['n'] for c in cells)
        assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
        if phase=='train':save(output/'no_selection.json',dict(selection=False,explanation='Fixed diagnostic only; no fitted action policy or changes after train.'))
    save(output/'manifest.json',dict(games=games,elapsed_seconds=time.monotonic()-started,
         files={str(p.name):sha256(p.read_bytes()).hexdigest() for p in output.glob('*.json')}))
    print('complete',games,flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
