"""Frozen 2x2 continuation ablation; no strategy search or equilibrium solve."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from fractions import Fraction
from hashlib import sha256
from math import log,sqrt
from pathlib import Path
from statistics import mean,NormalDist
import json,shutil,time
from . import strategies_v22 as d
from .engine import Rules,Role,Observation,Message,Investigation,Death,PublicEvent
from .policies import teammates
from .simulation import opening,continue_game
from .statistics import paired_summary,win_summary
from .experiments import fingerprint
from .reply_evaluation_v19 import metrics as opening_metrics

PAIRS=(('combined','legacy','both'),('live_only','legacy','live_pair'),
       ('current_only','legacy','current_day'),('live_given_current','current_day','both'),
       ('current_given_live','live_pair','both'))


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=None if 'cells' in value else 2)+'\n')


def build_spec(config):
    rules=Rules(**config['rules'])
    common=dict(reveal='silent',trust='none',dead_police_message='truth',dead_claim_response='trust',
        live_counter='hidden',inspect_position='gap',dead_clear_plan='truth',leadership='nominate',
        position_model='posterior',prior_model='equal',shortlist_rule='list2',flow='timed',
        source_credit=True,history=False,reply='keep',routing='evidence',remember=True,response_probability='1/2')
    good=tuple(d.GoodPolicyV22(**common,**row) for row in config['good'])
    mafia=tuple(d.MafiaPolicyV22(bluff='none',kill='claims',opening_mode='ordinary',dead_mafia_message='silent',**row) for row in config['mafia'])
    assert (rules.police,rules.mafia,rules.civilians)==(4,4,8)
    a,b=config['blocks'];assert a['seed_start']+a['n']<=b['seed_start']
    return rules,good,mafia


def restore_observation(row):
    """Restore actor-only audit snapshots; never accepts referee roles."""
    out=dict(row);out['role']=Role(out['role']);out['rules']=Rules(**out['rules'])
    for key in ('teammates','alive','pending_pk'):out[key]=tuple(out[key])
    out['messages']=tuple(Message(**dict(m,targets=tuple(m['targets']))) for m in out['messages'])
    out['investigations']=tuple(Investigation(**r) for r in out['investigations'])
    out['deaths']=tuple(Death(**r) for r in out['deaths'])
    out['public_events']=tuple(PublicEvent(**dict(e,ballots=tuple(tuple(x) for x in e['ballots']),candidates=tuple(e['candidates']))) for e in out['public_events'])
    return Observation(**out)


class AuditAPI:
    def __init__(self):
        self.votes=[]
    def __getattr__(self,key):return getattr(d,key)
    def vote(self,obs,policy,rng,candidates=None):
        target=d.vote(obs,policy,rng,candidates)
        if obs.role!=Role.MAFIA:
            info=d.explain(obs,policy,candidates)
            assert target==info['target']
            old_edges=info['history_edges']
            lonely=info['reason']=='compare_conflicting_sources' and len(info['conflict_targets'])==1
            dead_edge=any(target in e and any(p not in obs.alive for p in e) for e in old_edges)
            live_partner=any(target in e and all(p in obs.alive for p in e) for e in old_edges)
            stale=any(m.kind=='report' and m.verdict and m.target==target and m.day<obs.day
                and m.speaker not in obs.alive and m.speaker in info['sources'] for m in obs.messages)
            self.votes.append(dict(day=obs.day,role=obs.role.value,target=target,reason=info['reason'],
                orphan_conflict=lonely and dead_edge and not live_partner,stale_dead_hit_reference=stale,
                stale_dead_advice_selected=info['reason'] in {'single_source_protocol','common_recommendation_protocol','compatible_sources_protocol'}
                    and any(m.kind=='report' and m.verdict and m.target==target and m.day<obs.day
                        and m.speaker not in obs.alive
                        and target in info['proposals'].get(str(m.speaker),[])
                        and target not in d.current_recommendations(obs,m.speaker,set(info['legal']))
                        for m in obs.messages),
                ignores_private_bad=bool(info['known_bad']) and target not in info['known_bad'],
                votes_private_good=target in info['known_good'],
                illegal=target is not None and target not in info['legal']))
        return target


def evaluate(job):
    phase,rules,g,m,start,n=job;raw={};samples=[]
    for i,seed in enumerate(range(start,start+n)):
        api=AuditAPI();initial=opening(rules,g,m,seed,api)
        outcome=continue_game(initial,g,m,seed,trace=True,decision_api=api,public_ballots=True)
        values=opening_metrics(initial,outcome);roles=initial.roles
        later=[e for e in outcome.transcript if e['day']>=2]
        day2deaths=[e['payload']['victim'] for e in later if e['day']==2 and e['event']=='day_death']
        values.update(day2_police_exile=int(bool(day2deaths) and roles[day2deaths[0]]==Role.POLICE),
            day2_mafia_exile=int(bool(day2deaths) and roles[day2deaths[0]]==Role.MAFIA),
            post_day1_police_exiles=sum(e['event']=='day_death' and roles[e['payload']['victim']]==Role.POLICE for e in later if e['event']=='day_death'))
        for flag in ('orphan_conflict','stale_dead_hit_reference','stale_dead_advice_selected','ignores_private_bad','votes_private_good','illegal'):
            votes=[v for v in api.votes if v['day']>=2 and v[flag]]
            values[flag+'_ballots']=len(votes)
            values[flag+'_games']=int(bool(votes))
            values[flag+'_police_ballots']=sum(v['target'] is not None and roles[v['target']]==Role.POLICE for v in votes)
        for k,v in values.items():raw.setdefault(k,[]).append(v)
        prefix=[]
        for e in outcome.transcript:
            if e['day']>=2 and e['event']=='votes':break
            prefix.append(e)
        # Checks entire day one and night two + ordinary day-two speeches.
        raw.setdefault('pre_day2_vote_hash',[]).append(sha256(repr(tuple(prefix)).encode()).hexdigest())
        if i in {0,n//2,n-1}:samples.append(dict(index=i,seed=seed,trace_hash=sha256(repr(outcome.transcript).encode()).hexdigest()))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,
        means={k:mean(v) for k,v in raw.items() if k!='pre_day2_vote_hash'},samples=samples,
        win=win_summary(raw['win']))


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};rows=[]
    for name,a,b in PAIRS:
        for m in sorted({c['mafia'] for c in cells}):
            x,y=lookup[a,m],lookup[b,m]
            for key in ('pre_day2_vote_hash','day1_mafia_exile','day1_police_exile','day1_fake_exile','police_claims','first_check','first_dead'):
                assert x['raw'][key]==y['raw'][key],(name,m,key)
            row=dict(name=name,control=a,treatment=b,mafia=m)
            for metric in ('win','day2_police_exile','day2_mafia_exile'):
                result=paired_summary(x['raw'][metric],y['raw'][metric])
                if name=='combined' and metric=='win':
                    av,bv=x['raw'][metric],y['raw'][metric];n=len(av)
                    ds=[b-a for a,b in zip(av,bv)];mu=sum(ds)/n
                    variance=sum((v-mu)**2 for v in ds)/(n-1)
                    z=NormalDist().inv_cdf(1-.05/16);half=z*sqrt(variance/n)
                    bound=sqrt(2*log(320)/n)
                    result['family8_normal']=[max(-1,mu-half),min(1,mu+half)]
                    result['family8_hoeffding']=[max(-1,mu-bound),min(1,mu+bound)]
                row[metric]=result
            rows.append(row)
    return rows


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    rules,good,mafia=build_spec(config);output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v22.py'))+list((root/'tests').glob('*v22.py'))+[root/'configs/continuation_repair_v22.json',root/'docs/continuation_repair_protocol_v22.md']
    for source in assets:
        target=output/'source'/source.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    freeze=dict(config=config,good=[asdict(g) for g in good],mafia=[asdict(m) for m in mafia],package_sha256=fingerprint(),
        assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    for block in config['blocks']:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            cells=list(pool.map(evaluate,[(block['name'],rules,g,m,block['seed_start'],block['n']) for g in good for m in mafia]))
        save(output/(block['name']+'.json'),dict(cells=cells,contrasts=contrasts(cells)))
        total+=sum(c['n'] for c in cells)
        assert fingerprint()==freeze['package_sha256']
        print(block['name']+' completed',flush=True)
    files=['freeze.json']+[b['name']+'.json' for b in config['blocks']]
    manifest=dict(games=total,elapsed_seconds=time.monotonic()-started,files={n:sha256((output/n).read_bytes()).hexdigest() for n in files})
    save(output/'manifest.json',manifest);return manifest
