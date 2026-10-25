#!/usr/bin/env python3
"""After-train explanatory diagnostic, not a new independent evaluation."""
import sys,json
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v20';sys.path.insert(0,str(folder/'source'))
from mafia_lab.evidence_experiment_v20 import build_spec,AuditedAPI
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab import strategies_v20 as d

class DiagnosticAPI(AuditedAPI):
    def __init__(self):
        super().__init__();self.details=[]
    def vote(self,obs,policy,rng,candidates=None):
        target=super().vote(obs,policy,rng,candidates)
        if obs.role==Role.CIVILIAN and obs.day==1:
            if policy.routing=='evidence':
                reason=d.route(obs,policy,candidates)[1]
                sources=sorted({m.speaker for m in d.public_claims(obs)}-d.impossible_sources(obs,policy))
                source=sources[0] if reason=='single_source_protocol' else None
            else:
                reason='fixed_credit';source=None
            self.details.append((reason,source,target))
        return target

def diagnose(job):
    rules,g,m,start,n,wins=job;counts=Counter()
    for i,seed in enumerate(range(start,start+n)):
        api=DiagnosticAPI();s=opening(rules,g,m,seed,api)
        outcome=continue_game(s,g,m,seed,trace=True,decision_api=api,public_ballots=True)
        assert outcome.good_win==wins[i]
        for reason,source,target in api.details:
            counts['day1_civilian_ballots']+=1
            counts['route_'+reason]+=1
            if reason=='single_source_protocol':
                counts['single_source_'+s.roles[source].value]+=1
                counts['single_target_'+('abstain' if target is None else s.roles[target].value)]+=1
            if reason=='compare_conflicting_sources':
                counts['conflict_target_'+('abstain' if target is None else s.roles[target].value)]+=1
    return dict(good=g.name,mafia=m.name,games=n,counts=dict(counts),scope='First 128 held-out seeds, day-one civilian first/PK ballots; repeated ballots not independent games.')

if __name__=='__main__':
    f=json.loads((folder/'freeze.json').read_text());r,gs,ms=build_spec(f['config'])
    h=json.loads((folder/'holdout.json').read_text());lookup={(c['good'],c['mafia']):c for c in h['cells']}
    names={'credit_today','credit_memory','evidence_today','evidence_q50'}
    jobs=[(r,g,m,f['config']['holdout']['seed_start'],128,lookup[g.name,m.name]['raw']['win'][:128]) for g in gs if g.name in names for m in ms]
    with ProcessPoolExecutor(max_workers=4) as pool:rows=list(pool.map(diagnose,jobs))
    result=dict(scope='Explanatory diagnostic planned after viewing train, before viewing holdout. Existing first 128 held-out seeds reused; no strategy changes, no new independent evidence, no seed search.',
        games_replayed=sum(r['games'] for r in rows),outcome_agreement=True,rows=rows,
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    (ROOT/'results/v20_adoption_diagnostic.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(games_replayed=result['games_replayed'],status='pass')))
