#!/usr/bin/env python3
"""Read-only fixed prefix replay audit of archived v24, no policy changes."""
import sys,json
from pathlib import Path
from collections import Counter,defaultdict
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'results/v24'
sys.path.insert(0,str(ARCHIVE/'source'))
from mafia_lab import strategies_v24 as d
from mafia_lab.engine import Role
from mafia_lab.simulation import opening,continue_game
from mafia_lab.succession_experiment_v24 import build_spec
from mafia_lab import strategies_v20 as evidence
from mafia_lab import strategies_v22 as routing


def report_gate_shadow(obs,policy,info):
    """Change suggestion eligibility only; historical sources/conflicts persist."""
    backed={m.speaker for m in obs.messages if m.kind=='report'}
    eligible=[s for s in info['proposal_sources'] if s in backed]
    if obs.day<2 or info['known_bad'] or not info['legal']:
        return info['target'],eligible
    pool=[p for p in info['legal'] if p not in info['known_good']]
    if not pool:return None,eligible
    guarded=evidence.old.constraints._clear_priority(obs,pool)
    recs={s:set(info['proposals'][str(s)]) for s in eligible}
    if not info['sources']:return evidence._rank_choice(obs,policy,guarded),eligible
    if len(eligible)==1:return evidence._rank_choice(obs,policy,recs[eligible[0]]),eligible
    common=set.intersection(*(recs[s] for s in eligible)) if eligible else set()
    if common:return evidence._rank_choice(obs,policy,common),eligible
    if info['conflict_targets']:return evidence._rank_choice(obs,policy,info['conflict_targets']),eligible
    union=set.union(*(recs[s] for s in eligible)) if eligible else set()
    return evidence._rank_choice(obs,policy,union or guarded),eligible


class Audit:
    def __init__(self):self.rows=[]
    def __getattr__(self,k):return getattr(d,k)
    def vote(self,obs,policy,rng,candidates=None):
        target=d.vote(obs,policy,rng,candidates)
        if obs.role==Role.MAFIA or obs.day<2:return target
        info=d.explain(obs,policy,candidates);assert info['target']==target
        shadow,eligible=report_gate_shadow(obs,policy,info)
        backed={m.speaker for m in obs.messages if m.kind=='report'}
        bare=[s for s in info['proposal_sources'] if s not in backed]
        good_recs=[set(info['proposals'][str(s)]) for s in eligible]
        common=set.intersection(*good_recs) if good_recs else set()
        dilution=bool(bare and common and info['reason']=='compatible_sources_protocol' and target!=shadow)
        own=[m for m in obs.messages if m.day==obs.day and m.speaker==obs.player and m.kind=='report' and m.verdict and m.target in info['legal']]
        mismatch=bool(obs.role==Role.POLICE and own and target!=own[-1].target)
        self.rows.append(dict(day=obs.day,player=obs.player,round='first' if candidates is None else 'pk',
            role=obs.role.value,target=target,reason=info['reason'],shadow_target=shadow,
            bare_sources=bare,report_sources=eligible,common_without_bare=sorted(common),
            dilution=dilution,own_public_hit=own[-1].target if own else None,
            police_report_vote_mismatch=mismatch,known_bad=info['known_bad'],
            mismatch_both_known_bad=bool(mismatch and target in info['known_bad'] and own[-1].target in info['known_bad'])))
        return target


def replay(job):
    base,mode,start,n=job
    config=json.loads((ARCHIVE/'freeze.json').read_text())['config'];rules,gs,ms=build_spec(config)
    g=next(g for g in gs if g.name=='repair_q50');m=next(m for m in ms if m.name==base+'_'+mode)
    archived=json.loads((ARCHIVE/'holdout.json').read_text())
    cell=next(c for c in archived['cells'] if c['good']==g.name and c['mafia']==m.name)
    counts=Counter();raw=[];cohorts=Counter();examples={}
    for seed in range(start,start+n):
        api=Audit();initial=opening(rules,g,m,seed,api)
        o=continue_game(initial,g,m,seed,trace=True,decision_api=api,public_ballots=True)
        idx=seed-cell['seed_start'];assert o.good_win==cell['raw']['win'][idx]
        sample=next((s for s in cell['samples'] if s['seed']==seed),None)
        if sample:assert sha256(repr(o.transcript).encode()).hexdigest()==sample['trace_hash']
        flags={key:any(v[key] for v in api.rows) for key in ('dilution','police_report_vote_mismatch')}
        counts.update({key+'_games':int(v) for key,v in flags.items()})
        counts.update({key+'_ballots':sum(v[key] for v in api.rows) for key in flags})
        counts['mismatch_both_known_bad_ballots']+=sum(v['mismatch_both_known_bad'] for v in api.rows)
        counts['wins']+=o.good_win
        for key in flags:
            if flags[key] and key not in examples:
                row=next(v for v in api.rows if v[key]);examples[key]=dict(seed=seed,ballot=row,roles_evaluation_only=[r.value for r in initial.roles])
        # Truth labels below only characterize completed public-vote cohorts.
        messages=[]
        for e in o.transcript:
            if e['event'] in ('message','speech_extension'):messages.append(e['payload'])
            if e['event']!='votes':continue
            groups=defaultdict(list)
            for voter,target in e['payload'].items():
                if target is not None:groups[target].append(int(voter))
            for target,voters in groups.items():
                if len(voters)<3:continue
                proponents={z['speaker'] for z in messages if z['day']==e['day'] and z['target']==target and (z['kind']=='accuse' or (z['kind']=='report' and z['verdict']))}
                if not proponents:continue
                roles=[initial.roles[p] for p in voters];mafia=sum(r==Role.MAFIA for r in roles)
                cohorts['groups']+=1;cohorts['voters']+=len(voters);cohorts['mafia_voters']+=mafia
                cohorts['good_voters']+=len(voters)-mafia
                cohorts['zero_mafia_groups']+=int(mafia==0)
                cohorts['police_majority_groups']+=int(sum(r==Role.POLICE for r in roles)>len(roles)/2)
                cohorts['mafia_majority_groups']+=int(mafia>len(roles)/2)
        raw.append(dict(seed=seed,win=o.good_win,**flags,trace_hash=sha256(repr(o.transcript).encode()).hexdigest()))
    return dict(base=base,mode=mode,n=n,seed_start=start,counts=dict(counts),vote_cohorts=dict(cohorts),examples=examples,raw=raw)


if __name__=='__main__':
    # Fixed prefix in all four columns, independent of outcome or mechanism flags.
    jobs=[(b,m,174000000,512) for b in ('late_near','late_far','decoy_near','decoy_far') for m in ('restate','claim')]
    rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(replay,j) for j in jobs]
        for fut in as_completed(futures):rows.append(fut.result())
    out=dict(scope='Read-only replay audit of fixed first 512 v24 held seeds per q50/base/mode. This previously inspected holdout is development data now; no new confirmation. Shadow gate is an action diagnostic on same observations, not terminal causal effect.',
             source_freeze_sha256=sha256((ARCHIVE/'freeze.json').read_bytes()).hexdigest(),
             source_holdout_sha256=sha256((ARCHIVE/'holdout.json').read_bytes()).hexdigest(),
             replayed_games=sum(r['n'] for r in rows),rows=sorted(rows,key=lambda r:(r['base'],r['mode'])))
    (ROOT/'results/v25_source_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
