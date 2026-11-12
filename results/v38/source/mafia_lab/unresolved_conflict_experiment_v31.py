"""Frozen relay/receiver and targeted counter controls, matched opening seeds."""
import shutil,time,platform
from dataclasses import asdict
from pathlib import Path
from hashlib import sha256
from statistics import mean
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import strategies_v31 as d
from . import relay_receiver_experiment_v30 as previous
from .engine import Role
from .simulation import opening,continue_game
from .statistics import win_summary
from .experiments import fingerprint
from .restatement_experiment_v23 import pair_result,save
from .source_advice_experiment_v25 import exact_paired_interval
from .police_execution_experiment_v26 import hash_events

PAIRS=(('legacy','neutral'),('neutral','aligned'))
FAMILY=74
HASH_KEYS={'process_hash','opening_hash','speech_prefix_hash','nature_hash'}


def build_spec(config):
    c=dict(config,good=[{k:v for k,v in g.items() if k not in {'neutral_conflicts','align_intent'}} for g in config['good']])
    r,gs,ms=previous.build_spec(c)
    return r,tuple(d.GoodPolicyV31(**asdict(g),neutral_conflicts=x['neutral_conflicts'],align_intent=x['align_intent']) for g,x in zip(gs,config['good'])),ms


class AuditAPI(previous.AuditAPI):
    def __getattr__(self,k):return getattr(d,k)
    def choose_kill(self,obs,policy,rng):
        target=d.choose_kill(obs,policy,rng);self.nights.append(('kill',obs.day,target));return target
    def after_last_words(self,obs,policy,rng):
        result=d.after_last_words(obs,policy,rng)
        for m in result if isinstance(result,tuple) else (result,):
            if m is not None:self.extensions.append(asdict(m))
        return result
    def final_call(self,obs,policy,rng):
        result=d.final_call(obs,policy,rng)
        if result is not None and result.kind=='relay':
            offer=d.gold.dead_offers(obs,policy)[0][1]
            self.calls.append(dict(day=obs.day,speaker=obs.player,source=offer.speaker,target=result.target,
                pool=list(offer.targets),outside=result.target not in offer.targets,
                planned_target=d.explain(obs,policy)['target']))
        return result
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:return d.vote(obs,policy,rng,candidates)
        v=d.explain(obs,policy,candidates);target=v['target']
        own=[m for m in obs.messages if m.speaker==obs.player and m.day==obs.day
             and m.context=='day' and m.kind in {'accuse','relay'}]
        call=own[-1] if own else None
        team_call=d.execution.team_execution_call(obs) if obs.role==Role.POLICE else None
        applicable=(obs.day>=2 or policy.align_intent) and team_call is not None and team_call.target in v['known_bad']
        self.votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,
            round='pk' if candidates is not None else 'first',target=target,reason=v['reason'],
            known_bad=v['known_bad'],known_good=v['known_good'],legal=v['legal'],
            illegal=target is not None and target not in v['legal'],
            ignored_known=bool(v['known_bad']) and target not in v['known_bad'],voted_good=target in v['known_good'],
            scope=v['receiver_scope'],changed=v['receiver_changed'],common=v['common_targets'],
            incompatible=v['contributors_conflict'],kinds=v['proposal_kinds'],
            early_common=v['early_common_accepted'],conflict_block=v['blocked_by_conflict'],
            admitted=bool(v['dead_relay_admitted']),
            own_call=call.target if call else None,own_kind=call.kind if call else None,
            own_mismatch=bool(call and call.target!=target),
            own_call_legal=bool(call and call.target in v['legal']),
            team_call_mismatch=bool(applicable and target!=team_call.target),
            team_call_applicable=bool(applicable),sources=v['sources'],proposals=v['proposals'],
            history_edges=v['history_edges'],conflict_targets=v['conflict_targets'],
            orphan=v['orphan_not_actionable'],live_edges=v['live_edges'],
            orphan_directive=v['reason'] in {'compare_conflicting_sources','compare_live_conflicting_sources'} and bool(v['history_edges']) and not v['live_edges'] if policy.neutral_conflicts else False))
        return target


