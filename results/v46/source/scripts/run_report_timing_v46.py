"""Reproduce risk traces and evaluate three fixed paired comparisons on fresh deals."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import platform
import shutil
import time

import scipy
from scipy.stats import binomtest

from run_continuation_audit_v45 import verify_parent
from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.report_timing_v46 import ReportTimingAPI
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval

CONFIG = ROOT/'configs/report_timing_v46.json'


def play(spec, q, setup, seed, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = ReportTimingAPI(cooperation, relay, q, *setup)
    start = opening(rules, good, mafia, seed, api)
    result = continue_game(start, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = result.transcript
    roles = [r.value for r in start.roles]
    exiles = {e['day']: e['payload']['victim'] for e in events if e['event'] == 'day_death'}
    counts = Counter()
    for report in api.reports:
        counts['report_'+report['reason']] += 1
    for row in api.choices:
        mode, role = row['reason'], roles[row['source']]
        counts['eligible_'+mode+'_'+role] += 1
        if row['baseline'] != row['proposed']:
            counts['would_change_'+mode+'_'+role] += 1
        if row['baseline'] != row['actual']:
            counts['changed_'+mode+'_'+role] += 1
    for ballot in api.pilot_ballots:
        if ballot['day'] == 2 and ballot['first']:
            for speaker, target in ballot['calls']:
                if roles[speaker] == 'police':
                    counts['day2_follow_opportunities'] += 1
                    counts['day2_follows'] += ballot['target'] == target
    before_day2_vote = []
    for event in events:
        if event['day'] == 2 and event['event'] == 'votes' or event['day'] > 2:
            break
        before_day2_vote.append(event)
    d2_call = next((c for c in api.call_events if c['day'] == 2), None)
    row = dict(seed=seed, win=result.good_win, trace=hash_events(events),
               opening=hash_events((start.roles,start.deaths,start.investigations)),
               day1=hash_events(e for e in events if e['day'] == 1),
               prefix2=hash_events(before_day2_vote),
               exiles=exiles, exile_roles={d:roles[p] for d,p in exiles.items()},
               counts=dict(counts), warnings=api.warnings, day2_call=d2_call,
               day3_succession=any(x['day'] == 3 for x in api.successions),
               timing_changed=any(x['baseline'] != x['actual'] for x in api.choices))
    if details:
        row.update(events=events, roles_evaluation_only=roles, reports=api.reports,
                   choices=api.choices, successions=api.successions, ballots=api.pilot_ballots)
    return row


def batch(job):
    name, spec, q, setup, seeds = job
    rows = [play(spec,q,setup,s) for s in seeds]
    return name, rows


def summarize(arms, comparisons):
    wins = {}
    for group in zip(*arms.values(), strict=True):
        assert len({(r['seed'],r['opening'],r['day1']) for r in group}) == 1
    for name, rows in arms.items():
        wins[name] = dict(wins=sum(r['win'] for r in rows),
                          day2=Counter(r['exile_roles'].get(2,'none') for r in rows),
                          day3=Counter(r['exile_roles'].get(3,'none') for r in rows),
                          day3_successions=sum(r['day3_succession'] for r in rows),
                          warnings=sum(bool(r['warnings']) for r in rows),
                          timing_changed_games=sum(r['timing_changed'] for r in rows),
                          counts=sum((Counter(r['counts']) for r in rows),Counter()))
    contrasts = {}
    for a,b in comparisons:
        pairs = list(zip(arms[a],arms[b],strict=True))
        before, after = [x['win'] for x,_ in pairs], [y['win'] for _,y in pairs]
        gains = sum(x<y for x,y in zip(before,after,strict=True))
        losses = sum(x>y for x,y in zip(before,after,strict=True))
        precision = exact_paired_interval(before,after,len(comparisons))
        for count, key in [(gains,'p_plus'),(losses,'p_minus')]:
            ci = binomtest(count,len(pairs)).proportion_ci(1-2*precision['tail_alpha'],method='exact')
            assert all(abs(x-y)<1e-10 for x,y in zip(ci,precision[key]))
        if a == 'greedy':
            assert all(x['prefix2'] == y['prefix2'] or x['warnings'] for x,y in pairs)
            assert all(x['warnings'] or x['trace'] == y['trace'] for x,y in pairs)
        else:
            assert all(x['prefix2'] == y['prefix2'] for x,y in pairs)
            assert all(y['timing_changed'] or x['trace'] == y['trace'] for x,y in pairs)
        same_loss = [(x,y) for x,y in pairs if not x['win'] and not y['win']]
        contrasts[a+'_to_'+b] = dict(gains=gains,losses=losses,precision=precision,
            changed_same_loss=sum(x['trace'] != y['trace'] for x,y in same_loss),
            changed_traces=sum(x['trace'] != y['trace'] for x,y in pairs),
            day2_transitions=Counter(x['exile_roles'].get(2,'none')+'→'+y['exile_roles'].get(2,'none')
                                     for x,y in pairs))
    return dict(n=len(next(iter(arms.values()))),arms=wins,contrasts=contrasts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--workers',type=int,default=6)
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    parents = verify_parent(cfg['parent_freeze'])
    spec = load_spec(parent)
    out = ROOT/('results/v46_smoke' if args.smoke else 'results/v46')
    out.mkdir()
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'mafia_lab/report_timing_v46.py',
             ROOT/'docs/report_timing_protocol_v46.md',ROOT/'tests/test_report_timing_v46.py']
    assets = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for rel in assets:
        dest = out/'source'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest)
    history = ROOT/'results/v44/pairs.json.gz'
    save_json(out/'freeze.json',dict(config=cfg,assets=assets,parents=parents,q=parent['q'],
        reference_sha256=digest(history),python=platform.python_version(),scipy=scipy.__version__))
    t0 = time.monotonic()
    parameter = cfg['smoke' if args.smoke else 'holdout']
    seeds = range(parameter['seed_start'],parameter['seed_start']+parameter['n'])
    jobs = [(arm,spec,parent['q'],setup,seeds[i:i+256]) for arm,setup in cfg['arms'].items()
            for i in range(0,len(seeds),256)]
    arms = {arm:[] for arm in cfg['arms']}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for name, rows in pool.map(batch,jobs):
            arms[name].extend(rows)
            if len(arms[name]) == len(seeds):
                print(name,len(seeds),flush=True)
    summary = summarize(arms,cfg['comparisons'])
    references = {}
    cases = {}
    replays = 0
    if not args.smoke:
        archive = {r['seed']:r for r in json.load(gzip.open(history,'rt'))['copy_both']}
        for seed in cfg['reference_seeds']:
            references[str(seed)] = {arm:play(spec,parent['q'],cfg['arms'][arm],seed,True)
                                     for arm in ['greedy','lookahead']}
            assert references[str(seed)]['greedy']['trace'] == archive[seed]['trace']
        for arm,rows in arms.items():
            for index in (0,len(rows)//2,len(rows)-1):
                assert play(spec,parent['q'],cfg['arms'][arm],seeds[index]) == rows[index]
                replays += 1
        for left,right in cfg['comparisons']:
            paired = list(zip(arms[left],arms[right],strict=True))
            selectors = {'first_changed':lambda a,b:a['trace']!=b['trace'],
                         'first_gain':lambda a,b:a['win']<b['win'],
                         'first_loss':lambda a,b:a['win']>b['win']}
            selected = set()
            for label, predicate in selectors.items():
                found = next(((a,b) for a,b in paired if predicate(a,b)),None)
                if found is None or found[0]['seed'] in selected:
                    continue
                seed = found[0]['seed']; selected.add(seed)
                cases[left+'_'+label] = {arm:play(spec,parent['q'],cfg['arms'][arm],seed,True)
                                        for arm in (left,right)}
                assert all(cases[left+'_'+label][arm]['trace']==row['trace']
                           for arm,row in zip((left,right),found,strict=True))
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in assets.items())
    save_gzip(out/'pairs.json.gz',arms)
    save_gzip(out/'cases.json.gz',dict(historical=references,fresh=cases))
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(games=len(seeds)*len(arms),historical_replays=2*len(references),
        sample_replays=replays,case_replays=2*len(cases),elapsed=time.monotonic()-t0,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print({arm:row['wins'] for arm,row in summary['arms'].items()})


if __name__=='__main__':
    main()
