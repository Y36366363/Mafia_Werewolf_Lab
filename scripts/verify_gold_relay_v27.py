#!/usr/bin/env python3
import json,sys
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.gold_relay_experiment_v27 import build_spec,simulate,contrasts
from mafia_lab import strategies_v27 as d
from mafia_lab import strategies_v26 as old
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import opening,continue_game
from mafia_lab.experiments import fingerprint
from mafia_lab.restatement_experiment_v23 import save
from scipy.stats import binomtest


def verify(output):
    output=Path(output);freeze=json.loads((output/'freeze.json').read_text());config=freeze['config']
    assert freeze['package_sha256']==fingerprint()
    for p,h in freeze['assets'].items():assert sha256((output/p).read_bytes()).hexdigest()==h
    manifest=json.loads((output/'manifest.json').read_text())
    for p,h in manifest['files'].items():assert sha256((output/p).read_bytes()).hexdigest()==h
    rules,gs,ms=build_spec(config);G={g.name:g for g in gs};M={m.name:m for m in ms}
    assert [asdict(g) for g in gs]==freeze['good'] and [asdict(m) for m in ms]==freeze['mafia']
    count=0;compat=0;intervals=0;games=0
    for phase in ('train','holdout'):
        result=json.loads((output/(phase+'.json')).read_text());spec=config[phase]
        assert len(result['cells'])==72
        assert {(c['good'],c['mafia']) for c in result['cells']}=={(g,m) for g in G for m in M}
        assert contrasts(result['cells'])==result['contrasts']
        for c in result['cells']:
            assert c['n']==spec['n'] and c['seed_start']==spec['seed_start']
            assert all(len(v)==spec['n'] for v in c['raw'].values());games+=c['n']
            for key in ('illegal_ballots','ignored_known_ballots','voted_good_ballots','relay_police_target_count','relay_police_recipient_count'):
                assert sum(c['raw'][key])==0
            g,m=G[c['good']],M[c['mafia']]
            for sample in c['samples']:
                seed=sample['seed'];s=opening(rules,g,m,seed,d)
                o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
                assert hash_events(o.transcript)==sample['trace_hash'];count+=1
                if g.relay_mode=='none' and seed==spec['seed_start']:
                    before=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
                    assert before.transcript==o.transcript;compat+=1
        for c in result['contrasts']:
            if not c['primary']:continue
            p=c['precision'];tail=p['tail_alpha']
            cells={(c['good'],c['mafia']):c for c in result['cells']}
            a,b=c['comparison'].split('->');x=cells[a+'_q50',c['mafia']]['raw']['win'];y=cells[b+'_q50',c['mafia']]['raw']['win']
            for name,k in [('p_plus',sum(i==0 and j==1 for i,j in zip(x,y))),('p_minus',sum(i==1 and j==0 for i,j in zip(x,y)))]:
                ci=binomtest(k,len(x)).proportion_ci(confidence_level=1-2*tail,method='exact')
                assert abs(ci.low-p[name][0])<1e-9 and abs(ci.high-p[name][1])<1e-9
            intervals+=1
    assert games==manifest['games']==165888
    result=dict(formal_games=games,cells_checked=144,direct_sample_replays=count,v26_compatibility_replays=compat,
                independently_checked_intervals=intervals,frozen_assets=len(freeze['assets']),all_checks_passed=True,
                limitation='All records checked for structure/invariants; only the declared sample seeds independently replayed, not all formal games.')
    save(ROOT/'results/v27_integrity_audit.json',result);return result


if __name__=='__main__':print(json.dumps(verify(ROOT/'results/v27')))
