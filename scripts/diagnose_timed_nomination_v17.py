#!/usr/bin/env python3
"""Read-only raw-data checks and four explanatory replays; no policy selection."""
import json,sys
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'results/v17/source'))
from mafia_lab.timed_nomination_experiment_v17 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab import strategies_v17 as decisions

def main():
    hold_path=ROOT/'results/v17/holdout.json'
    hold=json.loads(hold_path.read_text())
    lookup={(c['good'],c['mafia']):c for c in hold['cells']}
    keys=['shortlist_size','day1_exile_mafia','day1_exile_police','outside_reroute',
          'outside_exile','day1_no_exile','day1_pk','final_target_mafia']
    checks=[]
    for mafia in hold['matrix']['mafia']:
        a,b=lookup['credit2',mafia],lookup['history2',mafia]
        assert all(a['raw'][k]==b['raw'][k] for k in keys)
        checks.append({'mafia':mafia,'paired_openings':a['n'],'first_day_metric_keys':keys,'identical':True})
    rules,good,mafia,cal=build_spec(json.loads((ROOT/'results/v17/source/config.json').read_text()))
    gm,mm={p.name:p for p in good},{p.name:p for p in mafia}
    seed=146000009 # Posthoc illustrative seed, never used as independent statistical evidence.
    traces=[]
    for column in ('safe_late_quiet','safe_late_counter'):
        for row in ('credit2','history2'):
            state=opening(rules,gm[row],mm[column],seed,decisions)
            outcome=continue_game(state,gm[row],mm[column],seed,trace=True,
                                  decision_api=decisions,public_ballots=True)
            cell=lookup[row,column];index=seed-cell['seed_start']
            assert outcome.good_win==cell['raw']['win'][index]
            assert outcome.transcript[-1]['event']=='terminal'
            traces.append({'seed':seed,'good':row,'mafia':column,'win':outcome.good_win,
                           'roles_for_offline_explanation_only':[r.value for r in state.roles],
                           'transcript':outcome.transcript})
    output={'holdout_sha256':sha256(hold_path.read_bytes()).hexdigest(),
            'first_day_identity_checks':checks,'explanatory_replays':traces,
            'scope':'Posthoc mechanism diagnostic on existing holdout; not new validation data or isolated history-component ablation.'}
    path=ROOT/'results/v17_mechanism_diagnostics.json'
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'paired_first_day_openings_checked':sum(c['paired_openings'] for c in checks),
                      'explanatory_replays':len(traces),'status':'pass'}))
if __name__=='__main__':main()
