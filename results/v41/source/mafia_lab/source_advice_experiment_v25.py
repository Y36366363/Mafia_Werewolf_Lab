"""Fixed source-admission ablation with unchanged adversary and local-q grid."""
import json,shutil,time
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
from fractions import Fraction
from statistics import mean
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import strategies_v25 as d
from . import succession_experiment_v24 as old
from .engine import Role,speech_order
from .simulation import opening,continue_game
from .reply_evaluation_v19 import metrics
from .experiments import fingerprint
from .restatement_experiment_v23 import pair_result,save
from .statistics import win_summary

BASES=old.BASES


def build_spec(config):
    old_config=dict(config,good=[{k:v for k,v in g.items() if k!='report_advice_gate'} for g in config['good']])
    rules,gs,ms=old.build_spec(old_config)
    return rules,tuple(d.GoodPolicyV25(**asdict(g),report_advice_gate=r['report_advice_gate']) for g,r in zip(gs,config['good'])),ms


class AuditAPI(old.AuditAPI):
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:return d.vote(obs,policy,rng,candidates)
        info=d.explain(obs,policy,candidates);target=info['target']
        orphan=info['reason']=='compare_conflicting_sources' and len(info['conflict_targets'])==1
        dead_partner=any(target in e and any(p not in obs.alive for p in e) for e in info['history_edges'])
        live_partner=any(target in e and all(p in obs.alive for p in e) for e in info['history_edges'])
        stale=info['reason'] in {'single_source_protocol','common_recommendation_protocol','compatible_sources_protocol'} and any(
            m.kind=='report' and m.verdict and m.target==target and m.day<obs.day and m.speaker not in obs.alive
            and target in info['proposals'].get(str(m.speaker),[])
            and target not in d.base.base.repaired.current_recommendations(obs,m.speaker,set(info['legal'])) for m in obs.messages)
        own=[m for m in obs.messages if m.speaker==obs.player and m.day==obs.day and m.kind=='report' and m.verdict and m.target in info['legal']]
        self.votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,target=target,
            round='pk' if candidates is not None else 'first',reason=info['reason'],
            known_bad=info['known_bad'],known_good=info['known_good'],
            blocked_sources=info['blocked_advice_sources'],history_edges=info['history_edges'],
            orphan=orphan and dead_partner and not live_partner,stale=stale,
            ignored_known=bool(info['known_bad']) and target not in info['known_bad'],
            voted_good=target in info['known_good'],illegal=target is not None and target not in info['legal'],
            public_hit_mismatch=bool(obs.role==Role.POLICE and own and target!=own[-1].target)))
        return target


def hash_events(events):return sha256(repr(tuple(events)).encode()).hexdigest()


def simulate(rules,g,m,seed,details=False):
    api=AuditAPI();initial=opening(rules,g,m,seed,api)
    outcome=continue_game(initial,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=metrics(initial,outcome);order=list(speech_order(initial));fake=raw['fake_speaker']
    first=next(p for p in order if initial.roles[p]==Role.POLICE)
    raw['narrow_civilian']=int(raw['civilian_target'] and fake!=-1 and order.index(first)>order.index(fake))
    for flag in ('orphan','stale','ignored_known','voted_good','illegal','public_hit_mismatch'):
        relevant=[v for v in api.votes if v['day']>=2 and v[flag]]
        raw[flag+'_ballots']=len(relevant);raw[flag+'_game']=int(bool(relevant))
    raw['blocked_advice_ballots']=sum(bool(v['blocked_sources']) for v in api.votes)
    raw['blocked_advice_game']=int(bool(raw['blocked_advice_ballots']))
    raw['succession_game']=int(bool(api.successions))
    raw['day1_hash']=hash_events([e for e in outcome.transcript if e['day']==1])
    prefix=[]
    for e in outcome.transcript:
        if e['day']==2 and e['event']=='votes':break
        prefix.append(e)
    raw['pre_day2_vote_hash']=hash_events(prefix)
    result=dict(raw=raw,trace_hash=hash_events(outcome.transcript))
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in initial.roles],transcript=outcome.transcript,votes=api.votes)
    return result


