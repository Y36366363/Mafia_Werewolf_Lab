"""Verify v41 archives and replay the 17 historical v40 losses."""

from collections import Counter
from hashlib import sha256
import gzip
import json
from math import isclose

from scipy.stats import binomtest

from run_paired_source_routing_v40 import play as play_v40
from run_succession_channels_v41 import ROOT, digest, load_spec, play, save_gzip, save_json


def load(path):
    with gzip.open(path) as stream:
        return json.load(stream)


def first_ballot_change(control, changed):
    old, new = control['events'], changed['events']
    for left, right in zip(old, new):
        if left != right:
            assert left['day'] == right['day'] and left['event'] == right['event']
            assert left['event'] in {'votes', 'pk_votes'}
            return left, right
    raise AssertionError('Expected a vote divergence')


def main():
    out = ROOT / 'results/v41'
    for folder in (out, ROOT / 'results/v41_smoke'):
        manifest = json.loads((folder / 'manifest.json').read_text())
        freeze = json.loads((folder / 'freeze.json').read_text())
        for path, expected in manifest['files'].items():
            assert digest(folder / path) == expected
        for path, expected in freeze['assets'].items():
            assert digest(ROOT / path) == digest(folder / 'source' / path) == expected

    frozen = json.loads((out / 'freeze.json').read_text())
    cfg = frozen['config']
    spec = load_spec(cfg)
    manifest = json.loads((out / 'manifest.json').read_text())
    archive = load(out / 'pairs.json.gz')
    summary = json.loads((out / 'summary.json').read_text())
    n = summary['n']
    for name, contrast in summary['contrasts'].items():
        a, b = name.split('_to_')
        left, right = archive[a], archive[b]
        confidence = 1 - 2 * contrast['precision']['tail_alpha']
        counts = [sum(x['win'] < y['win'] for x,y in zip(left,right,strict=True)),
                  sum(x['win'] > y['win'] for x,y in zip(left,right,strict=True))]
        assert counts == [contrast['gains'], contrast['losses']]
        for k, direction in zip(counts, ('p_plus', 'p_minus'), strict=True):
            ci = binomtest(k, n).proportion_ci(confidence, method='exact')
            assert all(isclose(x, y, abs_tol=1e-10)
                       for x, y in zip(ci, contrast['precision'][direction], strict=True))
    for arm, rows in archive.items():
        for index in (0, n//2, n-1):
            old = rows[index]
            assert play(spec, cfg['q'], old['seed'], arm) == old
            if arm in {'bare', 'report_both'}:
                mode = 'merge_control' if arm == 'bare' else 'succession_report'
                assert play_v40(spec, cfg['q'], old['seed'], mode)['trace_hash'] == old['trace_hash']

    parent = ROOT / 'results/v40/pairs.json.gz'
    historical = load(parent)
    comparisons = {arm: Counter() for arm in ('source_exile', 'call_mapping')}
    details = []
    for control, source, mapped in zip(*(historical[arm] for arm in ('merge_control','source_exile','call_mapping')), strict=True):
        if not control['win'] or mapped['win']:
            continue
        assert not source['win']
        arms = {}
        for arm, original in zip(('merge_control','source_exile','call_mapping'), (control,source,mapped), strict=True):
            arms[arm] = play_v40(spec, cfg['q'], original['seed'], arm, details=True)
            assert arms[arm]['trace_hash'] == original['trace_hash']
        for arm, counts in comparisons.items():
            a, b = arms['merge_control'], arms[arm]
            old_ballot, new_ballot = first_ballot_change(a, b)
            counts[f"first_change_day_{old_ballot['day']}"] += 1
            counts[f"day2_exile_{a['exiles'].get(2)}_to_{b['exiles'].get(2)}"] += 1
            for voter, old in old_ballot['payload'].items():
                new = new_ballot['payload'][voter]
                if old == new:
                    continue
                roles = a['roles']
                counts[f"voter_{roles[voter]}"] += 1
                old_role = roles[old] if old is not None else 'abstain'
                new_role = roles[new] if new is not None else 'abstain'
                counts[f"vote_{old_role}_to_{new_role}"] += 1
            for day, role in b['exiles'].items():
                counts[f'day{day}_exiled_{role}'] += 1
            for night in b['days'][2:]:
                counts[f"night{night['day']}_death_{b['roles'][night['night_victim']]}"] += 1
            for role in ('police', 'mafia', 'civilian'):
                counts[f"day2_survival_delta_{role}"] += b['days'][1]['end'][role] - a['days'][1]['end'][role]
                counts[f"terminal_survival_total_{role}"] += b['days'][-1]['end'][role]
        details.append(dict(seed=control['seed'], arms=arms))
    assert len(details) == 17
    save_gzip(out / 'v40_losses.json.gz', details)
    trace_changes = {}
    for a, b in (('report_neither', 'report_conflict'), ('report_gate', 'report_both')):
        trace_changes[f'{a}_to_{b}'] = sum(x['trace_hash'] != y['trace_hash']
                                        for x,y in zip(archive[a],archive[b],strict=True))
    result = dict(trace_changes=trace_changes, historical_pairs=len(details), comparisons=comparisons, full_historical_replays=51,
                  sampled_new_replays=15, inherited_api_replays=6, interval_checks=10,
                  assets=len(frozen['assets']), historical_input_sha256=digest(parent))
    save_json(ROOT / 'results/v41_validation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
