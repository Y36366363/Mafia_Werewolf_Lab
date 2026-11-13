"""v13 position-aware night actions and dead-police internal nominations.

These are finite, inspectable heuristics rather than AI agents.  Strategic
randomness only breaks equal public-position scores.  Police may use police
team geometry and investigation history; mafia may use mafia team geometry;
neither policy receives an opponent's hidden role.
"""
from dataclasses import dataclass
from random import Random

from .engine import Message, Observation, Role, speech_order
from .policies import teammates
from .strategies_v12 import GoodPolicyV12, MafiaPolicyV12
from . import strategies_v12 as v12


@dataclass(frozen=True)
class GoodPolicyV13(GoodPolicyV12):
    inspect_position: str = "random"  # random, preempt, reply, gap
    dead_clear_plan: str = "truth"  # pass, truth, short1, short3, decoy_remove, clear_remove

    def __post_init__(self):
        super().__post_init__()
        if self.inspect_position not in {"random", "preempt", "reply", "gap"}:
            raise ValueError("invalid inspection-position policy")
        if self.dead_clear_plan not in {
            "pass", "truth", "short1", "short3", "decoy_remove", "clear_remove"
        }:
            raise ValueError("invalid dead-clear plan")


@dataclass(frozen=True)
class MafiaPolicyV13(MafiaPolicyV12):
    kill_position: str = "random"  # random, first, frontload, bookend
    shortlist_response: str = "random"  # random, omitted, removed, listed

    def __post_init__(self):
        super().__post_init__()
        if self.opening_mode != "ordinary":
            raise ValueError("v13 position/nomination experiment excludes self-kill")
        if self.kill_position not in {"random", "first", "frontload", "bookend"}:
            raise ValueError("invalid kill-position policy")
        if self.shortlist_response not in {"random", "omitted", "removed", "listed"}:
            raise ValueError("invalid shortlist response")


def _forward(a: int, b: int, obs: Observation) -> int:
    return ((b - a) * obs.rules.direction) % obs.rules.n_players


def _undirected(a: int, b: int, obs: Observation) -> int:
    d = _forward(a, b, obs)
    return min(d, obs.rules.n_players - d)


def _best(scores, rng: Random):
    maximum = max(scores.values())
    return rng.choice(sorted(p for p, score in scores.items() if score == maximum))


def _order_after(obs: Observation, victim: int) -> tuple[int, ...]:
    alive = set(obs.alive) - {victim}
    n, direction = obs.rules.n_players, obs.rules.direction
    return tuple((victim + direction * step) % n for step in range(1, n + 1)
                 if (victim + direction * step) % n in alive)


def choose_inspection(obs: Observation, policy: GoodPolicyV13, rng: Random) -> int:
    if obs.role != Role.POLICE:
        raise ValueError("only police can inspect")
    known = teammates(obs) | {record.target for record in obs.investigations}
    pool = [p for p in obs.alive if p not in known]
    if not pool:
        pool = list(obs.alive)
    if policy.inspect_position == "random":
        return rng.choice(pool)
    live_team = teammates(obs).intersection(obs.alive)
    if policy.inspect_position == "preempt":
        # A police seat speaks shortly before the inspected seat.
        scores = {p: -min(_forward(t, p, obs) for t in live_team) for p in pool}
    elif policy.inspect_position == "reply":
        # A police seat speaks shortly after the inspected seat.
        scores = {p: -min(_forward(p, t, obs) for t in live_team) for p in pool}
    else:
        # Inspect the centre of the largest gap in the known police geometry.
        scores = {p: min(_undirected(p, t, obs) for t in live_team) for p in pool}
    return _best(scores, rng)


def _latest_shortlist(obs: Observation) -> Message | None:
    if not obs.deaths:
        return None
    first_dead = obs.deaths[0].player
    rows = [m for m in obs.messages if m.speaker == first_dead and
            m.context == "last_words" and m.kind == "shortlist"]
    return rows[-1] if rows else None


