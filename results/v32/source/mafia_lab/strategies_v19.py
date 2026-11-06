"""v19 fixed-credit baseline with clear-order protection and first-day replies.

No role-assignment counting. All reply decisions use own police team knowledge;
private civilian denial does not authenticate its speaker to anyone else.
"""
from dataclasses import dataclass,replace
from fractions import Fraction
from .engine import Message,Role,speech_order
from .policies import teammates
from . import strategies_v17 as old
from . import strategies_v18 as constraints

@dataclass(frozen=True)
class GoodPolicyV19(old.GoodPolicyV17):
    clear_guard: bool = True
    reply: str = 'keep'
    civilian_denial: bool = True
    survival_guard: bool = False
    def __post_init__(self):
        super().__post_init__()
        if self.flow!='timed' or not self.source_credit or self.history:
            raise ValueError('v19 fixes timed credit and disables history')
        if self.reply not in {'keep','answer','police_target'}:
            raise ValueError('invalid reply')

@dataclass(frozen=True)
class MafiaPolicyV19(old.MafiaPolicyV17):
    def __post_init__(self):
        old.v16.MafiaPolicyV16.__post_init__(self)
        if self.response not in {'forward','last'}:
            raise ValueError('invalid first-day bluff timing')

choose_inspection=old.choose_inspection
choose_kill=old.choose_kill
turn_extensions=old.turn_extensions

def post_preferences(good):return False
def final_call(obs,policy,rng):return None
def preference(obs,policy,rng):return None
def final_selection(obs,policy,rng):return None

def threats(obs):
    allies=teammates(obs)
    return [m for m in obs.messages if m.day==obs.day and m.context=='day'
            and m.kind in {'report','police'} and m.speaker not in allies]

def reply_target(obs,policy):
    if obs.role!=Role.POLICE or obs.day!=1 or policy.reply=='keep':return None
    rows=threats(obs)
    if policy.reply=='police_target':
        rows=[m for m in rows if m.kind=='report' and m.verdict and m.target in teammates(obs)]
    if not rows:return None
    threat=rows[-1];index=max(i for i,m in enumerate(obs.messages) if m is threat)
    # Only a visible teammate's actual denial ends this episode; merely
    # publishing a different investigation does not silently count as a reply.
    if any(m.speaker in teammates(obs) and m.day==obs.day and m.context=='day'
           and m.kind=='accuse' and m.target==threat.speaker
           for m in obs.messages[index+1:]):return None
    return threat.speaker

def own_false_accusers(obs):
    # A civilian's own role refutes an accusation against itself. Public
    # observers do not receive this private fact.
    return [m.speaker for m in old._reports(obs) if m.verdict and m.target==obs.player]

def message(obs,policy,rng,context='day',override=None):
    if isinstance(policy,GoodPolicyV19):
        if context=='day' and reply_target(obs,policy) is not None:
            report=old.v16._latest_report(obs)
            if report is not None:
                return Message(obs.player,'report',report.target,report.is_mafia,'day',obs.day)
        return old.message(obs,policy,rng,context,override)
    if context=='day' and obs.day==1:
        order=list(speech_order(obs));allies=teammates(obs)
        if policy.response=='forward':
            first=next(p for p in order if p in allies)
            if obs.player==first:
                future=[p for p in order[order.index(first)+1:] if p not in allies]
                pool=future or [p for p in order if p not in allies]
                if pool:return Message(obs.player,'report',pool[0],True,'day',obs.day)
        elif policy.response=='last':
            last=next(p for p in reversed(order) if p in allies)
            seen=[m for m in old._reports(obs) if m.speaker not in allies]
            if obs.player==last and seen:
                return Message(obs.player,'report',seen[-1].speaker,True,'day',obs.day)
    # All columns share the same non-bluffing continuation after the day-one
    # intervention; the initial false declaration still remains public history.
    return old.v16.message(obs,policy,rng,context,override)

