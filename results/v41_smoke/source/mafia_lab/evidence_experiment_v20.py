"""Frozen mechanism ablations and a two-endpoint restricted response game."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from fractions import Fraction
from hashlib import sha256
from math import log,sqrt
from pathlib import Path
from statistics import mean,NormalDist
import json,shutil,time
from . import strategies_v20 as d
from .engine import Rules,Role,speech_order
from .simulation import opening,continue_game
from .statistics import paired_summary,win_summary
from .experiments import fingerprint
from .reply_evaluation_v19 import metrics as legacy_metrics
from .position_repair_experiment_v14 import _solution,_frozen

BRANCHES=('all','eligible','narrow_civilian','narrow_police','dead_police','no_opportunity')
PAIRS=(('memory_credit','credit_today','credit_memory'),
       ('memory_evidence','evidence_today','evidence_q50'),
       ('routing','credit_memory','evidence_q50'),
       ('response_endpoints','evidence_q0','evidence_q100'))
ENDPOINTS=('evidence_q0','evidence_q100')


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=None if isinstance(value,dict) and 'cells' in value else 2)+'\n')


def build_spec(config):
    rules=Rules(**config['rules'])
    common=dict(reveal='silent',trust='none',dead_police_message='truth',dead_claim_response='trust',
        live_counter='hidden',inspect_position='gap',dead_clear_plan='truth',leadership='nominate',
        position_model='posterior',prior_model='equal',shortlist_rule='list2',flow='timed',
        source_credit=True,history=False,reply='keep')
    good=tuple(d.GoodPolicyV20(**common,**r) for r in config['good'])
    mafia=tuple(d.MafiaPolicyV20(bluff='none',kill='claims',opening_mode='ordinary',
        dead_mafia_message='silent',**r) for r in config['mafia'])
    a,b=config['train'],config['holdout']
    if a['seed_start']+a['n']>b['seed_start']:
        raise ValueError('overlap')
    assert (rules.police,rules.mafia,rules.civilians)==(4,4,8)
    return rules,good,mafia


class AuditedAPI:
    def __init__(self):
        self.votes=[]
    def __getattr__(self,key):
        return getattr(d,key)
    def vote(self,obs,policy,rng,candidates=None):
        target=d.vote(obs,policy,rng,candidates)
        if obs.role!=Role.MAFIA:
            pool=set(obs.alive if candidates is None else candidates)-{obs.player}
            historical=d.private_bad(obs,True).intersection(pool)
            current=d.private_bad(obs,False).intersection(pool)
            prior_only=historical-current
            reason=d.route(obs,policy,candidates)[1] if policy.routing=='evidence' else 'fixed_credit'
            self.votes.append(dict(day=obs.day,player=obs.player,civilian=obs.role==Role.CIVILIAN,
                prior_only=bool(prior_only),uses_prior=target in prior_only,
                ignores_known_bad=bool(historical) and target not in historical,
                single_source=reason=='single_source_protocol',conflict=reason=='compare_conflicting_sources'))
        return target


def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for index,seed in enumerate(range(start,start+n)):
        api=AuditedAPI();s=opening(rules,g,m,seed,api)
        outcome=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
        values=legacy_metrics(s,outcome);order=list(speech_order(s));fake=values['fake_speaker']
        first=next(p for p in order if s.roles[p]==Role.POLICE)
        no_prior=fake!=-1 and order.index(fake)<order.index(first)
        values['narrow_civilian']=int(values['civilian_target'] and no_prior)
        values['narrow_police']=int(values['police_target'] and no_prior)
        values['optional_branch']=int(values['eligible'] and no_prior and not values['narrow_police'])
        votes=api.votes
        values['civil_prior_only_ballots']=sum(v['civilian'] and v['prior_only'] for v in votes)
        values['civil_prior_used_ballots']=sum(v['civilian'] and v['prior_only'] and v['uses_prior'] for v in votes)
        values['civil_ignored_known_ballots']=sum(v['civilian'] and v['ignores_known_bad'] for v in votes)
        values['civil_single_source_ballots']=sum(v['civilian'] and v['single_source'] for v in votes)
        values['civil_conflict_ballots']=sum(v['civilian'] and v['conflict'] for v in votes)
        for k,v in values.items():raw.setdefault(k,[]).append(v)
        if index in {0,n//2,n-1}:
            samples.append(dict(index=index,seed=seed,opening_hash=sha256(repr(s).encode()).hexdigest(),
                                trace_hash=sha256(repr(outcome.transcript).encode()).hexdigest()))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,
        means={k:mean(v) for k,v in raw.items()},samples=samples,
        branches={b:win_summary([v for i,v in enumerate(raw['win']) if b=='all' or raw[b][i]]) for b in BRANCHES})


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for name,a,b in PAIRS:
        for mafia in sorted({c['mafia'] for c in cells}):
            x,y=lookup[a,mafia],lookup[b,mafia]
            for k in ('first_dead','first_check','first_check_mafia','fake_speaker','fake_target','opportunity'):
                assert x['raw'][k]==y['raw'][k],(name,mafia,k)
            for branch in BRANCHES:
                mask=[True]*x['n'] if branch=='all' else [bool(v) for v in x['raw'][branch]]
                assert branch=='all' or x['raw'][branch]==y['raw'][branch]
                row=dict(name=name,control=a,treatment=b,mafia=mafia,branch=branch)
                for metric in ('win','day1_mafia_exile','day1_police_exile','police_claims'):
                    av=[v for v,k in zip(x['raw'][metric],mask) if k]
                    bv=[v for v,k in zip(y['raw'][metric],mask) if k]
                    summary=paired_summary(av,bv)
                    if metric=='win' and branch=='all' and name in {'routing','memory_evidence'}:
                        # Eight prespecified primary win contrasts, 5% family.
                        ds=[b-a for a,b in zip(av,bv)];n=len(ds);mu=sum(ds)/n
                        var=sum((v-mu)**2 for v in ds)/(n-1)
                        z=NormalDist().inv_cdf(1-.05/16)
                        half=z*sqrt(var/n);bound=sqrt(2*log(320)/n)
                        summary['family8_normal']=[max(-1,mu-half),min(1,mu+half)]
                        summary['family8_hoeffding']=[max(-1,mu-bound),min(1,mu+bound)]
                        summary['paired_variance']=var
                        independent=(mean(av)*(1-mean(av))+mean(bv)*(1-mean(bv)))*n/(n-1)
                        summary['unpaired_variance_reference']=independent
                    row[metric]=summary
                out.append(row)
    return out


def endpoint_matrix(cells,mafia):
    lookup={(c['good'],c['mafia']):c for c in cells}
    return [[Fraction(sum(lookup[g,m]['raw']['win']),lookup[g,m]['n']) for m in mafia] for g in ENDPOINTS]


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('output exists; do not overwrite')
    output.mkdir(parents=True);rules,good,mafia=build_spec(config);names=[m.name for m in mafia]
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v20.py'))+[root/'configs/evidence_memory_v20.json',root/'docs/evidence_memory_protocol_v20.md',root/'tests/test_evidence_memory_v20.py']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    freeze=dict(config=config,good=[asdict(p) for p in good],mafia=[asdict(p) for p in mafia],
                package_sha256=fingerprint(),assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic()
    train=config['train']
    with ProcessPoolExecutor(max_workers=workers) as pool:
        cells=list(pool.map(evaluate,[('train',rules,g,m,train['seed_start'],train['n']) for g in good for m in mafia]))
    matrix=endpoint_matrix(cells,names);certificate=_solution(matrix,list(ENDPOINTS),names)
    save(output/'train.json',dict(cells=cells,contrasts=contrasts(cells),endpoint_matrix=[[str(x) for x in row] for row in matrix],certificate=certificate))
    q=certificate['good_mixture'].get('evidence_q100','0')
    learned=replace(next(g for g in good if g.name=='evidence_q50'),name='trained_local_q',response_probability=q)
    selection=dict(holdout_unread=True,source='two endpoint empirical TRAIN matrix only',q_exact=q,
        policy=asdict(learned),certificate=certificate,
        realization='One designated first live police samples privately at its own eligible turn. No team secret random signal; no second claimant.')
    save(output/'selection_before_holdout.json',selection);print('train and q frozen before holdout',flush=True)
    assert fingerprint()==freeze['package_sha256']
    hold=config['holdout']
    with ProcessPoolExecutor(max_workers=workers) as pool:
        held=list(pool.map(evaluate,[('holdout',rules,g,m,hold['seed_start'],hold['n']) for g in (*good,learned) for m in mafia]))
    hmatrix=endpoint_matrix(held,names)
    save(output/'holdout.json',dict(cells=held,contrasts=contrasts(held),
        endpoint_matrix=[[str(x) for x in row] for row in hmatrix],
        frozen_train_mixture_bounds=_frozen(hmatrix,list(ENDPOINTS),names,certificate),
        scope='Frozen train endpoint mixtures evaluated on new empirical matrix. Bounds apply to 2x4 pool only; no population confidence or full game exploitability. Direct learned q also simulated.'))
    assert fingerprint()==freeze['package_sha256']
    files=['freeze.json','train.json','selection_before_holdout.json','holdout.json']
    manifest=dict(games=sum(c['n'] for c in cells+held),elapsed_seconds=time.monotonic()-started,
                  files={p:sha256((output/p).read_bytes()).hexdigest() for p in files})
    save(output/'manifest.json',manifest);return manifest
