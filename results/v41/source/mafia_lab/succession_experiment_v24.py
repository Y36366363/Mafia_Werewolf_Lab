"""Frozen counter coverage experiment; no strategy search on validation data."""
import json, shutil, time
from pathlib import Path
from dataclasses import asdict, replace
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor, as_completed
from statistics import mean
from fractions import Fraction
from . import strategies_v24 as d
from . import restatement_experiment_v23 as previous
from .engine import Role, speech_order
from .simulation import opening, continue_game
from .reply_evaluation_v19 import metrics
from .experiments import fingerprint
from .position_repair_experiment_v14 import _solution, _frozen

ENDPOINTS = previous.ENDPOINTS
BASES = ('late_near', 'late_far', 'decoy_near', 'decoy_far')
MODES = ('quiet', 'restate', 'support', 'claim')
save = previous.save


def build_spec(config):
    # Reuse frozen common parameters, then instantiate the new mafia type.
    old_config = dict(config, mafia=[{k:v for k,v in m.items() if k != 'succession'} for m in config['mafia']])
    rules, good, old_mafia = previous.build_spec(old_config)
    mafia = tuple(d.MafiaPolicyV24(**asdict(m), succession=r['succession']) for m,r in zip(old_mafia,config['mafia']))
    return rules, good, mafia


class AuditAPI(previous.AuditAPI):
    def __init__(self):
        super().__init__(); self.shadow = []; self.successions = []
    def __getattr__(self, key):
        return getattr(d, key)
    def message(self, obs, policy, rng, context='day', override=None):
        event = d.succession_opportunity(obs) if context == 'day' else None
        if event is not None:
            self.shadow.append(dict(day=obs.day, **event))
            if policy.succession != 'none':
                self.successions.append(dict(day=obs.day, mode=policy.succession, **event))
        return d.message(obs, policy, rng, context, override)
    def after_speech(self, obs, policy, rng):
        event = d.succession_event(obs, policy)
        target = d.base.restatement_target(obs, policy)
        msg = d.after_speech(obs, policy, rng)
        if event is not None:
            assert msg.kind == 'accuse' and msg.target == event['target'] and msg.verdict is None
        if target is not None:
            self.repeat.append(dict(day=obs.day, speaker=obs.player, target=target))
        return msg


def _hash(events):
    return sha256(repr(tuple(events)).encode()).hexdigest()


def simulate(rules, g, m, seed, details=False):
    api = AuditAPI(); s = opening(rules,g,m,seed,api)
    o = continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw = metrics(s,o); order = list(speech_order(s)); fake = raw['fake_speaker']
    first = next(p for p in order if s.roles[p] == Role.POLICE)
    no_prior = fake != -1 and order.index(first) > order.index(fake)
    raw['narrow_civilian'] = int(raw['civilian_target'] and no_prior)
    raw['narrow_police'] = int(raw['police_target'] and no_prior)
    for flag in ('orphan','stale','ignored_known','voted_good','illegal'):
        vv = [v for v in api.votes if v['day'] >= 2 and v[flag]]
        raw[flag+'_ballots'] = len(vv); raw[flag+'_game'] = int(bool(vv))
    raw.update(repeat_count=len(api.repeat), succession_count=len(api.successions),
               succession_game=int(bool(api.successions)), shadow_game=int(bool(api.shadow)),
               shadow_day=api.shadow[0]['day'] if api.shadow else -1)
    day2 = [e for e in o.transcript if e['day'] == 2 and e['event'] == 'night_death']
    if day2:
        idx = o.transcript.index(day2[0]); prefix = o.transcript[:idx+1]
        dead = {e['payload']['victim'] for e in prefix if e['event'] in {'night_death','day_death'}}
        raw['day2_dead_source_live_target'] = int(fake in dead and raw['fake_target'] not in dead)
    else:
        raw['day2_dead_source_live_target'] = 0
    exiles = [e for e in o.transcript if e['event'] == 'day_death']
    raw['day2_police_exile'] = int(any(e['day']==2 and s.roles[e['payload']['victim']]==Role.POLICE for e in exiles))
    raw['post_day1_police_exiles'] = sum(e['day']>=2 and s.roles[e['payload']['victim']]==Role.POLICE for e in exiles)
    raw['day1_hash'] = _hash([e for e in o.transcript if e['day']==1])
    prefix = []
    for e in o.transcript:
        if api.shadow and e['event']=='message' and e['day']==api.shadow[0]['day'] and e['payload']['context']=='day' and e['payload']['speaker']==api.shadow[0]['speaker']:
            break
        prefix.append(e)
    raw['pre_succession_hash'] = _hash(prefix)
    result = dict(raw=raw,trace_hash=_hash(o.transcript))
    if details:
        result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],transcript=o.transcript,
                      votes=api.votes,repeats=api.repeat,successions=api.successions,shadow=api.shadow)
    return result


HASH_KEYS = {'day1_hash','pre_succession_hash'}


