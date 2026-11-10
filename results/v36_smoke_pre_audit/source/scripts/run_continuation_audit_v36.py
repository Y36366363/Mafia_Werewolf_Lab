"""Replay frozen games and audit legal information flow; never change actions."""
import sys,json,gzip,shutil,time,platform
from pathlib import Path
from hashlib import sha256
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_private_response_v35 import spec
from mafia_lab.continuation_audit_v36 import ContinuationAuditAPI,classify_hit_vote
from mafia_lab.private_response_v35 import PrivateResponseAPI
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save


def load_json_gz(path):return json.loads(gzip.decompress(Path(path).read_bytes()))


def simulate(r,g,plan,profile,seed,details=False):
    _,m,coop,fake=plan
    api=ContinuationAuditAPI(coop,profile['receiver'],fake,profile['q'])
    s=opening(r,g,m,seed,api);o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    exiles={e['day']:e['payload']['victim'] for e in o.transcript if e['event']=='day_death'}
    events=list(api.audit_rounds.values())
    # This label join is evaluation only, after every decision has happened.
    true_reports=[x for x in api.audit_reports if x['role']=='police' and x['kind']=='report']
    for rep in true_reports:
        check=rep['latest_check']
        assert check and (check['target'],check['is_mafia'])==(rep['target'],rep['verdict'])
        assert bool(s.roles[rep['target']].value=='mafia')==rep['verdict']
    groups={}
    for rep in true_reports:
        if rep['verdict'] and rep['target_alive']:
            groups.setdefault((rep['day'],rep['target']),set()).add(rep['speaker'])
    hits=[]
    for (day,target),sources in sorted(groups.items()):
        for round_name in ('first','pk'):
            votes=[v for v in api.audit_votes if v['day']==day and v['round']==round_name and v['role']=='civilian']
            if not votes:continue
            reasons=Counter();follow=0;eligible=0
            for v in votes:
                source=next((z for z in sources if target in v['proposals'].get(str(z),())),min(sources))
                label=classify_hit_vote(v,source,target);reasons[label]+=1
                eligible+=int(target in v['legal']);follow+=int(v['target']==target)
            hits.append(dict(day=day,target=target,sources=sorted(sources),round=round_name,
                civilian_votes=len(votes),eligible=eligible,follow=follow,reasons=dict(reasons),
                target_exiled=exiles.get(day)==target))
    history=[]
    first_hits=[(t,ss) for (d,t),ss in groups.items() if d==1]
    for target,sources in first_hits:
        for event in events:
            if event['day']<2 or event['round']!='first':continue
            if target not in event['alive']:
                history.append(dict(day=event['day'],target=target,status='target_already_dead'));continue
            for source in sorted(sources):
                retained=any(m['speaker']==source and m['kind']=='report' and m['day']==1
                    and m['target']==target and m['verdict'] for m in event['messages'])
                votes=[v for v in api.audit_votes if v['day']==event['day'] and v['round']=='first' and v['role']=='civilian']
                history.append(dict(day=event['day'],target=target,source=source,status='target_still_alive',
                    source_alive=source in event['alive'],history_retained=retained,
                    today_source_proposes_target=sum(target in v['proposals'].get(str(source),()) for v in votes),
                    source_has_no_current_proposal=sum(not v['proposals'].get(str(source),()) for v in votes),
                    follows_target=sum(v['target']==target for v in votes),civilian_votes=len(votes)))
    duals=[];auto=[]
    for e in api.audit_extensions:
        parts=e['parts'];acc=[p['target'] for p in parts if p['kind']=='accuse'];rel=[p['target'] for p in parts if p['kind']=='relay']
        if e['role']=='civilian' and acc and rel:
            actual=next((v['target'] for v in api.audit_votes if v['day']==e['day'] and v['round']=='first' and v['player']==e['speaker']),None)
            duals.append(dict(day=e['day'],speaker=e['speaker'],accuse=acc[-1],relay=rel[-1],actual_vote=actual,
                disagreement=acc[-1]!=rel[-1],matches_relay=actual==rel[-1],
                before_selector=e['view']['target'] if e['view'] else None))
        if e['role']=='police' and e['day']>=2:
            reps=[q for q in true_reports if q['speaker']==e['speaker'] and q['day']==e['day'] and q['context']=='day']
            if reps:
                rep=reps[0]
                auto.append(dict(day=e['day'],speaker=e['speaker'],verdict=rep['verdict'],
                    live_private_bad=bool(e['view']['known_bad']),
                    no_current_mafia_claim=not any(q['day']==e['day'] and q['context']=='day' and q['role']=='mafia' for q in api.audit_reports)))
    day1hits=[h for h in hits if h['day']==1 and h['round']=='first']
    cop1=[q for q in true_reports if q['day']==1 and q['context']=='day']
    night2=next((z['target'] for z in api.nights if z['day']==2),None)
    row=dict(seed=seed,win=o.good_win,trace_hash=hash_events(o.transcript),
        opening_hash=hash_events((s.roles,s.deaths,s.investigations)),
        day1_mafia_exile=int(1 in exiles and s.roles[exiles[1]].value=='mafia'),
        true_day1_alive_hit=bool(day1hits),
        dead_target_day1_hit=sum(q['day']==1 and q['context']=='day' and q['verdict'] and not q['target_alive'] for q in true_reports),
        day1_hit_exiled=any(h['target_exiled'] for h in day1hits),
        day1_hit_all_civ_follow=bool(day1hits) and all(h['follow']==h['eligible'] for h in day1hits),
        day1_hit_majority_follow=bool(day1hits) and all(h['follow']*2>h['eligible'] for h in day1hits),
        source_killed_night2=bool(cop1) and night2 in {q['speaker'] for q in cop1},
        hits=hits,history=history,duals=duals,auto_reports=auto,
        day1_reasons=dict(sum((Counter(h['reasons']) for h in day1hits),Counter())),
        ballot_checks=len(api.audit_votes),
        dead_clear_links=sum(not link['source_alive'] for event in events for link in event['gold_links']),
        rounds=len(events))
    if details:
        row.update(roles_evaluation_only=[x.value for x in s.roles],transcript=o.transcript,
            reports=api.audit_reports,extensions=api.audit_extensions,rounds_detail=events,
            votes=api.audit_votes,nights=api.nights,inspections=api.inspections)
    return row


