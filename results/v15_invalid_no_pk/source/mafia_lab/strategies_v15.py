"""v15 living-police leadership, basic PK, and legal position inference.

The first-night survivor branch may appoint one living police spokesperson.
The spokesperson reports the shared inspection during ordinary speech and may
publish a post-speech shortlist.  A position-aware shortlist uses an exact
Bayesian likelihood over mafia seat sets, conditioned only on the public night
victim, the police team's privately known seats, and the reported clear.

No policy is told the realized opponent policy or any civilian/mafia label it
could not legally know.  The position prior is a frozen public equal mixture
of random, safe-middle, safe-late, and safe-mix kill rules.
"""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from fractions import Fraction
from itertools import combinations
from random import Random

from .engine import Message, Observation, Role, speech_order
from .policies import teammates
from .strategies_v13 import GoodPolicyV13, _order_after
from .strategies_v14 import MafiaPolicyV14, _geometry_score
from . import strategies_v13 as v13
from . import strategies_v14 as v14


LEADERSHIP = {"hidden", "report", "nominate", "pk"}
POSITION_MODELS = {"naive", "posterior"}
META_KILLS = ("random", "safe_middle", "safe_late", "safe_mix")
SAFE_COMPONENTS = (
    "safe_front", "safe_middle", "safe_late", "safe_sandwich", "safe_balanced"
)


@dataclass(frozen=True)
class GoodPolicyV15(GoodPolicyV13):
    leadership: str = "hidden"
    position_model: str = "naive"

    def __post_init__(self):
        super().__post_init__()
        if self.leadership not in LEADERSHIP:
            raise ValueError("invalid leadership protocol")
        if self.position_model not in POSITION_MODELS:
            raise ValueError("invalid position model")
        if self.leadership in {"hidden", "report"} and self.position_model != "naive":
            raise ValueError("position model needs a nomination protocol")


def choose_inspection(obs: Observation, policy: GoodPolicyV15, rng: Random) -> int:
    return v13.choose_inspection(obs, policy, rng)


def choose_kill(obs: Observation, policy: MafiaPolicyV14, rng: Random) -> int:
    return v14.choose_kill(obs, policy, rng)


def _first_victim(obs: Observation) -> int | None:
    return obs.deaths[0].player if obs.deaths else None


def _living_leader(obs: Observation) -> int | None:
    team = teammates(obs).intersection(obs.alive)
    return next((p for p in speech_order(obs) if p in team), None)


def _leadership_eligible(obs: Observation, policy: GoodPolicyV15) -> bool:
    victim = _first_victim(obs)
    return (
        policy.leadership != "hidden" and obs.day == 1 and victim is not None
        and victim not in teammates(obs) and obs.player == _living_leader(obs)
    )


def _latest_report(obs: Observation):
    live_hits = [r for r in obs.investigations if r.is_mafia and r.target in obs.alive]
    return live_hits[-1] if live_hits else (obs.investigations[-1]
                                           if obs.investigations else None)


def message(obs: Observation, policy: GoodPolicyV15 | MafiaPolicyV14, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV15) and obs.role == Role.POLICE:
        if context == "day" and _leadership_eligible(obs, policy):
            report = _latest_report(obs)
            if report is not None:
                return Message(obs.player, "report", report.target, report.is_mafia,
                               context, obs.day)
        # Other day-one living police stay hidden.  Dead-police words and the
        # shared later-game continuation retain the v13 behavior.
    return v13.message(obs, policy, rng, context, override)


def _order_from_victim(n: int, direction: int, victim: int) -> tuple[int, ...]:
    return tuple((victim + direction * step) % n for step in range(1, n + 1)
                 if (victim + direction * step) % n != victim)


@lru_cache(maxsize=None)
def _mode_probability(n: int, direction: int, victim: int,
                      mafia: frozenset[int], mode: str) -> Fraction:
    pool = [p for p in range(n) if p not in mafia]
    if victim not in pool:
        return Fraction(0)
    if mode == "random":
        return Fraction(1, len(pool))
    if mode == "safe_mix":
        return sum((_mode_probability(n, direction, victim, mafia, component)
                    for component in SAFE_COMPONENTS), Fraction(0)) / len(SAFE_COMPONENTS)
    scores = {}
    for target in pool:
        order = tuple(p for p in _order_from_victim(n, direction, target)
                      if p != target)
        scores[target] = _geometry_score(mode, order, set(mafia))
    best = max(scores.values())
    winners = [p for p, score in scores.items() if score == best]
    return Fraction(1, len(winners)) if victim in winners else Fraction(0)


