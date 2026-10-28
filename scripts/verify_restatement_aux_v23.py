#!/usr/bin/env python3
"""Independent bookkeeping and rational cross-checks of auxiliary diagnostics."""
import json,sys,random
from pathlib import Path
from hashlib import sha256
from collections import Counter
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v23'
sys.path.insert(0,str(folder/'source'))
from mafia_lab.position_repair_experiment_v14 import _solution
from mafia_lab.restatement_experiment_v23 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab import strategies_v23 as d
coverage=json.loads((ROOT/'results/v23_repair_coverage.json').read_text());aggregate=Counter()
for b in coverage['blocks']:
    assert sha256((ROOT/b['source_file']).read_bytes()).hexdigest()==b['source_sha256']
    assert sum(b['groups'].values())==b['n'];aggregate.update(b['groups'])
assert dict(aggregate)==coverage['aggregate'] and sum(aggregate.values())==coverage['pairs']
f=json.loads((folder/'freeze.json').read_text());train=json.loads((folder/'train.json').read_text())
rules,gs,ms=build_spec(f['config']);g=next(g for g in gs if g.name=='repair_q50');mm={m.name:m for m in ms}
lookup={(c['good'],c['mafia']):c for c in train['cells']}
sens=json.loads((ROOT/'results/v23_q_sensitivity.json').read_text())
assert sens['script_sha256']==sha256((ROOT/'scripts/bootstrap_local_q_v23.py').read_bytes()).hexdigest()
assert sens['optimal_set_includes_zero']==sum(Fraction(r['optimal_q_low'])==0 for r in sens['raw'])
assert sens['optimal_set_includes_one']==sum(Fraction(r['optimal_q_high'])==1 for r in sens['raw'])
assert sens['uniquely_interior']==sum(0<Fraction(r['optimal_q_low'])==Fraction(r['optimal_q_high'])<1 for r in sens['raw'])
rng=random.Random(sens['bootstrap_seed']);n=sens['training_n'];cols=list(mm)
for i in range(10):
    weights=Counter(rng.randrange(n) for _ in range(n))
    matrix=[[Fraction(sum(lookup[gn,m]['raw']['win'][index]*weight for index,weight in weights.items()),n) for m in cols] for gn in ('repair_q0','repair_q100')]
    cert=_solution(matrix,['q0','q1'],cols);row=sens['raw'][i]
    assert cert['value_exact']==row['value']
    q=Fraction(cert['good_mixture'].get('q1','0'))
    assert Fraction(row['optimal_q_low'])<=q<=Fraction(row['optimal_q_high'])
diag=json.loads((ROOT/'results/v23_restatement_diagnostic.json').read_text())
assert diag['script_sha256']==sha256((ROOT/'scripts/diagnose_restatement_v23.py').read_bytes()).hexdigest()
example_replays=0
for row in diag['rows']:
    c=lookup[g.name,row['base']+'_restate']
    assert row['executed_games']==sum(c['raw']['repeat_game'])
    assert row['action_chain_changed']+row['action_chain_unchanged']==row['executed_games']
    for ex in row['examples'].values():
        for mode in ('quiet','restate'):
            s=opening(rules,g,mm[row['base']+'_'+mode],ex['seed'],d)
            o=continue_game(s,g,mm[row['base']+'_'+mode],ex['seed'],trace=True,decision_api=d,public_ballots=True)
            assert sha256(repr(o.transcript).encode()).hexdigest()==ex[mode]['trace_hash'];example_replays+=1
result=dict(status='pass',coverage_pairs=coverage['pairs'],bootstrap_replicates_bookkept=500,independent_rational_bootstrap_checks=10,
    training_diagnostic_instrumented_replays=sum(row['paired_full_replays'] for row in diag['rows']),independent_example_full_replays=example_replays,
    scope='Auxiliary post-train/old-data diagnostics only; no added independent performance evidence or new q selection.')
(ROOT/'results/v23_aux_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
