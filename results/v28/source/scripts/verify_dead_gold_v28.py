#!/usr/bin/env python3
import sys,json
from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.dead_gold_experiment_v28 import build_spec,contrasts
from mafia_lab import strategies_v28 as d
from mafia_lab import strategies_v27 as old
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.experiments import fingerprint
from mafia_lab.statistics import win_summary
from mafia_lab.restatement_experiment_v23 import save
from scipy.stats import binomtest


def verify(output):
    output=Path(output);f=json.loads((output/'freeze.json').read_text());cfg=f['config']
    assert fingerprint()==f['package_sha256']
    for p,h in f['assets'].items():assert sha256((output/p).read_bytes()).hexdigest()==h
    manifest=json.loads((output/'manifest.json').read_text())
    for p,h in manifest['files'].items():assert sha256((output/p).read_bytes()).hexdigest()==h
    r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms}
    assert [asdict(g) for g in gs]==f['good'] and [asdict(m) for m in ms]==f['mafia']
    replays=0;compat=0;intervals=0;games=0;cells=0
    for phase in ('train','holdout'):
        result=json.loads((output/(phase+'.json')).read_text());spec=cfg[phase]
        assert len(result['cells'])==96
        D={(c['good'],c['mafia']):c for c in result['cells']}
        assert set(D)=={(g,m) for g in G for m in M}
        assert contrasts(result['cells'])==result['contrasts']
        for c in result['cells']:
            cells+=1;games+=c['n'];assert c['n']==spec['n'] and c['seed_start']==spec['seed_start']
            assert all(len(v)==c['n'] for v in c['raw'].values())
            assert c['win']==win_summary(c['raw']['win'])
            assert c['branch_win']==win_summary([v for v,k in zip(c['raw']['win'],c['raw']['dead_clear']) if k])
            for key in ('illegal_ballots','ignored_known_ballots','voted_good_ballots'):assert not sum(c['raw'][key])
            ref=D['reference_q'+c['good'].split('_q')[1],c['mafia']]
            for i,k in enumerate(c['raw']['dead_clear']):
                if not k:assert c['raw']['process_hash'][i]==ref['raw']['process_hash'][i]
            g,m=G[c['good']],M[c['mafia']]
            for sample in c['samples']:
                seed=sample['seed'];s=opening(r,g,m,seed,d)
                o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
                assert hash_events(o.transcript)==sample['trace_hash'];replays+=1
                if g.dead_gold=='reference' and seed==spec['seed_start']:
                    prior=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
                    assert o.transcript==prior.transcript;compat+=1
        for c in result['contrasts']:
            if 'precision' not in c:continue
            a,b=c['comparison'].split('->');x=D[a+'_q'+c['q'],c['mafia']]['raw'];y=D[b+'_q'+c['q'],c['mafia']]['raw']
            mask=x['dead_clear'] if c['branch']=='dead_clear' else [True]*spec['n']
            xx=[v for v,k in zip(x['win'],mask) if k];yy=[v for v,k in zip(y['win'],mask) if k]
            p=c['precision'];tail=p['tail_alpha']
            for name,k in [('p_plus',sum(i==0 and j==1 for i,j in zip(xx,yy))),('p_minus',sum(i==1 and j==0 for i,j in zip(xx,yy)))]:
                ci=binomtest(k,len(xx)).proportion_ci(confidence_level=1-2*tail,method='exact')
                assert abs(ci.low-p[name][0])<1e-9 and abs(ci.high-p[name][1])<1e-9
            intervals+=1
    assert games==manifest['games']==208896
    result=dict(formal_games=games,cells_checked=cells,direct_sample_replays=replays,v27_compatibility_replays=compat,
                independently_checked_intervals=intervals,frozen_assets=len(f['assets']),all_checks_passed=True,
                limitation='All records structurally/statistically checked, sampled runs independently replayed, not all formal games rerun.')
    save(ROOT/'results/v28_integrity_audit.json',result);print(json.dumps(result))


if __name__=='__main__':verify(ROOT/'results/v28')
