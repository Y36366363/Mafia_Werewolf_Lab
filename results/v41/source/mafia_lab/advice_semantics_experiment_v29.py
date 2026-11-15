"""Matched 2x2 semantic/compatibility ablation plus the pre-grant anchor."""
import json,shutil,time,platform
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
from statistics import mean
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import strategies_v29 as d
from . import dead_gold_experiment_v28 as previous
from .engine import Role
from .simulation import opening,continue_game
from .statistics import win_summary
from .experiments import fingerprint
from .restatement_experiment_v23 import pair_result,save
from .source_advice_experiment_v25 import exact_paired_interval
from .police_execution_experiment_v26 import hash_events

PROFILES=('anchor','plain','typed','guard','both')
PAIRS=(('plain','typed'),('plain','guard'),('typed','both'),('guard','both'),('anchor','both'))
HASH_KEYS={'process_hash','opening_hash','speech_prefix_hash'}


def build_spec(config):
    c=dict(config,good=[{k:v for k,v in g.items() if k not in {'typed_advice','conflict_guard'}} for g in config['good']])
    r,gs,ms=previous.build_spec(c)
    return r,tuple(d.GoodPolicyV29(**asdict(g),typed_advice=row['typed_advice'],conflict_guard=row['conflict_guard']) for g,row in zip(gs,config['good'])),ms


class AuditAPI(previous.AuditAPI):
    def __getattr__(self,k):return getattr(d,k)
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:return d.vote(obs,policy,rng,candidates)
        v=d.explain(obs,policy,candidates);target=v['target']
        self.votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,
            round='pk' if candidates is not None else 'first',target=target,reason=v['reason'],
            known_bad=v['known_bad'],known_good=v['known_good'],
            illegal=target is not None and target not in v['legal'],
            ignored_known=bool(v['known_bad']) and target not in v['known_bad'],voted_good=target in v['known_good'],
            scope=v['receiver_scope'],changed=v['receiver_changed'],proposal_kinds=v['proposal_kinds'],
            common=v['common_targets'],incompatible=v['contributors_conflict'],
            type_block=v['blocked_by_type'],conflict_block=v['blocked_by_conflict'],
            early_common=v['early_common_accepted'],sources=v['sources'],
            proposals=v['proposals'],history_edges=v['history_edges'],conflict_targets=v['conflict_targets']))
        return target


def simulate(r,g,m,seed,details=False):
    api=AuditAPI();s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=previous.metrics(s,o);victim=s.deaths[0].player
    raw['dead_clear']=int(s.roles[victim]==Role.POLICE and not s.investigations[0].is_mafia)
    raw['opening_hash']=hash_events((s.roles,s.deaths,s.investigations))
    actions=[e for e in o.transcript if e['event'] in {'night_death','day_death','votes','pk_votes','terminal'}]
    raw['process_hash']=hash_events((actions,api.nights))
    prefix=[]
    for e in o.transcript:
        if e['day']==1 and e['event']=='votes':break
        prefix.append(e)
    raw['speech_prefix_hash']=hash_events(prefix)
    for key in ('illegal','ignored_known','voted_good','scope','changed','type_block','conflict_block','early_common'):
        raw[key+'_ballots']=sum(v[key] for v in api.votes)
    raw['grant_game']=int(bool(api.extensions))
    raw['gold_final_call_game']=int(bool(api.calls))
    day1_exile=next((e['payload']['victim'] for e in actions if e['day']==1 and e['event']=='day_death'),None)
    raw['day1_civilian_exile']=int(day1_exile is not None and s.roles[day1_exile]==Role.CIVILIAN)
    early_deaths=[e['payload']['victim'] for e in actions if e['day']<=2 and e['event'] in {'night_death','day_death'}]
    raw['mafia_eliminated_by_day2']=sum(s.roles[p]==Role.MAFIA for p in early_deaths)
    raw['police_alive_after_day2']=r.police-sum(s.roles[p]==Role.POLICE for p in early_deaths)
    result=dict(raw=raw,trace_hash=hash_events(o.transcript))
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,
                            votes=api.votes,nights=api.nights,extensions=api.extensions)
    return result


