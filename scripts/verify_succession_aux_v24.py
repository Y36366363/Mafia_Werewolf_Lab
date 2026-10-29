#!/usr/bin/env python3
"""Independently verify v24 auxiliary bookkeeping without replaying simulations.

This verifies archived claims, hashes and exact-binomial calculations. Recorded
timestamps are provenance records, not an independent proof of wall-clock order.
"""
import json
from datetime import datetime
from hashlib import sha256
from math import isclose
from pathlib import Path

import scipy
from scipy.stats import binom, binomtest


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'results/v24'
BASES = ('late_near', 'late_far', 'decoy_near', 'decoy_far')
MODES = ('quiet', 'restate', 'support', 'claim')
CATEGORIES = ('baseline_win_to_loss', 'baseline_loss_to_win',
              'executed_and_baseline_win_retained')
TAIL_ALPHA = .05 / (4 * 2 * 2)


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def close(a, b):
    assert isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), (a, b)


def verify_binomial_interval(k, n, recorded):
    """Use a separate high-level exact inversion, then check binomial tails."""
    assert 0 <= k <= n and n > 0
    expected = binomtest(k, n).proportion_ci(
        confidence_level=1 - 2 * TAIL_ALPHA, method='exact')
    assert len(recorded) == 2
    close(recorded[0], expected.low)
    close(recorded[1], expected.high)
    lo, hi = recorded
    assert 0 <= lo <= hi <= 1
    if k == 0:
        assert lo == 0
    else:
        assert abs(binom.sf(k - 1, n, lo) - TAIL_ALPHA) < 1e-9
    if k == n:
        assert hi == 1
    else:
        assert abs(binom.cdf(k, n, hi) - TAIL_ALPHA) < 1e-9


