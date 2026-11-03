#!/usr/bin/env python3
import sys,json
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.advice_semantics_experiment_v29 import build_spec,contrasts
from mafia_lab import strategies_v29 as d
from mafia_lab import strategies_v28 as old
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
    games=0;replays=0;compat=0;intervals=0;cells=0
    for phase in ('train','holdout'):
        data=json.loads((output/(phase+'.json')).read_text());spec=cfg[phase]
        assert len(data['cells'])==40;D={(c['good'],c['mafia']):c for c in data['cells']}
        assert set(D)=={(g,m) for g in G for m in M}
        assert contrasts(data['cells'])==data['contrasts']
        for c in data['cells']:
            cells+=1;games+=c['n'];raw=c['raw']
            assert c['n']==spec['n'] and c['seed_start']==spec['seed_start']
            assert all(len(v)==c['n'] for v in raw.values())
            assert c['win']==win_summary(raw['win'])
            assert c['branch_win']==win_summary([v for v,k in zip(raw['win'],raw['dead_clear']) if k])
            for key in ('illegal_ballots','ignored_known_ballots','voted_good_ballots','gold_final_call_game'):assert not sum(raw[key])
            ref=D['anchor',c['mafia']]['raw']
            for i,k in enumerate(raw['dead_clear']):
                if not k:assert raw['process_hash'][i]==ref['process_hash'][i]
            g,m=G[c['good']],M[c['mafia']]
            for sample in c['samples']:
                seed=sample['seed'];s=opening(r,g,m,seed,d)
                o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
                assert hash_events(o.transcript)==sample['trace_hash'];replays+=1
                if g.name in {'anchor','plain'} and seed==spec['seed_start']:
                    before=continue_game(s,g,m,seed,trace=True,decision_api=old,public_ballots=True)
                    assert before.transcript==o.transcript;compat+=1
        for c in data['contrasts']:
            if not c['primary']:continue
            a,b=c['comparison'].split('->');x,y=D[a,c['mafia']]['raw'],D[b,c['mafia']]['raw']
            mask=x['dead_clear']
            for metric in ('win','day1_mafia_exile'):
                if metric+'_precision' not in c:
                    assert c[metric]['n']==0
                    continue
                p=c[metric+'_precision'];tail=p['tail_alpha']
                xx=[v for v,k in zip(x[metric],mask) if k];yy=[v for v,k in zip(y[metric],mask) if k]
                for name,k in [('p_plus',sum(i==0 and j==1 for i,j in zip(xx,yy))),('p_minus',sum(i==1 and j==0 for i,j in zip(xx,yy)))]:
                    ci=binomtest(k,len(xx)).proportion_ci(confidence_level=1-2*tail,method='exact')
                    assert abs(ci.low-p[name][0])<1e-9 and abs(ci.high-p[name][1])<1e-9
                intervals+=1
    assert games==manifest['games']==87040
    out=dict(formal_games=games,cells_checked=cells,direct_sample_replays=replays,v28_compatibility_replays=compat,
        independently_checked_intervals=intervals,frozen_assets=len(f['assets']),all_checks_passed=True,
        limitation='All records checked; only declared samples independently replayed, not all formal simulations rerun.')
    save(ROOT/'results/v29_integrity_audit.json',out);print(json.dumps(out))


if __name__=='__main__':verify(ROOT/'results/v29')
