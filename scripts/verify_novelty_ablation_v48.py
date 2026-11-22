"""Recompute paired effects and diagnostic coverage from the archived records."""
from collections import Counter
import gzip
import json

from run_novelty_ablation_v48 import CONTRASTS, ROOT, digest, save_json, summarize


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
    pairs = read_gzip(out/'pairs.json.gz')
    assert summarize(pairs,cfg)==json.loads((out/'summary.json').read_text())
    assert manifest['games']==len(pairs)*len(cfg['opponents'])*len(cfg['receivers'])
    indexed = {p[cfg['opponents'][0]]['novelty']['seed']:p for p in pairs}
    span = cfg['smoke' if out.name.endswith('smoke') else 'holdout']
    assert len(indexed)==len(pairs)==manifest['qualified']
    assert list(indexed)==sorted(indexed)
    assert all(span['seed_start']<=seed<span['seed_start']+span['n'] for seed in indexed)
    examples = {}
    for key,case in read_gzip(out/'cases.json.gz').items():
        opp = key.split('_',1)[0]
        for receiver,row in case.items():
            archived = indexed[row['seed']][opp][receiver]
            assert all(row[k]==v for k,v in archived.items())
            examples.setdefault(key,{})[receiver] = dict(seed=row['seed'],win=row['win'],
                exiles=row['exits'],roles=row['exit_roles'])
    coverage = {}
    for opp in cfg['opponents']:
        support = Counter()
        changes = Counter()
        for pair in pairs:
            rows = pair[opp]
            c = rows['neutral']['counts']
            for key,n in c.items():
                if n and key.startswith(('novel_','supported_','challenge_would_change_','eligible','num_challenged_')):
                    support[key] += 1
            for before,after in CONTRASTS:
                first,second = rows[before],rows[after]
                if first['votes'] != second['votes']:
                    changes[before+'→'+after+'_'+str(first['win'])+'→'+str(second['win'])] += 1
        coverage[opp] = dict(games_with_signal=support,changed_game_win_transitions=changes)
    return dict(manifest=manifest,coverage=coverage,examples=examples)


if __name__=='__main__':
    result = dict(formal=verify(ROOT/'results/v48'),smoke=verify(ROOT/'results/v48_smoke'))
    save_json(ROOT/'results/v48_verification.json',result)
    print(json.dumps(result['formal'],ensure_ascii=False,indent=2))
