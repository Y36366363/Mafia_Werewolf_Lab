"""Recompute v50 summaries, selected histories, and frozen archive hashes."""
from collections import Counter
import gzip
import json

from run_response_cost_v50 import PACES, ROOT, digest, save_json, summarize
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


def read_gzip(path):
    with gzip.open(path,'rt') as handle:
        return json.load(handle)


def verify(out):
    manifest = json.loads((out/'manifest.json').read_text())
    freeze = json.loads((out/'freeze.json').read_text())
    cfg = freeze['config']
    assert all(digest(out/name)==h for name,h in manifest['files'].items())
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in freeze['assets'].items())
    assert all(digest(ROOT/rel)==h for rel,h in freeze['parents'].items())
    pairs = read_gzip(out/'pairs.json.gz')
    flow = read_gzip(out/'screen.json.gz')
    assert summarize(pairs,flow)==json.loads((out/'summary.json').read_text())
    span = cfg['smoke' if out.name.endswith('smoke') else 'holdout']
    assert [r['seed'] for r in flow]==list(range(span['seed_start'],span['seed_start']+span['n']))
    index = {g['original_neutral']['seed']:g for g in pairs}
    assert len(index)==len(pairs)==manifest['qualified']
    assert set(index)=={r['seed'] for r in flow if r['original'] and all(r[p]==r['original'] for p in PACES)}
    assert manifest['games']==len(pairs)*len(cfg['arms'])
    examples = {}
    for name,case in read_gzip(out/'cases.json.gz').items():
        examples[name] = {}
        for arm,row in case.items():
            assert all(row[k]==v for k,v in index[row['seed']][arm].items())
            examples[name][arm] = {k:row[k] for k in ('seed','win','call','exit','role','alternative','counts')}
    activated = [(g['protected_neutral'],g['protected_current']) for g in pairs
                 if g['protected_neutral']['alternative'] is not None]
    opportunity = dict(n=len(activated), prior_speech=Counter(), recorded_supporters=0,
                       supporter_commitments=[0,0])
    for x,y in activated:
        alt = x['alternative']
        opportunity['prior_speech'][f"{len(alt['voters'])} vs {len(alt['rival_voters'])}"] += 1
        opportunity['recorded_supporters'] += len(alt['voters'])
        for i,r in enumerate((x,y)):
            opportunity['supporter_commitments'][i] += sum(r['votes'][str(p)]==alt['target'] for p in alt['voters'])
    if activated:
        before,after = zip(*((x['win'],y['win']) for x,y in activated))
        opportunity['gains'] = sum(x<y for x,y in zip(before,after,strict=True))
        opportunity['losses'] = sum(x>y for x,y in zip(before,after,strict=True))
        opportunity['descriptive_interval'] = exact_paired_interval(before,after,family=1)
    protection = {}
    for receiver in ('neutral','evidence'):
        rows = [(g['always_'+receiver],g['protected_'+receiver]) for g in pairs]
        protection[receiver] = dict(changed_wins=sum(a['win']!=b['win'] for a,b in rows),
                                    changed_traces=sum(a['trace']!=b['trace'] for a,b in rows))
    return dict(manifest=manifest,examples=examples,current_support=opportunity,protection=protection)


if __name__=='__main__':
    result = dict(formal=verify(ROOT/'results/v50'),smoke=verify(ROOT/'results/v50_smoke'))
    save_json(ROOT/'results/v50_verification.json',result)
    print(json.dumps(result['formal'],ensure_ascii=False,indent=2))
