"""Police-private false-dead-source response with one local random draw."""
from fractions import Fraction
from dataclasses import replace
from .day1_risk_v34 import RiskAPI
from . import strategies_v31 as base
from .engine import Role,Message,speech_order
from .policies import teammates


def private_branch(obs):
    """Known only to the officer from team membership, never a civilian label."""
    if obs.role!=Role.POLICE or obs.day!=1 or not obs.deaths:return None
    victim=obs.deaths[0].player
    if victim in teammates(obs):return None
    claims=[m for m in obs.messages if m.speaker==victim and m.day==1
            and m.context=='last_words' and m.kind in {'report','police'}]
    if not claims:return None
    team=teammates(obs)
    public=any(m.speaker in team and m.day==1 and m.context=='day'
               and m.kind in {'report','police'} for m in obs.messages)
    prior_turn=any(m.speaker in team and m.speaker!=obs.player and m.day==1 and m.context=='day'
                   for m in obs.messages)
    self_hit=any(m.speaker not in team and m.day==1 and m.context=='day'
                 and m.kind=='report' and m.verdict and m.target==obs.player for m in obs.messages)
    return dict(victim=victim,prior_public=public,prior_police_turn=prior_turn,self_hit=self_hit)


class PrivateResponseAPI(RiskAPI):
    def __init__(self,cooperation='ordinary',receiver='original',fake_relay=False,q=None):
        super().__init__('self',cooperation,receiver,fake_relay)
        self.q=None if q is None else Fraction(q)
        if self.q is not None and not 0<=self.q<=1:raise ValueError('q must be in [0,1]')
        self.response_audit=[]
    def message(self,obs,policy,rng,context='day',override=None):
        branch=private_branch(obs) if context=='day' else None
        if self.q is None or branch is None:return super().message(obs,policy,rng,context,override)
        # One earliest legal police turn draws. Later officers can observe a
        # previous police ordinary-turn message using their own team knowledge.
        # No secret team random signal and no retry after a failed draw.
        draw=None
        if branch['prior_public']:
            respond=False;reason='already_represented'
        elif branch['self_hit']:
            respond=True;reason='mandatory_self_defense'
        elif branch['prior_police_turn']:
            respond=False;reason='no_second_draw'
        else:
            draw=rng.random();respond=draw<float(self.q);reason='single_local_draw'
        report=obs.investigations[-1] if obs.investigations else None
        result=(Message(obs.player,'report',report.target,report.is_mafia,context,1)
                if respond and report is not None else Message(obs.player,'pass',context=context,day=1))
        row=dict(player=obs.player,position=list(speech_order(obs)).index(obs.player)+1,
                 **branch,q=str(self.q),draw=draw,reason=reason,reported=result.kind=='report')
        self.response_audit.append(row)
        # Keep inherited opportunity output meaningful for these new branches.
        self.opportunities.append(dict(player=obs.player,position=row['position'],dead_team_report=False,
             prior_live_team=branch['prior_public'],prior_outsider=any(m.speaker not in teammates(obs)
             and m.day==1 and m.context=='day' and m.kind in {'report','police'} for m in obs.messages),
             self_hit=branch['self_hit'],reported=row['reported']))
        return result