def after_speech(obs,policy,rng):
    base=old.after_speech(obs,policy,rng)
    if not isinstance(policy,GoodPolicyV19):return base
    if obs.role==Role.POLICE and obs.day==1:
        index=next((i for i in range(len(obs.messages)-1,-1,-1)
                    if obs.messages[i].speaker==obs.player and obs.messages[i].day==obs.day
                    and obs.messages[i].context=='day'),None)
        if index is not None:
            target=reply_target(replace(obs,messages=obs.messages[:index]),policy)
            if target is not None:
                denial=Message(obs.player,'accuse',target,context='day',day=obs.day)
                # Preserve the original spokesperson's shortlist and actual
                # investigation, then append a role-based denial, not a fake hit.
                return (base,denial) if base is not None and base.kind=='shortlist' else denial
    if obs.role==Role.CIVILIAN and policy.civilian_denial:
        accused=own_false_accusers(obs)
        if accused:
            return Message(obs.player,'nominate',accused[-1],context='day',day=obs.day)
    return base

def source_credit(obs,policy):
    values={p:old._credit(obs,p,policy) for p in obs.alive}
    if obs.role==Role.CIVILIAN and policy.survival_guard and obs.day>=2:
        first_claimants={m.speaker for m in obs.messages if m.day==1
                         and m.context=='day' and m.kind in {'report','police'}}
        # A publicly surviving claimant is challenged, not certified as mafia.
        # Same cap applies to a surviving real police claimant.
        for p in first_claimants.intersection(obs.alive):
            values[p]=min(values[p],Fraction(1,2))
    if policy.clear_guard:
        edges={(m.speaker,m.target) for m in obs.messages
               if m.kind=='report' and not m.verdict and m.target is not None}
        # Propagate relational source credit until fixed point. These remain
        # operation weights, not calibrated identity probabilities.
        for _ in range(obs.rules.n_players):
            changed=False
            for a,b in edges:
                if a in values and b in values and values[b]<values[a]:
                    values[b]=values[a];changed=True
            if not changed:break
    return values

def vote(obs,policy,rng,candidates=None):
    if not isinstance(policy,GoodPolicyV19):return old.vote(obs,policy,rng,candidates)
    pool=[p for p in (obs.alive if candidates is None else candidates)
          if p in obs.alive and p!=obs.player]
    if not pool:return None
    if obs.role==Role.POLICE:
        hits=[r.target for r in obs.investigations if r.is_mafia and r.target in pool]
        if hits:return hits[-1]
        known=teammates(obs)|{r.target for r in obs.investigations if not r.is_mafia}
        pool=[p for p in pool if p not in known]
        own_denials=[m.target for m in obs.messages if m.speaker==obs.player
                     and m.kind=='accuse' and m.day==obs.day and m.target in pool
                     and m.target not in teammates(obs)]
        if own_denials:return own_denials[-1]
    if obs.role==Role.CIVILIAN and policy.civilian_denial:
        accused=[p for p in own_false_accusers(obs) if p in pool]
        if accused:return accused[-1]
    if policy.clear_guard:
        pool=constraints._clear_priority(obs,pool)
    if not pool:return None
    credits=source_credit(obs,policy)
    proposals=[]
    for index,m in enumerate(obs.messages):
        if m.day!=obs.day or m.target not in pool or m.speaker==obs.player:continue
        if (m.kind=='report' and m.verdict) or m.kind=='accuse':
            if credits.get(m.speaker,Fraction(0))>=Fraction(3,5):
                proposals.append((credits[m.speaker],index,m.target))
    if proposals:return max(proposals)[2]
    ranked,scores=old._rank(obs,policy)
    shortlist=old._shortlist(obs)
    if shortlist:
        listed=[p for p in shortlist.targets if p in pool and p in ranked]
        if listed:return max(listed,key=lambda p:(scores[p],-ranked.index(p)))
    return next((p for p in ranked if p in pool),None)
