#!/usr/bin/env python3
"""Read-only explanation of preselected cases; no additional simulations."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.restatement_experiment_v23 import save


def explain():
    x=json.loads((ROOT/'results/v28_examples.json').read_text())
    D={(r['good'],r['mafia'],r['seed']):r for r in x['cases']};stories=[]
    for kind in ('loss','same_win_different_process'):
        candidates=sorted([c for c in x['selected'] if c['comparison']=='reference->notice' and c['kind']==kind and c['seed'] is not None],key=lambda c:(c['seed'],c['mafia']))
        for item in candidates:
            key=item['mafia'],item['seed'];ref=D['reference_q50',*key];notice=D['notice_q50',*key]
            pool=next((r['targets'] for r in notice['extensions'] if r['kind']=='shortlist'),[])
            fake_target=ref['raw']['fake_target']
            old={(v['player'],v['round']):v for v in ref['votes'] if v['day']==1}
            changes=[v for v in notice['votes'] if v['day']==1 and v['round']=='first' and v['role']=='civilian'
                     and v['target']==fake_target and v['reason']=='common_recommendation_protocol'
                     and old.get((v['player'],v['round']),{}).get('target')!=fake_target]
            if fake_target not in pool or not changes:continue
            variants={}
            for mode in ('reference','notice','list','evidence'):
                r=D[mode+'_q50',*key];deaths=[e for e in r['transcript'] if e['event']=='day_death']
                first=next((e['payload']['victim'] for e in deaths if e['day']==1),None)
                variants[mode]=dict(win=r['raw']['win'],first_day_exile=None if first is None else first+1,
                    first_day_exile_role=None if first is None else r['roles_evaluation_only'][first],
                    day_exiles=[dict(day=e['day'],seat=e['payload']['victim']+1,role=r['roles_evaluation_only'][e['payload']['victim']]) for e in deaths],
                    gold_call=None if not r['calls'] else dict(target=r['calls'][0]['target']+1,outside=r['calls'][0]['outside'],witness=r['calls'][0]['witness']),
                    first_votes=next((e['payload'] for e in r['transcript'] if e['day']==1 and e['event']=='votes'),{}),
                    night_actions=r['nights'])
            stories.append(dict(kind=kind,seed=item['seed'],mafia=item['mafia'],source=ref['raw']['first_dead']+1,
                gold=ref['raw']['first_check']+1,shortlist=[p+1 for p in pool],fake=ref['raw']['fake_speaker']+1,
                false_hit=fake_target+1,common_recommendation_receivers=[v['player']+1 for v in changes],variants=variants))
            break
    out=dict(posthoc_explanation=True,extra_simulations=0,source='Only the frozen-rule preselected v28_examples.json cases.',
        seat_numbering='Story seats 1-based; raw ballot keys/targets and night_actions remain engine 0-based.',
        stories=stories,limitation='Explains a receiver policy mechanism in selected traces, not proof of a generally optimal priority rule.')
    save(ROOT/'results/v28_case_explanations.json',out)
    print(json.dumps(stories,ensure_ascii=False))


if __name__=='__main__':explain()
