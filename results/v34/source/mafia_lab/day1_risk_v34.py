"""Day-one civilian risk controls and mimickable delegated final calls."""
from dataclasses import replace
from .source_generation_v33 import GenerationAPI
from . import strategies_v31 as base
from .engine import Role,Message

RECEIVERS=('original','first_live','conditional_gold')


def public_context(obs):
    """No role labels: every gate below is read from the current message prefix."""
    if obs.day!=1 or not obs.deaths:return None
    origin=obs.deaths[0].player
    dead=next((m for m in obs.messages if m.speaker==origin and m.day==1 and m.context=='last_words' and m.kind=='report' and m.verdict is False),None)
    if dead is None or dead.target not in obs.alive:return None
    live=[m for m in obs.messages if m.day==1 and m.context=='day' and m.speaker in obs.alive and m.kind in {'report','police'}]
    ordinary_reports=[m for m in live if m.kind=='report']
    if not ordinary_reports:return None
    first=ordinary_reports[0]
    current_claims=live+[m for m in obs.messages if m.day==1 and m.context=='pk' and m.speaker in obs.alive and m.kind in {'report','police'}]
    reports=[m for m in current_claims if m.kind=='report']
    claimants={origin,*[m.speaker for m in current_claims]}
    bare={m.speaker for m in current_claims if m.kind=='police'}-{m.speaker for m in reports}
    agreement=all(m.target==dead.target and m.verdict is False for m in reports)
    challenges=[m for m in obs.messages if m.day==1 and m.context in {'day','pk'}
                and m.kind in {'accuse','nominate'} and m.speaker in claimants and m.target in claimants and m.speaker!=m.target]
    grant=any(m.day==1 and m.context=='last_words' and m.kind=='delegate' and m.speaker==origin and m.target==dead.target for m in obs.messages)
    reasons=[]
    if not agreement:reasons.append('different_report')
    if bare:reasons.append('unresolved_bare_claim')
    if challenges:reasons.append('source_challenge')
    if not grant:reasons.append('no_matching_grant')
    return dict(origin=origin,gold=dead.target,first_live=first.speaker,
                sources=sorted(claimants),agreement=agreement,grant=grant,
                eligible=not reasons,blocks=reasons)


def explain(obs,policy,receiver='original',candidates=None):
    if receiver not in RECEIVERS:raise ValueError('unknown receiver')
    old=base.explain(obs,policy,candidates)
    info=dict(old,risk_context=False,risk_applied=False,risk_gate=False,risk_block=None,
              risk_first_live=None,risk_gold=None)
    if obs.day!=1 or obs.role!=Role.CIVILIAN:return info
    c=public_context(obs)
    if c is None:return info
    info.update(risk_context=True,risk_gate=c['eligible'],risk_first_live=c['first_live'],risk_gold=c['gold'])
    if receiver=='original':return info
    if old['known_bad']:return dict(info,risk_block='private_refutation')
    pool=[p for p in old['legal'] if p not in old['known_good']]
    pool=base.evidence.old.constraints._clear_priority(obs,pool) if pool else []
    if receiver=='first_live':
        target=c['first_live']
        if target in pool:return dict(info,target=target,reason='day1_first_live_risk',risk_applied=True)
        return dict(info,risk_block='illegal_or_protected_first_live')
    if not c['eligible']:return dict(info,risk_block='public_gate_failed')
    # An actor never validates its own relay by following it. B chooses from
    # the old evidence receiver and publishes that choice in the same window.
    if obs.player==c['gold']:return dict(info,risk_block='gold_uses_own_information')
    if c['origin'] in base.evidence.impossible_sources(obs,policy):
        return dict(info,risk_block='privately_refuted_origin')
    for index in range(len(obs.messages)-1,-1,-1):
        m=obs.messages[index]
        if m.kind!='relay' or m.speaker!=c['gold'] or m.targets!=(c['origin'],) or m.day!=1 or m.context!='day':continue
        prefix=replace(obs,messages=obs.messages[:index]);at_issue=public_context(prefix)
        if at_issue is None or not at_issue['eligible']:continue
        if m.target in pool:return dict(info,target=m.target,reason='day1_conditional_gold_call',risk_applied=True)
        return dict(info,risk_block='illegal_or_protected_gold_target')
    return dict(info,risk_block='no_eligible_relay')


