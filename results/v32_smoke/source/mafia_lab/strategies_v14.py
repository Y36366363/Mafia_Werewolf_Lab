"""v14 mafia kill geometry that controls order without exposing the anchor.

The mafia know only which seats are mafia.  Every safe policy first prefers a
known non-mafia first speaker, then optimizes a different segment of the public
speech order.  Hidden police/civilian labels are never inspected.
"""
from dataclasses import dataclass
from random import Random

from .engine import Observation, Role
from .policies import teammates
from .strategies_v12 import MafiaPolicyV12
from .strategies_v13 import GoodPolicyV13, _order_after
from . import strategies_v12 as v12
from . import strategies_v13 as v13


GEOMETRIES = {
    "random", "safe_front", "safe_middle", "safe_late",
    "safe_sandwich", "safe_balanced", "safe_mix",
}


@dataclass(frozen=True)
class MafiaPolicyV14(MafiaPolicyV12):
    geometry: str = "random"

    def __post_init__(self):
        super().__post_init__()
        if self.opening_mode != "ordinary":
            raise ValueError("v14 position experiment excludes self-kill")
        if self.geometry not in GEOMETRIES:
            raise ValueError("invalid kill geometry")


def choose_inspection(obs: Observation, policy: GoodPolicyV13, rng: Random) -> int:
    return v13.choose_inspection(obs, policy, rng)


def _geometry_score(mode: str, order: tuple[int, ...], allies: set[int]):
    # order[0] is the public anchor created by the kill.  A safe policy gives
    # absolute priority to making it a known non-mafia seat.
    safe_anchor = int(bool(order) and order[0] not in allies)
    front = sum(p in allies for p in order[1:4])
    front6 = sum(p in allies for p in order[1:6])
    middle = sum(p in allies for p in order[3:8])
    late = sum(p in allies for p in order[-4:])
    last = int(bool(order) and order[-1] in allies)
    if mode == "safe_front":
        return safe_anchor, front, front6, late, last
    if mode == "safe_middle":
        return safe_anchor, middle, front6, late, front
    if mode == "safe_late":
        return safe_anchor, late, last, middle, front
    if mode == "safe_sandwich":
        second_and_last = int(len(order) > 1 and order[1] in allies) + last
        return safe_anchor, second_and_last, front + late, middle, front6
    if mode == "safe_balanced":
        return safe_anchor, min(front, late), front + late, middle, last
    raise ValueError("geometry score requires a safe mode")


def _best(scores, rng: Random):
    maximum = max(scores.values())
    return rng.choice(sorted(p for p, value in scores.items() if value == maximum))


def choose_kill(obs: Observation, policy: MafiaPolicyV14, rng: Random) -> int:
    if obs.role != Role.MAFIA:
        raise ValueError("only mafia can kill")
    allies = teammates(obs).intersection(obs.alive)
    pool = [p for p in obs.alive if p not in allies]
    claimants = {m.speaker for m in obs.messages if m.kind in {"police", "report"}}
    live_claimants = [p for p in pool if p in claimants]
    if live_claimants:
        pool = live_claimants
    if policy.geometry == "random":
        return rng.choice(pool)
    mode = policy.geometry
    if mode == "safe_mix":
        mode = rng.choice(["safe_front", "safe_middle", "safe_late",
                           "safe_sandwich", "safe_balanced"])
    scores = {victim: _geometry_score(mode, _order_after(obs, victim), allies)
              for victim in pool}
    return _best(scores, rng)


def message(obs, policy, rng, context="day", override=None):
    return v12.message(obs, policy, rng, context, override)


def vote(obs, policy, rng, candidates=None):
    return v12.vote(obs, policy, rng, candidates)
