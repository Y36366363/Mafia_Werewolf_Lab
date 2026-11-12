"""Frozen paired ballot-candidate ablation; no strategy or seed selection."""
import sys, json, gzip, shutil, platform, time
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_private_response_v35 import spec
from mafia_lab.hit_candidates_v37 import HitCandidatesAPI
from mafia_lab.simulation import opening, continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save


def simulate(r,g,plan,seed,retain=False,details=False):
    _,m,coop,fake=plan
    api=HitCandidatesAPI(coop,fake,'1/2',retain)
    s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    exiles=[e['payload']['victim'] for e in o.transcript if e['day']==1 and e['event']=='day_death']
    prefix=[]
    for e in o.transcript:
        if e['day']==1 and e['event']=='votes':break
        prefix.append(e)
    first=[v for v in api.candidate_votes if v['day']==1 and v['round']=='first']
    civ=[v for v in first if v['role']=='civilian']
    # Labels are joined only after the complete game, never read by the API.
    hits={p for v in civ for p in v['admitted_hits']}
    police_hits={e['payload']['target'] for e in prefix if e['event']=='message'
        and e['payload']['kind']=='report' and e['payload']['verdict']
        and s.roles[e['payload']['speaker']].value=='police'
        and e['payload']['target'] in s.alive}
    true_hits={p for p in hits if s.roles[p].value=='mafia'}
    wrong_hits=hits-true_hits
    row=dict(seed=seed,win=int(o.good_win),
        day1_mafia_exile=int(bool(exiles) and s.roles[exiles[0]].value=='mafia'),
        day1_police_exile=int(bool(exiles) and s.roles[exiles[0]].value=='police'),
        day1_victim=exiles[0] if exiles else None,
        opening_hash=hash_events((s.roles,s.deaths,s.investigations)),
        prefix_hash=hash_events(prefix),trace_hash=hash_events(o.transcript),
        first_changed=sum(v['changed'] for v in first),
        pk_changed=sum(v['changed'] for v in api.candidate_votes if v['round']=='pk'),
        scope_game=any(v['hit_scope'] for v in first),
        pool_expanded_game=any(set(v['expanded_pool'])-set(v['old_pool']) for v in first),
        true_hit_available=bool(true_hits),wrong_hit_available=bool(wrong_hits),
        public_police_hit=bool(police_hits),
        civilian_follow_police_hit=sum(v['target'] in police_hits for v in civ),
        police_hit_exiled=bool(exiles) and exiles[0] in police_hits,
        true_hit_votes=sum(v['target'] in true_hits for v in civ),
        wrong_hit_votes=sum(v['target'] in wrong_hits for v in civ),
        true_hit_exiled=bool(exiles) and exiles[0] in true_hits,
        wrong_hit_exiled=bool(exiles) and exiles[0] in wrong_hits,
        vote_checks=len(api.candidate_votes),day2_scopes=sum(v['hit_scope'] for v in api.candidate_votes if v['day']>=2),
        response_audit=api.response_audit)
    if details:row.update(roles_evaluation_only=[x.value for x in s.roles],
        transcript=o.transcript,votes=api.candidate_votes,nights=api.nights,inspections=api.inspections)
    return row


def job(args):
    r,g,plan,seeds=args
    cells=[]
    for receiver in ('original','retain_hits'):
        cells.append(dict(mafia=plan[0],receiver=receiver,
            rows=[simulate(r,g,plan,s,receiver=='retain_hits') for s in seeds]))
    return cells


def contrasts(cells,cfg):
    D={(c['mafia'],c['receiver']):c['rows'] for c in cells};out=[]
    for name in cfg['mafia']:
        a,b=D[name,'original'],D[name,'retain_hits']
        assert all(x['seed']==y['seed'] and x['opening_hash']==y['opening_hash']
            and x['prefix_hash']==y['prefix_hash'] and x['response_audit']==y['response_audit'] for x,y in zip(a,b))
        row=dict(mafia=name,n=len(a),process_changed=sum(x['trace_hash']!=y['trace_hash'] for x,y in zip(a,b)))
        for metric in ('win','day1_mafia_exile'):
            x=[v[metric] for v in a];y=[v[metric] for v in b]
            row[metric]=dict(counts=[sum(x),sum(y)],gains=sum(u<v for u,v in zip(x,y)),
                losses=sum(u>v for u,v in zip(x,y)),precision=exact_paired_interval(x,y,cfg['family']))
        # Empirical paired/unpaired variance ratio for the difference in means.
        import statistics
        x=[v['win'] for v in a];y=[v['win'] for v in b]
        denom=statistics.variance(x)+statistics.variance(y)
        row['paired_variance_ratio']=statistics.variance([v-u for u,v in zip(x,y)])/denom if denom else None
        out.append(row)
    return out


def main(smoke=False):
    cfg=json.loads((ROOT/'configs/hit_candidates_v37.json').read_text())
    bc=json.loads((ROOT/cfg['base_config']).read_text());r,g,plans,_=spec(bc)
    plans=[p for p in plans if p[0] in cfg['mafia']]
    assert len(plans)==4 and cfg['q']=='1/2'
    phase='smoke' if smoke else 'holdout';out=ROOT/('results/v37_smoke' if smoke else 'results/v37')
    if out.exists():raise ValueError('new output required')
    out.mkdir()
    assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v37.py'))+list((ROOT/'tests').glob('*v37.py'))
    assets += [ROOT/'scripts/run_private_response_v35.py',ROOT/'scripts/run_day1_risk_v34.py',
        ROOT/'configs/hit_candidates_v37.json',ROOT/cfg['base_config'],ROOT/bc['base_config'],ROOT/'docs/hit_candidates_protocol_v37.md']
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    for p in assets:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    save(out/'freeze.json',dict(config=cfg,base_config=bc,good=asdict(g),rules=asdict(r),
        plans=[dict(name=n,policy=asdict(m),cooperation=c,fake_relay=f) for n,m,c,f in plans],
        assets=hashes,python=platform.python_version()))
    started=time.monotonic();cells=[]
    seeds=list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(job,(r,g,p,seeds)) for p in plans]
        for future in as_completed(futures):
            cells.extend(future.result());print(phase,len(cells),'/8',flush=True)
    cells.sort(key=lambda c:(c['mafia'],c['receiver']))
    data=dict(cells=cells,contrasts=contrasts(cells,cfg),selection=False)
    (out/(phase+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    save(out/'manifest.json',dict(games=sum(len(c['rows']) for c in cells),elapsed_seconds=time.monotonic()-started,
        files={p.name:sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}))
    print(json.dumps(data['contrasts']),flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
