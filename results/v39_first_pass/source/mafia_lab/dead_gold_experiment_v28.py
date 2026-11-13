"""Frozen deceased-source delegation: information versus authority versus scope."""
import json,shutil,time,platform
from pathlib import Path
from dataclasses import asdict,replace
from hashlib import sha256
from statistics import mean
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import strategies_v28 as d
from . import gold_relay_experiment_v27 as previous
from .engine import Role
from .simulation import opening,continue_game
from .reply_evaluation_v19 import metrics
from .statistics import win_summary
from .experiments import fingerprint
from .restatement_experiment_v23 import pair_result,save
from .source_advice_experiment_v25 import exact_paired_interval
from .police_execution_experiment_v26 import hash_events

MODES=('reference','notice','list','evidence')
PAIRS=(('reference','notice'),('notice','list'),('list','evidence'))
HASH_KEYS={'process_hash','opening_hash'}


def build_spec(config):
    c=dict(config,good=[{k:v for k,v in g.items() if k!='dead_gold'} for g in config['good']])
    r,gs,ms=previous.build_spec(c)
    return r,tuple(d.GoodPolicyV28(**asdict(g),dead_gold=row['dead_gold']) for g,row in zip(gs,config['good'])),ms


class AuditAPI:
    def __init__(self):self.extensions=[];self.calls=[];self.votes=[];self.nights=[]
    def __getattr__(self,k):return getattr(d,k)
    def choose_inspection(self,obs,policy,rng):
        p=d.choose_inspection(obs,policy,rng);self.nights.append(('check',obs.day,p));return p
    def choose_kill(self,obs,policy,rng):
        p=d.choose_kill(obs,policy,rng);self.nights.append(('kill',obs.day,p));return p
    def after_last_words(self,obs,policy,rng):
        result=d.after_last_words(obs,policy,rng)
        for m in result if isinstance(result,tuple) else (result,):
            if m is not None:self.extensions.append(asdict(m))
        return result
    def final_call(self,obs,policy,rng):
        result=d.final_call(obs,policy,rng)
        if result is not None and result.kind=='relay':
            offer=d.dead_offers(obs,policy)[0][1]
            prefix=obs.messages
            cut=next((i for i,m in enumerate(prefix) if m.day==1 and m.speaker==obs.player and m.context=='day'),len(prefix))
            before=replace(obs,messages=prefix[:cut])
            witnesses=d.reroute_witnesses(obs,offer)
            self.calls.append(dict(day=obs.day,speaker=obs.player,source=offer.speaker,target=result.target,
                pool=list(offer.targets),outside=result.target not in offer.targets,
                witness=witnesses.get(result.target),
                turn_target=d.base.explain(before,policy)['target'],final_target=d.base.explain(obs,policy)['target']))
        return result
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:return d.vote(obs,policy,rng,candidates)
        v=d.explain(obs,policy,candidates);target=v['target']
        self.votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,
            round='pk' if candidates is not None else 'first',target=target,reason=v['reason'],
            known_bad=v['known_bad'],known_good=v['known_good'],
            illegal=target is not None and target not in v['legal'],
            ignored_known=bool(v['known_bad']) and target not in v['known_bad'],voted_good=target in v['known_good'],
            admitted=bool(v['dead_relay_admitted']),changed=v['dead_relay_changed'],outside=v['dead_relay_outside']))
        return target


def simulate(r,g,m,seed,details=False):
    api=AuditAPI();s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=metrics(s,o);victim=s.deaths[0].player
    raw['dead_clear']=int(s.roles[victim]==Role.POLICE and not s.investigations[0].is_mafia)
    initial_key=(s.roles,s.deaths,s.investigations)
    raw['opening_hash']=hash_events(initial_key)
    actions=[e for e in o.transcript if e['event'] in {'night_death','day_death','votes','pk_votes','terminal'}]
    raw['process_hash']=hash_events((actions,api.nights))
    for key in ('illegal','ignored_known','voted_good','admitted','changed','outside'):
        raw[key+'_ballots']=sum(v[key] for v in api.votes)
    raw['grant_game']=int(bool(api.extensions));raw['gold_call_game']=int(bool(api.calls))
    raw['outside_call_game']=int(any(c['outside'] for c in api.calls))
    raw['conditional_call_game']=int(any(c['witness'] and c['witness']['conditional'] for c in api.calls))
    raw['gold_turn_final_change']=int(any(c['turn_target']!=c['final_target'] for c in api.calls))
    result=dict(raw=raw,trace_hash=hash_events(o.transcript))
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,
                            calls=api.calls,votes=api.votes,nights=api.nights,extensions=api.extensions)
    return result


