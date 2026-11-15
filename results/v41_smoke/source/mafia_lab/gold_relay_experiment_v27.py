"""Frozen delegation evaluation, matched deals, and provenance audits."""
import json
import shutil
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from statistics import mean
from . import strategies_v27 as d
from . import police_execution_experiment_v26 as previous
from .source_advice_experiment_v25 import exact_paired_interval
from .restatement_experiment_v23 import pair_result, save
from .engine import Role, speech_order
from .simulation import opening, continue_game
from .experiments import fingerprint
from .reply_evaluation_v19 import metrics
from .statistics import win_summary


def build_spec(config):
    c = dict(config, good=[{k:v for k,v in g.items() if k != 'relay_mode'} for g in config['good']])
    rules, gs, ms = previous.build_spec(c)
    return rules, tuple(d.GoodPolicyV27(**asdict(g), relay_mode=r['relay_mode']) for g,r in zip(gs, config['good'])), ms


class AuditAPI:
    def __init__(self):
        self.extensions = []; self.votes = []
    def __getattr__(self, name):
        return getattr(d, name)
    def after_speech(self, obs, policy, rng):
        result = d.after_speech(obs, policy, rng)
        for m in result if isinstance(result, tuple) else (result,):
            if m is not None and m.kind in {'delegate', 'relay'}:
                self.extensions.append(asdict(m))
        return result
    def vote(self, obs, policy, rng, candidates=None):
        if obs.role == Role.MAFIA:
            return d.vote(obs, policy, rng, candidates)
        info = d.explain(obs, policy, candidates); target = info['target']
        self.votes.append(dict(day=obs.day, player=obs.player, role=obs.role.value,
            round='pk' if candidates is not None else 'first', target=target, reason=info['reason'],
            known_bad=info['known_bad'], known_good=info['known_good'],
            relay_admitted=info['relay_admitted'], relay_changed=info['relay_changed'],
            relay_sources=info['relay_sources'], relay_targets=info['relay_targets'],
            illegal=target is not None and target not in info['legal'],
            ignored_known=bool(info['known_bad']) and target not in info['known_bad'],
            voted_good=target in info['known_good']))
        return target


def simulate(rules, g, m, seed, details=False):
    api = AuditAPI(); s = opening(rules,g,m,seed,api)
    o = continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
    raw = metrics(s,o)
    raw['day1_hash'] = previous.hash_events([e for e in o.transcript if e['day']==1])
    for kind in ('delegate','relay'):
        rows = [v for v in api.extensions if v['kind']==kind]
        raw[kind+'_count'] = len(rows); raw[kind+'_game'] = int(bool(rows))
    for key in ('relay_admitted','relay_changed','illegal','ignored_known','voted_good'):
        raw[key+'_ballots'] = sum(bool(v[key]) for v in api.votes)
    # Realized disagreement rates are descriptive, not a matched causal estimand:
    # game survival and available rounds can change under the intervention.
    groups = defaultdict(list)
    for v in api.votes:
        groups[v['day'],v['round']].append(v)
    raw['good_split_rounds'] = sum(len({v['target'] for v in vv})>1 for vv in groups.values())
    raw['good_rounds'] = len(groups)
    raw['relay_mafia_target_count'] = sum(s.roles[v['target']]==Role.MAFIA for v in api.extensions if v['kind']=='relay')
    raw['relay_police_target_count'] = sum(s.roles[v['target']]==Role.POLICE for v in api.extensions if v['kind']=='relay')
    raw['relay_police_recipient_count'] = sum(s.roles[v['speaker']]==Role.POLICE for v in api.extensions if v['kind']=='relay')
    result = dict(raw=raw,trace_hash=previous.hash_events(o.transcript))
    if details:
        result.update(seed=seed,roles_evaluation_only=[r.value for r in s.roles],
                      transcript=o.transcript,votes=api.votes,extensions=api.extensions)
    return result


def evaluate(job):
    phase,rules,g,m,start,n = job; raw={}; samples=[]
    for i,seed in enumerate(range(start,start+n)):
        row=simulate(rules,g,m,seed)
        for k,v in row['raw'].items():raw.setdefault(k,[]).append(v)
        if i in {0,n//2,n-1}:samples.append(dict(seed=seed,trace_hash=row['trace_hash']))
    return dict(phase=phase,good=g.name,mafia=m.name,n=n,seed_start=start,raw=raw,samples=samples,
                win=win_summary(raw['win']),means={k:mean(v) for k,v in raw.items() if k!='day1_hash'})


def contrasts(cells):
    lookup={(c['good'],c['mafia']):c for c in cells}; result=[]
    for mn in sorted({c['mafia'] for c in cells}):
        for q in ('0','50','100'):
            for a,b in [('base','fixed'),('base','local'),('fixed','local')]:
                x,y=lookup[a+'_q'+q,mn],lookup[b+'_q'+q,mn]
                assert x['raw']['day1_hash']==y['raw']['day1_hash']
                row=dict(mafia=mn,q=q,comparison=a+'->'+b,primary=q=='50',
                         win=pair_result(x['raw']['win'],y['raw']['win']))
                if row['primary']:row['precision']=exact_paired_interval(x['raw']['win'],y['raw']['win'],24)
                result.append(row)
    return result


def run(config, output, workers=4):
    root=Path(__file__).resolve().parents[1];output=Path(output)
    if output.exists():raise ValueError('new output required')
    r,gs,ms=build_spec(config); output.mkdir(parents=True)
    assets=list((root/'mafia_lab').glob('*.py'))+list((root/'scripts').glob('*v27.py'))+list((root/'tests').glob('*v27.py'))+[root/'configs/gold_relay_v27.json',root/'docs/gold_relay_protocol_v27.md']
    for src in assets:
        dst=output/'source'/src.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    import scipy, platform
    freeze=dict(config=config,good=[asdict(g) for g in gs],mafia=[asdict(m) for m in ms],
                package_sha256=fingerprint(),python=platform.python_version(),scipy=scipy.__version__,
                assets={str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest() for p in (output/'source').rglob('*') if p.is_file()})
    save(output/'freeze.json',freeze); started=time.monotonic();total=0
    for phase in ('train','holdout'):
        rows=[];spec=config[phase]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(evaluate,(phase,r,g,m,spec['seed_start'],spec['n'])) for g in gs for m in ms]
            for future in as_completed(jobs):
                rows.append(future.result())
                if len(rows)%12==0:print(f'{phase} {len(rows)}/{len(jobs)} cells',flush=True)
        rows.sort(key=lambda c:(c['good'],c['mafia']))
        save(output/(phase+'.json'),dict(cells=rows,contrasts=contrasts(rows)))
        total+=sum(c['n'] for c in rows)
        assert fingerprint()==freeze['package_sha256']
        if phase=='train':save(output/'no_selection_before_holdout.json',dict(policy_selection=False,q_selection=False,
            declaration='No strategy, threshold, seeds or comparison changes permitted from development outcomes.'))
    files=['freeze.json','train.json','holdout.json','no_selection_before_holdout.json']
    result=dict(games=total,elapsed_seconds=time.monotonic()-started,files={f:sha256((output/f).read_bytes()).hexdigest() for f in files})
    save(output/'manifest.json',result);return result
