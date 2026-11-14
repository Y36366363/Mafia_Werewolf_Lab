"""Speech-timed non-binding shortlists, fallible source credit, public vote history."""
from dataclasses import dataclass
from fractions import Fraction
from random import Random
from collections import Counter
from .engine import Message, Role, speech_order
from .policies import teammates
from . import strategies_v13 as v13
from . import strategies_v16 as v16

@dataclass(frozen=True)
class GoodPolicyV17(v16.GoodPolicyV16):
    flow: str = 'timed'
    source_credit: bool = False
    history: bool = False
    def __post_init__(self):
        super().__post_init__()
        if self.flow not in {'legacy', 'timed'}:
            raise ValueError('invalid flow')

@dataclass(frozen=True)
class MafiaPolicyV17(v16.MafiaPolicyV16):
    response: str = 'quiet'
    def __post_init__(self):
        super().__post_init__()
        if self.response not in {'quiet', 'counter'}:
            raise ValueError('invalid response')

choose_inspection = v16.choose_inspection
choose_kill = v16.choose_kill

def turn_extensions(good):
    return good.flow == 'timed'

def post_preferences(good):
    return good.flow == 'legacy'

def _make(obs, kind, target=None, verdict=None, targets=()):
    return Message(obs.player, kind, target, verdict, 'day', obs.day, targets)

def _shortlist(obs):
    return next((m for m in reversed(obs.messages) if m.kind == 'shortlist'
                 and m.day == obs.day and m.context == 'day'), None)

def _reports(obs):
    latest = {}
    for m in obs.messages:
        if m.kind == 'report' and m.context == 'day' and m.day == obs.day:
            latest[m.speaker] = m
    return list(latest.values())

def _credit(obs, speaker, policy):
    if obs.role == Role.POLICE:
        return Fraction(1) if speaker in teammates(obs) else Fraction(0)
    if speaker == obs.player:
        return Fraction(1)  # own actual role is used only for own action
    if not policy.source_credit:
        return Fraction(3, 5)
    # A reported clear is only a public claim, not referee-certified identity.
    # One-hop support only; no recursive corroboration or duplicate counting.
    supported = any(not m.verdict and m.target == speaker and m.speaker != speaker
                    for m in _reports(obs))
    accused = any(m.verdict and m.target == speaker and m.speaker != speaker
                  for m in _reports(obs))
    return Fraction(3, 4) if supported and not accused else Fraction(1, 2)

def history_scores(obs):
    """Uncalibrated public heuristic: no role labels or inferred flip identities."""
    scores = {p: Fraction(0) for p in obs.alive}
    rounds = [e for e in obs.public_events if e.kind in {'vote', 'pk_vote'}
              and e.day < obs.day]
    declarations = {}
    for m in obs.messages:
        if m.day < obs.day and m.kind in {'nominate', 'accuse'}:
            declarations[m.day, m.speaker] = m.target
    disagreements = Counter()
    for event in rounds:
        for voter, target in event.ballots:
            stated = declarations.get((event.day, voter))
            if stated is not None and target != stated:
                # Abstention after a stated target is included; abstention alone
                # is not intrinsically suspicious.
                disagreements[voter] += 1
    for p in scores:
        scores[p] += min(disagreements[p], 2) * Fraction(1, 20)
    # Repeated co-voting is a weak association only, not independent evidence.
    # It propagates an existing public/private suspicion by at most .05.
    suspect = {m.target for m in _reports(obs) if m.verdict}
    if obs.role == Role.POLICE:
        suspect |= {r.target for r in obs.investigations if r.is_mafia}
    for p in scores:
        repeated = 0
        for q in suspect - {p}:
            common = sum(1 for e in rounds if dict(e.ballots).get(p) is not None
                         and dict(e.ballots).get(p) == dict(e.ballots).get(q))
            repeated = max(repeated, common)
        if repeated >= 2:
            scores[p] += Fraction(1, 20)
    return scores

def _rank(obs, policy):
    known = teammates(obs) if obs.role == Role.POLICE else {obs.player}
    hits = []
    if obs.role == Role.POLICE:
        for r in obs.investigations:
            if r.is_mafia:
                hits.append(r.target)
            else:
                known.add(r.target)
    # Use opening posterior only on day one; do not reuse a stale opening
    # model after later deaths/investigations.
    scores = (v16.seat_scores(obs, known, policy.prior_model) if obs.day == 1
              else {p: Fraction(0) for p in obs.alive})
    if policy.history:
        adjustment = history_scores(obs)
        scores = {p: scores[p] + adjustment.get(p, 0) for p in scores}
    for p in hits:
        if p in scores:
            scores[p] = Fraction(2)
    order = {p: i for i, p in enumerate(speech_order(obs))}
    pool = [p for p in obs.alive if p not in known]
    return sorted(pool, key=lambda p: (-scores[p], order[p])), scores

