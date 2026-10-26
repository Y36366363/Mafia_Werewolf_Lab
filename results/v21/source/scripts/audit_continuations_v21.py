#!/usr/bin/env python3
"""Read-only replay of archived v20b policies; no strategy or engine changes."""
import json,sys,shutil
from dataclasses import asdict
from pathlib import Path
from hashlib import sha256
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'results/v20b/source'
sys.path.insert(0,str(ARCHIVE))
from mafia_lab import strategies_v20 as original, strategies_v20b as corrected
from mafia_lab.engine import Role,speech_order
from mafia_lab.simulation import opening,continue_game
from mafia_lab.evidence_experiment_v20 import build_spec
from mafia_lab.reply_evaluation_v19 import metrics


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def conflicts(obs,sources,mode):
    reports=[m for m in obs.messages if m.kind=='report' and m.speaker in sources]
    edges=set()
    for i,a in enumerate(reports):
        if a.verdict and a.target in sources and a.target!=a.speaker:
            edges.add(tuple(sorted((a.speaker,a.target))))
        for b in reports[i+1:]:
            if a.speaker==b.speaker:continue
            mismatch=a.target==b.target and a.verdict!=b.verdict
            shared=mode=='corrected' and a.day==b.day==1 and (a.target,a.verdict)!=(b.target,b.verdict)
            if mismatch or shared:edges.add(tuple(sorted((a.speaker,b.speaker))))
    return sorted(edges)


class AuditAPI:
    def __init__(self,mode,detail=False):
        self.api=original if mode=='original' else corrected
        self.mode=mode;self.detail=detail;self.votes=[];self.nights=[];self.declarations=[]
    def __getattr__(self,key):return getattr(self.api,key)
    def choose_inspection(self,obs,policy,rng):
        target=self.api.choose_inspection(obs,policy,rng)
        self.nights.append(dict(kind='inspection',night=obs.day+1,actor=obs.player,target=target,
            alive=list(obs.alive),private_team=list(obs.teammates),previous_checks=[asdict(r) for r in obs.investigations]))
        return target
    def choose_kill(self,obs,policy,rng):
        target=self.api.choose_kill(obs,policy,rng)
        claimants=sorted({m.speaker for m in original.public_claims(obs)}.intersection(obs.alive)-set(obs.teammates))
        self.nights.append(dict(kind='kill',night=obs.day+1,actor=obs.player,target=target,public_claimants=claimants))
        return target
    def message(self,obs,policy,rng,context='day',override=None):
        msg=self.api.message(obs,policy,rng,context,override)
        if obs.role==Role.POLICE and msg.kind=='report':
            live_hits=[r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive]
            self.declarations.append(dict(day=obs.day,context=context,speaker=obs.player,target=msg.target,
                verdict=msg.verdict,live_private_hits=live_hits,ignores_live_hit=bool(live_hits) and msg.target not in live_hits))
        return msg
    def vote(self,obs,policy,rng,candidates=None):
        target=self.api.vote(obs,policy,rng,candidates)
        if obs.role==Role.MAFIA:return target
        pool=set(obs.alive if candidates is None else candidates)-{obs.player}
        bad=original.private_bad(obs,True).intersection(pool)
        good=({obs.player}|set(obs.teammates)|{r.target for r in obs.investigations if not r.is_mafia}) if obs.role==Role.POLICE else {obs.player}
        sources=sorted({m.speaker for m in original.public_claims(obs)}-original.impossible_sources(obs,policy))
        dead=[p for p in sources if p not in obs.alive]
        edges=conflicts(obs,sources,self.mode)
        live_conflicts=sorted(set(p for e in edges for p in e).intersection(pool-good))
        choice,reason=self.api.route(obs,policy,candidates)
        assert choice==target
        recs={str(s):sorted(original._recommendations(obs,s,pool-good)) for s in sources}
        row=dict(day=obs.day,round='pk' if candidates is not None else 'first',player=obs.player,
            role=obs.role.value,target=target,legal=sorted(pool),private_bad=sorted(bad),private_good=sorted(good.intersection(obs.alive)),
            reason=reason,sources=sources,dead_sources=dead,conflicts=edges,live_conflicts=live_conflicts,
            ignores_private_bad=bool(bad) and target not in bad,votes_private_good=target in good,
            illegal=target is not None and target not in pool,
            orphan_conflict=reason=='compare_conflicting_sources' and len(live_conflicts)==1 and any(target in e and any(p not in obs.alive for p in e) for e in edges),
            sole_dead_source=reason=='single_source_protocol' and len(sources)==1 and sources[0] not in obs.alive,
            dead_hit_used=any(s not in obs.alive and target in original._recommendations(obs,s,pool-good) for s in sources),
            source_recommendations=recs)
        if self.detail:row['observation']=asdict(obs)
        self.votes.append(row)
        return target