def simulate(r,g,m,seed,details=False):
    api=AuditAPI();s=opening(r,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=previous.previous.previous.metrics(s,o);victim=s.deaths[0].player
    raw['dead_clear']=int(s.roles[victim]==Role.POLICE and not s.investigations[0].is_mafia)
    raw['opening_hash']=hash_events((s.roles,s.deaths,s.investigations))
    raw['nature_hash']=hash_events(s.roles)
    actions=[e for e in o.transcript if e['event'] in {'night_death','day_death','votes','pk_votes','terminal'}]
    raw['process_hash']=hash_events((actions,api.nights))
    prefix=[]
    for e in o.transcript:
        if e['day']==1 and e['event']=='votes':break
        prefix.append(e)
    raw['speech_prefix_hash']=hash_events(prefix)
    for flag in ('illegal','ignored_known','voted_good','scope','changed','early_common','conflict_block','admitted','own_mismatch','team_call_mismatch','team_call_applicable','orphan','orphan_directive'):
        raw[flag+'_ballots']=sum(v[flag] for v in api.votes)
    raw['incompatible_early_common_ballots']=sum(v['incompatible'] and v['early_common'] for v in api.votes)
    raw['explicit_conflict_common_ballots']=sum(v['incompatible'] and v['early_common'] and all(k in {'execution','claimed_hit'} for k in v['kinds'].values()) for v in api.votes)
    raw['relay_game']=int(bool(api.calls))
    raw['relay_count']=len(api.calls)
    raw['relay_own_mismatch_ballots']=sum(v['own_kind']=='relay' and v['own_mismatch'] for v in api.votes)
    raw['relay_own_first_mismatch_ballots']=sum(v['own_kind']=='relay' and v['own_mismatch'] and v['round']=='first' for v in api.votes)
    raw['police_own_first_mismatch_ballots']=sum(v['role']=='police' and v['own_kind']=='accuse' and v['own_mismatch'] and v['round']=='first' for v in api.votes)
    raw['day1_live_police_reports']=sum(e['event']=='message' and e['day']==1 and e['payload']['context']=='day' and e['payload']['kind']=='report' and s.roles[e['payload']['speaker']]==Role.POLICE for e in o.transcript)
    raw['relay_true_police_source_count']=sum(s.roles[c['source']]==Role.POLICE for c in api.calls)
    raw['relay_false_source_count']=sum(s.roles[c['source']]==Role.MAFIA for c in api.calls)
    result=dict(raw=raw,trace_hash=hash_events(o.transcript))
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,
                             votes=api.votes,nights=api.nights,extensions=api.extensions,calls=api.calls)
    return result


def column_job(job):
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
    def comparison(a,b,kind,all_deals=False):
        x,y=D[a]['raw'],D[b]['raw'];assert x['nature_hash']==y['nature_hash']
        if kind!='selfkill_cost':assert x['opening_hash']==y['opening_hash']
        mask=[True]*len(x['win']) if all_deals or a[1].startswith('false_') else x['dead_clear']
        if not all_deals:assert mask==y['dead_clear'] or a[1].startswith('false_')
        diff=[i for i,k in enumerate(mask) if k and x['process_hash'][i]!=y['process_hash'][i]]
        row=dict(control=list(a),treatment=list(b),kind=kind,branch='all' if all_deals or a[1].startswith('false_') else 'dead_clear',
            process_different=len(diff),same_terminal_different_process=sum(x['win'][i]==y['win'][i] for i in diff))
        for metric in ('win','day1_mafia_exile'):
            xx=[v for v,k in zip(x[metric],mask) if k];yy=[v for v,k in zip(y[metric],mask) if k]
            row[metric]=pair_result(xx,yy)
            if xx:row[metric+'_precision']=exact_paired_interval(xx,yy,FAMILY)
        out.append(row)
    for m in sorted({c['mafia'] for c in cells}):
        for a,b in PAIRS:comparison((a,m),(b,m),'receiver')
    for g in sorted({c['good'] for c in cells}):
        for knife in ('late','decoy'):
            for mode in ('copy','quiet'):comparison((g,knife+'_old'),(g,knife+'_'+mode),'opponent')
            comparison((g,knife+'_quiet'),(g,'false_grant'),'selfkill_cost',True)
        comparison((g,'false_notice'),(g,'false_grant'),'false_authority',True)
    assert len(out)*2==FAMILY
    return out


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    r,gs,ms=build_spec(config);output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v31.py'))+list((root/'tests').glob('*v31.py'))+[root/'configs/unresolved_conflict_v31.json',root/'docs/unresolved_conflict_protocol_v31.md']
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
            for f in as_completed(jobs):
                rows.extend(f.result());print(f'{phase} {len(rows)}/24 cells',flush=True)
        rows.sort(key=lambda c:(c['good'],c['mafia']));save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows);assert fingerprint()==freeze['package_sha256']
        if phase=='train':save(output/'no_selection_before_holdout.json',dict(selection=False,note='All three receivers and eight controls frozen; no change after train.'))
    files=['freeze.json','train.json','holdout.json','no_selection_before_holdout.json']
    result=dict(games=total,elapsed_seconds=time.monotonic()-started,files={f:sha256((output/f).read_bytes()).hexdigest() for f in files})
    save(output/'manifest.json',result);return result
