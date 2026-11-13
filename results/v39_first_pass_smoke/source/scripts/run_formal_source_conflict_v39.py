"""Frozen paired holdout for the continuation formal-call intervention."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from random import Random
import argparse
import gzip
import json
import platform
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_private_response_v35 import spec
from mafia_lab.formal_source_conflict_v39 import FormalSourceConflictAPI
from mafia_lab.hit_candidates_v37 import HitCandidatesAPI
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


CONFIG = ROOT / 'configs/formal_source_conflict_v39.json'


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def save_gzip(path, value):
    path.write_bytes(gzip.compress(json.dumps(value, separators=(',', ':')).encode(), mtime=0))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load_spec(config):
    parent = json.loads((ROOT / config['source_freeze']).read_text())
    rules, good, plans, _ = spec(parent['base_config'])
    plan = next(plan for plan in plans if plan[0] == config['mafia'])
    return rules, good, plan


def play(rules, good, plan, q, seed, enabled, details=False):
    _, mafia, cooperation, fake_relay = plan
    api = FormalSourceConflictAPI(cooperation, fake_relay, q, enabled)
    start = opening(rules, good, mafia, seed, api)
    outcome = continue_game(start, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = outcome.transcript
    roles = [role.value for role in start.roles]
    first_day = [event for event in events if event['day'] == 1]
    day2_prefix = []
    for event in events:
        if event['day'] == 2 and event['event'] == 'votes':
            break
        if event['day'] > 2:
            break
        day2_prefix.append(event)
    day1_exile = next((event['payload']['victim'] for event in first_day
                       if event['event'] == 'day_death'), None)
    counts = Counter()
    edge_ballots = []
    for ballot in api.continuation_ballots:
        counts['civilian_ballots'] += 1
        if ballot['formal_edges']:
            counts['edge_ballots'] += 1
            if ballot['target'] != ballot['original_target']:
                counts['changed_ballots'] += 1
            edge_ballots.append(ballot)
        for source, target in ballot['eligible_calls']:
            if roles[source] != 'police':
                continue
            followed = int(ballot['target'] == target)
            counts['all_opportunities'] += 1
            counts['all_follows'] += followed
            if ballot['day'] == 2 and ballot['round'] == 'first':
                counts['day2_opportunities'] += 1
                counts['day2_follows'] += followed
                if ballot['formal_edges']:
                    counts['day2_edge_opportunities'] += 1
                    counts['day2_edge_follows'] += followed
    row = dict(seed=seed, win=outcome.good_win, day1_exile=day1_exile,
               day1_mafia=int(day1_exile is not None and roles[day1_exile] == 'mafia'),
               day1_hash=hash_events(first_day), day2_prefix_hash=hash_events(day2_prefix),
               trace_hash=hash_events(events), counts=dict(counts))
    if details:
        row.update(roles_evaluation_only=roles, events=events, edge_ballots=edge_ballots)
    return row


def play_batch(args):
    rules, good, plan, q, seeds, enabled = args
    return [play(rules, good, plan, q, seed, enabled) for seed in seeds]


def compare(control, treatment, bootstrap):
    paired = list(zip(control, treatment, strict=True))
    for a, b in paired:
        for field in ('seed', 'day1_hash', 'day1_exile', 'day2_prefix_hash'):
            assert a[field] == b[field], (a['seed'], field)
        for field in ('day2_opportunities', 'day2_edge_opportunities'):
            assert a['counts'].get(field, 0) == b['counts'].get(field, 0)
    a_wins = [a['win'] for a in control]
    b_wins = [b['win'] for b in treatment]
    a_total = sum((Counter(a['counts']) for a in control), Counter())
    b_total = sum((Counter(b['counts']) for b in treatment), Counter())
    triples = [(b['counts'].get('day2_follows', 0) - a['counts'].get('day2_follows', 0),
                a['counts'].get('day2_opportunities', 0)) for a, b in paired]
    rng = Random(bootstrap['seed'])
    n = len(triples)
    samples = []
    if a_total['day2_opportunities']:
        for _ in range(bootstrap['replicates']):
            delta = denominator = 0
            for index in rng.choices(range(n), k=n):
                diff, eligible = triples[index]
                delta += diff
                denominator += eligible
            if denominator:
                samples.append(delta / denominator)
    samples.sort()
    interval = ([samples[int(0.025 * (len(samples) - 1))],
                 samples[int(0.975 * (len(samples) - 1))]] if samples else None)
    return dict(n=n, day1_mafia=sum(a['day1_mafia'] for a in control),
                wins=[sum(a_wins), sum(b_wins)],
                gains=sum(a < b for a, b in zip(a_wins, b_wins)),
                losses=sum(a > b for a, b in zip(a_wins, b_wins)),
                win_interval=exact_paired_interval(a_wins, b_wins, family=1),
                day2_follow_interval=interval, bootstrap_valid=len(samples),
                totals=[dict(a_total), dict(b_total)],
                changed_games=sum(a['trace_hash'] != b['trace_hash'] for a, b in paired),
                edge_games=[sum(bool(a['counts'].get('edge_ballots')) for a in arm)
                            for arm in (control, treatment)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    smoke = parser.parse_args().smoke
    config = json.loads(CONFIG.read_text())
    rules, good, plan = load_spec(config)
    out = ROOT / ('results/v39_smoke' if smoke else 'results/v39')
    out.mkdir()
    parent = ROOT / config['source_freeze']
    inherited = json.loads(parent.read_text())['assets']
    assets = set(inherited)
    assets.update(str(path.relative_to(ROOT)) for path in (
        CONFIG, Path(__file__).resolve(), parent,
        ROOT / 'mafia_lab/formal_source_conflict_v39.py',
        ROOT / 'tests/test_formal_source_conflict_v39.py',
        ROOT / 'docs/formal_source_conflict_protocol_v39.md'))
    assert all(digest(ROOT / rel) == expected for rel, expected in inherited.items())
    hashes = {rel: digest(ROOT / rel) for rel in sorted(assets)}
    for rel in hashes:
        dest = out / 'source' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    save_json(out / 'freeze.json', dict(config=config, assets=hashes, python=platform.python_version()))
    start = time.monotonic()
    batch = config['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'], batch['seed_start'] + batch['n'])
    args = (rules, good, plan, config['q'], seeds)
    with ProcessPoolExecutor(max_workers=2) as pool:
        control, treatment = pool.map(play_batch, ((*args, False), (*args, True)))
    summary = compare(control, treatment, config['bootstrap'])
    _, mafia, cooperation, fake_relay = plan
    replay_count = 0
    for index in sorted({0, len(seeds) // 2, len(seeds) - 1}):
        seed = seeds[index]
        api = HitCandidatesAPI(cooperation, fake_relay, config['q'], retain=True)
        state = opening(rules, good, mafia, seed, api)
        replay = continue_game(state, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
        assert hash_events(replay.transcript) == control[index]['trace_hash']
        replay_count += 1
    cases = []
    if not smoke:
        for category in (1, -1, 0):
            match = next(((a, b) for a, b in zip(control, treatment)
                          if b['win'] - a['win'] == category and a['trace_hash'] != b['trace_hash']), None)
            if match is None:
                continue
            case = [play(rules, good, plan, config['q'], row['seed'], enabled, details=True)
                    for row, enabled in zip(match, (False, True))]
            assert all(result['trace_hash'] == row['trace_hash'] for result, row in zip(case, match))
            cases.append(dict(delta=category, arms=case))
    assert all(digest(ROOT / rel) == h and digest(out / 'source' / rel) == h for rel, h in hashes.items())
    save_gzip(out / 'pairs.json.gz', dict(merge_control=control, formal_conflict=treatment))
    save_gzip(out / 'cases.json.gz', cases)
    save_json(out / 'summary.json', summary)
    save_json(out / 'manifest.json', dict(games=2 * len(seeds), elapsed=time.monotonic() - start,
              baseline_replays=replay_count, case_replays=2 * len(cases),
              files={p.name: digest(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