def choose_kill(obs: Observation, policy: MafiaPolicyV13, rng: Random) -> int:
    if obs.role != Role.MAFIA:
        raise ValueError("only mafia can kill")
    allies = teammates(obs).intersection(obs.alive)
    pool = [p for p in obs.alive if p not in allies]
    claimants = {m.speaker for m in obs.messages if m.kind in {"police", "report"}}
    live_claimants = [p for p in pool if p in claimants]
    shortlist = _latest_shortlist(obs)
    if live_claimants:
        pool = live_claimants
    elif shortlist is not None and obs.day >= 1 and policy.shortlist_response != "random":
        listed = set(shortlist.targets)
        removed = {shortlist.target} if shortlist.target is not None else set()
        buckets = {
            "omitted": [p for p in pool if p not in listed],
            "removed": [p for p in pool if p in removed],
            "listed": [p for p in pool if p in listed - removed],
        }
        preferred = buckets[policy.shortlist_response]
        if preferred:
            pool = preferred
    if policy.kill_position == "random":
        return rng.choice(pool)
    scores = {}
    for victim in pool:
        order = _order_after(obs, victim)
        first = int(bool(order) and order[0] in allies)
        first4 = sum(p in allies for p in order[:4])
        last3 = sum(p in allies for p in order[-3:])
        last = int(bool(order) and order[-1] in allies)
        if policy.kill_position == "first":
            score = 100 * first + first4
        elif policy.kill_position == "frontload":
            score = 100 * first4 + first
        else:
            score = 1000 * (first + last) + 10 * (first4 + last3) + first
        scores[victim] = score
    return _best(scores, rng)


def _latest_investigation(obs: Observation):
    live_hits = [r for r in obs.investigations if r.is_mafia and r.target in obs.alive]
    return live_hits[-1] if live_hits else (obs.investigations[-1]
                                           if obs.investigations else None)


def _ordered(obs: Observation, pool) -> list[int]:
    allowed = set(pool)
    return [p for p in speech_order(obs) if p in allowed]


def _shortlist_message(obs: Observation, plan: str) -> Message:
    report = _latest_investigation(obs)
    if report is None:
        return Message(obs.player, "pass", context="last_words", day=obs.day)
    # A hit is always released in v13; the v12 experiment already compared
    # withholding it.  This experiment varies only the clear-result branch.
    if report.is_mafia:
        return Message(obs.player, "report", report.target, True, "last_words", obs.day)
    if plan == "pass":
        return Message(obs.player, "pass", context="last_words", day=obs.day)
    if plan == "truth":
        return Message(obs.player, "report", report.target, False, "last_words", obs.day)
    police = teammates(obs)
    eligible = _ordered(obs, set(obs.alive) - police - {report.target})
    if plan == "short1":
        targets, removed = tuple(eligible[:1]), None
    elif plan == "short3":
        targets, removed = tuple(eligible[:3]), None
    elif plan == "decoy_remove":
        decoys = _ordered(obs, police.intersection(obs.alive))
        if not decoys:
            targets, removed = tuple(eligible[:3]), None
        else:
            combined = set(eligible[:2]) | {decoys[0]}
            targets, removed = tuple(_ordered(obs, combined)), decoys[0]
    else:  # clear_remove
        combined = set(eligible[:2]) | ({report.target} if report.target in obs.alive else set())
        targets = tuple(_ordered(obs, combined))
        removed = report.target if report.target in targets else None
    return Message(obs.player, "shortlist", removed, None, "last_words", obs.day, targets)


def message(obs: Observation, policy: GoodPolicyV13 | MafiaPolicyV13, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV13) and obs.role == Role.POLICE and context == "last_words":
        return _shortlist_message(obs, policy.dead_clear_plan)
    return v12.message(obs, policy, rng, context, override)


def _shortlist_vote(obs: Observation, pool: list[int]) -> int | None:
    row = _latest_shortlist(obs)
    if row is None:
        return None
    final = set(row.targets) - ({row.target} if row.target is not None else set())
    return next((p for p in speech_order(obs) if p in final and p in pool), None)


def vote(obs: Observation, policy: GoodPolicyV13 | MafiaPolicyV13, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    row = _latest_shortlist(obs)
    if row is not None:
        if isinstance(policy, MafiaPolicyV13):
            legal = [p for p in pool if p not in teammates(obs)]
            target = _shortlist_vote(obs, legal)
            return target if target is not None else v12.vote(obs, policy, rng, candidates)
        if isinstance(policy, GoodPolicyV13) and obs.role == Role.POLICE:
            hits = [r.target for r in obs.investigations if r.is_mafia and r.target in pool]
            if hits:
                return hits[-1]
            known_good = teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
            target = _shortlist_vote(obs, [p for p in pool if p not in known_good])
            return target if target is not None else v12.vote(obs, policy, rng, candidates)
        if isinstance(policy, GoodPolicyV13):
            target = _shortlist_vote(obs, pool)
            return target if target is not None else v12.vote(obs, policy, rng, candidates)
    return v12.vote(obs, policy, rng, candidates)
