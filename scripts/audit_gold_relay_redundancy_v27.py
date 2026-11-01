#!/usr/bin/env python3
"""Post-result explanation audit, not a predeclared confirmatory experiment.

Replay first accepted q50 relay for each column, without searching for gains.
Policies, seeds and formal estimates remain unchanged.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.gold_relay_experiment_v27 import build_spec,simulate,AuditAPI
from mafia_lab import strategies_v27 as d
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.engine import Role
from mafia_lab.restatement_experiment_v23 import save


class Capture(AuditAPI):
    def __init__(self):super().__init__();self.views=[]
    def after_speech(self,obs,policy,rng):
        if obs.role==Role.CIVILIAN:
            relay=d.relay_decision(obs,policy)
            if relay is not None:
                offers=d.valid_delegations(obs,policy)
                own=[m for _,m in offers if m.target==obs.player][0]
                before=d.base.explain(obs,policy)
                scoped=d.base.explain(obs,policy,list(own.targets))
                self.views.append(dict(day=obs.day,recipient=obs.player,source=own.speaker,
                    offered_candidates=list(own.targets),chosen=relay.target,
                    unmodified_target=before['target'],scoped_target=scoped['target'],
                    own_team=list(obs.teammates),private_investigations=len(obs.investigations),
                    private_bad=sorted(d.evidence.private_bad(obs,policy.remember)),
                    accepted_sources=before['sources'],original_reason=before['reason']))
        return super().after_speech(obs,policy,rng)


def strip(transcript):
    return [e for e in transcript if not(e['event']=='speech_extension' and e['payload']['kind'] in {'delegate','relay'})]


def run():
    cfg=json.loads((ROOT/'results/v27/freeze.json').read_text())['config']
    held=json.loads((ROOT/'results/v27/holdout.json').read_text())
    D={(c['good'],c['mafia']):c for c in held['cells']}
    r,gs,ms=build_spec(cfg);G={g.name:g for g in gs};M={m.name:m for m in ms};cases=[]
    for mn in sorted(M):
        raw=D['local_q50',mn]['raw'];i=next((i for i,v in enumerate(raw['relay_game']) if v),None)
        if i is None:cases.append(dict(mafia=mn,seed=None));continue
        seed=cfg['holdout']['seed_start']+i;rows={}
        for gn in ('base_q50','fixed_q50','local_q50'):
            a=simulate(r,G[gn],M[mn],seed,details=True)
            s=opening(r,G[gn],M[mn],seed,d)
            o=continue_game(s,G[gn],M[mn],seed,trace=True,decision_api=d,public_ballots=True)
            assert hash_events(o.transcript)==a['trace_hash']
            assert all(v==D[gn,mn]['raw'][k][i] for k,v in a['raw'].items())
            rows[gn]=a
        api=Capture();s=opening(r,G['local_q50'],M[mn],seed,api)
        o=continue_game(s,G['local_q50'],M[mn],seed,trace=True,decision_api=api,public_ballots=True)
        assert hash_events(o.transcript)==rows['local_q50']['trace_hash']
        eq=all(strip(rows[g]['transcript'])==strip(rows['base_q50']['transcript']) for g in ('fixed_q50','local_q50'))
        assert eq
        cases.append(dict(mafia=mn,seed=seed,ordinary_actions_identical_after_removing_relay_content=eq,
            first_relay_view=api.views[0],outcome=rows['base_q50']['raw']['win'],
            transcripts={g:a['transcript'] for g,a in rows.items()}))
    count=sum(c['seed'] is not None for c in cases)
    result=dict(posthoc=True,selection='After formal outcomes were inspected, first accepted local_q50 seed in each of all eight columns; no benefit filtering.',
        same_heldout_seeds=True,new_validation_samples=0,detail_runs=count*3,unwrapped_replays=count*3,
        observation_capture_replays=count,cases=cases,
        limitation='Describes redundancy in eight fixed sample cases; not proof of behavioral equivalence for all possible histories.')
    save(ROOT/'results/v27_redundancy_audit.json',result)
    print(json.dumps(dict(cases=count,detail_runs=count*3,unwrapped_replays=count*3,observation_capture_replays=count)))


if __name__=='__main__':run()
