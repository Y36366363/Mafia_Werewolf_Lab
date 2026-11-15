"""v06 local mixtures, anti-bait cover and limited mafia ballot disguise.

Every mixture is sampled by the acting player from the runner-supplied local
decision RNG, or determined by that player's public speech position.  No secret
faction-wide strategy index is available.  Day-one timing interventions use
only police private checks or an explicitly public civilian rule.
"""
from collections import Counter
from dataclasses import dataclass, replace
from math import isfinite
from random import Random

from . import policies as base
from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4
from . import strategies_v05 as v5


@dataclass(frozen=True)
class GoodPolicyV6(v5.GoodPolicyV5):
    cover_mode: str = "public"  # public, random, local, confirm
    local_public_probability: float = 0.75
    inspect_reasoning_probability: float = 0.0
    police_nomination_mode: str = "random"  # random, position
    day1_timing: str = "normal"  # normal, early, late, silent, civilian_first

    def __post_init__(self):
        super().__post_init__()
        if self.cover_mode not in {"public", "random", "local", "confirm"}:
            raise ValueError("invalid cover mode")
        for name in ("local_public_probability", "inspect_reasoning_probability"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite probability")
        if self.police_nomination_mode not in {"random", "position"}:
            raise ValueError("invalid police nomination mode")
        if self.day1_timing not in {"normal", "early", "late", "silent", "civilian_first"}:
            raise ValueError("invalid day-one timing")


@dataclass(frozen=True)
class MafiaPolicyV6(v5.MafiaPolicyV5):
    nomination_style: str = "score"  # score, bait_first

    def __post_init__(self):
        MafiaPolicy.__post_init__(self)
        if self.inference not in {"signals", "history", "votes", "combined", "origin"}:
            raise ValueError("unknown inference mode")
        v4._probability(self.nomination_probability, "nomination_probability")
        if self.vote_style not in {"coordinate", "split", "one_decoy", "late_decoy"}:
            raise ValueError("invalid vote style")
        if self.nomination_style not in {"score", "bait_first"}:
            raise ValueError("invalid nomination style")


published_ballots = v5.published_ballots
good_history_scores = v5.good_history_scores
mafia_scores = v5.mafia_scores


def _public_target(obs: Observation, rng: Random, minimum: int = 1) -> int | None:
    pool = [p for p in obs.alive if p != obs.player]
    nominations = v4._nominations(obs)
    counts = Counter(target for (day, speaker), target in nominations.items()
                     if day == obs.day and speaker != obs.player and target in pool)
    eligible = {target: count for target, count in counts.items() if count >= minimum}
    return base.choose_best(eligible, rng)


def _random_target(obs: Observation, rng: Random) -> int | None:
    pool = [p for p in obs.alive if p != obs.player]
    return rng.choice(pool) if pool else None


def _civilian_target(obs: Observation, policy: GoodPolicyV6, rng: Random) -> int | None:
    if policy.cover_mode == "random":
        return _random_target(obs, rng)
    if policy.cover_mode == "local":
        if policy.local_public_probability == 0:
            return _random_target(obs, rng)
        if policy.local_public_probability < 1 and rng.random() >= policy.local_public_probability:
            return _random_target(obs, rng)
        return _public_target(obs, rng) or _random_target(obs, rng)
    if policy.cover_mode == "confirm":
        return _public_target(obs, rng, minimum=2) or _random_target(obs, rng)
    return _public_target(obs, rng) or next(
        (p for p in speech_order(obs) if p != obs.player and p in obs.alive), None)


def civilian_first_alignment(obs: Observation) -> int | None:
    """Legal public target for the first speaker; independent of hidden roles/checks."""
    order = speech_order(obs)
    if not order or order[0] != obs.player:
        return None
    return next((p for p in order if p != obs.player), None)


def choose_inspection(obs: Observation, policy: GoodPolicy, rng: Random) -> int:
    if not isinstance(policy, GoodPolicyV6):
        return v5.choose_inspection(obs, policy, rng)
    if policy.inspect_reasoning or policy.inspect_reasoning_probability == 1:
        use_history = True
    elif policy.inspect_reasoning_probability == 0:
        use_history = False
    else:
        use_history = rng.random() < policy.inspect_reasoning_probability
    return v5.choose_inspection(obs, replace(policy, inspect_reasoning=use_history), rng)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    return v5.choose_kill(obs, policy, rng)


def _timed_message(obs: Observation, policy: GoodPolicyV6) -> Message | None:
    if obs.day != 1 or policy.day1_timing == "normal":
        return None
    make = lambda kind, target=None: Message(obs.player, kind, target, None, "day", obs.day)
    live_hits = [r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive]
    if obs.role == Role.CIVILIAN:
        if policy.day1_timing == "civilian_first":
            target = civilian_first_alignment(obs)
            if target is not None:
                return make("nominate", target)
        return make("civilian")
    if obs.role != Role.POLICE:
        return None
    if not live_hits or policy.day1_timing == "silent":
        return make("civilian")
    target = live_hits[0]
    team_order = [p for p in speech_order(obs) if p in base.teammates(obs) and p in obs.alive]
    if policy.day1_timing == "early":
        return make("nominate", target)
    if policy.day1_timing == "late":
        return make("nominate", target) if obs.player == team_order[-1] else make("civilian")
    # In the legal-alignment cohort, police follow only after the public target
    # already matches their private hit.  No target is communicated to civilians.
    public = v4._nominations(obs)
    aligned = any(day == obs.day and nominated == target for (day, _), nominated in public.items())
    return make("nominate", target) if aligned else make("civilian")


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV6):
        if override is None and context == "day":
            timed = _timed_message(obs, policy)
            if timed is not None:
                return timed
        if override is not None:
            return v5.message(obs, policy, rng, context, override)
        if context != "day":
            return v5.message(obs, policy, rng, context)
        make = lambda kind, target=None: Message(obs.player, kind, target, None, context, obs.day)
        if obs.role == Role.POLICE and policy.reveal == "covert":
            live_hits = {r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive}
            probability = policy.hit_nominate_probability if live_hits else policy.police_nominate_probability
            if policy.police_nomination_mode == "position" and not live_hits:
                order = speech_order(obs)
                nominate = (order.index(obs.player) + 0.5) / len(order) < probability
            else:
                nominate = rng.random() < probability
            if not nominate:
                return make("civilian")
            target = base._covert_target(obs)
            return make("nominate", target) if target is not None else make("civilian")
        if obs.role == Role.CIVILIAN:
            if rng.random() >= policy.civilian_cover_probability:
                return make("civilian")
            target = _civilian_target(obs, policy, rng)
            return make("nominate", target) if target is not None else make("civilian")
        return v5.message(obs, policy, rng, context)
    if not isinstance(policy, MafiaPolicyV6):
        return v5.message(obs, policy, rng, context, override)
    if override is not None or policy.nomination_style == "score" or policy.bluff != "nominate":
        return v5.message(obs, policy, rng, context, override)
    make = lambda kind, target=None: Message(obs.player, kind, target, None, context, obs.day)
    if rng.random() >= policy.nomination_probability:
        return make("civilian")
    allies = [p for p in speech_order(obs) if p in base.teammates(obs) and p in obs.alive]
    scores = mafia_scores(obs, policy)
    if obs.player == allies[0] and scores:
        minimum = min(scores.values())
        target = rng.choice(sorted(p for p, score in scores.items() if score == minimum))
    else:
        target = base.choose_best(scores, rng)
    return make("nominate", target) if target is not None else make("civilian")


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if not isinstance(policy, MafiaPolicyV6):
        return v5.vote(obs, policy, rng, candidates)
    if obs.role != Role.MAFIA:
        raise TypeError("MafiaPolicyV6 needs a mafia observation")
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player and p not in base.teammates(obs)]
    if not pool:
        return None
    scores = v5._mafia_vote_scores(obs, policy, pool)
    if policy.vote_style in {"coordinate", "split"}:
        return v5.vote(obs, policy, rng, candidates)
    ordered = sorted(pool, key=lambda p: (-scores[p], p))
    if len(ordered) == 1:
        return ordered[0]
    allies = [p for p in speech_order(obs) if p in base.teammates(obs) and p in obs.alive]
    decoy = (obs.player == max(allies) if policy.vote_style == "one_decoy"
             else obs.player == allies[-1])
    return ordered[1] if decoy else ordered[0]
