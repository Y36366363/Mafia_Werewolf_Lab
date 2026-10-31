"""Targeted counter-response, repair coverage and frozen local-q evaluation."""
import json,shutil,time
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict,replace
from fractions import Fraction
from hashlib import sha256
from math import sqrt,log
from statistics import mean,NormalDist
from . import strategies_v23 as d
from .engine import Role,Rules,speech_order
from .simulation import opening,continue_game
from .statistics import paired_summary,win_summary
from .experiments import fingerprint
from .reply_evaluation_v19 import metrics as base_metrics
from .position_repair_experiment_v14 import _solution,_frozen

ENDPOINTS=('repair_q0','repair_q100')


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=None if 'cells' in value else 2)+'\n')


def build_spec(config):
    rules=Rules(**config['rules'])
    common=dict(reveal='silent',trust='none',dead_police_message='truth',dead_claim_response='trust',
        live_counter='hidden',inspect_position='gap',dead_clear_plan='truth',leadership='nominate',
        position_model='posterior',prior_model='equal',shortlist_rule='list2',flow='timed',
        source_credit=True,history=False,reply='keep',routing='evidence',remember=True)
    good=tuple(d.GoodPolicyV23(**common,**r) for r in config['good'])
    mafia=tuple(d.MafiaPolicyV23(bluff='none',kill='claims',opening_mode='ordinary',dead_mafia_message='silent',**r) for r in config['mafia'])
    assert config['train']['seed_start']+config['train']['n']<=config['holdout']['seed_start']
    assert (rules.police,rules.mafia,rules.civilians)==(4,4,8)
    return rules,good,mafia


class AuditAPI:
    def __init__(self):
        self.votes=[];self.repeat=[]
    def __getattr__(self,key):return getattr(d,key)
    def after_speech(self,obs,policy,rng):
        target=d.restatement_target(obs,policy)
        msg=d.after_speech(obs,policy,rng)
        if target is not None:
            self.repeat.append(dict(day=obs.day,speaker=obs.player,target=target))
            assert msg.kind=='accuse' and msg.target==target
        return msg
    def vote(self,obs,policy,rng,candidates=None):
        if obs.role==Role.MAFIA:return d.vote(obs,policy,rng,candidates)
        # Same pure function as d.vote, evaluated once; it consumes no RNG.
        info=d.explain(obs,policy,candidates);target=info['target']
        orphan=info['reason']=='compare_conflicting_sources' and len(info['conflict_targets'])==1
        dead_partner=any(target in e and any(p not in obs.alive for p in e) for e in info['history_edges'])
        live_partner=any(target in e and all(p in obs.alive for p in e) for e in info['history_edges'])
        stale=info['reason'] in {'single_source_protocol','common_recommendation_protocol','compatible_sources_protocol'} and any(
            m.kind=='report' and m.verdict and m.target==target and m.day<obs.day and m.speaker not in obs.alive
            and target in info['proposals'].get(str(m.speaker),[])
            and target not in d.repaired.current_recommendations(obs,m.speaker,set(info['legal'])) for m in obs.messages)
        self.votes.append(dict(day=obs.day,round='pk' if candidates is not None else 'first',player=obs.player,
            role=obs.role.value,target=target,reason=info['reason'],known_bad=info['known_bad'],
            orphan=orphan and dead_partner and not live_partner,stale=stale,
            ignored_known=bool(info['known_bad']) and target not in info['known_bad'],
            voted_good=target in info['known_good'],illegal=target is not None and target not in info['legal']))
        return target


def simulate(rules,g,m,seed,details=False):
    api=AuditAPI();s=opening(rules,g,m,seed,api)
    o=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw=base_metrics(s,o);order=list(speech_order(s));fake=raw['fake_speaker']
    first=next(p for p in order if s.roles[p]==Role.POLICE)
    no_prior=fake!=-1 and order.index(first)>order.index(fake)
    raw['narrow_civilian']=int(raw['civilian_target'] and no_prior)
    raw['narrow_police']=int(raw['police_target'] and no_prior)
    for flag in ('orphan','stale','ignored_known','voted_good','illegal'):
        votes=[v for v in api.votes if v['day']>=2 and v[flag]]
        raw[flag+'_ballots']=len(votes);raw[flag+'_game']=int(bool(votes))
    raw['repeat_count']=len(api.repeat)
    raw['repeat_game']=int(bool(api.repeat))
    raw['repeat_target_civilian']=sum(s.roles[e['target']]==Role.CIVILIAN for e in api.repeat)
    raw['repeat_target_police']=sum(s.roles[e['target']]==Role.POLICE for e in api.repeat)
    exiles=[e for e in o.transcript if e['event']=='day_death']
    raw['day2_police_exile']=int(any(e['day']==2 and s.roles[e['payload']['victim']]==Role.POLICE for e in exiles))
    raw['post_day1_police_exiles']=sum(e['day']>=2 and s.roles[e['payload']['victim']]==Role.POLICE for e in exiles)
    hash_prefix=[]
    for e in o.transcript:
        if e['day']==2 and e['event']=='votes':break
        hash_prefix.append(e)
    raw['pre_day2_vote_hash']=sha256(repr(tuple(hash_prefix)).encode()).hexdigest()
    result=dict(raw=raw,trace_hash=sha256(repr(o.transcript).encode()).hexdigest())
    if details:result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,votes=api.votes,repeats=api.repeat)
    return result