def main():
    record = load(ROOT / 'results/v24_precision_before_holdout.json')
    assert record['holdout_file_exists'] is False
    assert datetime.fromisoformat(record['utc_recorded']).utcoffset() is not None
    recorded_hashes = {
        'train_sha256': FOLDER / 'train.json',
        'method_doc_sha256': ROOT / 'docs/succession_precision_scope_v24.md',
        'script_sha256': ROOT / 'scripts/paired_precision_v24.py',
    }
    for key, path in recorded_hashes.items():
        assert record[key] == digest(path), (key, str(path))

    holdout = load(FOLDER / 'holdout.json')
    lookup = {(c['good'], c['mafia']): c for c in holdout['cells']}
    assert len(lookup) == len(holdout['cells'])
    primary = {c['base']: c for c in holdout['contrasts'] if c['primary']}
    assert set(primary) == set(BASES)
    assert sum(bool(c['primary']) for c in holdout['contrasts']) == 4
    precision = load(ROOT / 'results/v24_paired_precision.json')
    assert precision['input_sha256'] == digest(FOLDER / 'holdout.json')
    close(precision['tail_alpha'], TAIL_ALPHA)
    assert len(precision['rows']) == 4
    precision_rows = {row['base']: row for row in precision['rows']}
    assert set(precision_rows) == set(BASES)
    for base in BASES:
        comparison = primary[base]
        assert (comparison['good'], comparison['control'], comparison['treatment']) == (
            'repair_q50', 'restate', 'claim')
        control = lookup['repair_q50', base + '_restate']
        treatment = lookup['repair_q50', base + '_claim']
        assert (control['n'], control['seed_start']) == (
            treatment['n'], treatment['seed_start'])
        x, y = control['raw']['win'], treatment['raw']['win']
        n = control['n']
        assert len(x) == len(y) == n
        assert set(x + y) <= {0, 1}
        improved = sum(a == 0 and b == 1 for a, b in zip(x, y))
        worsened = sum(a == 1 and b == 0 for a, b in zip(x, y))
        row, win = precision_rows[base], comparison['win']
        for target in (row, win):
            assert (target['n'], target['improved'], target['worsened']) == (
                n, improved, worsened)
            close(target['delta'], (improved - worsened) / n)
        verify_binomial_interval(improved, n, row['p_plus'])
        verify_binomial_interval(worsened, n, row['p_minus'])
        expected = [row['p_plus'][0] - row['p_minus'][1],
                    row['p_plus'][1] - row['p_minus'][0]]
        for a, b in zip(row['simultaneous_ci'], expected):
            close(a, b)
        assert len(row['simultaneous_ci']) == 2

    examples = load(ROOT / 'results/v24_examples.json')
    freeze = load(FOLDER / 'freeze.json')
    input_paths = {
        'v24_freeze': FOLDER / 'freeze.json',
        'v24_holdout': FOLDER / 'holdout.json',
        'v23_reference': ROOT / 'results/v23_restatement_diagnostic.json',
    }
    assert set(examples['input_sha256']) == set(input_paths)
    for key, path in input_paths.items():
        assert examples['input_sha256'][key] == digest(path), key
    assert examples['script_sha256'] == digest(
        ROOT / 'scripts/diagnose_succession_counter_v24.py')
    assert examples['source_assets_checked'] == len(freeze['assets'])
    rows = {(r['base'], r['category']): r for r in examples['selected']}
    assert len(rows) == len(examples['selected']) == len(BASES) * len(CATEGORIES)
    assert set(rows) == {(base, category) for base in BASES for category in CATEGORIES}
    selected_cases = saved_runs = raw_fields_checked = 0
    for base in BASES:
        control = lookup['repair_q50', base + '_restate']
        treatment = lookup['repair_q50', base + '_claim']
        x, y = control['raw']['win'], treatment['raw']['win']
        execution = treatment['raw']['succession_game']
        predicates = {
            'baseline_win_to_loss': lambda i: x[i] == 1 and y[i] == 0,
            'baseline_loss_to_win': lambda i: x[i] == 0 and y[i] == 1,
            'executed_and_baseline_win_retained':
                lambda i: bool(execution[i]) and x[i] == y[i] == 1,
        }
        for category in CATEGORIES:
            row = rows[base, category]
            index = next((i for i in range(control['n']) if predicates[category](i)), None)
            if index is None:
                assert row['seed'] is None and row['status'] == 'no_matching_case'
                assert 'runs' not in row
                continue
            selected_cases += 1
            assert row['status'] == 'replayed'
            assert row['index'] == index
            assert row['seed'] == control['seed_start'] + index
            assert set(row['runs']) == set(row['summaries']) == set(MODES)
            for mode in MODES:
                run, summary = row['runs'][mode], row['summaries'][mode]
                cell = lookup['repair_q50', base + '_' + mode]
                assert run['seed'] == cell['seed_start'] + index == row['seed']
                assert set(run['raw']) == set(cell['raw'])
                for key, values in cell['raw'].items():
                    assert run['raw'][key] == values[index], (base, category, mode, key)
                    raw_fields_checked += 1
                assert summary['win'] == run['raw']['win']
                saved_runs += 1

    historical = examples['historical_restatement']
    assert (historical['seed'], historical['base']) == (169000044, 'late_near')
    reference = load(input_paths['v23_reference'])
    candidates = [ex for row in reference['rows'] if row['base'] == historical['base']
                  for ex in row['examples'].values() if ex['seed'] == historical['seed']]
    assert len(candidates) == 1
    reference_case = candidates[0]
    checks = {c['mode']: c for c in historical['archived_v23_checks']}
    assert len(checks) == len(historical['archived_v23_checks']) == 2
    assert set(checks) == set(historical['runs']) == {'quiet', 'restate'}
    for mode in ('quiet', 'restate'):
        run, old, check = historical['runs'][mode], reference_case[mode], checks[mode]
        assert run['seed'] == historical['seed']
        assert run['trace_hash'] == old['trace_hash'] == check['trace_hash']
        assert check['status'] == 'matches_v23'
        assert run['raw']['win'] == old['raw']['win'] == historical['summaries'][mode]['win']
    assert examples['detailed_replays'] == examples['independently_unwrapped_replays'] == saved_runs + 2

    result = dict(
        status='pass', scipy_version=scipy.__version__,
        precision_record_utc=record['utc_recorded'],
        precision_record_says_holdout_absent=True,
        precision_record_hashes_checked=len(recorded_hashes),
        primary_paired_comparisons_checked=4,
        independently_inverted_binomial_intervals=8,
        family_tail_alpha=TAIL_ALPHA, union_bound_error=16 * TAIL_ALPHA,
        category_slots_checked=len(rows), selected_first_seed_cases=selected_cases,
        archived_case_runs_checked=saved_runs, archived_case_raw_fields_checked=raw_fields_checked,
        archived_v23_hash_matches=2, new_simulations=0, new_full_replays=0,
        input_sha256={
            'precision_record': digest(ROOT / 'results/v24_precision_before_holdout.json'),
            'precision_result': digest(ROOT / 'results/v24_paired_precision.json'),
            'examples': digest(ROOT / 'results/v24_examples.json'),
            'holdout': digest(FOLDER / 'holdout.json'),
        },
        scope='Auxiliary bookkeeping and independent finite-sample interval inversion only. '
              'Uses archived held outcomes; no new performance evidence or strategy selection. '
              'Verifies recorded pre-held provenance claims, not an independent wall-clock proof.',
    )
    destination = ROOT / 'results/v24_aux_integrity_audit.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