@lru_cache(maxsize=None)
def _posterior_cached(n: int, mafia_count: int, direction: int, victim: int,
                      known_good: tuple[int, ...]) -> tuple[Fraction, ...]:
    excluded = set(known_good) | {victim}
    possible = [p for p in range(n) if p not in excluded]
    weights: list[tuple[frozenset[int], Fraction]] = []
    for seats in combinations(possible, mafia_count):
        mafia = frozenset(seats)
        likelihood = sum((_mode_probability(n, direction, victim, mafia, mode)
                          for mode in META_KILLS), Fraction(0)) / len(META_KILLS)
        if likelihood:
            weights.append((mafia, likelihood))
    total = sum((weight for _, weight in weights), Fraction(0))
    if not total:
        return tuple(Fraction(0) for _ in range(n))
    return tuple(sum((weight for mafia, weight in weights if seat in mafia), Fraction(0)) / total
                 for seat in range(n))


def position_posterior(obs: Observation, known_good: set[int]) -> dict[int, Fraction]:
    """Return legal seat-level mafia probabilities for the day-one leader."""
    victim = _first_victim(obs)
    if victim is None:
        return {p: Fraction(0) for p in range(obs.rules.n_players)}
    values = _posterior_cached(obs.rules.n_players, obs.rules.mafia,
                               obs.rules.direction, victim, tuple(sorted(known_good)))
    return {p: values[p] for p in range(obs.rules.n_players)}


def _nominees(obs: Observation, policy: GoodPolicyV15) -> tuple[int, ...]:
    report = _latest_report(obs)
    if report is None:
        return ()
    if report.is_mafia and report.target in obs.alive:
        return (report.target,)
    known_good = teammates(obs)
    if not report.is_mafia:
        known_good.add(report.target)
    eligible = [p for p in speech_order(obs)
                if p in obs.alive and p not in known_good]
    count = 2 if policy.leadership == "pk" else 1
    if policy.position_model == "naive":
        return tuple(eligible[:count])
    posterior = position_posterior(obs, known_good)
    rank = {p: i for i, p in enumerate(speech_order(obs))}
    eligible.sort(key=lambda p: (-posterior[p], rank[p]))
    return tuple(eligible[:count])


def final_call(obs: Observation, policy: GoodPolicyV15 | MafiaPolicyV14,
               rng: Random) -> Message | None:
    if (not isinstance(policy, GoodPolicyV15) or obs.role != Role.POLICE
            or policy.leadership not in {"nominate", "pk"}
            or not _leadership_eligible(obs, policy)):
        return None
    targets = _nominees(obs, policy)
    if not targets:
        return None
    return Message(obs.player, "shortlist", context="day", day=obs.day,
                   targets=targets)


def _latest_day_shortlist(obs: Observation) -> Message | None:
    rows = [m for m in obs.messages if m.kind == "shortlist" and m.day == obs.day
            and m.context == "day"]
    return rows[-1] if rows else None


def _accepted_live_report(obs: Observation) -> Message | None:
    rows = [m for m in obs.messages if m.kind == "report" and m.day == obs.day
            and m.context == "day" and m.speaker in obs.alive]
    return rows[-1] if rows else None


def _published_counts(obs: Observation, *, pk: bool) -> Counter:
    kind = "live_pk_vote" if pk else "live_vote"
    return Counter(event.ballots[0][1] for event in obs.public_events
                   if event.kind == kind and event.day == obs.day
                   and event.ballots and event.ballots[0][1] is not None)


def _least_supported(obs: Observation, pool: list[int], rng: Random, *, pk: bool) -> int:
    counts = _published_counts(obs, pk=pk)
    minimum = min(counts[p] for p in pool)
    tied = [p for p in pool if counts[p] == minimum]
    # Public seat/order tie break avoids a faction-secret coordination device.
    order = {p: i for i, p in enumerate(speech_order(obs))}
    return min(tied, key=lambda p: order.get(p, p))


def vote(obs: Observation, policy: GoodPolicyV15 | MafiaPolicyV14, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    shortlist = _latest_day_shortlist(obs)
    pk = candidates is not None
    if isinstance(policy, MafiaPolicyV14):
        if shortlist is not None:
            preferred = [p for p in shortlist.targets if p in pool
                         and p not in teammates(obs)]
            if preferred:
                counts = _published_counts(obs, pk=pk)
                maximum = max(counts[p] for p in preferred)
                return next(p for p in shortlist.targets
                            if p in preferred and counts[p] == maximum)
        return v13.vote(obs, policy, rng, candidates)
    if not isinstance(policy, GoodPolicyV15):
        raise TypeError("unknown v15 policy")
    if shortlist is not None:
        listed = [p for p in shortlist.targets if p in pool]
        if listed:
            if obs.role == Role.POLICE:
                hits = [r.target for r in obs.investigations
                        if r.is_mafia and r.target in listed]
                if hits:
                    return hits[-1]
            return listed[0] if len(listed) == 1 else _least_supported(
                obs, listed, rng, pk=pk)
    if policy.leadership != "hidden":
        report = _accepted_live_report(obs)
        if report is not None:
            if report.verdict and report.target in pool:
                return report.target
            if not report.verdict:
                pool = [p for p in pool if p != report.target]
                if not pool:
                    return None
                return next((p for p in speech_order(obs) if p in pool), pool[0])
    return v13.vote(obs, policy, rng, candidates)
