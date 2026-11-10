"""Nonintervening instrumentation of v35 strategies and local observations."""
from .private_response_v35 import PrivateResponseAPI
from .day1_risk_v34 import explain
from . import strategies_v31 as base
from .engine import Role


def public_gold_links(obs):
    """A dated claim ledger, never authentication or a posterior."""
    return [dict(source=m.speaker,target=m.target,day=m.day,context=m.context,
                 source_alive=m.speaker in obs.alive,target_alive=m.target in obs.alive)
            for m in obs.messages if m.kind=='report' and m.verdict is False]


def observation_view(obs,policy,candidates=None):
    info=explain(obs,policy,'original',candidates)
    excluded=base.evidence.impossible_sources(obs,policy)
    guarded=base.evidence.old.constraints._clear_priority(obs,[p for p in info['legal'] if p not in info['known_good']])
    return dict(target=info['target'],reason=info['reason'],legal=info['legal'],
      known_bad=info['known_bad'],known_good=info['known_good'],sources=info['sources'],
      proposal_sources=info.get('proposal_sources',[]),proposals=info['proposals'],
      excluded_sources=sorted(excluded),guarded=guarded,
      history_edges=info['history_edges'],active_edges=info.get('active_edges',[]))


def classify_hit_vote(vote,source,target):
    """Reasons for nonalignment, not a judgement that the source is genuine."""
    if target not in vote['legal']:return 'target_not_legal'
    if vote['target']==target:return 'aligned_with_hit'
    if vote['known_bad']:return 'other_private_bad'
    if target in vote['known_good']:return 'private_good_conflict'
    if source in vote['excluded_sources']:return 'source_locally_refuted'
    if target not in vote['guarded']:return 'public_clear_order'
    proposals=vote['proposals'].get(str(source),[])
    if source not in vote['proposal_sources'] and not proposals:return 'no_current_proposal_from_source'
    if proposals and target not in proposals:return 'source_proposes_other_target'
    return vote['reason']


class ContinuationAuditAPI(PrivateResponseAPI):
    def __init__(self,*args):
        super().__init__(*args)
        self.audit_reports=[];self.audit_extensions=[];self.audit_rounds={};self.audit_votes=[]
    def message(self,obs,policy,rng,context='day',override=None):
        m=super().message(obs,policy,rng,context,override)
        if m.kind in {'report','police'}:
            self.audit_reports.append(dict(day=obs.day,context=context,speaker=obs.player,
              role=obs.role.value,kind=m.kind,target=m.target,verdict=m.verdict,
              target_alive=m.target in obs.alive,
              latest_check=(dict(day=obs.investigations[-1].day,target=obs.investigations[-1].target,
                is_mafia=obs.investigations[-1].is_mafia) if obs.role==Role.POLICE and obs.investigations else None)))
        return m
    def after_speech(self,obs,policy,rng):
        result=super().after_speech(obs,policy,rng)
        parts=result if isinstance(result,tuple) else (result,)
        visible=[dict(kind=m.kind,target=m.target,targets=list(m.targets)) for m in parts if m is not None]
        if visible:
            self.audit_extensions.append(dict(day=obs.day,speaker=obs.player,role=obs.role.value,
                 parts=visible,view=observation_view(obs,policy) if obs.role!=Role.MAFIA else None))
        return result
    def vote(self,obs,policy,rng,candidates=None):
        target=super().vote(obs,policy,rng,candidates)
        round_name='first' if candidates is None else 'pk';key=(obs.day,round_name)
        if key not in self.audit_rounds:
            self.audit_rounds[key]=dict(day=obs.day,round=round_name,alive=list(obs.alive),
              messages=[dict(speaker=m.speaker,kind=m.kind,target=m.target,verdict=m.verdict,
                   context=m.context,day=m.day,targets=list(m.targets)) for m in obs.messages],
              gold_links=public_gold_links(obs))
        if obs.role!=Role.MAFIA:
            v=observation_view(obs,policy,candidates)
            assert target==v['target']
            assert target is None or target in v['legal']
            assert not v['known_bad'] or target in v['known_bad']
            assert target not in v['known_good']
            self.audit_votes.append(dict(day=obs.day,round=round_name,player=obs.player,role=obs.role.value,**v))
        return target
