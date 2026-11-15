"""Small explicit source generators. Observation-only actions; no fitted credit."""
from .source_hypotheses_v32 import ResponseAPI, suppress_redundant
from . import strategies_v31 as base
from .engine import Message, Role, speech_order
from .policies import teammates

MODES=('hide','self','available')
SELF_PLANS=('quiet','copy_early','copy_late','hit_early','hit_late','copy_team')

class GenerationAPI(ResponseAPI):
    def __init__(self, mode='hide', cooperation='ordinary'):
        if mode not in MODES or cooperation not in ('ordinary',*SELF_PLANS):
            raise ValueError('unknown frozen source generator')
        super().__init__(mode=='hide')
        self.mode=mode;self.cooperation=cooperation;self.opportunities=[]
        self.nights=[];self.inspections=[]
    def choose_kill(self,obs,policy,rng):
        target=base.choose_kill(obs,policy,rng)
        self.nights.append(dict(day=obs.day+1,target=target));return target
    def choose_inspection(self,obs,policy,rng):
        target=base.choose_inspection(obs,policy,rng)
        self.inspections.append(dict(day=obs.day+1,target=target));return target
    def collaborator(self,obs):
        order=[p for p in speech_order(obs) if p in teammates(obs)]
        if self.cooperation=='copy_team':
            # First remaining mafia is the fabricated gold; another mafia speaks.
            order=[p for p in order if p!=self.team_gold(obs)]
        return (order[-1] if self.cooperation.endswith('_late') else order[0]) if order else None
    def team_gold(self,obs):
        return next((p for p in speech_order(obs) if p in teammates(obs)),None)
    def message(self,obs,policy,rng,context='day',override=None):
        if obs.role==Role.MAFIA and self.cooperation!='ordinary' and obs.day==1:
            if context=='last_words' and self.cooperation=='copy_team':
                return Message(obs.player,'report',self.team_gold(obs),False,context,1)
            if context=='day':
                if self.cooperation=='quiet' or obs.player!=self.collaborator(obs):
                    return Message(obs.player,'pass',context=context,day=1)
                clear=base.base.dead_clear(obs)
                if clear is not None:
                    hit=self.cooperation.startswith('hit_')
                    target=base.base.copy_target(obs,clear) if hit else clear.target
                    if target is not None:return Message(obs.player,'report',target,hit,context,1)
        if obs.role!=Role.POLICE or obs.day!=1 or context!='day':
            return base.message(obs,policy,rng,context,override)
        team=teammates(obs)
        public=any(m.day==1 and m.context=='day' and m.kind in {'report','police'} and m.speaker in team for m in obs.messages)
        threats=[m for m in obs.messages if m.day==1 and m.context=='day' and m.kind in {'report','police'} and m.speaker not in team]
        self_hit=any(m.kind=='report' and m.verdict and m.target==obs.player for m in threats)
        dead_team=suppress_redundant(obs,context)
        original=base.message(obs,policy,rng,context,override)
        if self.mode=='hide':
            result=Message(obs.player,'pass',context=context,day=1) if dead_team and original.kind in {'report','police'} else original
        elif public:
            result=Message(obs.player,'pass',context=context,day=1)
        elif self_hit or (self.mode=='available' and threats):
            report=obs.investigations[-1] if obs.investigations else None
            result=Message(obs.player,'report',report.target,report.is_mafia,context,1) if report else Message(obs.player,'pass',context=context,day=1)
        elif dead_team:
            result=Message(obs.player,'pass',context=context,day=1)
        else:
            result=original
        self.opportunities.append(dict(player=obs.player,position=list(speech_order(obs)).index(obs.player)+1,
            dead_team_report=dead_team,prior_live_team=public,prior_outsider=bool(threats),self_hit=self_hit,
            reported=result.kind in {'report','police'}))
        return result
    def after_speech(self,obs,policy,rng):
        if obs.role==Role.MAFIA and obs.day==1 and self.cooperation!='ordinary':
            if self.cooperation=='quiet' or obs.player!=self.collaborator(obs):return None
            own=next((m for m in reversed(obs.messages) if m.speaker==obs.player and m.context=='day' and m.kind=='report'),None)
            clear=base.base.dead_clear(obs)
            target=own.target if own and own.verdict else base.base.copy_target(obs,clear) if clear else None
            return Message(obs.player,'accuse',target,context='day',day=1) if target is not None else None
        return base.after_speech(obs,policy,rng)
    def after_last_words(self,obs,policy,rng):
        if obs.role==Role.MAFIA and obs.day==1 and self.cooperation=='copy_team':
            recipient=self.team_gold(obs)
            pool=tuple(p for p in speech_order(obs) if p not in teammates(obs))[:2]
            return (Message(obs.player,'shortlist',context='last_words',day=1,targets=pool),
                    Message(obs.player,'delegate',recipient,context='last_words',day=1,targets=pool))
        return base.after_last_words(obs,policy,rng)
