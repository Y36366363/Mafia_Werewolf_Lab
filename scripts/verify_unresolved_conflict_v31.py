"""Raw integrity, independent sampled replay, paired interval cross-check."""
import sys,json
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab import strategies_v31 as d
from mafia_lab import strategies_v30 as old
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec,contrasts
from mafia_lab.simulation import opening,continue_game
from mafia_lab.experiments import fingerprint
from mafia_lab.statistics import win_summary
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save


def run():
 out=ROOT/'results/v31';f=json.loads((out/'freeze.json').read_text());cfg=f['config'];manifest=json.loads((out/'manifest.json').read_text())
 assert fingerprint()==f['package_sha256']
 for p,h in f['assets'].items():assert sha256((out/p).read_bytes()).hexdigest()==h
 for p,h in manifest['files'].items():assert sha256((out/p).read_bytes()).hexdigest()==h
 r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms}
 assert list(map(asdict,gs))==f['good'] and list(map(asdict,ms))==f['mafia']
 total=sample=compat=intervals=0;audit={}
 for phase in ('train','holdout'):
  data=json.loads((out/(phase+'.json')).read_text());assert len(data['cells'])==24
  assert contrasts(data['cells'])==data['contrasts']
  D={(c['good'],c['mafia']):c for c in data['cells']};assert set(D)=={(g,m) for g in G for m in M}
  for c in data['cells']:
   raw=c['raw'];n=cfg[phase]['n'];assert c['n']==n and c['seed_start']==cfg[phase]['seed_start']
   assert all(len(v)==n for v in raw.values());total+=n
   assert c['win']==win_summary(raw['win'])
   assert c['branch_win']==win_summary([v for v,k in zip(raw['win'],raw['dead_clear']) if k])
   for k in ('illegal_ballots','ignored_known_ballots','voted_good_ballots','team_call_mismatch_ballots'):assert not sum(raw[k]),(c['good'],c['mafia'],k)
   if G[c['good']].neutral_conflicts:
    assert not sum(raw['incompatible_early_common_ballots'])
   for sm in c['samples']:
    s=opening(r,G[c['good']],M[c['mafia']],sm['seed'],d)
    o=continue_game(s,G[c['good']],M[c['mafia']],sm['seed'],trace=True,decision_api=d,public_ballots=True)
    assert hash_events(o.transcript)==sm['trace_hash'];sample+=1
    if c['good']=='legacy' and sm['seed']==cfg[phase]['seed_start']:
     b=continue_game(s,G[c['good']],M[c['mafia']],sm['seed'],trace=True,decision_api=old,public_ballots=True)
     assert b.transcript==o.transcript;compat+=1
  for c in data['contrasts']:
   a,b=tuple(c['control']),tuple(c['treatment']);x,y=D[a]['raw'],D[b]['raw']
   mask=[True]*len(x['win']) if c['branch']=='all' else x['dead_clear']
   for metric in ('win','day1_mafia_exile'):
    xx=[v for v,k in zip(x[metric],mask) if k];yy=[v for v,k in zip(y[metric],mask) if k]
    p=c.get(metric+'_precision')
    if not xx:assert p is None;continue
    for name,k in [('p_plus',sum(i==0 and j==1 for i,j in zip(xx,yy))),('p_minus',sum(i==1 and j==0 for i,j in zip(xx,yy)))]:
     ci=binomtest(k,len(xx)).proportion_ci(confidence_level=1-2*p['tail_alpha'],method='exact')
     assert abs(ci.low-p[name][0])<1e-9 and abs(ci.high-p[name][1])<1e-9
    intervals+=1
  audit[phase]={str(k):{f:sum(c['raw'][f]) for f in ('relay_count','relay_false_source_count','incompatible_early_common_ballots','explicit_conflict_common_ballots','relay_own_first_mismatch_ballots','relay_own_mismatch_ballots','police_own_first_mismatch_ballots','team_call_applicable_ballots','orphan_ballots','orphan_directive_ballots','day1_live_police_reports')} for k,c in D.items()}
 assert total==manifest['games']==50688
 result=dict(audit_field_caveat='Frozen orphan_directive_ballots does not restrict day1 and can count valid later-day live/live comparisons; not used as a day1 invariant. Diagnosis checks each scoped observation directly.',all_checks_passed=True,formal_games=total,cells_checked=48,direct_sample_replays=sample,v30_compatibility_replays=compat,independently_checked_intervals=intervals,frozen_assets=len(f['assets']),counts=audit,
  limitation='All saved raw arrays checked; only declared first/middle/last complete games independently replayed, not all simulations rerun.')
 save(ROOT/'results/v31_integrity_audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='counts'}))

if __name__=='__main__':run()
