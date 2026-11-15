"""v16 robust position beliefs, variable shortlists, and posterior camouflage.

Good policies compare an equal-model Bayesian posterior with a maximin score:
for each seat, take the lowest posterior probability across safe-middle,
safe-late, and a frozen posterior-decoy model.  Each assumed kill model has a
2% uniform tremble, giving every legal public death positive likelihood.

Mafia policies include a deliberate middle/late mixture and a decoy kill that
uses only mafia seats to choose a safe-anchor victim that minimizes the total
v15 public posterior mass on the real mafia team.  It never reads police or
civilian labels.
"""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from fractions import Fraction
from itertools import combinations
from random import Random

from .engine import Message, Observation, Role, speech_order
from .policies import teammates
from .strategies_v12 import MafiaPolicyV12
from .strategies_v13 import GoodPolicyV13, _order_after
from .strategies_v14 import _geometry_score
from .strategies_v15 import GoodPolicyV15, _posterior_cached as v15_public_model
from . import strategies_v13 as v13
from . import strategies_v15 as v15


KILL_MODES = {"random", "safe_middle", "safe_late", "middle_late_mix", "posterior_decoy"}
PRIOR_MODELS = {"equal", "robust"}
SHORTLIST_RULES = {"hard1", "list2", "list3", "adaptive"}
ROBUST_VERTICES = ("safe_middle", "safe_late", "posterior_decoy")
EQUAL_COMPONENTS = ("safe_middle", "safe_late", "middle_late_mix", "posterior_decoy")
TREMBLE = Fraction(1, 50)


@dataclass(frozen=True)
class GoodPolicyV16(GoodPolicyV15):
    prior_model: str = "equal"
    shortlist_rule: str = "hard1"

    def __post_init__(self):
        super().__post_init__()
        if self.leadership != "nominate" or self.position_model != "posterior":
            raise ValueError("v16 requires living report plus posterior nomination")
        if self.prior_model not in PRIOR_MODELS:
            raise ValueError("invalid prior model")
        if self.shortlist_rule not in SHORTLIST_RULES:
            raise ValueError("invalid shortlist rule")


@dataclass(frozen=True)
class MafiaPolicyV16(MafiaPolicyV12):
    kill_mode: str = "safe_late"

    def __post_init__(self):
        super().__post_init__()
        if self.opening_mode != "ordinary":
            raise ValueError("v16 excludes self-kill")
        if self.kill_mode not in KILL_MODES:
            raise ValueError("invalid v16 kill mode")


def choose_inspection(obs: Observation, policy: GoodPolicyV16, rng: Random) -> int:
    return v13.choose_inspection(obs, policy, rng)


def _order(n: int, direction: int, victim: int) -> tuple[int, ...]:
    return tuple((victim + direction * step) % n for step in range(1, n + 1)
                 if (victim + direction * step) % n != victim)


@lru_cache(maxsize=None)
def _decoy_score(n: int, direction: int, victim: int,
                 mafia: frozenset[int]):
    posterior = v15_public_model(n, len(mafia), direction, victim, ())
    exposure = sum((posterior[p] for p in mafia), Fraction(0))
    order = _order(n, direction, victim)
    safe_anchor = int(order[0] not in mafia)
    late = sum(p in mafia for p in order[-4:])
    # First protect the non-mafia public anchor, then minimize the frozen v15
    # model's belief in the true team; late control breaks exact score ties.
    return safe_anchor, -exposure, late


@lru_cache(maxsize=None)
def kill_probability(n: int, direction: int, victim: int,
                     mafia: frozenset[int], mode: str) -> Fraction:
    pool = [p for p in range(n) if p not in mafia]
    if victim not in pool:
        return Fraction(0)
    if mode == "random":
        return Fraction(1, len(pool))
    if mode == "middle_late_mix":
        return (kill_probability(n, direction, victim, mafia, "safe_middle")
                + kill_probability(n, direction, victim, mafia, "safe_late")) / 2
    scores = {}
    for target in pool:
        order = _order(n, direction, target)
        if mode == "posterior_decoy":
            scores[target] = _decoy_score(n, direction, target, mafia)
        else:
            scores[target] = _geometry_score(mode, order, set(mafia))
    maximum = max(scores.values())
    winners = [p for p, score in scores.items() if score == maximum]
    return Fraction(1, len(winners)) if victim in winners else Fraction(0)


