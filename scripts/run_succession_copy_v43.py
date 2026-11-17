"""Paired four-arm holdout for succession copying and civilian routing."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import shutil
import time

from scipy.stats import binomtest

from run_paired_source_routing_v40 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.succession_copy_v43 import SuccessionCopyAPI

CONFIG = ROOT / 'configs/succession_copy_v43.json'
CONTRASTS = [('old_base', 'old_agreement'), ('copy_base', 'copy_agreement'),
             ('old_base', 'copy_base'), ('old_agreement', 'copy_agreement')]


def play(spec, q, setup, seed, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    copy, agreement = setup
    api = SuccessionCopyAPI(cooperation, relay, q, agreement, copy)
    start = opening(rules, good, mafia, seed, api)
    result = continue_game(start, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    counts = Counter()
    day2_matches = {}
    for ballot, diag in zip(api.pilot_ballots, api.match_events, strict=True):
        day2 = ballot['day'] == 2 and ballot['first']
        matches = diag['matches']
        if matches is not None:
            label = 'zero' if not matches else 'multiple' if len(matches) > 1 else roles[matches[0]]
            counts['match_' + label] += 1
            counts['current_copy_opportunity_' + label] += diag['copier'] is not None
            if day2:
                day2_matches[str(ballot['player'])] = label
                counts['day2_match_' + label] += 1
            if len(matches) == 1 and ballot['supported'][1] != ballot['baseline']:
                counts['local_change_' + label] += 1
                counts['day2_local_change_' + label] += day2
                counts['actual_change_' + label] += ballot['target'] != ballot['baseline']
        for source, target in ballot['calls']:
            if roles[source] != 'police':
                continue
            counts['opportunities'] += 1
            counts['follows'] += ballot['target'] == target
            if day2:
                counts['day2_opportunities'] += 1
                counts['day2_follows'] += ballot['target'] == target
    exiles = {e['day']: e['payload']['victim'] for e in events if e['event'] == 'day_death'}
    first2 = []
    for event in events:
        if event['day'] > 2 or event['day'] == 2 and event['event'] == 'votes':
            break
        first2.append(event)
    first_copy = next((e for e in api.copy_events if e['changes_report']), None)
    copy_prefix = None
    for index, e in enumerate(events):
        if (first_copy is not None and e['day'] == first_copy['day'] and e['event'] == 'message'
                and e['payload']['context'] == 'day'
                and e['payload']['speaker'] == first_copy['speaker']):
            copy_prefix = hash_events(events[:index])
            break
    row = dict(seed=seed, win=result.good_win, trace=hash_events(events),
        opening=hash_events((start.roles, start.deaths, start.investigations)),
        day1=hash_events(e for e in events if e['day'] == 1), first2=hash_events(first2),
        first_copy=first_copy or None, copy_prefix=copy_prefix,
        copies=len(api.copy_events), changed_reports=sum(e['changes_report'] for e in api.copy_events),
        hit_teammate=sum(e['changes_report'] and e['hit_teammate'] for e in api.copy_events),
        exile=exiles, exile_roles={d: roles[p] for d,p in exiles.items()},
        counts=dict(counts), day2_matches=day2_matches)
    if details:
        row.update(events=events, roles=roles, ballots=api.pilot_ballots,
                   matches=api.match_events, copy_events=api.copy_events)
    return row


def job(args):
    arm, spec, q, setup, seeds = args
    rows = [play(spec, q, setup, seed) for seed in seeds]
    print(arm, len(rows), flush=True)
    return arm, rows


def summary(arms):
    for quartet in zip(*arms.values(), strict=True):
        assert len({(v['seed'], v['opening'], v['day1']) for v in quartet}) == 1
    n = len(arms['old_base'])
    totals = {}
    for arm, rows in arms.items():
        totals[arm] = dict(wins=sum(r['win'] for r in rows),
            day1=Counter(r['exile_roles'].get(1, 'none') for r in rows),
            day2=Counter(r['exile_roles'].get(2, 'none') for r in rows),
            copy_games=sum(r['copies'] > 0 for r in rows),
            eligible_slots=sum(r['copies'] for r in rows),
            changed_reports=sum(r['changed_reports'] for r in rows),
            hit_teammate=sum(r['hit_teammate'] for r in rows),
            counts=sum((Counter(r['counts']) for r in rows), Counter()))
    comparisons = {}
    for a, b in CONTRASTS:
        pairs = list(zip(arms[a], arms[b], strict=True))
        if b.endswith('_agreement') and a.split('_')[0] == b.split('_')[0]:
            for x, y in pairs:
                assert x['first2'] == y['first2']
                assert x['counts'].get('day2_opportunities', 0) == y['counts'].get('day2_opportunities', 0)
                assert x['day2_matches'] == y['day2_matches']
        else:
            for x, y in pairs:
                assert x['copy_prefix'] == y['copy_prefix']
                if y['first_copy']:
                    assert x['first_copy'] == dict(y['first_copy'], copied=False)
                else:
                    assert x['first_copy'] is None and x['trace'] == y['trace']
        before = [x['win'] for x, _ in pairs]
        after = [y['win'] for _, y in pairs]
        ci = exact_paired_interval(before, after, len(CONTRASTS))
        gains = sum(x < y for x, y in zip(before, after))
        losses = sum(x > y for x, y in zip(before, after))
        for count, key in ((gains, 'p_plus'), (losses, 'p_minus')):
            checked = binomtest(count, n).proportion_ci(1-2*ci['tail_alpha'], method='exact')
            assert all(abs(x-y)<1e-10 for x,y in zip(checked,ci[key]))
        comparisons[a+'_to_'+b] = dict(gains=gains, losses=losses,
            changed_traces=sum(x['trace'] != y['trace'] for x,y in pairs),
            day2_transitions=Counter(x['exile_roles'].get(2,'none')+'_to_'+y['exile_roles'].get(2,'none')
                                     for x,y in pairs), precision=ci)
    transitions = Counter()
    for a,b in zip(arms['old_base'], arms['copy_base'], strict=True):
        for player in a['day2_matches'].keys() | b['day2_matches'].keys():
            x = a['day2_matches'].get(player, 'out_of_scope')
            y = b['day2_matches'].get(player, 'out_of_scope')
            transitions[x+'_to_'+y] += 1
    return dict(n=n, arms=totals, comparisons=comparisons, day2_match_transitions=transitions)


def case_indices(arms):
    loss = next((i for i,(a,b) in enumerate(zip(arms['old_base'], arms['copy_base']))
                 if any(v == 'police' and b['day2_matches'].get(p) != 'police'
                        for p,v in a['day2_matches'].items())), None)
    fake = next((i for i,b in enumerate(arms['copy_agreement'])
                 if b['counts'].get('actual_change_mafia')), None)
    return {'lost_unique_police': loss, 'changed_by_unique_mafia': fake}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    smoke = parser.parse_args().smoke
    config = json.loads(CONFIG.read_text())
    spec = load_spec(config)
    out = ROOT / ('results/v43_smoke' if smoke else 'results/v43')
    out.mkdir()
    parent = ROOT / config['parent_freeze']
    ancestor = ROOT / config['ancestor_freeze']
    parent_data = json.loads(parent.read_text())
    assert parent_data['parent_sha256'] == digest(ancestor)
    for freeze in (parent, ancestor):
        for rel, expected in json.loads(freeze.read_text())['assets'].items():
            assert digest(ROOT/rel) == digest(freeze.parent/'source'/rel) == expected
    assets = [CONFIG, Path(__file__).resolve(), ROOT/'mafia_lab/succession_copy_v43.py',
              ROOT/'tests/test_succession_copy_v43.py', ROOT/'docs/succession_copy_protocol_v43.md']
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in assets}
    if not smoke:
        for rel in hashes:
            target = out/'source'/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/rel, target)
    save_json(out/'freeze.json', dict(config=config, assets=hashes,
        parents={str(p.relative_to(ROOT)):digest(p) for p in (parent, ancestor)},
        python=platform.python_version()))
    start = time.monotonic()
    batch = config['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'], batch['seed_start']+batch['n'])
    with ProcessPoolExecutor(max_workers=4) as pool:
        arms = dict(pool.map(job, ((arm,spec,config['q'],setup,seeds)
                                   for arm,setup in config['arms'].items())))
    results = summary(arms)
    cases = {}
    sampled = 0
    if not smoke:
        for arm, setup in config['arms'].items():
            for index in (0,len(seeds)//2,len(seeds)-1):
                row = arms[arm][index]
                assert play(spec,config['q'],setup,row['seed']) == row
                sampled += 1
        for name, index in case_indices(arms).items():
            if index is None:
                continue
            cases[name] = {}
            for arm,setup in config['arms'].items():
                row = arms[arm][index]
                detail = play(spec,config['q'],setup,row['seed'],True)
                assert detail['trace'] == row['trace']
                cases[name][arm] = detail
        assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in hashes.items())
    save_gzip(out/'pairs.json.gz',arms)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',results)
    save_json(out/'manifest.json',dict(games=len(seeds)*len(arms),elapsed=time.monotonic()-start,
        sampled_replays=sampled, case_replays=sum(len(c) for c in cases.values()),
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print({k:v['wins'] for k,v in results['arms'].items()}, flush=True)


if __name__ == '__main__':
    main()
