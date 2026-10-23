#!/usr/bin/env python3
"""Existing holdout coverage checks and posthoc explanatory replays only."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'results/v18/source'))
from mafia_lab.police_response_experiment_v18 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab import strategies_v18 as decisions
from mafia_lab.statistics import paired_summary

def main():
    folder=ROOT/'results/v18'
    h=json.loads((folder/'holdout.json').read_text())
    lookup={(c['good'],c['mafia']):c for c in h['cells']}
    quiet_checks=[]
    for column in h['matrix']['mafia']:
        if column.endswith('_quiet'):
            for left,right in [('fixed_keep','fixed_answer'),('logical_keep','logical_answer'),('logical_keep','logical_self')]:
                assert lookup[left,column]['raw']==lookup[right,column]['raw']
                quiet_checks.append({'mafia':column,'left':left,'right':right,'all_metrics_identical':True})
    checks=[]
    for column in h['matrix']['mafia']:
        for row in ('fixed_answer','logical_answer'):
            c=lookup[row,column]
            assert c['raw']['response_opportunity']==c['raw']['police_response_day1']
            checks.append({'good':row,'mafia':column,'n':c['n'],
                           'opportunities':sum(c['raw']['response_opportunity']),
                           'responses':sum(c['raw']['police_response_day1'])})
    rules,good,mafia,cal=build_spec(json.loads((folder/'source/config.json').read_text()))
    gm,mm={g.name:g for g in good},{m.name:m for m in mafia}
    traces=[]
    # Select first improved/worsened existing paired examples. These are not
    # representative samples or new inferential validation data.
    for column in ('safe_late_early','safe_late_counter'):
        a,b=lookup['logical_keep',column],lookup['logical_answer',column]
        for sign in (1,-1):
            indices=[i for i,(x,y) in enumerate(zip(a['raw']['win'],b['raw']['win']))
                     if y-x==sign and a['raw']['response_opportunity'][i]]
            if not indices:continue
            seed=a['seed_start']+indices[0]
            for row in ('logical_keep','logical_answer'):
                initial=opening(rules,gm[row],mm[column],seed,decisions)
                out=continue_game(initial,gm[row],mm[column],seed,trace=True,
                                  decision_api=decisions,public_ballots=True)
                assert out.good_win==lookup[row,column]['raw']['win'][indices[0]]
                traces.append({'good':row,'mafia':column,'seed':seed,'paired_delta':sign,
                    'win':out.good_win,'roles_offline_only':[r.value for r in initial.roles],
                    'transcript':out.transcript})
    diagnostics=[]
    for column in ('safe_late_early','posterior_decoy_early'):
        a,b=lookup['logical_keep',column],lookup['logical_answer',column]
        masks={'alive_and_opportunity':[bool(x and y) for x,y in zip(a['raw']['leader_eligible'],a['raw']['response_opportunity'])],
               'first_dead_police':[not x for x in a['raw']['leader_eligible']]}
        for branch,mask in masks.items():
            av=[x for x,k in zip(a['raw']['win'],mask) if k]
            bv=[x for x,k in zip(b['raw']['win'],mask) if k]
            diagnostics.append({'mafia':column,'branch':branch,'win':paired_summary(av,bv)})
    examples=[]
    for verdict in (False,True):
        values=decisions._claim_marginals(16,4,4,15,(0,),((0,1,verdict),))
        examples.append({'A':0,'B':1,'observer':15,'verdict_mafia':verdict,
                         'A_mafia_exact':str(values[0]),'B_mafia_exact':str(values[1])})
    result={'branch_diagnostics_posthoc':diagnostics,'single_claim_reference_examples':examples,'status':'pass' ,'coverage_checks':checks,'no_false_claim_invariance':quiet_checks,'explanatory_replays':traces,
            'scope':'Posthoc existing-holdout diagnostic; selection of outcome examples is explanatory, not independent evidence.'}
    (ROOT/'results/v18_mechanism_diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'coverage_cells':len(checks),'explanatory_replays':len(traces),'status':'pass'}))
if __name__=='__main__':main()