def evaluate(job):
    phase,r,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        v=simulate(r,g,m,seed)
        for k,x in v['raw'].items():raw.setdefault(k,[]).append(x)
        if i in {0,n//2,n-1}:samples.append(dict(seed=seed,trace_hash=v['trace_hash']))
    mask=raw['dead_clear']
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,samples=samples,
        win=win_summary(raw['win']),branch_win=win_summary([v for v,k in zip(raw['win'],mask) if k]),
        means={k:mean(v) for k,v in raw.items() if k not in HASH_KEYS})


def contrasts(cells):
    D={(c['good'],c['mafia']):c for c in cells};out=[]
    for mn in sorted({c['mafia'] for c in cells}):
        for q in ('0','50','100'):
            for a,b in PAIRS:
                x,y=D[a+'_q'+q,mn],D[b+'_q'+q,mn]
                assert x['raw']['opening_hash']==y['raw']['opening_hash']
                assert x['raw']['dead_clear']==y['raw']['dead_clear']
                for branch in ('all','dead_clear'):
                    mask=[True]*x['n'] if branch=='all' else x['raw']['dead_clear']
                    xx=[v for v,k in zip(x['raw']['win'],mask) if k];yy=[v for v,k in zip(y['raw']['win'],mask) if k]
                    diff=[i for i,k in enumerate(mask) if k and x['raw']['process_hash'][i]!=y['raw']['process_hash'][i]]
                    row=dict(mafia=mn,q=q,comparison=a+'->'+b,branch=branch,primary=q=='50',win=pair_result(xx,yy),
                        process_different=len(diff),same_terminal_different_process=sum(x['raw']['win'][i]==y['raw']['win'][i] for i in diff),
                        day1_mafia_exile=pair_result([v for v,k in zip(x['raw']['day1_mafia_exile'],mask) if k],
                                                    [v for v,k in zip(y['raw']['day1_mafia_exile'],mask) if k]))
                    if row['primary'] and xx:row['precision']=exact_paired_interval(xx,yy,48)
                    out.append(row)
    # q has no optional-response node if police died on the first night.
    for mode in MODES:
        for mn in sorted({c['mafia'] for c in cells}):
            a=D[mode+'_q0',mn]
            for q in ('50','100'):
                b=D[mode+'_q'+q,mn]
                for k in ('win','process_hash'):
                    assert [v for v,z in zip(a['raw'][k],a['raw']['dead_clear']) if z]==[v for v,z in zip(b['raw'][k],b['raw']['dead_clear']) if z]
    return out


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    r,gs,ms=build_spec(config);output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v28.py'))+list((root/'tests').glob('*v28.py'))+[root/'configs/dead_gold_v28.json',root/'docs/dead_gold_protocol_v28.md',root/'docs/gold_evidence_audit_scope_v28.md',root/'results/v28_evidence_audit.json']
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
            jobs=[pool.submit(evaluate,(phase,r,g,m,spec['seed_start'],spec['n'])) for g in gs for m in ms]
            for f in as_completed(jobs):
                rows.append(f.result())
                if len(rows)%16==0:print(f'{phase} {len(rows)}/{len(jobs)}',flush=True)
        rows.sort(key=lambda c:(c['good'],c['mafia']))
        save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows);assert fingerprint()==freeze['package_sha256']
        if phase=='train':save(output/'no_selection_before_holdout.json',dict(policy_selection=False,q_selection=False,
            note='All frozen candidates retained; no response to development win rates.'))
    files=['freeze.json','train.json','holdout.json','no_selection_before_holdout.json']
    result=dict(games=total,elapsed_seconds=time.monotonic()-started,files={f:sha256((output/f).read_bytes()).hexdigest() for f in files})
    save(output/'manifest.json',result);return result