def evaluate(job):
    phase,rules,g,m,start,n = job; raw={}; samples=[]
    for i,seed in enumerate(range(start,start+n)):
        result = simulate(rules,g,m,seed)
        for k,v in result['raw'].items(): raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:
            samples.append(dict(index=i,seed=seed,trace_hash=result['trace_hash']))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,samples=samples,
                means={k:mean(v) for k,v in raw.items() if k not in HASH_KEYS},
                win=previous.win_summary(raw['win']))


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells};out=[]
    for gn in sorted({c['good'] for c in cells}):
        for base in BASES:
            rows={mode:lookup[gn,base+'_'+mode] for mode in MODES}
            a=rows['restate']
            for b in rows.values():
                assert a['raw']['day1_hash']==b['raw']['day1_hash']
                assert a['raw']['day2_dead_source_live_target']==b['raw']['day2_dead_source_live_target']
            for mode in ('support','claim'):
                b=rows[mode]
                # First intervention opportunity is shared, even when its day varies.
                assert a['raw']['pre_succession_hash']==b['raw']['pre_succession_hash']
                assert a['raw']['shadow_game']==b['raw']['succession_game']
            for control,treatment in (('quiet','restate'),('restate','support'),('restate','claim'),('support','claim')):
                x,y=rows[control],rows[treatment]
                mask=x['raw']['day2_dead_source_live_target']
                family=4 if gn=='repair_q50' and (control,treatment)==('restate','claim') else None
                out.append(dict(good=gn,base=base,control=control,treatment=treatment,
                    primary=bool(family),win=previous.pair_result(x['raw']['win'],y['raw']['win'],family),
                    day2_branch=previous.pair_result([v for v,k in zip(x['raw']['win'],mask) if k],
                                                    [v for v,k in zip(y['raw']['win'],mask) if k])))
    return out


def coverage(cells):
    lookup={(c['good'],c['mafia']):c for c in cells}; out=[]
    for gn in sorted({c['good'] for c in cells}):
        for base in BASES:
            a=lookup[gn,base+'_restate']; wins=a['raw']['win']; shadow=a['raw']['shadow_game']
            for mode in ('support','claim'):
                b=lookup[gn,base+'_'+mode]
                out.append(dict(good=gn,base=base,mode=mode,baseline_wins=sum(wins),
                    baseline_wins_with_opportunity=sum(w and s for w,s in zip(wins,shadow)),
                    baseline_win_treatment_exec=sum(w and s for w,s in zip(wins,b['raw']['succession_game'])),
                    baseline_wins_lost=sum(x and not y for x,y in zip(wins,b['raw']['win'])),
                    baseline_losses_won=sum(not x and y for x,y in zip(wins,b['raw']['win'])),
                    baseline_opportunities=sum(shadow),treatment_executed=sum(b['raw']['succession_game'])) )
    return out


def matrix(cells,names):
    lookup={(c['good'],c['mafia']):c for c in cells}
    return [[Fraction(sum(lookup[g,m]['raw']['win']),lookup[g,m]['n']) for m in names] for g in ENDPOINTS]


def run(config,output,workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    rules,good,mafia=build_spec(config);names=[m.name for m in mafia];output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v24.py'))+list((root/'tests').glob('*v24.py'))+[root/'configs/succession_counter_v24.json',root/'docs/succession_counter_protocol_v24.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    freeze=dict(config=config,good=[asdict(g) for g in good],mafia=[asdict(m) for m in mafia],package_sha256=fingerprint(),
        assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze);started=time.monotonic();total=0
    def block(phase,policies):
        cfg=config[phase];rows=[]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(evaluate,(phase,rules,g,m,cfg['seed_start'],cfg['n'])) for g in policies for m in mafia]
            for future in as_completed(futures):
                rows.append(future.result())
                if len(rows)%8==0:print(f'{phase} {len(rows)}/{len(futures)} cells',flush=True)
        return sorted(rows,key=lambda r:(r['good'],r['mafia']))
    train=block('train',good);mat=matrix(train,names);cert=_solution(mat,list(ENDPOINTS),names)
    save(output/'train.json',dict(cells=train,contrasts=contrasts(train),coverage=coverage(train),
        matrix=[[str(v) for v in row] for row in mat],certificate=cert));total+=sum(c['n'] for c in train)
    q=cert['good_mixture'].get('repair_q100','0')
    learned=replace(next(g for g in good if g.name=='repair_q50'),name='trained_local_q',response_probability=q)
    alias=next((g.name for g in good if Fraction(g.response_probability)==Fraction(q)),None)
    save(output/'selection_before_holdout.json',dict(q_exact=q,policy=asdict(learned),alias_of=alias,
        certificate=cert,holdout_unread=True,scope='2 endpoints x 16 fixed adversary columns TRAIN empirical matrix; no full-game GTO.'))
    print('train choice frozen before holdout: q='+q,flush=True)
    assert fingerprint()==freeze['package_sha256']
    held=block('holdout',good if alias else (*good,learned));hm=matrix(held,names)
    save(output/'holdout.json',dict(cells=held,contrasts=contrasts(held),coverage=coverage(held),
        matrix=[[str(v) for v in row] for row in hm],frozen_bounds=_frozen(hm,list(ENDPOINTS),names,cert)))
    total+=sum(c['n'] for c in held)
    assert fingerprint()==freeze['package_sha256']
    files=['freeze.json','train.json','selection_before_holdout.json','holdout.json']
    manifest=dict(games=total,alias_reused=alias,elapsed_seconds=time.monotonic()-started,
        files={n:sha256((output/n).read_bytes()).hexdigest() for n in files})
    save(output/'manifest.json',manifest);return manifest