def message(obs, policy, rng, context='day', override=None):
    if isinstance(policy, GoodPolicyV17):
        if policy.flow == 'legacy':
            return v16.message(obs, policy, rng, context, override)
        # Retain one spokesperson and dead-police rules. Later spokespeople
        # publish the latest useful investigation through the shared v15 API.
        return v16.message(obs, policy, rng, context, override)
    if context == 'day' and policy.response == 'counter':
        allies = teammates(obs)
        last = next(p for p in reversed(speech_order(obs)) if p in allies)
        outsiders = [m for m in _reports(obs) if m.speaker not in allies]
        if obs.player == last and outsiders:
            # Respond to visible claims; mafia never knows whether claimant is
            # a real police officer or a civilian impostor.
            return _make(obs, 'report', outsiders[-1].speaker, True)
    return v16.message(obs, policy, rng, context, override)

def after_speech(obs, policy, rng):
    """One optional structured extension at this actor's ordinary speech turn."""
    if isinstance(policy, GoodPolicyV17) and policy.flow == 'legacy':
        return None
    current = _shortlist(obs)
    if isinstance(policy, GoodPolicyV17):
        own_report = next((m for m in reversed(obs.messages) if m.day == obs.day
                           and m.speaker == obs.player and m.kind == 'report'), None)
        if obs.role == Role.POLICE and own_report is not None and current is None:
            ranked, scores = _rank(obs, policy)
            if not ranked:
                return None
            hit = any(r.is_mafia and r.target == ranked[0] for r in obs.investigations)
            size = 1 if hit else v16._list_size(policy, ranked, scores)
            return _make(obs, 'shortlist', targets=tuple(ranked[:size]))
        ranked, _ = _rank(obs, policy)
        if not ranked:
            return None
        # Only publicly cleared actors or a police claimant may propose a
        # binding reroute. Other actors state a cheap suspicion only.
        public_clear = any(not m.verdict and m.target == obs.player for m in _reports(obs))
        own_claim = any(m.speaker == obs.player for m in _reports(obs))
        kind = 'accuse' if current is not None and (public_clear or own_claim) else 'nominate'
        return _make(obs, kind, ranked[0])
    if current is None:
        return None
    allies = teammates(obs)
    pool = [p for p in speech_order(obs) if p not in allies]
    if not pool:
        return None
    # Redirect outside the list where possible; late counterclaimers and
    # publicly cleared mafia have the same public action channel as good.
    public_clear = any(not m.verdict and m.target == obs.player for m in _reports(obs))
    claimant = any(m.speaker == obs.player for m in _reports(obs))
    target = next((p for p in pool if p not in current.targets), pool[0])
    return _make(obs, 'accuse' if claimant or public_clear else 'nominate', target)

def final_call(obs, policy, rng):
    if isinstance(policy, GoodPolicyV17) and policy.flow == 'legacy':
        return v16.final_call(obs, policy, rng)
    return None

def preference(obs, policy, rng):
    if isinstance(policy, GoodPolicyV17) and policy.flow == 'legacy':
        return v16.preference(obs, policy, rng)
    return v16.preference(obs, policy, rng)

def final_selection(obs, policy, rng):
    if isinstance(policy, GoodPolicyV17) and policy.flow == 'legacy':
        return v16.final_selection(obs, policy, rng)
    return None

def _decision(obs, policy, pool):
    ranked, scores = _rank(obs, policy)
    private_hits = [r.target for r in obs.investigations if r.is_mafia and r.target in pool]
    if obs.role == Role.POLICE and private_hits:
        return private_hits[-1]
    current = _shortlist(obs)
    # Choose strongest source, then latest visible recommendation. Claims are
    # weighted as uncertain claims; no true-role lookup for civilians.
    proposals = []
    for index, m in enumerate(obs.messages):
        if m.day != obs.day or m.target not in pool or m.speaker == obs.player:
            continue
        if m.kind == 'report' and m.verdict:
            proposals.append((_credit(obs, m.speaker, policy), index, m.target))
        elif m.kind == 'accuse':
            proposals.append((_credit(obs, m.speaker, policy), index, m.target))
    proposals = [x for x in proposals if x[0] >= Fraction(3, 5)]
    if proposals:
        return max(proposals)[2]
    if current:
        listed = [p for p in current.targets if p in pool and p in ranked]
        if listed:
            return max(listed, key=lambda p: (scores[p], -ranked.index(p)))
    return next((p for p in ranked if p in pool), None)

def vote(obs, policy, rng, candidates=None):
    if isinstance(policy, GoodPolicyV17) and policy.flow == 'legacy':
        return v16.vote(obs, policy, rng, candidates)
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    if isinstance(policy, MafiaPolicyV17):
        allies = teammates(obs)
        legal = [p for p in pool if p not in allies]
        if not legal:
            return None
        allied_claims = [m.target for m in obs.messages if m.day == obs.day
                         and m.speaker in allies and m.kind in {'report', 'accuse'}
                         and m.target in legal]
        return allied_claims[-1] if allied_claims else legal[0]
    known = teammates(obs) if obs.role == Role.POLICE else {obs.player}
    if obs.role == Role.POLICE:
        known |= {r.target for r in obs.investigations if not r.is_mafia}
    return _decision(obs, policy, [p for p in pool if p not in known])