def replay(mode,rules,good,mafia,seed,detail=False):
    api=AuditAPI(mode,detail);initial=opening(rules,good,mafia,seed,api)
    outcome=continue_game(initial,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
    raw=metrics(initial,outcome);roles=initial.roles
    counts=Counter();daily=defaultdict(Counter)
    for v in api.votes:
        day=v['day'];prefix=v['role']
        counts['good_ballots']+=1
        for flag in ('ignores_private_bad','votes_private_good','illegal','orphan_conflict','sole_dead_source','dead_hit_used'):
            if v[flag]:
                counts[flag]+=1;daily[day][flag]+=1
                if v['target'] is not None:counts[flag+'_target_'+roles[v['target']].value]+=1
        if v['role']=='civilian':
            counts['civilian_'+v['reason']]+=1
            if v['target'] is not None:counts['civilian_'+v['reason']+'_target_'+roles[v['target']].value]+=1
    groups=defaultdict(list)
    for v in api.votes:
        if v['role']=='police' and v['private_bad']:groups[v['day'],v['round']].append(v)
    for key,rows in groups.items():
        if len(rows)>=2:
            counts['police_known_bad_rounds']+=1
            if len({v['target'] for v in rows})>1:counts['police_known_bad_split_rounds']+=1
    for n in api.nights:
        if n['kind']=='kill':
            counts['night_kills']+=1
            if roles[n['target']]==Role.POLICE:counts['night_kills_police']+=1
            if n['public_claimants']:
                counts['night_public_claimants_available']+=1
                counts['night_targets_public_claimant']+=n['target'] in n['public_claimants']
    counts['police_reports']=len(api.declarations)
    counts['reports_omit_live_hit']=sum(r['ignores_live_hit'] for r in api.declarations)
    deaths={}
    for e in outcome.transcript:
        if e['event'] in {'night_death','day_death'}:
            p=e['payload']['victim'];deaths[f"{e['day']}_{e['event']}"]=dict(player=p,role=roles[p].value)
    summary=dict(raw=raw,counts=dict(counts),daily={str(k):dict(v) for k,v in daily.items()},deaths=deaths,
        game_flags={flag:any(v[flag] for v in api.votes) for flag in ('ignores_private_bad','votes_private_good','orphan_conflict','sole_dead_source','dead_hit_used')},
        trace_hash=sha256(repr(outcome.transcript).encode()).hexdigest())
    if detail:summary.update(seed=seed,mode=mode,roles_evaluation_only=[r.value for r in roles],
        transcript=outcome.transcript,votes=api.votes,nights=api.nights,police_reports=api.declarations)
    return summary


def block(job):
    phase,rules,good,mafia,start,n,expected=job
    sums={mode:Counter() for mode in ('original','corrected')};flags={mode:Counter() for mode in sums}
    transitions=Counter();pairs=[];examples={};matches=0
    for i,seed in enumerate(range(start,start+n)):
        a=replay('original',rules,good,mafia,seed);b=replay('corrected',rules,good,mafia,seed)
        if expected is not None:
            for mode,result in [('original',a),('corrected',b)]:
                for k,v in result['raw'].items():assert v==expected[mode][k][i],(mode,seed,k)
                matches+=1
        for mode,result in [('original',a),('corrected',b)]:
            sums[mode].update(result['counts']);flags[mode].update({k:int(v) for k,v in result['game_flags'].items()})
        def exile(result):
            return result['deaths'].get('1_day_death',{}).get('role','none')
        oldwin,newwin=a['raw']['win'],b['raw']['win']
        transitions[f'{exile(a)}->{exile(b)};{oldwin}->{newwin}']+=1
        same=a['deaths'].get('1_day_death')==b['deaths'].get('1_day_death')
        kinds=[]
        if oldwin and not newwin and exile(b)=='mafia':kinds.append('lost_despite_day1_mafia')
        if not oldwin and newwin:kinds.append('gained_win')
        if same and oldwin!=newwin:kinds.append('same_day1_victim_different_win')
        if b['counts'].get('orphan_conflict_target_police',0):kinds.append('sole_surviving_conflict_police')
        for kind in kinds:
            if kind not in examples:examples[kind]=seed
        pairs.append(dict(seed=seed,old_win=oldwin,new_win=newwin,old_exile=exile(a),new_exile=exile(b),
            same_day1_victim=same,old_deaths=a['deaths'],new_deaths=b['deaths'],
            old_counts=a['counts'],new_counts=b['counts'],old_flags=a['game_flags'],new_flags=b['game_flags'],
            old_trace_hash=a['trace_hash'],new_trace_hash=b['trace_hash']))
    return dict(phase=phase,mafia=mafia.name,n=n,seed_start=start,replays=n*2,old_outcomes_checked=matches,
        totals={k:dict(v) for k,v in sums.items()},game_flags={k:dict(v) for k,v in flags.items()},
        transitions=dict(transitions),example_seeds=examples,pairs=pairs)


def main():
    out=ROOT/'results/v21'
    if out.exists():raise ValueError('new output required')
    out.mkdir();f=json.loads((ROOT/'results/v20b/freeze.json').read_text());data=json.loads((ROOT/'results/v20b/probe.json').read_text())
    # Use archived package only. Verify its immutable manifest before replay.
    for name,digest in f['assets'].items():assert sha256((ROOT/'results/v20b'/name).read_bytes()).hexdigest()==digest
    rules,gs,ms=build_spec(f['config']);g=next(p for p in gs if p.name=='evidence_q50')
    assets=[Path(__file__).resolve(),ROOT/'docs/continuation_audit_protocol_v21.md']
    for src in assets:
        dst=out/'source'/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    save(out/'freeze.json',dict(archived_package='results/v20b/source',archive_freeze_sha256=sha256((ROOT/'results/v20b/freeze.json').read_bytes()).hexdigest(),
        old_seed_start=163000000,old_n=2048,new_seed_start=164000000,new_n=512,
        assets={str(p.relative_to(out)):sha256(p.read_bytes()).hexdigest() for p in (out/'source').rglob('*') if p.is_file()}))
    jobs=[]
    for phase,start,n in [('historical_replay',163000000,2048),('fresh_audit',164000000,512)]:
        for m in ms:
            expected={c['mode']:c['raw'] for c in data['cells'] if c['mafia']==m.name} if phase=='historical_replay' else None
            jobs.append((phase,rules,g,m,start,n,expected))
    with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(block,jobs))
    save(out/'audit.json',dict(blocks=results,scope='Read-only whole-game audit. Historical games fully replayed, fresh games confirm mechanism occurrence only. No policy changes.'))
    examples=[]
    mm={m.name:m for m in ms}
    for r in results:
        if r['phase']!='historical_replay':continue
        for kind,seed in r['example_seeds'].items():
            examples.append(dict(kind=kind,mafia=r['mafia'],seed=seed,
                original=replay('original',rules,g,mm[r['mafia']],seed,True),
                corrected=replay('corrected',rules,g,mm[r['mafia']],seed,True)))
    save(out/'examples.json',dict(scope='First seed per predeclared explanatory category; not representative independent evidence. Referee role labels for evaluation only.',examples=examples))
    files=['freeze.json','audit.json','examples.json']
    save(out/'manifest.json',dict(historical_full_replays=16384,fresh_games=4096,
        files={n:sha256((out/n).read_bytes()).hexdigest() for n in files}))
    print(json.dumps(dict(status='complete',historical_full_replays=16384,fresh_games=4096,examples=len(examples))))
if __name__=='__main__':main()
