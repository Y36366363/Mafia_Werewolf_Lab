"""Recompute the frozen evaluation, flow and winner changes from its raw files."""
from collections import Counter
import gzip
import json

from run_adaptive_counter_v49 import CONTRASTS, ROOT, digest, load_spec, play, save_gzip, save_json, summarize
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


def read_gzip(path):
    with gzip.open(path,'rt') as handle:
        return json.load(handle)


def verify(out):
    manifest = json.loads((out/'manifest.json').read_text())
    freeze = json.loads((out/'freeze.json').read_text())
    cfg = freeze['config']
    assert all(digest(out/name)==value for name,value in manifest['files'].items())
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==value for rel,value in freeze['assets'].items())
    assert all(digest(ROOT/rel)==value for rel,value in freeze['parents'].items())
    flow = read_gzip(out/'screen.json.gz')
    pairs = read_gzip(out/'pairs.json.gz')
    summary = summarize(pairs,flow)
    assert summary==json.loads((out/'summary.json').read_text())
    span = cfg['smoke' if out.name.endswith('smoke') else 'holdout']
    assert [r['seed'] for r in flow]==list(range(span['seed_start'],span['seed_start']+span['n']))
    index = {g['original_neutral']['seed']:g for g in pairs}
    assert len(pairs)==len(index)==manifest['qualified']
    assert set(index)=={r['seed'] for r in flow if r['baseline'] and r['baseline']==r['revised']}
    assert manifest['games']==len(index)*len(cfg['arms'])
    examples = {}
    for name,case in read_gzip(out/'cases.json.gz').items():
        for arm,row in case.items():
            assert all(row[key]==value for key,value in index[row['seed']][arm].items())
            examples.setdefault(name,{})[arm] = dict(seed=row['seed'],win=row['win'],
                exits=row['exiles'],roles=row['exile_roles'])

    strata = {}
    for a,b in CONTRASTS[:2]:
        both = Counter()
        for group in pairs:
            earlier,later = group[a],group[b]
            response = bool(group['counter_neutral']['counts']['counter_ballot'])
            changed = earlier['votes'] != later['votes']
            both[('counter_available' if response else 'no_counter')+'_n'] += 1
            both[('counter_available' if response else 'no_counter')
                 +f"_win_{earlier['win']}→{later['win']}"] += 1
            both[('counter_available' if response else 'no_counter')+'_changed_day2'] += changed
        strata[b] = both

    support = Counter()
    backed = []
    for group in pairs:
        row = group['counter_neutral']
        alt = row['alternative']
        if alt is not None:
            support[f"{len(alt['voters'])} vs {len(alt['rival_voters'])}"] += 1
            backed.append((row['win'],group['counter_backed']['win']))
    conditional = {}
    if backed:
        base,changed = zip(*backed)
        conditional = dict(gains=sum(a<b for a,b in backed),losses=sum(a>b for a,b in backed),
                           descriptive_interval=exact_paired_interval(base,changed,family=1))
    collapse = {}
    if out.name=='v49':
        bridge = next((g for g in pairs if g['original_neutral']['win'] < g['original_evidence']['win']
                       and g['counter_neutral']['trace']==g['counter_evidence']['trace']
                       and g['counter_neutral']['counts'].get('counter_ballot')
                       and g['counter_neutral']['counts'].get('challenged_2')),None)
        if bridge is not None:
            parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
            spec = load_spec(parent)
            for arm in ('original_neutral','original_evidence','counter_neutral','counter_evidence'):
                row = bridge[arm]
                case = play(spec,freeze['q'],cfg['arms'][arm],row['seed'],tuple(row['pair']),True)
                normalized = json.loads(json.dumps(case))
                assert all(normalized[key]==value for key,value in row.items())
                collapse[arm] = case
            target = out/'evidence_counter_case.json.gz'
            save_gzip(target,collapse)
            collapse = dict(seed=next(iter(collapse.values()))['seed'],sha256=digest(target),replays=4)
    return dict(manifest=manifest, examples=examples, evidence_strata=strata, evidence_counter_case=collapse,
                backed_prior_support=support, backed_conditional=conditional)


if __name__=='__main__':
    result = dict(formal=verify(ROOT/'results/v49'),smoke=verify(ROOT/'results/v49_smoke'))
    save_json(ROOT/'results/v49_verification.json',result)
    print(json.dumps(result['formal'],ensure_ascii=False,indent=2))
