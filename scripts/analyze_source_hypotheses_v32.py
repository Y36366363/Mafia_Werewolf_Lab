"""Read frozen v32 outputs; no strategy selection or new outcome seeds."""
import sys,json
from pathlib import Path
from dataclasses import replace
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_source_hypotheses_v32 import simulate
from mafia_lab.source_hypotheses_v32 import ResponseAPI, role_support, source_prefix
from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save
from mafia_lab import strategies_v31 as base
from mafia_lab.engine import Observation,Rules,Death,Message,Role

EVENTS=['no_live_at_end','hit_early','hit_late','copy_early','copy_late','other_clear_early','other_clear_late']

def read_obs(x):
    return Observation(player=x['player'],role=Role(x['role']),teammates=tuple(x['teammates']),alive=tuple(x['alive']),
        day=x['day'],messages=tuple(Message(**dict(m,targets=tuple(m['targets']))) for m in x['messages']),
        investigations=(),deaths=tuple(Death(**d) for d in x['deaths']),public_events=(),pending_pk=(),
        last_anchor=x['last_anchor'],rules=Rules(**x['rules']),winner=x['winner'])

class CheckAPI(ResponseAPI):
    def __init__(self,restrained):super().__init__(restrained);self.checks=0
    def vote(self,obs,policy,rng,candidates=None):
        target=super().vote(obs,policy,rng,candidates)
        if obs.role!=Role.MAFIA:
            v=base.explain(obs,policy,candidates)
            assert target is None or target in v['legal']
            assert not v['known_bad'] or target in v['known_bad']
            assert target not in v['known_good']
            self.checks+=1
        return target


def main():
    out=ROOT/'results/v32';freeze=json.loads((out/'freeze.json').read_text());cfg=freeze['config']
    for rel,h in freeze['assets'].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
        assert sha256((out/'source'/rel).read_bytes()).hexdigest()==h
    manifest=json.loads((out/'manifest.json').read_text())
    for rel,h in manifest['files'].items():assert sha256((out/rel).read_bytes()).hexdigest()==h
    r,gs,ms=build_spec(freeze['base_config']);g=gs[-1];M={m.name:m for m in ms}
    events=[];sensitivity=[];checks=0;replays=0;baseline=0;logic=0;ambiguous=0;examples=[]
    for phase in ('train','holdout'):
        data=json.loads((out/(phase+'.json')).read_text());D={(c['response'],c['mafia']):c for c in data['cells']}
        for c in data['cells']:
            rows=c['rows'];mn=c['mafia'];resp=c['response']
            for idx in (0,len(rows)//2,len(rows)-1):
                seed=rows[idx]['seed'];api=CheckAPI(resp=='restrained');s=opening(r,g,M[mn],seed,api)
                o=continue_game(s,g,M[mn],seed,trace=True,decision_api=api,public_ballots=True)
                assert hash_events(o.transcript)==rows[idx]['trace_hash'];checks+=api.checks;replays+=1
                if resp=='inherited':
                    s=opening(r,g,M[mn],seed,base);o=continue_game(s,g,M[mn],seed,trace=True,decision_api=base,public_ballots=True)
                    assert hash_events(o.transcript)==rows[idx]['trace_hash'];baseline+=1
            for row in rows:
                if resp=='restrained' and row['dead_clear']:assert row['live_police_reports']==0
                d=row.get('diagnostic')
                if not d or 'support' not in d:continue
                obs=read_obs(d['observation']);a=role_support(obs,d['dead_source'],d['live_source']);assert a==d['support']
                b=role_support(replace(obs,messages=tuple(m for m in obs.messages if m.kind!='delegate')),d['dead_source'],d['live_source'])
                assert a==b
                actual=('P' if d['dead_police'] else 'M')+'/'+('-' if d['live_role'] is None else 'P' if d['live_role']=='police' else 'M')
                assert actual in a['counts'];logic+=1
                both=any(k.startswith('P/') for k in a['counts']) and any(k.startswith('M/') for k in a['counts']);ambiguous+=both
                if phase=='holdout' and not any(e['event']==d['event'] for e in examples):
                    examples.append(dict(seed=row['seed'],response=resp,mafia=mn,event=d['event'],diagnostic=d))
            for event in EVENTS:
                samples=[x['diagnostic'] for x in rows if x.get('diagnostic',{}).get('event')==event]
                events.append(dict(phase=phase,response=resp,mafia=mn,event=event,n=len(samples),dead_police=sum(x['dead_police'] for x in samples),
                    live_police=sum(x['live_role']=='police' for x in samples),live_mafia=sum(x['live_role']=='mafia' for x in samples)))
        for resp in ('inherited','restrained'):
            for share in cfg['selfkill_shares']:
                for event in EVENTS:
                    mass=[0.,0.];counts=[0,0]
                    for mn in M:
                        c=D[resp,mn];weight=share/2 if mn.startswith('false_') else (1-share)/6
                        for row in c['rows']:
                            d=row.get('diagnostic')
                            if d and d['event']==event:
                                label=d['dead_police'];mass[label]+=weight/c['n'];counts[label]+=1
                    sensitivity.append(dict(phase=phase,response=resp,selfkill_share=share,event=event,
                        raw_counts_false_true=counts,event_mass=sum(mass),
                        conditional_dead_police=mass[1]/sum(mass) if all(counts) else None,
                        status='both_labels_observed_not_calibrated' if all(counts) else 'missing_generator_support_or_sample_coverage'))
    result=dict(replays=replays,baseline_direct_replays=baseline,ballot_checks=checks,logic_prefix_checks=logic,
                both_dead_hypotheses_supported=ambiguous,examples=examples,events=events,sensitivity=sensitivity,
                limitation='Role-compatible worlds are not strategy likelihoods; diagnostic tables are not action posteriors; no new validation seeds.')
    save(ROOT/'results/v32_diagnostics.json',result)
    print(json.dumps({k:result[k] for k in ('replays','baseline_direct_replays','ballot_checks','logic_prefix_checks','both_dead_hypotheses_supported')}))

if __name__=='__main__':main()
