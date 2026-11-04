import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.relay_receiver_experiment_v30 import build_spec,column_job,contrasts
from mafia_lab.restatement_experiment_v23 import save
if __name__=='__main__':
 c=json.loads((ROOT/'configs/relay_receiver_v30.json').read_text());r,gs,ms=build_spec(c);rows=[]
 for m in ms:rows.extend(column_job(('smoke',r,gs,m,c['smoke']['seed_start'],c['smoke']['n'])))
 for row in rows:
  for k in ('illegal_ballots','ignored_known_ballots','voted_good_ballots','team_call_mismatch_ballots'):assert not sum(row['raw'][k])
 out=dict(games=sum(r['n'] for r in rows),cells=len(rows),contrast_contracts=len(contrasts(rows)),all_checks_passed=True)
 save(ROOT/'results/v30_smoke.json',out);print(out)
