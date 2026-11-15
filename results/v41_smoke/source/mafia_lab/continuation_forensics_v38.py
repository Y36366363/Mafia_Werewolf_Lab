"""Observation-only, nonintervening instrumentation of v37 continuations."""
from .hit_candidates_v37 import HitCandidatesAPI, explain
from . import strategies_v31 as base
from . import strategies_v26 as execution
from . import strategies_v27 as relay
from .engine import Role
from .policies import teammates


def local_view(obs, policy, candidates=None, retain=False):
    info = explain(obs, policy, candidates, retain)
    call = execution.team_execution_call(obs) if obs.role == Role.POLICE else None
    false = ({m.speaker for m in base.evidence.public_claims(obs)} - teammates(obs)) if obs.role == Role.POLICE else set()
    guarded = base.evidence.old.constraints._clear_priority(
        obs, [p for p in info['legal'] if p not in info['known_good']])
    return dict(target=info['target'], reason=info['reason'], legal=info['legal'],
        known_bad=info['known_bad'], known_good=info['known_good'],
        known_false_sources=sorted(false.intersection(obs.alive)),
        sources=info['sources'], proposals=info['proposals'],
        proposal_sources=info.get('proposal_sources', []), guarded=guarded,
        excluded_sources=sorted(base.evidence.impossible_sources(obs, policy)),
        history_edges=info['history_edges'], active_edges=info.get('active_edges', []),
        team_call=None if call is None else dict(source=call.speaker, target=call.target),
        accepted_relays=[dict(source=a.speaker, recipient=r.speaker, target=r.target)
                         for a,r in relay.admitted_relays(obs,policy)] if obs.day>=2 else [],
        blocked_advice_sources=info.get('blocked_advice_sources', []))


def follow_reason(v, source, target):
    if target not in v['legal']: return 'target_not_legal'
    if v['target'] == target: return 'followed'
    if v['known_bad']: return 'other_private_bad'
    if target in v['known_good']: return 'private_good'
    if source in v['excluded_sources']: return 'privately_refuted_source'
    if target not in v['guarded']: return 'clear_order_protection'
    recs=v['proposals'].get(str(source),[])
    if target not in recs:
        if any(r['source']==source and r['target']!=target for r in v['accepted_relays']):return 'relay_replaced_call'
        return 'source_call_not_admitted'
    return v['reason']


class ContinuationForensicsAPI(HitCandidatesAPI):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.forensic_speeches=[];self.forensic_votes=[];self.forensic_rounds={}

    def after_speech(self,obs,policy,rng):
        result=super().after_speech(obs,policy,rng)
        if obs.role==Role.POLICE:
            parts=result if isinstance(result,tuple) else (result,)
            v=local_view(obs,policy,retain=self.retain)
            self.forensic_speeches.append(dict(day=obs.day,speaker=obs.player,
                own_report=any(m.day==obs.day and m.context=='day' and m.kind=='report' and m.speaker==obs.player for m in obs.messages),
                parts=[dict(kind=m.kind,target=m.target,targets=list(m.targets)) for m in parts if m is not None],
                **v))
        return result

    def vote(self,obs,policy,rng,candidates=None):
        target=super().vote(obs,policy,rng,candidates)
        rd='first' if candidates is None else 'pk';key=(obs.day,rd)
        if key not in self.forensic_rounds:
            self.forensic_rounds[key]=dict(day=obs.day,round=rd,alive=list(obs.alive),
                messages=[dict(speaker=m.speaker,kind=m.kind,target=m.target,
                    verdict=m.verdict,context=m.context,day=m.day,targets=list(m.targets)) for m in obs.messages])
        if obs.role!=Role.MAFIA:
            v=local_view(obs,policy,candidates,self.retain)
            assert target==v['target']
            assert not v['known_bad'] or target in v['known_bad']
            assert target not in v['known_good']
            assert not v['known_false_sources'] or not set(v['known_false_sources']).intersection(v['legal']) or v['known_bad']
            self.forensic_votes.append(dict(day=obs.day,round=rd,player=obs.player,role=obs.role.value,**v))
        return target


def daily_counts(roles, nights, transcript, win):
    """Evaluation only, including the otherwise unlogged terminal-night death."""
    alive=set(range(len(roles)));days=[]
    exiles={e['day']:e['payload']['victim'] for e in transcript if e['event']=='day_death'}
    voted_days={e['day'] for e in transcript if e['event']=='votes'}
    def counts():return {k:sum(roles[p]==k for p in alive) for k in ('police','mafia','civilian')}
    for night in nights:
        day=night['day'];before=counts();victim=night['target']
        assert victim in alive;alive.remove(victim);post_night=counts()
        exile=exiles.get(day)
        if exile is not None:
            assert exile in alive;alive.remove(exile)
        days.append(dict(day=day,pre_night=before,night_victim=victim,
            post_night=post_night,day_exile=exile,day_played=day in voted_days,end=counts()))
    final=counts()
    assert (final['mafia']==0) if win else (final['police']==0)
    return days
