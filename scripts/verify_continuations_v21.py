#!/usr/bin/env python3
import sys,json,importlib.util
from pathlib import Path
from hashlib import sha256
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'results/v21_verified'
f=json.loads((out/'freeze.json').read_text());manifest=json.loads((out/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((out/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((out/n).read_bytes()).hexdigest()==h
assert sha256((ROOT/'results/v20b/freeze.json').read_bytes()).hexdigest()==f['archive_freeze_sha256']
oldfreeze=json.loads((ROOT/'results/v20b/freeze.json').read_text())
for n,h in oldfreeze['assets'].items():assert sha256((ROOT/'results/v20b'/n).read_bytes()).hexdigest()==h
sys.path.insert(0,str(ROOT/'results/v20b/source'))
from mafia_lab import strategies_v20 as original,strategies_v20b as corrected
from mafia_lab.evidence_experiment_v20 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.reply_evaluation_v19 import metrics
rules,gs,ms=build_spec(oldfreeze['config']);g=next(p for p in gs if p.name=='evidence_q50');mm={m.name:m for m in ms}
data=json.loads((out/'audit.json').read_text());examples=json.loads((out/'examples.json').read_text());replays=0
old=json.loads((ROOT/'results/v20b/probe.json').read_text());oldmap={(c['mode'],c['mafia']):c for c in old['cells']}
for block in data['blocks']:
    assert len(block['pairs'])==block['n']
    transitions=Counter()
    for pair in block['pairs']:
        transitions[f"{pair['old_exile']}->{pair['new_exile']};{pair['old_win']}->{pair['new_win']}"]+=1
        if block['phase']=='historical_replay':
            i=pair['seed']-block['seed_start']
            assert pair['old_win']==oldmap['original',block['mafia']]['raw']['win'][i]
            assert pair['new_win']==oldmap['corrected',block['mafia']]['raw']['win'][i]
    assert dict(transitions)==block['transitions']
    for mode,prefix in [('original','old'),('corrected','new')]:
        counts=Counter();flags=Counter()
        for pair in block['pairs']:
            counts.update(pair[prefix+'_counts']);flags.update({k:int(v) for k,v in pair[prefix+'_flags'].items()})
        assert dict(counts)==block['totals'][mode] and dict(flags)==block['game_flags'][mode]
    for i in sorted({0,block['n']//2,block['n']-1}):
        pair=block['pairs'][i];seed=pair['seed']
        for mode,prefix,api in [('original','old',original),('corrected','new',corrected)]:
            s=opening(rules,g,mm[block['mafia']],seed,api)
            o=continue_game(s,g,mm[block['mafia']],seed,trace=True,decision_api=api,public_ballots=True)
            assert sha256(repr(o.transcript).encode()).hexdigest()==pair[prefix+'_trace_hash']
            assert o.good_win==pair[prefix+'_win'];replays+=1
for ex in examples['examples']:
    block=next(b for b in data['blocks'] if b['phase']=='historical_replay' and b['mafia']==ex['mafia'])
    assert block['example_seeds'][ex['kind']]==ex['seed']
    pair=block['pairs'][ex['seed']-block['seed_start']]
    for mode,prefix in [('original','old'),('corrected','new')]:
        detail=ex[mode]
        # JSON transport converts transcript tuples into lists; compare the
        # stored hash with aggregate replay, not repr of transported arrays.
        assert detail['trace_hash']==pair[prefix+'_trace_hash']
        for v in detail['votes']:
            assert v['observation']['player']==v['player']
            assert v['observation']['role']==v['role']
            assert v['target'] is None or v['target'] in v['legal']
result=dict(status='pass',historical_full_replays=sum(b['old_outcomes_checked'] for b in data['blocks']),
    fresh_games=sum(b['replays'] for b in data['blocks'] if b['phase']=='fresh_audit'),
    sampled_uninstrumented_full_replays=replays,blocks_checked=len(data['blocks']),examples_checked=len(examples['examples']),
    scope='All historical raw metrics checked in instrumented run; independent uninstrumented trace samples and aggregate arithmetic verified. Explanatory audit, not strategy optimization.')
(ROOT/'results/v21_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
