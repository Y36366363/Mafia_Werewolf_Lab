"""Predeclared execution-call experiment and a separate vote-history pilot."""
import json,shutil,time
from pathlib import Path
from dataclasses import asdict
from collections import defaultdict
from hashlib import sha256
from statistics import mean
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import strategies_v26 as d
from . import source_advice_experiment_v25 as old
from . import strategies_v22 as repaired
from .engine import Role,speech_order
from .simulation import opening,continue_game
from .reply_evaluation_v19 import metrics
from .statistics import win_summary
from .experiments import fingerprint
from .restatement_experiment_v23 import pair_result,save

BASES=old.BASES
HASH_KEYS={'day1_hash','pre_day2_speech_hash','pre_day2_vote_hash'}


def build_spec(config):
    c=dict(config,good=[{k:v for k,v in g.items() if k not in {'execution_call','vote_history'}} for g in config['good']],
           mafia=[{k:v for k,v in m.items() if k!='vote_mode'} for m in config['mafia']])
    rules,gs,ms=old.build_spec(c)
    good=tuple(d.GoodPolicyV26(**asdict(g),execution_call=r['execution_call'],vote_history=r['vote_history']) for g,r in zip(gs,config['good']))
    mafia=tuple(d.MafiaPolicyV26(**asdict(m),vote_mode=r['vote_mode']) for m,r in zip(ms,config['mafia']))
    return rules,good,mafia


class AuditAPI:
    def __init__(self):self.votes=[];self.bus=[];self.calls=[]
    def __getattr__(self,k):return getattr(d,k)
    def after_speech(self,obs,policy,rng):
        result=d.after_speech(obs,policy,rng)
        if obs.role==Role.POLICE and obs.day>=2 and policy.execution_call:
            parts=result if isinstance(result,tuple) else (result,)
            own_report=any(m.speaker==obs.player and m.kind=='report' and m.day==obs.day and m.context=='day' for m in obs.messages)
            for m in parts:
                if own_report and m is not None and m.kind=='accuse':
                    self.calls.append(dict(day=obs.day,speaker=obs.player,target=m.target))
        return result
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:
            target=d.costless_bus_target(obs,policy,candidates)
            value=d.vote(obs,policy,rng,candidates)
            if target is not None:
                self.bus.append(dict(day=obs.day,player=obs.player,target=target,round='pk' if candidates is not None else 'first'))
            return value
        info=d.explain(obs,policy,candidates);target=info['target']
        dead_partner=any(target in e and any(p not in obs.alive for p in e) for e in info['history_edges'])
        live_partner=any(target in e and all(p in obs.alive for p in e) for e in info['history_edges'])
        orphan=info['reason']=='compare_conflicting_sources' and len(info['conflict_targets'])==1 and dead_partner and not live_partner
        stale=info['reason'] in {'single_source_protocol','common_recommendation_protocol','compatible_sources_protocol'} and any(
            m.kind=='report' and m.verdict and m.target==target and m.day<obs.day and m.speaker not in obs.alive
            and target in info['proposals'].get(str(m.speaker),[])
            and target not in repaired.current_recommendations(obs,m.speaker,set(info['legal'])) for m in obs.messages)
        own=[m for m in obs.messages if m.speaker==obs.player and m.kind=='report' and m.verdict and m.day==obs.day and m.target in info['legal']]
        call=d.team_execution_call(obs) if obs.role==Role.POLICE else None
        applicable=obs.day>=2 and policy.execution_call and call is not None and call.target in info['known_bad']
        self.votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,target=target,
            round='pk' if candidates is not None else 'first',reason=info['reason'],known_bad=info['known_bad'],
            call_target=call.target if call else None,call_applicable=applicable,
            call_mismatch=bool(applicable and target!=call.target),orphan=orphan,stale=stale,
            ignored_known=bool(info['known_bad']) and target not in info['known_bad'],
            voted_good=target in info['known_good'],illegal=target is not None and target not in info['legal'],
            report_vote_mismatch=bool(obs.role==Role.POLICE and own and target!=own[-1].target),
            history_available=bool(info['history_evidence']),history_changed=info['history_changed'],
            history_pool=info['history_pool'],history_scores=info['history_scores'],history_evidence=info['history_evidence']))
        return target


def hash_events(events):return sha256(repr(tuple(events)).encode()).hexdigest()