class RiskAPI(GenerationAPI):
    def __init__(self,mode='self',cooperation='ordinary',receiver='original',fake_relay=False):
        super().__init__(mode,cooperation)
        if receiver not in RECEIVERS:raise ValueError('unknown receiver')
        self.receiver=receiver;self.fake_relay=fake_relay;self.risk_votes=[];self.final_calls=[];self.end_public=None
    def final_call(self,obs,policy,rng):
        if (obs.role==Role.MAFIA and self.fake_relay and self.cooperation=='copy_team' and obs.day==1):
            victim=obs.deaths[0].player
            offers=[m for m in obs.messages if m.kind=='delegate' and m.speaker==victim and m.target==obs.player and m.context=='last_words' and m.day==1]
            if offers:
                # The mafia actor uses its own team and existing public calls;
                # it cannot see police/civilian identities among nonmafia.
                targets=[m.target for m in obs.messages if m.kind=='accuse' and m.day==1 and m.context=='day'
                         and m.speaker in base.teammates(obs) and m.target in obs.alive and m.target not in base.teammates(obs)]
                clear=base.base.dead_clear(obs)
                target=targets[-1] if targets else base.base.copy_target(obs,clear) if clear else None
                if target is not None:
                    call=Message(obs.player,'relay',target,context='day',day=1,targets=(victim,))
                    self.final_calls.append(dict(speaker=obs.player,target=target,kind='fake',gate=bool(public_context(obs) and public_context(obs)['eligible'])))
                    return call
        if obs.role==Role.CIVILIAN and obs.day==1:
            offers=base.gold.dead_offers(obs,policy)
            if len(offers)==1 and offers[0][1].target==obs.player:
                target=explain(obs,policy,self.receiver)['target']
                if target is not None:
                    self.final_calls.append(dict(speaker=obs.player,target=target,kind='civilian',gate=bool(public_context(obs) and public_context(obs)['eligible'])))
                    return Message(obs.player,'relay',target,context='day',day=1,targets=(offers[0][1].speaker,))
        return base.final_call(obs,policy,rng)
    def vote(self,obs,policy,rng,candidates=None):
        # Preserve v32 focal capture, but use the audited day-one selector.
        if obs.day==1 and candidates is None and obs.player==0 and obs.role==Role.CIVILIAN:
            self.focal=replace(obs,public_events=(),pending_pk=())
        if obs.day==1 and candidates is None and self.end_public is None:self.end_public=public_context(obs)
        if obs.role==Role.MAFIA:return base.vote(obs,policy,rng,candidates)
        v=explain(obs,policy,self.receiver,candidates)
        assert v['target'] is None or v['target'] in v['legal']
        assert not v['known_bad'] or v['target'] in v['known_bad']
        assert v['target'] not in v['known_good']
        own=[m for m in obs.messages if m.speaker==obs.player and m.day==obs.day and m.context=='day' and m.kind=='relay']
        self.risk_votes.append(dict(day=obs.day,player=obs.player,role=obs.role.value,round='first' if candidates is None else 'pk',
            target=v['target'],context=v['risk_context'],gate=v['risk_gate'],applied=v['risk_applied'],block=v['risk_block'],
            first_live=v['risk_first_live'],gold=v['risk_gold'],reason=v['reason'],
            own_relay_mismatch=bool(own and own[-1].target!=v['target']),
            known_bad=v['known_bad'],known_good=v['known_good'],legal=v['legal']))
        return v['target']
