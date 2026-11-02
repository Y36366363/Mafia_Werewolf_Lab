#!/usr/bin/env python3
"""Fixed old-seed process audit, prior to the new intervention freeze."""
import sys,json
from dataclasses import asdict
from collections import Counter
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab import strategies_v27 as d
from mafia_lab.gold_relay_experiment_v27 import build_spec
from mafia_lab.simulation import opening,continue_game
from mafia_lab.engine import Role
from mafia_lab.experiments import fingerprint
from mafia_lab.restatement_experiment_v23 import save


def facts(obs):
    report=next((m for m in obs.messages if m.day==1 and m.context=='last_words' and m.kind=='report' and m.verdict is False),None)
    if obs.day!=1 or obs.role!=Role.CIVILIAN or report is None or report.target!=obs.player:return None
    new=obs.messages[obs.messages.index(report)+1:]
    own_hits=[m.speaker for m in new if m.kind=='report' and m.verdict and m.target==obs.player and m.speaker in obs.alive]
    verdicts={};bad=set()
    for m in obs.messages:
        if m.kind!='report':continue
        k=(m.speaker,m.target)
        if (m.verdict and m.speaker==m.target) or (k in verdicts and verdicts[k]!=m.verdict):bad.add(m.speaker)
        verdicts[k]=m.verdict
    return dict(source=report.speaker,recipient=obs.player,own_hit_sources=sorted(set(own_hits)),
                public_hard_sources=sorted(bad.intersection(obs.alive)))


class Audit:
    def __init__(self):self.turn=None;self.ballot=None
    def __getattr__(self,k):return getattr(d,k)
    def after_speech(self,obs,policy,rng):
        f=facts(obs)
        if f is not None:
            f.update(target=d.explain(obs,policy)['target']);self.turn=f
        return d.after_speech(obs,policy,rng)
    def vote(self,obs,policy,rng,candidates=None):
        f=facts(obs)
        if f is not None and candidates is None:
            f.update(target=d.explain(obs,policy)['target']);self.ballot=f
        return d.vote(obs,policy,rng,candidates)


def strip(events):
    return tuple(e for e in events if not(e['event']=='speech_extension' and e['payload']['kind'] in {'delegate','relay'}))


def run():
    out=ROOT/'results/v28_evidence_audit.json'
    if out.exists():raise ValueError('audit output already exists')
    cfg=json.loads((ROOT/'results/v27/freeze.json').read_text())['config'];r,gs,ms=build_spec(cfg)
    G={g.name:g for g in gs};held=json.loads((ROOT/'results/v27/holdout.json').read_text())
    old={(c['good'],c['mafia']):c for c in held['cells']};rows=[];counts=Counter();examples={}
    start=183000000;n=256
    for m in ms:
        for seed in range(start,start+n):
            outcomes=[];views=[];states=[]
            for name in ('base_q50','local_q50'):
                api=Audit();s=opening(r,G[name],m,seed,api)
                o=continue_game(s,G[name],m,seed,trace=True,decision_api=api,public_ballots=True)
                assert o.good_win==old[name,m.name]['raw']['win'][seed-start]
                outcomes.append(o);states.append(s);views.append(api)
            a,b=outcomes;equal=strip(a.transcript)==strip(b.transcript)
            same_win=a.good_win==b.good_win
            first=states[0].deaths[0].player
            branch=states[0].roles[first]==Role.POLICE and not states[0].investigations[0].is_mafia
            v=views[0];row=dict(seed=seed,mafia=m.name,dead_police_clear=branch,
                same_terminal=same_win,same_public_process=equal,turn=v.turn,ballot=v.ballot)
            counts['pairs']+=1;counts['same_terminal_different_process']+=int(same_win and not equal)
            counts['different_process']+=int(not equal);counts['dead_police_clear']+=int(branch)
            if v.turn:
                counts['civilian_gold_turn']+=1
                before=set(v.turn['own_hit_sources']);after=set(v.ballot['own_hit_sources'])
                keys=dict(own_false_hit_before_turn=bool(before),own_false_hit_only_after_turn=bool(after-before),
                    public_hard_before_turn=bool(v.turn['public_hard_sources']),
                    turn_vote_target_changed=v.turn['target']!=v.ballot['target'])
                row.update(keys)
                for k,yes in keys.items():
                    counts[k]+=int(yes)
                    if yes and k not in examples:examples[k]=row
            if branch and 'first_dead_police_clear' not in examples:examples['first_dead_police_clear']=row
            rows.append(row)
        print(m.name+' audited',flush=True)
    scope=ROOT/'docs/gold_evidence_audit_scope_v28.md'
    result=dict(date='2026-11-02',runs=4096,seed_start=start,n=n,package_sha256=fingerprint(),
        scope_sha256=sha256(scope.read_bytes()).hexdigest(),script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        counts=dict(counts),examples=examples,rows=rows,
        limitation='Already viewed v27 seeds; descriptive development audit, not new validation data.')
    save(out,result);print(json.dumps(result['counts']))


if __name__=='__main__':run()
