#!/usr/bin/env python3
"""Independent bookkeeping for the audit, chosen scope and example selection."""
import json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
def hashfile(p):return sha256((ROOT/p).read_bytes()).hexdigest()
x=load('results/v25_source_audit.json');old=load('results/v24/holdout.json');lookup={(c['good'],c['mafia']):c for c in old['cells']}
assert x['source_freeze_sha256']==hashfile('results/v24/freeze.json') and x['source_holdout_sha256']==hashfile('results/v24/holdout.json')
assert len(x['rows'])==8
for r in x['rows']:
    assert r['n']==512 and r['seed_start']==174000000 and len(r['raw'])==512
    a=lookup['repair_q50',r['base']+'_'+r['mode']]
    for i,row in enumerate(r['raw']):assert row['seed']==174000000+i and row['win']==a['raw']['win'][i]
    for flag in ('dilution','police_report_vote_mismatch'):
        assert r['counts'][flag+'_games']==sum(bool(v[flag]) for v in r['raw'])
    assert r['counts']['police_report_vote_mismatch_ballots']==r['counts']['mismatch_both_known_bad_ballots']
    co=r['vote_cohorts'];assert co['voters']==co['good_voters']+co['mafia_voters'] and co['zero_mafia_groups']<=co['groups']
decision=load('results/v25_ablation_decision.json');assert decision['audit_sha256']==hashfile('results/v25_source_audit.json') and decision['new_experiment_output_absent']
plan=load('results/v25_diagnostic_before_holdout.json');assert plan['holdout_file_exists'] is False
for path,h in plan['files'].items():assert hashfile(path)==h
held=load('results/v25/holdout.json');lookup={(c['good'],c['mafia']):c for c in held['cells']};ex=load('results/v25_examples.json');assert ex['held_sha256']==hashfile('results/v25/holdout.json')
count=0
for row in ex['rows']:
    a,b=lookup['base_q50',row['base']+'_claim'],lookup['gate_q50',row['base']+'_claim']
    cat=row['category']
    def eligible(i):
        x,y=a['raw']['win'][i],b['raw']['win'][i]
        return (not x and y) if cat=='gain' else (x and not y) if cat=='loss' else (not x and not y and b['raw']['blocked_advice_game'][i])
    i=next((j for j in range(a['n']) if eligible(j)),None)
    if i is None:assert row['status']=='no_case';continue
    assert row['index']==i and row['seed']==a['seed_start']+i
    for gn,run in row['runs'].items():
        c=lookup[gn,row['base']+'_claim']
        for k,v in run['raw'].items():assert v==c['raw'][k][i]
        count+=1
assert count==ex['detailed_replays']==ex['unwrapped_replays']
out=dict(status='pass',archived_unique_episodes=4096,old_audit_passes=2,old_audit_replay_runs=8192,
         paired_raw_labels_checked=4096,examples_checked=count,scope='Independent bookkeeping; does not newly rerun all old or new trajectories.')
(ROOT/'results/v25_aux_integrity_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
