#!/usr/bin/env python3
"""Classify target-mechanism repair separately from terminal game success."""
import json
from pathlib import Path
from collections import Counter
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
blocks=[]
for phase in ('evaluation_A','replication_B'):
    p=ROOT/f'results/v22/{phase}.json';report=json.loads(p.read_text())
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    for m in ('late_near','late_far','decoy_near','decoy_far'):
        a,b=lookup['legacy',m],lookup['both',m];groups=Counter()
        old_mechanism=[bool(x or y) for x,y in zip(a['raw']['orphan_conflict_ballots'],a['raw']['stale_dead_advice_selected_ballots'])]
        new_mechanism=[bool(x or y) for x,y in zip(b['raw']['orphan_conflict_ballots'],b['raw']['stale_dead_advice_selected_ballots'])]
        for i,(before,after) in enumerate(zip(old_mechanism,new_mechanism)):
            if after:groups['target_mechanism_remains']+=1
            elif before:groups['old_path_removed_'+('win' if b['raw']['win'][i] else 'loss')]+=1
            else:groups['no_old_target_path_'+('win' if b['raw']['win'][i] else 'loss')]+=1
        assert sum(groups.values())==a['n']
        blocks.append(dict(phase=phase,mafia=m,n=a['n'],groups=dict(groups),
            source_file=str(p.relative_to(ROOT)),source_sha256=sha256(p.read_bytes()).hexdigest()))
# Prespecified third old regression: preserve the actual before/after mechanism.
r=json.loads((ROOT/'results/v22_regression_examples.json').read_text())
case=next(e for e in r['examples'] if e['seed']==163000001)['runs']['both']
rows=[]
for day in sorted({v['observation']['day'] for v in case['votes']}):
    actual=next((e['payload']['victim'] for e in case['transcript'] if e['day']==day and e['event']=='day_death'),None)
    checks=[n['target'] for n in case['nights'] if n['night']==day and n['kind']=='inspection']
    deaths=[e['payload']['victim'] for e in case['transcript'] if e['day']==day and e['event']=='night_death']
    rows.append(dict(day=day,checked=checks,night_deaths=deaths,day_exile=actual,
        day_exile_role=case['roles_evaluation_only'][actual] if actual is not None else None,
        police_votes=[dict(player=v['observation']['player'],target=v['decision']['target'],known_bad=v['decision']['known_bad']) for v in case['votes'] if v['observation']['day']==day and v['observation']['role']=='police']))
aggregate=Counter()
for b in blocks:aggregate.update(b['groups'])
result=dict(scope='Posthoc read-only coverage audit of all v22 paired records; repeated seeds across mafia columns, not new independent data. Flags identify target paths, not every irrational move or a causal mediator.',
    blocks=blocks,aggregate=dict(aggregate),pairs=sum(b['n'] for b in blocks),
    third_regression=dict(seed=163000001,roles_evaluation_only=case['roles_evaluation_only'],win=case['win'],days=rows,
        final_night=[n for n in case['nights'] if n['kind']=='kill'][-1],
        interpretation='Target bug removed; one civilian day-exile spent tempo, three mafia exiled before fourth police was killed. Other strategies may improve this, but present loss is not evidence of surviving orphan-conflict bug.'))
(ROOT/'results/v23_repair_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(pairs=result['pairs'],groups=result['aggregate']),ensure_ascii=False))