HASH_KEYS={'day1_hash','pre_day2_vote_hash'}


def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        row=simulate(rules,g,m,seed)
        for k,v in row['raw'].items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=row['trace_hash']))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,samples=samples,
                win=win_summary(raw['win']),means={k:mean(v) for k,v in raw.items() if k not in HASH_KEYS})


def exact_paired_interval(a,b,family=4):
    from scipy.stats import beta
    n=len(a);plus=sum(x==0 and y==1 for x,y in zip(a,b));minus=sum(x==1 and y==0 for x,y in zip(a,b));tail=.05/(4*family)
    def bounds(k):return [0. if not k else float(beta.ppf(tail,k,n-k+1)),1. if k==n else float(beta.ppf(1-tail,k+1,n-k))]
    p,m=bounds(plus),bounds(minus)
    return dict(method='Marginal Clopper-Pearson plus union bound',family=family,tail_alpha=tail,
                p_plus=p,p_minus=m,ci_simultaneous=[p[0]-m[1],p[1]-m[0]])


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for mn in sorted({c['mafia'] for c in cells}):
        for q in ('0','50','100'):
            a,b=lookup['base_q'+q,mn],lookup['gate_q'+q,mn]
            assert a['raw']['day1_hash']==b['raw']['day1_hash']
            assert a['raw']['pre_day2_vote_hash']==b['raw']['pre_day2_vote_hash']
            primary=q=='50' and mn.endswith('_claim')
            row=dict(kind='gate',mafia=mn,q=q,primary=primary,win=pair_result(a['raw']['win'],b['raw']['win'],4 if primary else None))
            if primary:row['precision']=exact_paired_interval(a['raw']['win'],b['raw']['win'])
            out.append(row)
        for prefix in ('base','gate'):
            a,b=lookup[prefix+'_q0',mn],lookup[prefix+'_q100',mn]
            assert a['raw']['narrow_civilian']==b['raw']['narrow_civilian']
            for key in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
                assert a['raw'][key]==b['raw'][key]
            mask=a['raw']['narrow_civilian']
            out.append(dict(kind='response',good_family=prefix,mafia=mn,primary=False,
                win=pair_result(a['raw']['win'],b['raw']['win']),
                conditional=pair_result([v for v,k in zip(a['raw']['win'],mask) if k],[v for v,k in zip(b['raw']['win'],mask) if k])))
    return out


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    rules,gs,ms=build_spec(config);output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v25.py'))+list((root/'tests').glob('*v25.py'))+[root/'configs/source_advice_v25.json',root/'docs/source_advice_protocol_v25.md',root/'docs/source_audit_scope_v25.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    import scipy
    freeze=dict(config=config,good=[asdict(g) for g in gs],mafia=[asdict(m) for m in ms],package_sha256=fingerprint(),scipy_version=scipy.__version__,
        assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    for phase in ('train','holdout'):
        cfg=config[phase];rows=[]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(evaluate,(phase,rules,g,m,cfg['seed_start'],cfg['n'])) for g in gs for m in ms]
            for fut in as_completed(jobs):
                rows.append(fut.result())
                if len(rows)%8==0:print(f'{phase} {len(rows)}/{len(jobs)} cells',flush=True)
        rows.sort(key=lambda c:(c['good'],c['mafia']));save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows);assert fingerprint()==freeze['package_sha256']
        if phase=='train':
            save(output/'no_selection_before_holdout.json',dict(holdout_unread=True,rule='All mechanisms, q values, adversary columns and primary comparisons unchanged; no policy or q selected from train.'))
    files=['freeze.json','train.json','no_selection_before_holdout.json','holdout.json']
    result=dict(games=total,elapsed_seconds=time.monotonic()-started,files={n:sha256((output/n).read_bytes()).hexdigest() for n in files})
    save(output/'manifest.json',result);return result
