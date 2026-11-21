"""Verify archived outcomes and check what generated the public-signal gains."""
from collections import Counter
import gzip
import json

from run_returning_sources_v47 import CONTRASTS, ROOT, digest, save_json, summarize


def verify(out):
    manifest = json.loads((out/'manifest.json').read_text())
    freeze = json.loads((out/'freeze.json').read_text())
    assert all(digest(out/k)==v for k,v in manifest['files'].items())
    assert all(digest(ROOT/k)==digest(out/'source'/k)==v for k,v in freeze['assets'].items())
    assert all(digest(ROOT/k)==v for k,v in freeze['parents'].items())
    with gzip.open(out/'pairs.json.gz','rt') as handle:
        rows = json.load(handle)
    assert len(rows)==manifest['qualified']
    assert len(rows)*len(freeze['config']['arms'])==manifest['games']
    assert summarize(rows)==json.loads((out/'summary.json').read_text())
    with gzip.open(out/'cases.json.gz','rt') as handle:
        cases = json.load(handle)
    archived = {next(iter(row.values()))['seed']:row for row in rows}
    sample_spec = freeze['config']['smoke' if out.name.endswith('smoke') else 'holdout']
    assert list(archived)==sorted(archived) and len(archived)==len(rows)
    assert all(sample_spec['seed_start']<=s<sample_spec['seed_start']+sample_spec['n'] for s in archived)
    examples = {}
    for name, rich in cases.items():
        examples[name] = {}
        for arm, game in rich.items():
            assert all(game[k]==v for k,v in archived[game['seed']][arm].items())
            examples[name][arm] = dict(seed=game['seed'],win=game['win'],exile=game['exile'],
                                       exile_role=game['exile_role'])
    deltas = {}
    for a,b in CONTRASTS:
        transitions = Counter()
        ballot_games = Counter()
        changed_traces = 0
        for row in rows:
            x,y = row[a],row[b]
            changed_traces += x['trace']!=y['trace']
            transitions[x['exile_role']+'→'+y['exile_role']] += 1
            for key in ('qualified','preferred_police','preferred_mafia','fresh_1','fresh_2'):
                if x['counts'].get(key):
                    ballot_games[key]+=1
        deltas[a] = dict(exile_transitions=transitions, games_with_comparable_ballots=ballot_games,
                         changed_traces=changed_traces)
    return dict(manifest=manifest, contrasts=deltas, examples=examples)


if __name__ == '__main__':
    formal = verify(ROOT/'results/v47')
    smoke = verify(ROOT/'results/v47_smoke')
    result = dict(formal=formal,smoke=smoke)
    save_json(ROOT/'results/v47_verification.json',result)
    print(json.dumps(formal,ensure_ascii=False,indent=2))