def simulate(rules,g,m,seed,details=False):
    api=AuditAPI();s=opening(rules,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=metrics(s,o);order=list(speech_order(s));fake=raw['fake_speaker'];first=next(p for p in order if s.roles[p]==Role.POLICE)
    raw['narrow_civilian']=int(raw['civilian_target'] and fake!=-1 and order.index(first)>order.index(fake))
    for flag in ('orphan','stale','ignored_known','voted_good','illegal','call_mismatch','report_vote_mismatch','history_available','history_changed'):
        rows=[v for v in api.votes if v['day']>=2 and v[flag]]
        raw[flag+'_ballots']=len(rows);raw[flag+'_game']=int(bool(rows))
    raw['call_count']=len(api.calls);raw['bus_count']=len(api.bus)
    raw['day1_hash']=hash_events([e for e in o.transcript if e['day']==1])
    for name,event in [('pre_day2_speech_hash','message'),('pre_day2_vote_hash','votes')]:
        prefix=[]
        for e in o.transcript:
            if e['day']==2 and e['event']==event and (event!='message' or e['payload']['context']=='day'):break
            prefix.append(e)
        raw[name]=hash_events(prefix)
    rounds=defaultdict(list)
    for v in api.votes:
        if v['day']>=2 and v['role']=='police' and v['known_bad']:rounds[v['day'],v['round']].append(v)
    raw['police_split_rounds']=sum(len({v['target'] for v in vv})>1 for vv in rounds.values())
    result=dict(raw=raw,trace_hash=hash_events(o.transcript))
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,votes=api.votes,calls=api.calls,buses=api.bus)
    return result


def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        row=simulate(rules,g,m,seed)
        for k,v in row['raw'].items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=row['trace_hash']))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,samples=samples,
                win=win_summary(raw['win']),means={k:mean(v) for k,v in raw.items() if k not in HASH_KEYS})


def contrasts(cells):
    D={(c['good'],c['mafia']):c for c in cells};out=[]
    for mn in sorted({c['mafia'] for c in cells if c['mafia'].endswith('_team')}):
        for q in ('0','50','100'):
            a,b=D['legacy_q'+q,mn],D['aligned_q'+q,mn]
            for k in ('day1_hash','pre_day2_speech_hash'):assert a['raw'][k]==b['raw'][k]
            r=dict(kind='alignment',q=q,mafia=mn,primary=q=='50',win=pair_result(a['raw']['win'],b['raw']['win'],8 if q=='50' else None))
            if q=='50':r['precision']=old.exact_paired_interval(a['raw']['win'],b['raw']['win'],8)
            out.append(r)
    for mn in ('late_far_claim_team','late_far_claim_bus','decoy_far_claim_team','decoy_far_claim_bus'):
        a,b=D['aligned_q50',mn],D['history_q50',mn]
        for k in ('day1_hash','pre_day2_vote_hash'):assert a['raw'][k]==b['raw'][k]
        out.append(dict(kind='history',mafia=mn,primary=False,win=pair_result(a['raw']['win'],b['raw']['win'],4),precision=old.exact_paired_interval(a['raw']['win'],b['raw']['win'],4)))
    for group in ('legacy','aligned'):
        for mn in sorted({c['mafia'] for c in cells if c['mafia'].endswith('_team')}):
            a,b=D[group+'_q0',mn],D[group+'_q100',mn];mask=a['raw']['narrow_civilian']
            assert mask==b['raw']['narrow_civilian']
            for k in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):assert a['raw'][k]==b['raw'][k]
            out.append(dict(kind='response',group=group,mafia=mn,primary=False,win=pair_result(a['raw']['win'],b['raw']['win']),
                conditional=pair_result([v for v,k in zip(a['raw']['win'],mask) if k],[v for v,k in zip(b['raw']['win'],mask) if k])))
    return out


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    rules,gs,ms=build_spec(config);G={g.name:g for g in gs};M={m.name:m for m in ms};output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v26.py'))+list((root/'tests').glob('*v26.py'))+[root/'configs/police_execution_v26.json',root/'docs/police_execution_protocol_v26.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    import scipy
    freeze=dict(config=config,good=[asdict(g) for g in gs],mafia=[asdict(m) for m in ms],package_sha256=fingerprint(),scipy_version=scipy.__version__,
                assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);total=0;started=time.monotonic()
    for phase in ('train','holdout'):
        cfg=config[phase];rows=[]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(evaluate,(phase,rules,G[gn],M[mn],cfg['seed_start'],cfg['n'])) for gn,mn in config['cells']]
            for fut in as_completed(jobs):
                rows.append(fut.result())
                if len(rows)%9==0:print(f'{phase} {len(rows)}/{len(jobs)} cells',flush=True)
        rows.sort(key=lambda r:(r['good'],r['mafia']));save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows);assert fingerprint()==freeze['package_sha256']
        if phase=='train':save(output/'no_selection_before_holdout.json',dict(holdout_unread=True,policy_selection=False,q_selection=False,rule='All declared mechanisms and pairs unchanged; history pilot is not promoted from train.'))
    files=['freeze.json','train.json','no_selection_before_holdout.json','holdout.json']
    out=dict(games=total,elapsed_seconds=time.monotonic()-started,files={n:sha256((output/n).read_bytes()).hexdigest() for n in files})
    save(output/'manifest.json',out);return out
