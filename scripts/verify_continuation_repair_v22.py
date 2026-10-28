#!/usr/bin/env python3
"""Archive, arithmetic, paired-prefix and independent trace audit."""
import sys,json
from pathlib import Path
from hashlib import sha256
from statistics import mean
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v22'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
for n,h in manifest['files'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
for n,h in f['assets'].items():assert sha256((folder/n).read_bytes()).hexdigest()==h
for n in ['engine.py','simulation.py','strategies_v20.py','strategies_v20b.py']:
    assert (folder/'source/mafia_lab'/n).read_bytes()==(ROOT/'results/v20b/source/mafia_lab'/n).read_bytes()
sys.path.insert(0,str(folder/'source'))
from mafia_lab.continuation_repair_v22 import build_spec,evaluate,contrasts
from mafia_lab.statistics import win_summary
from mafia_lab.simulation import opening,continue_game
from mafia_lab import strategies_v22 as d
r,gs,ms=build_spec(f['config']);gm={g.name:g for g in gs};mm={m.name:m for m in ms}
replays=legacy_checks=cells_count=0
for block in f['config']['blocks']:
    report=json.loads((folder/(block['name']+'.json')).read_text());assert report['contrasts']==contrasts(report['cells'])
    reference={c['mafia']:c for c in report['cells'] if c['good']=='legacy'}
    for c in report['cells']:
        cells_count+=1
        assert all(len(v)==c['n'] for v in c['raw'].values())
        assert c['means']=={k:mean(v) for k,v in c['raw'].items() if k!='pre_day2_vote_hash'}
        assert c['win']==win_summary(c['raw']['win'])
        assert c['raw']['pre_day2_vote_hash']==reference[c['mafia']]['raw']['pre_day2_vote_hash']
        for flag in ['ignores_private_bad','votes_private_good','illegal']:
            assert sum(c['raw'][flag+'_ballots'])==0
        if c['good'] in {'live_pair','both'}:assert sum(c['raw']['orphan_conflict_ballots'])==0
        if c['good'] in {'current_day','both'}:assert sum(c['raw']['stale_dead_advice_selected_ballots'])==0
        for sample in c['samples']:
            api=d
            state=opening(r,gm[c['good']],mm[c['mafia']],sample['seed'],api)
            o=continue_game(state,gm[c['good']],mm[c['mafia']],sample['seed'],trace=True,decision_api=api,public_ballots=True)
            assert sha256(repr(o.transcript).encode()).hexdigest()==sample['trace_hash']
            replay=evaluate((block['name'],r,gm[c['good']],mm[c['mafia']],sample['seed'],1))
            for k in c['raw']:assert replay['raw'][k][0]==c['raw'][k][sample['index']]
            replays+=1
            if c['good']=='legacy':
                s=opening(r,gm[c['good']],mm[c['mafia']],sample['seed'],d.legacy)
                original=continue_game(s,gm[c['good']],mm[c['mafia']],sample['seed'],trace=True,decision_api=d.legacy,public_ballots=True)
                assert sha256(repr(original.transcript).encode()).hexdigest()==sample['trace_hash'];legacy_checks+=1
result=dict(status='pass',games_recorded=manifest['games'],cells_checked=cells_count,sampled_full_replays=replays,
    additional_legacy_api_comparisons=legacy_checks,source_assets_checked=len(f['assets']),
    scope='All stored prefix hashes invariant, full raw arithmetic checked; 3 sampled full independent traces per cell plus instrumented metrics replay. Not all games independently rerun. No equilibrium claims.')
(ROOT/'results/v22_integrity_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
