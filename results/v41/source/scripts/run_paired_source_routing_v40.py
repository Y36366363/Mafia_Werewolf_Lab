"""Run separate paired interventions on frozen continuation policies."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse
import json
import platform
import shutil
import time

from run_formal_source_conflict_v39 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.continuation_forensics_v38 import daily_counts
from mafia_lab.paired_source_routing_v40 import SourceRoutingAPI
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


CONFIG = ROOT / 'configs/paired_source_routing_v40.json'


def play(spec, q, seed, arm, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = SourceRoutingAPI(cooperation, relay, q, arm)
    state = opening(rules, good, mafia, seed, api)
    outcome = continue_game(state, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = outcome.transcript
    roles = [role.value for role in state.roles]
    counts = Counter()
    day2_pairs = []
    for ballot in api.ballots:
        day = ballot['day']
        first_day2 = day == 2 and ballot['round'] == 'first'
        pair = ballot['pair']
        if pair:
            counts['pair_ballots'] += 1
            counts['mapped_changes_local'] += pair['mapped'] != pair['source_exile']
            if first_day2:
                day2_pairs.append((ballot['player'], pair))
        counts['civilian_ballots'] += 1
        counts['admitted_mafia_advice_ballots'] += any(
            roles[source] == 'mafia' for source in ballot['proposal_sources'])
        for source, target in ballot['calls']:
            if roles[source] == 'police':
                followed = ballot['target'] == target
                counts['followed'] += followed
                counts['opportunities'] += 1
                if first_day2:
                    counts['day2_followed'] += followed
                    counts['day2_opportunities'] += 1
    exiles = {e['day']: roles[e['payload']['victim']] for e in events if e['event'] == 'day_death'}
    prefix = [e for e in events if e['day'] < 2]
    day2 = []
    for event in events:
        if event['day'] > 2 or event['day'] == 2 and event['event'] == 'votes':
            break
        day2.append(event)
    row = dict(seed=seed, win=outcome.good_win, trace_hash=hash_events(events),
        day1_hash=hash_events(prefix), day2_prefix=hash_events(day2),
        pair_hash=hash_events(day2_pairs), day2_pairs=len(day2_pairs), exiles=exiles,
        pk=sum(e['event'] == 'pk_votes' for e in events), counts=dict(counts),
        successions=api.successions)
    if details:
        row.update(events=events, roles=roles, ballots=api.ballots,
                   days=daily_counts(roles, api.nights, events, outcome.good_win))
    return row


def play_arm(args):
    arm, spec, q, seeds = args
    rows = [play(spec, q, seed, arm) for seed in seeds]
    return arm, rows


def summarize(rows, family):
    modes = list(rows)
    for quartet in zip(*rows.values(), strict=True):
        control, source, mapped, succession = quartet
        assert len({v['day1_hash'] for v in quartet}) == 1
        assert control['day2_prefix'] == source['day2_prefix'] == mapped['day2_prefix']
        assert control['pair_hash'] == source['pair_hash'] == mapped['pair_hash']
        if not control['successions'] and not succession['successions']:
            assert control['trace_hash'] == succession['trace_hash']
    summaries = {}
    for arm, matches in rows.items():
        totals = sum((Counter(r['counts']) for r in matches), Counter())
        summaries[arm] = dict(wins=sum(r['win'] for r in matches),
            day1_mafia=sum(r['exiles'].get(1) == 'mafia' for r in matches),
            day2_exiles=Counter(r['exiles'].get(2, 'none') for r in matches),
            pair_games=sum(bool(r['counts'].get('pair_ballots')) for r in matches),
            day2_pair_ballots=sum(r['day2_pairs'] for r in matches),
            succession_games=sum(bool(r['successions']) for r in matches),
            day2_succession_games=sum(any(x['day'] == 2 for x in r['successions']) for r in matches),
            pk=sum(r['pk'] for r in matches), **totals)
    comparisons = {}
    for first, second in [(1, 2), (0, 2), (0, 3)]:
        pairs = list(zip(rows[modes[first]], rows[modes[second]], strict=True))
        a, b = zip(*[(x['win'], y['win']) for x, y in pairs], strict=True)
        comparisons[modes[first] + '_to_' + modes[second]] = dict(
            gains=sum(x < y for x, y in zip(a, b)),
            losses=sum(x > y for x, y in zip(a, b)),
            changed_games=sum(x['trace_hash'] != y['trace_hash'] for x, y in pairs),
            day2_exile_transitions=Counter(
                x['exiles'].get(2, 'none') + '_to_' + y['exiles'].get(2, 'none')
                for x, y in pairs),
            precision=exact_paired_interval(a, b, family))
    return dict(arms=summaries, comparisons=comparisons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    smoke = parser.parse_args().smoke
    config = json.loads(CONFIG.read_text())
    spec = load_spec(config)
    out = ROOT / ('results/v40_smoke' if smoke else 'results/v40')
    out.mkdir()
    parent = ROOT / config['parent_freeze']
    inherited = json.loads(parent.read_text())['assets']
    assert all(digest(ROOT / rel) == h for rel, h in inherited.items())
    assets = set(inherited)
    assets.update(str(p.relative_to(ROOT)) for p in (
        parent, CONFIG, Path(__file__).resolve(),
        ROOT / 'mafia_lab/continuation_forensics_v38.py',
        ROOT / 'mafia_lab/paired_source_routing_v40.py',
        ROOT / 'tests/test_paired_source_routing_v40.py',
        ROOT / 'docs/paired_source_routing_protocol_v40.md'))
    hashes = {rel: digest(ROOT / rel) for rel in sorted(assets)}
    for rel in hashes:
        dest = out / 'source' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    save_json(out / 'freeze.json', dict(config=config, assets=hashes, python=platform.python_version()))
    start = time.monotonic()
    batch = config['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'], batch['seed_start'] + batch['n'])
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows = dict(pool.map(play_arm, ((arm, spec, config['q'], seeds) for arm in config['arms'])))
    summary = summarize(rows, config['terminal_family'])
    cases = []
    if not smoke:
        for seed in (217000045, 217000087):
            cases.append(dict(kind='v39_diagnostic', seed=seed,
                arms={arm: play(spec, config['q'], seed, arm, True) for arm in config['arms'][:3]}))
        for a, b in [('source_exile', 'call_mapping'), ('merge_control', 'succession_report')]:
            match = next(((x, y) for x, y in zip(rows[a], rows[b]) if x['win'] != y['win']), None)
            if match:
                seed = match[0]['seed']
                details = {arm: play(spec, config['q'], seed, arm, True) for arm in (a, b)}
                assert all(details[arm]['trace_hash'] == row['trace_hash']
                           for arm, row in zip((a, b), match))
                cases.append(dict(kind='holdout_flip', seed=seed, arms=details))
    assert all(digest(ROOT / rel) == h and digest(out / 'source' / rel) == h for rel, h in hashes.items())
    save_gzip(out / 'pairs.json.gz', rows)
    save_gzip(out / 'cases.json.gz', cases)
    save_json(out / 'summary.json', summary)
    save_json(out / 'manifest.json', dict(games=len(seeds) * len(rows), elapsed=time.monotonic() - start,
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
