"""Replay full old batch and fresh fixed policies with nonintervening audit."""
import sys,json,gzip,time,shutil,platform
from pathlib import Path
from hashlib import sha256
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_private_response_v35 import spec
from mafia_lab.continuation_forensics_v38 import ContinuationForensicsAPI,daily_counts,follow_reason
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.restatement_experiment_v23 import save


def read_gz(path):return json.loads(gzip.decompress(Path(path).read_bytes()))


def simulate(r,g,plan,seed,retain=False,details=False):
    _,m,coop,fake=plan;api=ContinuationForensicsAPI(coop,fake,'1/2',retain)
    s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    # All hidden-role joins start after the complete game.
    roles=[x.value for x in s.roles]
    days=daily_counts(roles,api.nights,o.transcript,o.good_win)
    exiles={e['day']:e['payload']['victim'] for e in o.transcript if e['event']=='day_death'}
    rounds=[]
    for event in api.forensic_rounds.values():
        day=event['day'];rd=event['round'];votes=[v for v in api.forensic_votes if v['day']==day and v['round']==rd]
        cops=[v for v in votes if v['role']=='police'];civs=[v for v in votes if v['role']=='civilian']
        own_counts={k:sum(roles[p]==k for p in event['alive']) for k in ('police','mafia','civilian')}
        assert own_counts==next(d['post_night'] for d in days if d['day']==day)
        current=[m for m in event['messages'] if m['day']==day and m['context']=='day' and m['kind']=='accuse' and roles[m['speaker']]=='police']
        calls={m['speaker']:m for m in current}  # latest ordinary formal call per source
        uptake=[]
        for source,call in sorted(calls.items()):
            target=call['target'];reasons=Counter(follow_reason(v,source,target) for v in civs)
            uptake.append(dict(source=source,target=target,target_role_evaluation_only=roles[target],
                civilians=len(civs),eligible=sum(target in v['legal'] for v in civs),
                followed=sum(v['target']==target for v in civs),
                proposal_contains=sum(target in v['proposals'].get(str(source),()) for v in civs),
                reasons=dict(reasons)))
        known=[v for v in cops if v['known_bad']]
        coordinated=(len({v['target'] for v in known})<=1) if known else None
        rounds.append(dict(day=day,round=rd,counts=own_counts,police=cops,
            police_with_known_bad=len(known),police_coordinated=coordinated,
            police_known_false=sum(bool(v['known_false_sources']) for v in cops),
            police_votes_false=sum(v['target'] in v['known_false_sources'] for v in cops),
            civilian_targets=dict(Counter(str(v['target']) for v in civs)),
            civilian_reasons=dict(Counter(v['reason'] for v in civs)),calls=uptake,
            alive_claimants=[dict(player=p,role_evaluation_only=roles[p]) for p in sorted({m['speaker'] for m in event['messages'] if m['kind'] in {'report','police'} and m['speaker'] in event['alive']})]))
    prefix=[]
    for e in o.transcript:
        if e['day']==1 and e['event']=='votes':break
        prefix.append(e)
    row=dict(seed=seed,win=int(o.good_win),trace_hash=hash_events(o.transcript),
        opening_hash=hash_events((s.roles,s.deaths,s.investigations)),prefix_hash=hash_events(prefix),
        day1_mafia_exile=int(1 in exiles and roles[exiles[1]]=='mafia'),
        day1_police_exile=int(1 in exiles and roles[exiles[1]]=='police'),
        day1_victim=exiles.get(1),rounds=rounds,speeches=api.forensic_speeches,days=days,
        vote_checks=len(api.forensic_votes),response_audit=api.response_audit)
    if details:row.update(roles_evaluation_only=roles,transcript=o.transcript,
        votes=api.forensic_votes,nights=api.nights,inspections=api.inspections)
    return row


def job(args):
    phase,r,g,plan,retain,seeds,expected=args;rows=[]
    for seed in seeds:
        row=simulate(r,g,plan,seed,retain)
        if expected is not None:
            old=expected[seed]
            assert all(row[k]==old[k] for k in ('win','trace_hash','opening_hash','day1_mafia_exile','day1_police_exile','day1_victim'))
        rows.append(row)
    return dict(receiver='retain_hits' if retain else 'original',rows=rows)


def contrasts(cells,family):
    D={c['receiver']:c['rows'] for c in cells};a,b=D['original'],D['retain_hits']
    assert all(x['opening_hash']==y['opening_hash'] and x['prefix_hash']==y['prefix_hash']
        and x['response_audit']==y['response_audit'] for x,y in zip(a,b))
    out={}
    for metric in ('win','day1_mafia_exile'):
        x=[v[metric] for v in a];y=[v[metric] for v in b]
        out[metric]=dict(counts=[sum(x),sum(y)],gains=sum(u<v for u,v in zip(x,y)),
            losses=sum(u>v for u,v in zip(x,y)),precision=exact_paired_interval(x,y,family))
    return out


def main(smoke=False):
    cfg=json.loads((ROOT/'configs/continuation_forensics_v38.json').read_text())
    source=json.loads((ROOT/cfg['source_freeze']).read_text());old=read_gz(ROOT/cfg['source_results'])
    r,g,plans,_=spec(source['base_config']);plan=next(p for p in plans if p[0]==cfg['mafia'])
    D={c['receiver']:{v['seed']:v for v in c['rows']} for c in old['cells'] if c['mafia']==cfg['mafia']}
    out=ROOT/('results/v38_smoke' if smoke else 'results/v38')
    if out.exists():raise ValueError('new output required')
    out.mkdir()
    assets=list((ROOT/'mafia_lab').glob('*.py'))+list((ROOT/'scripts').glob('*v38.py'))+list((ROOT/'tests').glob('*v38.py'))
    assets += [ROOT/'scripts/run_private_response_v35.py',ROOT/'scripts/run_day1_risk_v34.py',ROOT/'scripts/run_hit_candidates_v37.py',
        ROOT/'configs/continuation_forensics_v38.json',ROOT/'docs/continuation_forensics_protocol_v38.md']
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    for p in assets:
        dest=out/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    save(out/'freeze.json',dict(config=cfg,source_config=source,assets=hashes,
        inputs={rel:sha256((ROOT/rel).read_bytes()).hexdigest() for rel in (cfg['source_freeze'],cfg['source_results'])},python=platform.python_version()))
    start=time.monotonic();total=0
    for phase in (('smoke',) if smoke else ('historical','fresh')):
        cells=[]
        with ProcessPoolExecutor(max_workers=2) as pool:
            futures=[]
            for receiver in cfg['receivers']:
                seeds=list(range(cfg[phase]['seed_start'],cfg[phase]['seed_start']+cfg[phase]['n']))
                expected=D[receiver] if phase=='historical' else None
                futures.append(pool.submit(job,(phase,r,g,plan,receiver=='retain_hits',seeds,expected)))
            for future in as_completed(futures):cells.append(future.result());print(phase,len(cells),'/2',flush=True)
        cells.sort(key=lambda c:c['receiver'])
        data=dict(cells=cells,contrasts=contrasts(cells,cfg['family']),
            label='Viewed old data replay audit, not new confirmation' if phase=='historical' else 'Fresh fixed-policy confirmation; no selection')
        (out/(phase+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode(),mtime=0))
        total+=sum(len(c['rows']) for c in cells)
        assert hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in assets}
    save(out/'manifest.json',dict(games=total,elapsed_seconds=time.monotonic()-start,
        files={p.name:sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}))
    print('complete',total,flush=True)

if __name__=='__main__':main('--smoke' in sys.argv)