def column_job(job):
    """Run all frozen receivers per seed to share deterministic likelihood caches.

    This changes orchestration only. Every profile is actually simulated, each
    with its own keyed random stream, not copied from an alleged equivalent.
    """
    phase,r,gs,m,start,n=job
    cells={g.name:dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw={},samples=[]) for g in gs}
    for i,seed in enumerate(range(start,start+n)):
        for g in gs:
            row=simulate(r,g,m,seed);c=cells[g.name]
            for k,v in row['raw'].items():c['raw'].setdefault(k,[]).append(v)
            if i in {0,n//2,n-1}:c['samples'].append(dict(seed=seed,trace_hash=row['trace_hash']))
    for c in cells.values():
        raw=c['raw'];mask=raw['dead_clear']
        c.update(win=win_summary(raw['win']),branch_win=win_summary([v for v,k in zip(raw['win'],mask) if k]),
                 means={k:mean(v) for k,v in raw.items() if k not in HASH_KEYS})
    return list(cells.values())


def contrasts(cells):
    D={(c['good'],c['mafia']):c for c in cells};out=[]
    for mn in sorted({c['mafia'] for c in cells}):
        a=D['plain',mn]
        for g in PROFILES:
            b=D[g,mn]
            assert a['raw']['opening_hash']==b['raw']['opening_hash']
            assert a['raw']['dead_clear']==b['raw']['dead_clear']
            if g!='anchor':assert a['raw']['speech_prefix_hash']==b['raw']['speech_prefix_hash']
        for a,b in PAIRS:
            x,y=D[a,mn]['raw'],D[b,mn]['raw']
            for branch in ('all','dead_clear'):
                mask=x['dead_clear'] if branch=='dead_clear' else [True]*len(x['win'])
                diff=[i for i,k in enumerate(mask) if k and x['process_hash'][i]!=y['process_hash'][i]]
                row=dict(mafia=mn,comparison=a+'->'+b,branch=branch,primary=branch=='dead_clear',
                    process_different=len(diff),same_terminal_different_process=sum(x['win'][i]==y['win'][i] for i in diff))
                for metric in ('win','day1_mafia_exile'):
                    xx=[v for v,k in zip(x[metric],mask) if k];yy=[v for v,k in zip(y[metric],mask) if k]
                    row[metric]=pair_result(xx,yy)
                    if row['primary'] and xx:row[metric+'_precision']=exact_paired_interval(xx,yy,80)
                out.append(row)
    return out


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    r,gs,ms=build_spec(config);output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v29.py'))+list((root/'tests').glob('*v29.py'))+[root/'configs/advice_semantics_v29.json',root/'docs/advice_semantics_protocol_v29.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    import scipy
    freeze=dict(config=config,good=[asdict(g) for g in gs],mafia=[asdict(m) for m in ms],package_sha256=fingerprint(),
                python=platform.python_version(),scipy=scipy.__version__,
                assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    for phase in ('train','holdout'):
        spec=config[phase];rows=[]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(column_job,(phase,r,gs,m,spec['seed_start'],spec['n'])) for m in ms]
            for future in as_completed(jobs):
                rows.extend(future.result());print(f'{phase} {len(rows)}/40 receiver cells',flush=True)
        rows.sort(key=lambda c:(c['good'],c['mafia']));save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows);assert fingerprint()==freeze['package_sha256']
        if phase=='train':save(output/'no_selection_before_holdout.json',dict(policy_selection=False,q_selection=False,
            note='2x2 receiver and anchor unchanged; no new adversary or seed search.'))
    files=['freeze.json','train.json','holdout.json','no_selection_before_holdout.json']
    result=dict(games=total,elapsed_seconds=time.monotonic()-started,files={f:sha256((output/f).read_bytes()).hexdigest() for f in files})
    save(output/'manifest.json',result);return result