def _best_victim(obs: Observation, mode: str, rng: Random) -> int:
    mafia = frozenset(teammates(obs).intersection(obs.alive))
    pool = [p for p in obs.alive if p not in mafia]
    scores = {}
    for victim in pool:
        order = _order_after(obs, victim)
        if mode == "posterior_decoy":
            scores[victim] = _decoy_score(obs.rules.n_players, obs.rules.direction,
                                          victim, mafia)
        else:
            scores[victim] = _geometry_score(mode, order, set(mafia))
    maximum = max(scores.values())
    return rng.choice(sorted(p for p, score in scores.items() if score == maximum))


def choose_kill(obs: Observation, policy: MafiaPolicyV16, rng: Random) -> int:
    if obs.role != Role.MAFIA:
        raise ValueError("only mafia can kill")
    allies = teammates(obs).intersection(obs.alive)
    pool = [p for p in obs.alive if p not in allies]
    claimants = {m.speaker for m in obs.messages if m.kind in {"police", "report"}}
    live_claimants = [p for p in pool if p in claimants]
    if live_claimants:
        return rng.choice(sorted(live_claimants))
    mode = policy.kill_mode
    if mode == "random":
        return rng.choice(pool)
    # The frozen decoy model describes the public first-night victim only.
    # Once that signal has been emitted, later unclaimed nights use the strong
    # late-control continuation instead of applying a stale opening posterior
    # to a state with earlier deaths.
    if mode == "posterior_decoy" and obs.day > 0:
        mode = "safe_late"
    if mode == "middle_late_mix":
        mode = rng.choice(["safe_middle", "safe_late"])
    return _best_victim(obs, mode, rng)


def _assumed_likelihood(n: int, direction: int, victim: int,
                        mafia: frozenset[int], mode: str) -> Fraction:
    uniform = kill_probability(n, direction, victim, mafia, "random")
    structural = kill_probability(n, direction, victim, mafia, mode)
    return (1 - TREMBLE) * structural + TREMBLE * uniform


@lru_cache(maxsize=None)
def _posterior_for_mode(n: int, mafia_count: int, direction: int, victim: int,
                        known_good: tuple[int, ...], mode: str) -> tuple[Fraction, ...]:
    excluded = set(known_good) | {victim}
    possible = [p for p in range(n) if p not in excluded]
    weighted = []
    for seats in combinations(possible, mafia_count):
        mafia = frozenset(seats)
        if mode == "equal":
            likelihood = sum((_assumed_likelihood(n, direction, victim, mafia, component)
                              for component in EQUAL_COMPONENTS), Fraction(0)) / len(EQUAL_COMPONENTS)
        else:
            likelihood = _assumed_likelihood(n, direction, victim, mafia, mode)
        weighted.append((mafia, likelihood))
    total = sum((weight for _, weight in weighted), Fraction(0))
    return tuple(sum((weight for mafia, weight in weighted if seat in mafia), Fraction(0)) / total
                 for seat in range(n))


def seat_scores(obs: Observation, known_good: set[int], prior_model: str) -> dict[int, Fraction]:
    victim = obs.deaths[0].player
    args = (obs.rules.n_players, obs.rules.mafia, obs.rules.direction,
            victim, tuple(sorted(known_good)))
    if prior_model == "equal":
        values = _posterior_for_mode(*args, "equal")
    else:
        vertices = [_posterior_for_mode(*args, mode) for mode in ROBUST_VERTICES]
        values = tuple(min(row[p] for row in vertices)
                       for p in range(obs.rules.n_players))
    return {p: values[p] for p in range(obs.rules.n_players)}


def _latest_report(obs: Observation):
    return v15._latest_report(obs)


def _leader(obs: Observation) -> int | None:
    return v15._living_leader(obs)


def _eligible_leader(obs: Observation, policy: GoodPolicyV16) -> bool:
    return v15._leadership_eligible(obs, policy)


def message(obs: Observation, policy: GoodPolicyV16 | MafiaPolicyV16, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV16):
        return v15.message(obs, policy, rng, context, override)
    return v13.message(obs, policy, rng, context, override)


def _private_known_good(obs: Observation) -> set[int]:
    known = teammates(obs) if obs.role == Role.POLICE else {obs.player}
    report = _latest_report(obs) if obs.role == Role.POLICE else next(
        (m for m in reversed(obs.messages) if m.kind == "report" and m.day == obs.day), None)
    if report is not None:
        verdict = report.is_mafia if hasattr(report, "is_mafia") else report.verdict
        if not verdict and report.target is not None:
            known.add(report.target)
    return known