def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        result=simulate(rules,g,m,seed)
        for k,v in result['raw'].items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=result['trace_hash']))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,
        means={k:mean(v) for k,v in raw.items() if k!='pre_day2_vote_hash'},samples=samples,
        win=win_summary(raw['win']),branches={b:win_summary([v for i,v in enumerate(raw['win']) if raw[b][i]]) for b in ('eligible','narrow_civilian','narrow_police','dead_police')})


def pair_result(a,b,family=None):
    result=paired_summary(a,b)
    if family and a:
        n=len(a);mu=result['delta'];ds=[y-x for x,y in zip(a,b)]
        var=sum((d-mu)**2 for d in ds)/(n-1);z=NormalDist().inv_cdf(1-.05/(2*family))
        half=z*sqrt(var/n);h=sqrt(2*log(2*family/.05)/n)
        result['family_normal']=[max(-1,mu-half),min(1,mu+half)]
        result['family_hoeffding']=[max(-1,mu-h),min(1,mu+h)]
    return result


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for m in sorted({c['mafia'] for c in cells}):
        a,b=lookup['legacy_q50',m],lookup['repair_q50',m]
        assert a['raw']['pre_day2_vote_hash']==b['raw']['pre_day2_vote_hash']
        for name,x,y in [('repair','legacy_q50','repair_q50'),('response','repair_q0','repair_q100')]:
            a,b=lookup[x,m],lookup[y,m]
            for key in ('first_dead','first_check','fake_speaker','fake_target','opportunity'):
                assert a['raw'][key]==b['raw'][key]
            for branch in ('all','narrow_civilian','narrow_police'):
                mask=[True]*a['n'] if branch=='all' else [bool(v) for v in a['raw'][branch]]
                assert branch=='all' or a['raw'][branch]==b['raw'][branch]
                out.append(dict(name=name,mafia=m,branch=branch,
                    win=pair_result([v for v,k in zip(a['raw']['win'],mask) if k],
                                    [v for v,k in zip(b['raw']['win'],mask) if k],8 if name=='repair' and branch=='all' else None)))
    for g in ('legacy_q50','repair_q50'):
        for base_name in ('late_near','late_far','decoy_near','decoy_far'):
            a,b=lookup[g,base_name+'_quiet'],lookup[g,base_name+'_restate']
            for key in ('first_dead','first_check','fake_speaker','fake_target','day1_mafia_exile','police_claims'):
                assert a['raw'][key]==b['raw'][key]
            out.append(dict(name='counter',good=g,base=base_name,branch='all',win=pair_result(a['raw']['win'],b['raw']['win'],8)))
    return out


def matrix(cells,mafia):
    lookup={(c['good'],c['mafia']):c for c in cells}
    return [[Fraction(sum(lookup[g,m]['raw']['win']),lookup[g,m]['n']) for m in mafia] for g in ENDPOINTS]


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    rules,good,mafia=build_spec(config);names=[m.name for m in mafia];output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v23.py'))+list((root/'tests').glob('*v23.py'))+[root/'configs/restatement_response_v23.json',root/'docs/restatement_response_protocol_v23.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    freeze=dict(config=config,good=[asdict(g) for g in good],mafia=[asdict(m) for m in mafia],package_sha256=fingerprint(),
        assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    tr=config['train']
    with ProcessPoolExecutor(max_workers=workers) as pool:
        train=list(pool.map(evaluate,[('train',rules,g,m,tr['seed_start'],tr['n']) for g in good for m in mafia]))
    mat=matrix(train,names);cert=_solution(mat,list(ENDPOINTS),names)
    save(output/'train.json',dict(cells=train,contrasts=contrasts(train),matrix=[[str(v) for v in row] for row in mat],certificate=cert));total+=sum(c['n'] for c in train)
    q=cert['good_mixture'].get('repair_q100','0')
    template=next(g for g in good if g.name=='repair_q50');learned=replace(template,name='trained_local_q',response_probability=q)
    alias=next((g.name for g in good if g.name!='legacy_q50' and Fraction(g.response_probability)==Fraction(q)),None)
    save(output/'selection_before_holdout.json',dict(q_exact=q,policy=asdict(learned),alias_of=alias,
        certificate=cert,holdout_unread=True,scope='2 endpoint x 8 frozen mafia TRAIN empirical game; local single actor randomization, no team secret signal.'))
    print('train q frozen before holdout',flush=True)
    assert fingerprint()==freeze['package_sha256']
    ho=config['holdout'];pool_good=good if alias else (*good,learned)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        held=list(pool.map(evaluate,[('holdout',rules,g,m,ho['seed_start'],ho['n']) for g in pool_good for m in mafia]))
    total+=sum(c['n'] for c in held);hm=matrix(held,names)
    selected=[c for c in held if c['good']==(alias or 'trained_local_q')]
    save(output/'holdout.json',dict(cells=held,contrasts=contrasts(held),matrix=[[str(v) for v in row] for row in hm],
        frozen_bounds=_frozen(hm,list(ENDPOINTS),names,cert),local_q_evaluation=dict(alias_of=alias,rates={c['mafia']:c['win'] for c in selected})))
    assert fingerprint()==freeze['package_sha256']
    files=['freeze.json','train.json','selection_before_holdout.json','holdout.json']
    manifest=dict(games=total,alias_reused=alias,elapsed_seconds=time.monotonic()-started,files={n:sha256((output/n).read_bytes()).hexdigest() for n in files})
    save(output/'manifest.json',manifest);return manifest
