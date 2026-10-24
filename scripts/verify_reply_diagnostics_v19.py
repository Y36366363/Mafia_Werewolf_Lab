#!/usr/bin/env python3
import json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];diag=json.loads((ROOT/'results/v19_timing_diagnostic.json').read_text())
assert diag['analyzer_sha256']==sha256((ROOT/'scripts/analyze_reply_timing_v19.py').read_bytes()).hexdigest()
checks=0
for block in ('evaluation_A','replication_B'):
    rep=json.loads((ROOT/f'results/v19/{block}.json').read_text())
    lookup={(c['good'],c['mafia']):c for c in rep['cells']}
    for m in {c['mafia'] for c in rep['cells']}:
        a,b=lookup['guard_selective',m],lookup['guard_bait',m]
        assert a['raw']==b['raw']
        assert [s['trace_hash'] for s in a['samples']]==[s['trace_hash'] for s in b['samples']]
        for branch in ('eligible','civilian_target','police_target'):
            rows=[r for r in diag['rows'] if r['phase']==block and r['mafia']==m and r['branch']==branch]
            assert len(rows)==2
            for policy in ('guard_keep','guard_answer','guard_selective'):
                expected=lookup[policy,m]['branches'][branch]
                assert sum(r['policies'][policy]['n'] for r in rows)==expected['n']
                assert sum(r['policies'][policy]['wins'] for r in rows)==expected['wins']
            full=next(r for r in rep['contrasts'] if r['name']=='reply' and r['mafia']==m and r['branch']==branch)
            for metric in ('win','day1_mafia_exile','day1_police_exile','police_claims'):
                for key in ('n','improved','worsened'):
                    if key in full[metric]:assert sum(r[metric].get(key,0) for r in rows)==full[metric][key]
            checks+=1
result=dict(status='pass',partition_checks=checks,survival_rows_raw_identical=True,survival_sampled_traces_identical=True,
            scope='Aggregate partition and raw-null audit; timing strata use replayed openings, not newly simulated outcomes.')
(ROOT/'results/v19_diagnostic_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