def _ranked_candidates(obs: Observation, policy: GoodPolicyV16):
    report = _latest_report(obs)
    if report is None:
        return [], {}
    if report.is_mafia and report.target in obs.alive:
        return [report.target], {report.target: Fraction(1)}
    known = _private_known_good(obs)
    scores = seat_scores(obs, known, policy.prior_model)
    order = {p: i for i, p in enumerate(speech_order(obs))}
    pool = [p for p in obs.alive if p not in known]
    pool.sort(key=lambda p: (-scores[p], order.get(p, p)))
    return pool, scores


def _list_size(policy: GoodPolicyV16, ranked: list[int], scores: dict[int, Fraction]) -> int:
    if policy.shortlist_rule == "hard1":
        return 1
    if policy.shortlist_rule == "list2":
        return min(2, len(ranked))
    if policy.shortlist_rule == "list3":
        return min(3, len(ranked))
    if len(ranked) < 2 or scores[ranked[0]] - scores[ranked[1]] >= Fraction(1, 10):
        return 1
    if len(ranked) < 3 or scores[ranked[1]] - scores[ranked[2]] >= Fraction(1, 20):
        return 2
    return 3


def final_call(obs: Observation, policy: GoodPolicyV16 | MafiaPolicyV16,
               rng: Random) -> Message | None:
    if (not isinstance(policy, GoodPolicyV16) or obs.role != Role.POLICE
            or not _eligible_leader(obs, policy)):
        return None
    ranked, scores = _ranked_candidates(obs, policy)
    if not ranked:
        return None
    size = _list_size(policy, ranked, scores)
    return Message(obs.player, "shortlist", context="day", day=obs.day,
                   targets=tuple(ranked[:size]))


def _latest_shortlist(obs: Observation) -> Message | None:
    return next((m for m in reversed(obs.messages)
                 if m.kind == "shortlist" and m.day == obs.day and m.context == "day"), None)


def _preferences_after_shortlist(obs: Observation) -> list[Message]:
    index = next((i for i in range(len(obs.messages) - 1, -1, -1)
                  if obs.messages[i].kind == "shortlist" and obs.messages[i].day == obs.day), None)
    if index is None:
        return []
    return [m for m in obs.messages[index + 1:] if m.kind == "nominate" and m.day == obs.day]


def preference(obs: Observation, policy: GoodPolicyV16 | MafiaPolicyV16,
               rng: Random) -> Message | None:
    shortlist = _latest_shortlist(obs)
    if shortlist is None or len(shortlist.targets) <= 1:
        return None
    pool = [p for p in shortlist.targets if p != obs.player and p in obs.alive]
    if not pool:
        return None
    if isinstance(policy, MafiaPolicyV16):
        nonallies = [p for p in pool if p not in teammates(obs)]
        pool = nonallies or pool
        counts = Counter(m.target for m in _preferences_after_shortlist(obs))
        target = max(pool, key=lambda p: (counts[p], -shortlist.targets.index(p)))
    else:
        known = _private_known_good(obs)
        scores = seat_scores(obs, known, policy.prior_model)
        target = max(pool, key=lambda p: (scores[p], -shortlist.targets.index(p)))
    return Message(obs.player, "nominate", target=target, context="day", day=obs.day)


def final_selection(obs: Observation, policy: GoodPolicyV16 | MafiaPolicyV16,
                    rng: Random) -> Message | None:
    if (not isinstance(policy, GoodPolicyV16) or obs.role != Role.POLICE
            or not _eligible_leader(obs, policy)):
        return None
    shortlist = _latest_shortlist(obs)
    if shortlist is None:
        return None
    counts = Counter(m.target for m in _preferences_after_shortlist(obs))
    ranked, scores = _ranked_candidates(obs, policy)
    order = {p: i for i, p in enumerate(ranked)}
    target = max(shortlist.targets, key=lambda p: (counts[p], scores[p], -order[p]))
    return Message(obs.player, "accuse", target=target, context="day", day=obs.day)


def _final_target(obs: Observation) -> int | None:
    return next((m.target for m in reversed(obs.messages)
                 if m.kind == "accuse" and m.day == obs.day), None)


def vote(obs: Observation, policy: GoodPolicyV16 | MafiaPolicyV16, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    target = _final_target(obs)
    if target in pool:
        if isinstance(policy, MafiaPolicyV16) and target in teammates(obs):
            alternatives = [p for p in pool if p not in teammates(obs)]
            return next((p for p in speech_order(obs) if p in alternatives),
                        alternatives[0] if alternatives else None)
        return target
    return v13.vote(obs, policy, rng, candidates)
