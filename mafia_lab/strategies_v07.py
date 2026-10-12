"""v07 public-ballot decoration, public civilian rules and learned local tables."""
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from random import Random

from . import policies as base
from .engine import Message, Observation, PublicEvent, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4
from . import strategies_v05 as v5
from . import strategies_v06 as v6


def _probabilities(values, name, length):
    if len(values) != length or any(not isinstance(v, (int, float)) or
                                    not isfinite(v) or not 0 <= v <= 1 for v in values):
        raise ValueError(f"{name} must contain {length} finite probabilities")


@dataclass(frozen=True)
class GoodPolicyV7(v6.GoodPolicyV6):
    civilian_first_rule: str = "next"  # next, second, opposite, hashed
    conditional_cover_table: tuple[float, ...] = ()  # 1/2+ nominations x speech tercile
    conditional_police_table: tuple[float, ...] = ()  # speech tercile

    def __post_init__(self):
        # V7 adds ``table`` while retaining every V4/V5 contract.
        v5.GoodPolicyV5.__post_init__(self)
        if self.cover_mode not in {"public", "random", "local", "confirm", "table"}:
            raise ValueError("invalid cover mode")
        for name in ("local_public_probability", "inspect_reasoning_probability"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite probability")
        if self.police_nomination_mode not in {"random", "position", "table"}:
            raise ValueError("invalid police nomination mode")
        if self.day1_timing not in {"normal", "early", "late", "silent", "civilian_first"}:
            raise ValueError("invalid day-one timing")
        if self.civilian_first_rule not in {"next", "second", "opposite", "hashed"}:
            raise ValueError("invalid civilian-first rule")
        if self.cover_mode == "table":
            _probabilities(self.conditional_cover_table, "conditional_cover_table", 6)
        if self.police_nomination_mode == "table":
            _probabilities(self.conditional_police_table, "conditional_police_table", 3)


@dataclass(frozen=True)
class MafiaPolicyV7(v6.MafiaPolicyV6):
    def __post_init__(self):
        MafiaPolicy.__post_init__(self)
        if self.inference not in {"signals", "history", "votes", "combined", "origin"}:
            raise ValueError("unknown inference mode")
        v4._probability(self.nomination_probability, "nomination_probability")
        if self.vote_style not in {"coordinate", "split", "one_decoy", "late_decoy",
                                   "live_margin", "live_final"}:
            raise ValueError("invalid vote style")
        if self.nomination_style not in {"score", "bait_first"}:
            raise ValueError("invalid nomination style")


published_ballots = v6.published_ballots
good_history_scores = v6.good_history_scores
mafia_scores = v6.mafia_scores
choose_inspection = v6.choose_inspection
choose_kill = v6.choose_kill


def _tercile(obs: Observation) -> int:
    order = speech_order(obs)
    return min(2, 3 * order.index(obs.player) // len(order))


def _current_nominations(obs: Observation) -> Counter:
    return Counter(target for (day, _), target in v4._nominations(obs).items()
                   if day == obs.day and target in obs.alive and target != obs.player)


def civilian_rule_target(obs: Observation, rule: str) -> int | None:
    """Target derived only from the acting civilian's public observation."""
    order = speech_order(obs)
    if not order or order[0] != obs.player:
        return None
    pool = [p for p in obs.alive if p != obs.player]
    if not pool:
        return None
    if rule == "next":
        return next((p for p in order if p != obs.player), None)
    if rule == "second":
        ordered = [p for p in order if p != obs.player]
        return ordered[min(1, len(ordered) - 1)]
    if rule == "opposite":
        n = obs.rules.n_players
        anchor = (obs.player + n // 2) % n
        return min(pool, key=lambda p: (min((p - anchor) % n, (anchor - p) % n), p))
    material = f"{obs.day}/{obs.player}/{obs.last_anchor}/{','.join(map(str, obs.alive))}".encode()
    return pool[int.from_bytes(sha256(material).digest()[:8], "big") % len(pool)]


def _timed_message(obs: Observation, policy: GoodPolicyV7) -> Message | None:
    if obs.day != 1 or policy.day1_timing != "civilian_first":
        return None
    make = lambda kind, target=None: Message(obs.player, kind, target, None, "day", obs.day)
    if obs.role == Role.CIVILIAN:
        target = civilian_rule_target(obs, policy.civilian_first_rule)
        return make("nominate", target) if target is not None else make("civilian")
    if obs.role == Role.POLICE:
        hits = {r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive}
        public = {target for (day, _), target in v4._nominations(obs).items() if day == obs.day}
        aligned = sorted(hits & public)
        return make("nominate", aligned[0]) if aligned else make("civilian")
    return None


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if not isinstance(policy, GoodPolicyV7):
        return v6.message(obs, policy, rng, context, override)
    if override is not None or context != "day":
        return v6.message(obs, policy, rng, context, override)
    timed = _timed_message(obs, policy)
    if timed is not None:
        return timed
    make = lambda kind, target=None: Message(obs.player, kind, target, None, context, obs.day)
    if obs.role == Role.CIVILIAN and policy.cover_mode == "table":
        if rng.random() >= policy.civilian_cover_probability:
            return make("civilian")
        counts = _current_nominations(obs)
        if not counts:
            target = v6._random_target(obs, rng)
        else:
            bucket = 0 if max(counts.values()) == 1 else 1
            probability = policy.conditional_cover_table[3 * bucket + _tercile(obs)]
            target = (v6._public_target(obs, rng) if rng.random() < probability
                      else v6._random_target(obs, rng))
        return make("nominate", target) if target is not None else make("civilian")
    if (obs.role == Role.POLICE and policy.reveal == "covert" and
            policy.police_nomination_mode == "table"):
        hits = {r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive}
        probability = policy.hit_nominate_probability if hits else policy.conditional_police_table[_tercile(obs)]
        if rng.random() >= probability:
            return make("civilian")
        target = base._covert_target(obs)
        return make("nominate", target) if target is not None else make("civilian")
    return v6.message(obs, policy, rng, context, override)


def live_ballots(obs: Observation, pk: bool = False) -> dict[int, int | None]:
    kind = "live_pk_vote" if pk else "live_vote"
    return {event.player: event.ballots[0][1] for event in obs.public_events
            if event.kind == kind and event.day == obs.day and event.player is not None}


def _unique_leader(ballots, target) -> bool:
    counts = Counter(value for value in ballots.values() if value is not None)
    return bool(counts) and counts[target] > max((count for player, count in counts.items()
                                                 if player != target), default=0)


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if not isinstance(policy, MafiaPolicyV7) or policy.vote_style not in {"live_margin", "live_final"}:
        return v6.vote(obs, policy, rng, candidates)
    if obs.role != Role.MAFIA:
        raise TypeError("MafiaPolicyV7 needs a mafia observation")
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player and p not in base.teammates(obs)]
    if not pool:
        return None
    scores = v5._mafia_vote_scores(obs, policy, pool)
    ordered = sorted(pool, key=lambda p: (-scores[p], p))
    main = ordered[0]
    if len(ordered) == 1:
        return main
    order = [p for p in speech_order(obs) if p in obs.alive]
    allies = [p for p in order if p in base.teammates(obs)]
    ballots = live_ballots(obs, pk=candidates is not None)
    if not ballots or obs.player != allies[-1]:
        return main
    if policy.vote_style == "live_final" and obs.player != order[-1]:
        return main
    proposed = {**ballots, obs.player: ordered[1]}
    return ordered[1] if _unique_leader(proposed, main) else main
