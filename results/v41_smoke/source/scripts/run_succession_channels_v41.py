"""Frozen five-arm experiment and common-observation vote diagnostics."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import shutil
import time

from run_paired_source_routing_v40 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.succession_channels_v41 import SuccessionChannelsAPI


CONFIG = ROOT / 'configs/succession_channels_v41.json'
CONTRASTS = [('bare', 'report_neither'), ('report_neither', 'report_gate'),
             ('report_neither', 'report_conflict'), ('report_gate', 'report_both'),
             ('bare', 'report_both')]


def play(spec, q, seed, arm, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = SuccessionChannelsAPI(cooperation, relay, q, arm)
    state = opening(rules, good, mafia, seed, api)
    result = continue_game(state, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = result.transcript
    roles = [role.value for role in state.roles]
    counts = Counter()
    shadows = Counter()
    for ballot in api.channel_votes:
        first_day2 = ballot['day'] == 2 and ballot['first']
        for source, target in ballot['calls']:
            if roles[source] == 'police':
                followed = ballot['target'] == target
                counts['follow'] += followed
                counts['opportunities'] += 1
                if first_day2:
                    counts['day2_follow'] += followed
                    counts['day2_opportunities'] += 1
        if 'shadow' not in ballot:
            continue
        successor = api.successions[0]['speaker']
        shadows['votes'] += 1
        for a, b in CONTRASTS[1:4]:
            left, right = (ballot['shadow'][key] for key in (a, b))
            name = f'{a}_to_{b}'
            shadows[f'{name}:admission'] += successor not in left['sources'] and successor in right['sources']
            shadows[f'{name}:added_edge'] += bool(set(map(tuple, right['edges'])) - set(map(tuple, left['edges'])))
            if left['target'] != right['target']:
                shadows[f'{name}:changed'] += 1
                old = roles[left['target']] if left['target'] is not None else 'abstain'
                new = roles[right['target']] if right['target'] is not None else 'abstain'
                shadows[f'{name}:role:{old}_to_{new}'] += 1
                shadows[f"{name}:route:{left['reason']}_to_{right['reason']}"] += 1
    exiles = {str(e['day']): roles[e['payload']['victim']] for e in events if e['event']=='day_death'}
    row = dict(seed=seed, win=result.good_win, exiles=exiles,
               day1_hash=hash_events(e for e in events if e['day']==1),
               trace_hash=hash_events(events), counts=dict(counts), shadows=dict(shadows),
               first_succession=next(iter(api.successions), None))
    if details:
        row.update(events=events, roles=roles, ballots=api.channel_votes, successions=api.successions)
    return row


def run_arm(args):
    arm, spec, q, seeds = args
    rows = [play(spec, q, seed, arm) for seed in seeds]
    print(arm, len(rows), flush=True)
    return arm, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    smoke = parser.parse_args().smoke
    config = json.loads(CONFIG.read_text())
    spec = load_spec(config)
    out = ROOT / ('results/v41_smoke' if smoke else 'results/v41')
    out.mkdir()
    inherited = json.loads((ROOT / config['parent_freeze']).read_text())['assets']
    assert all(digest(ROOT / rel) == h for rel, h in inherited.items())
    assets = set(inherited)
    assets.update(str(p.relative_to(ROOT)) for p in (
        CONFIG, Path(__file__).resolve(), ROOT / config['parent_freeze'],
        ROOT / 'mafia_lab/succession_channels_v41.py',
        ROOT / 'tests/test_succession_channels_v41.py',
        ROOT / 'docs/succession_channels_protocol_v41.md'))
    hashes = {rel: digest(ROOT / rel) for rel in sorted(assets)}
    for rel in hashes:
        dest = out / 'source' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    save_json(out / 'freeze.json', dict(config=config, assets=hashes, python=platform.python_version()))

    started = time.monotonic()
    batch = config['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'], batch['seed_start'] + batch['n'])
    with ProcessPoolExecutor(max_workers=5) as pool:
        arms = dict(pool.map(run_arm, ((arm, spec, config['q'], seeds) for arm in config['arms'])))
    groups = list(zip(*arms.values(), strict=True))
    for group in groups:
        for key in ('seed', 'day1_hash', 'first_succession'):
            assert all(row[key] == group[0][key] for row in group)
        if group[0]['first_succession'] is None:
            assert len({row['trace_hash'] for row in group}) == 1
    summaries = {}
    for arm, rows in arms.items():
        summaries[arm] = dict(wins=sum(row['win'] for row in rows),
            day2_exiles=dict(Counter(row['exiles'].get('2', 'none') for row in rows)),
            counts=sum((Counter(row['counts']) for row in rows), Counter()))
    contrasts = {}
    for a, b in CONTRASTS:
        pairs = list(zip(arms[a], arms[b], strict=True))
        left = [x['win'] for x, y in pairs]
        right = [y['win'] for x, y in pairs]
        contrasts[a + '_to_' + b] = dict(
            gains=sum(x < y for x,y in zip(left,right)), losses=sum(x > y for x,y in zip(left,right)),
            day2_transitions=Counter(x['exiles'].get('2','none')+'_to_'+y['exiles'].get('2','none')
                                     for x,y in pairs),
            precision=exact_paired_interval(left, right, len(CONTRASTS)))
    shadows = sum((Counter(row['shadows']) for row in arms['report_both']), Counter())
    cases = []
    if not smoke:
        for a, b in CONTRASTS[1:]:
            match = next((x for x,y in zip(arms[a],arms[b]) if x['win'] != y['win']), None)
            if match and match['seed'] not in {case['seed'] for case in cases}:
                index = match['seed'] - seeds.start
                detail = {arm: play(spec, config['q'], match['seed'], arm, True) for arm in arms}
                assert all(row['trace_hash'] == arms[arm][index]['trace_hash'] for arm,row in detail.items())
                cases.append(dict(seed=match['seed'], arms=detail))
    summary = dict(n=len(seeds), triggered=sum(bool(group[0]['first_succession']) for group in groups),
                   day1_mafia=sum(group[0]['exiles'].get('1')=='mafia' for group in groups),
                   arms=summaries, contrasts=contrasts, shadows=shadows)
    assert all(digest(ROOT / rel) == h == digest(out / 'source' / rel) for rel,h in hashes.items())
    save_gzip(out / 'pairs.json.gz', arms)
    save_gzip(out / 'cases.json.gz', cases)
    save_json(out / 'summary.json', summary)
    save_json(out / 'manifest.json', dict(games=len(seeds) * len(arms), elapsed=time.monotonic()-started,
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()}))


if __name__ == '__main__':
    main()
