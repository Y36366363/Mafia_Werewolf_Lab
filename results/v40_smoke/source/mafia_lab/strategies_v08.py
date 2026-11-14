"""v08 common mafia tie breaks and public multi-probe civilian openings."""
from collections import Counter
from dataclasses import dataclass
from math import isfinite
from random import Random

from . import policies as base
from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4
from . import strategies_v05 as v5
from . import strategies_v07 as v7


PROBE_RULES = {"next", "second", "opposite", "hashed", "cycle"}


@dataclass(frozen=True)
class GoodPolicyV8(v7.GoodPolicyV7):
    probe_window: int = 1
    probe_pattern: tuple[str, ...] = ("next",)

    def __post_init__(self):
        super().__post_init__()
        if type(self.probe_window) is not int or not 1 <= self.probe_window <= 16:
            raise ValueError("probe_window must be between 1 and 16")
        if not self.probe_pattern or any(rule not in PROBE_RULES for rule in self.probe_pattern):
            raise ValueError("invalid probe pattern")


@dataclass(frozen=True)
class MafiaPolicyV8(v7.MafiaPolicyV7):
    def __post_init__(self):
        MafiaPolicy.__post_init__(self)
        if self.inference not in {"signals", "history", "votes", "combined", "origin"}:
            raise ValueError("unknown inference mode")
        v4._probability(self.nomination_probability, "nomination_probability")
        if self.vote_style not in {"deterministic", "deterministic_one_decoy",
                                   "deterministic_live_margin", "deterministic_live_final"}:
            raise ValueError("invalid v08 vote style")
        if self.nomination_style not in {"score", "bait_first"}:
            raise ValueError("invalid nomination style")


published_ballots = v7.published_ballots
good_history_scores = v7.good_history_scores
mafia_scores = v7.mafia_scores
choose_inspection = v7.choose_inspection
choose_kill = v7.choose_kill
live_ballots = v7.live_ballots


def deterministic_mafia_ranking(obs: Observation, policy: MafiaPolicyV8,
                                candidates: tuple[int, ...] | None = None) -> list[int]:
    """Common ranking: score, then public speech order, then seat.

    Every living mafia member has the same public history and reconstructs the
    same full teammate set, so no actor-keyed RNG or private identity outside
    the faction enters the tie break.
    """
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p not in base.teammates(obs)]
    scores = v5._mafia_vote_scores(obs, policy, pool)
    rank = {player: i for i, player in enumerate(speech_order(obs))}
    return sorted(pool, key=lambda p: (-scores[p], rank.get(p, len(rank)), p))


def public_probe_target(obs: Observation, rule: str) -> int | None:
    order = speech_order(obs)
    if obs.player not in order:
        return None
    rotated = order[order.index(obs.player):] + order[:order.index(obs.player)]
    pool = [p for p in rotated if p != obs.player]
    if not pool:
        return None
    if rule == "cycle":
        anchor = obs.last_anchor if obs.last_anchor is not None else 0
        rule = ("next", "second", "opposite", "hashed")[(obs.player + anchor) % 4]
    if rule == "next":
        return pool[0]
    if rule == "second":
        return pool[min(1, len(pool) - 1)]
    if rule == "opposite":
        n = obs.rules.n_players
        anchor = (obs.player + n // 2) % n
        return min(pool, key=lambda p: (min((p-anchor) % n, (anchor-p) % n), p))
    return v7.civilian_rule_target(obs, "hashed") if order[0] == obs.player else _hashed_probe(obs, pool)


def _hashed_probe(obs: Observation, pool: list[int]) -> int:
    # Reuse v07's stable public material while permitting a later speaker.
    from hashlib import sha256
    material = f"{obs.day}/{obs.player}/{obs.last_anchor}/{','.join(map(str, obs.alive))}".encode()
    return pool[int.from_bytes(sha256(material).digest()[:8], "big") % len(pool)]


def _probe_message(obs: Observation, policy: GoodPolicyV8) -> Message | None:
    if obs.day != 1 or policy.day1_timing != "civilian_first":
        return None
    make = lambda kind, target=None: Message(obs.player, kind, target, None, "day", obs.day)
    if obs.role == Role.CIVILIAN:
        order = speech_order(obs)
        rank = order.index(obs.player)
        if rank >= policy.probe_window:
            return make("civilian")
        rule = policy.probe_pattern[rank % len(policy.probe_pattern)]
        target = public_probe_target(obs, rule)
        return make("nominate", target) if target is not None else make("civilian")
    if obs.role == Role.POLICE:
        hits = {r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive}
        public = {target for (day, _), target in v4._nominations(obs).items() if day == obs.day}
        aligned = sorted(hits & public)
        return make("nominate", aligned[0]) if aligned else make("civilian")
    return None


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV8) and override is None and context == "day":
        result = _probe_message(obs, policy)
        if result is not None:
            return result
    return v7.message(obs, policy, rng, context, override)


def _unique_leader(ballots, target) -> bool:
    counts = Counter(value for value in ballots.values() if value is not None)
    return bool(counts) and counts[target] > max((count for player, count in counts.items()
                                                 if player != target), default=0)


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if not isinstance(policy, MafiaPolicyV8):
        return v7.vote(obs, policy, rng, candidates)
    if obs.role != Role.MAFIA:
        raise TypeError("MafiaPolicyV8 needs a mafia observation")
    ordered = deterministic_mafia_ranking(obs, policy, candidates)
    if not ordered:
        return None
    main = ordered[0]
    if len(ordered) == 1 or policy.vote_style == "deterministic":
        return main
    order = list(speech_order(obs))
    allies = [p for p in order if p in base.teammates(obs) and p in obs.alive]
    if obs.player != allies[-1]:
        return main
    if policy.vote_style == "deterministic_one_decoy":
        return ordered[1]
    ballots = live_ballots(obs, pk=candidates is not None)
    if not ballots:
        return main
    if policy.vote_style == "deterministic_live_final" and obs.player != order[-1]:
        return main
    proposed = {**ballots, obs.player: ordered[1]}
    return ordered[1] if _unique_leader(proposed, main) else main
