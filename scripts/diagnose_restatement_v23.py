#!/usr/bin/env python3
"""Train-only full-action diagnosis of all q50 restatement execution cases."""
import sys,json
from pathlib import Path
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v23'
sys.path.insert(0,str(folder/'source'))
from mafia_lab.restatement_experiment_v23 import build_spec,simulate


def action_trace(result):
    return [e for e in result['transcript'] if e['event'] in {'votes','pk_votes','night_death','day_death','terminal'}]


def diagnose(job):
    rules,g,quiet,restate,start,indices,quietwins,restwins=job
    changed=unchanged=0;examples={}
    for i in indices:
        seed=start+i;a=simulate(rules,g,quiet,seed,True);b=simulate(rules,g,restate,seed,True)
        assert a['raw']['win']==quietwins[i] and b['raw']['win']==restwins[i]
        assert b['raw']['repeat_count']>0
        same=action_trace(a)==action_trace(b)
        if same:unchanged+=1
        else:changed+=1
        kind='same_actions' if same else 'changed_actions'
        if kind not in examples:examples[kind]=dict(seed=seed,quiet=a,restate=b)
    return dict(base=restate.name.removesuffix('_restate'),executed_games=len(indices),action_chain_changed=changed,
        action_chain_unchanged=unchanged,paired_full_replays=2*len(indices),examples=examples)

if __name__=='__main__':
    f=json.loads((folder/'freeze.json').read_text());r,gs,ms=build_spec(f['config']);g=next(g for g in gs if g.name=='repair_q50');mm={m.name:m for m in ms}
    train=json.loads((folder/'train.json').read_text());lookup={(c['good'],c['mafia']):c for c in train['cells']}
    jobs=[]
    for base in ('late_near','late_far','decoy_near','decoy_far'):
        a,b=lookup[g.name,base+'_quiet'],lookup[g.name,base+'_restate']
        indices=[i for i,v in enumerate(b['raw']['repeat_game']) if v]
        jobs.append((r,g,mm[base+'_quiet'],mm[base+'_restate'],f['config']['train']['seed_start'],indices,a['raw']['win'],b['raw']['win']))
    with ProcessPoolExecutor(max_workers=4) as pool:rows=list(pool.map(diagnose,jobs))
    result=dict(scope='Post-train diagnostic planned before reading holdout. All executed q50 training cases replayed, not new independent evidence. First action-changed / unchanged seed examples, not outcome selection.',
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),rows=rows)
    (ROOT/'results/v23_restatement_diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([dict(base=r['base'],executed=r['executed_games'],changed=r['action_chain_changed'],unchanged=r['action_chain_unchanged']) for r in rows]))