def job(args):
    phase,r,g,plan,profile,seeds,expected=args;rows=[]
    for seed in seeds:
        row=simulate(r,g,plan,profile,seed)
        if expected is not None:
            old=expected[seed]
            assert all(row[k]==old[k] for k in ('win','trace_hash','opening_hash','day1_mafia_exile'))
        rows.append(row)
    return dict(phase=phase,profile=profile['name'],mafia=plan[0],rows=rows)


def contrasts(cells,cfg):
    D={(c['profile'],c['mafia']):c['rows'] for c in cells};result=[]
    for mn in cfg['mafia']:
        a,b=D['dead_q0',mn],D['dead_q50',mn]
        assert all(x['opening_hash']==y['opening_hash'] for x,y in zip(a,b))
        c=dict(mafia=mn,n=len(a))
        for metric in ('win','day1_mafia_exile'):
            x=[v[metric] for v in a];y=[v[metric] for v in b]
            c[metric]=dict(counts=[sum(x),sum(y)],gains=sum(u<v for u,v in zip(x,y)),losses=sum(u>v for u,v in zip(x,y)),
                precision=exact_paired_interval(x,y,cfg['family']))
        result.append(c)
    return result


def main(smoke=False):
    cfg=json.loads((ROOT/'configs/continuation_audit_v36.json').read_text())
    source=json.loads((ROOT/cfg['source_freeze']).read_text());old=load_json_gz(ROOT/cfg['source_holdout'])
    r,g,plans,bc=spec(source['config']);P={p[0]:p for p in plans};G={p['name']:p for p in source['config']['profiles']}
    D={(c['profile'],c['mafia']):c['rows'] for c in old['cells']}
    out=ROOT/('results/v36_smoke' if smoke else 'results/v36')
    if out.exists():raise ValueError('new output required')
    out.mkdir()
    assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v36.py'))+list((ROOT/'tests').glob('*v36.py'))
    assets += [ROOT/'scripts/run_private_response_v35.py',ROOT/'scripts/run_day1_risk_v34.py',ROOT/'configs/continuation_audit_v36.json',ROOT/'docs/continuation_audit_protocol_v36.md']
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    for p in assets:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    inputs={rel:sha256((ROOT/rel).read_bytes()).hexdigest() for rel in (cfg['source_freeze'],cfg['source_holdout'])}
    save(out/'freeze.json',dict(config=cfg,source_config=source['config'],good=source['good'],assets=hashes,inputs=inputs,python=platform.python_version()))
    started=time.monotonic();total=0
    for phase in (('smoke',) if smoke else ('historical','fresh')):
        cells=[]
        with ProcessPoolExecutor(max_workers=4) as pool:
            futures=[]
            for mn in cfg['mafia']:
                for gn in cfg['profiles']:
                    expected={v['seed']:v for v in D[gn,mn]} if phase=='historical' else None
                    seeds=sorted(expected) if expected is not None else list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
                    futures.append(pool.submit(job,(phase,r,g,P[mn],G[gn],seeds,expected)))
            for future in as_completed(futures):
                cells.append(future.result());print(phase,len(cells),'/4',flush=True)
        cells.sort(key=lambda c:(c['profile'],c['mafia']))
        result=dict(cells=cells,contrasts=contrasts(cells,cfg) if phase!='historical' else [],
                    label='Old viewed data, exact full replays only' if phase=='historical' else 'New fixed-policy diagnostic confirmation')
        (out/(phase+'.json.gz')).write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
        total+=sum(len(c['rows']) for c in cells)
        assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    save(out/'manifest.json',dict(games=total,elapsed_seconds=time.monotonic()-started,
        files={p.name:sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}))
    print('complete',total,flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
