"""v09 probe decomposition and public echo counters.

The added mafia counters use only faction membership and public message order.
The added civilian probe targets are public anchors, allowing target breadth to
vary while holding the eligible speaking window fixed.
"""
from collections import Counter
from dataclasses import dataclass
from random import Random

from . import policies as base
from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4
from . import strategies_v05 as v5
from . import strategies_v07 as v7
from . import strategies_v08 as v8


PROBE_RULES = v8.PROBE_RULES | {"anchor_first", "anchor_pair"}


@dataclass(frozen=True)
class GoodPolicyV9(v8.GoodPolicyV8):
    def __post_init__(self):
        # V8 has a narrower rule set, so validate the inherited fields here.
        v7.GoodPolicyV7.__post_init__(self)
        if type(self.probe_window) is not int or not 1 <= self.probe_window <= 16:
            raise ValueError("probe_window must be between 1 and 16")
        if not self.probe_pattern or any(rule not in PROBE_RULES for rule in self.probe_pattern):
            raise ValueError("invalid v09 probe pattern")


@dataclass(frozen=True)
class MafiaPolicyV9(v8.MafiaPolicyV8):
    vote_style: str = "deterministic"

    def __post_init__(self):
        MafiaPolicy.__post_init__(self)
        if self.inference not in {"signals", "history", "votes", "combined", "origin", "echo"}:
            raise ValueError("unknown inference mode")
        v4._probability(self.nomination_probability, "nomination_probability")
        if self.vote_style not in {"deterministic", "deterministic_one_decoy",
                                   "deterministic_live_margin", "deterministic_live_final"}:
            raise ValueError("invalid v09 vote style")
        if self.nomination_style not in {"score", "bait_first", "echo_public"}:
            raise ValueError("invalid nomination style")


published_ballots = v8.published_ballots
good_history_scores = v8.good_history_scores
choose_inspection = v8.choose_inspection
live_ballots = v8.live_ballots


def public_probe_target(obs: Observation, rule: str) -> int | None:
    if rule not in {"anchor_first", "anchor_pair"}:
        return v8.public_probe_target(obs, rule)
    order = [p for p in speech_order(obs) if p in obs.alive]
    pool = [p for p in order if p != obs.player]
    if not pool:
        return None
    if rule == "anchor_first":
        return pool[0]
    anchor = obs.last_anchor if obs.last_anchor is not None else 0
    choice = (obs.player + anchor) % 2
    return pool[min(choice, len(pool) - 1)]


def _echo_scores(obs: Observation) -> dict[int, float]:
    """Prioritize non-allied speakers who repeat an earlier public target."""
    allies = base.teammates(obs)
    pool = [p for p in obs.alive if p not in allies]
    seen, repeats, starts = Counter(), Counter(), Counter()
    for message in v4._messages(obs):
        if message.kind != "nominate" or message.speaker in allies:
            continue
        if seen[(message.day, message.target)]:
            repeats[message.speaker] += 1
        else:
            starts[message.speaker] += 1
        seen[(message.day, message.target)] += 1
    claims = {m.speaker for m in v4._messages(obs) if m.kind in {"police", "report"}}
    return {p: 5.0 * repeats[p] + 1.0 * starts[p] + 2.0 * (p in claims) for p in pool}


def mafia_scores(obs: Observation, policy: MafiaPolicyV9) -> dict[int, float]:
    if obs.role != Role.MAFIA:
        raise ValueError("mafia scores require mafia observation")
    return _echo_scores(obs) if policy.inference == "echo" else v8.mafia_scores(obs, policy)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    if not isinstance(policy, MafiaPolicyV9) or policy.inference != "echo":
        return v8.choose_kill(obs, policy, rng)
    if obs.day == 0 and obs.rules.allow_self_kill and rng.random() < policy.first_self_kill:
        return rng.choice(sorted(base.teammates(obs).intersection(obs.alive)))
    scores = mafia_scores(obs, policy)
    order = {p: i for i, p in enumerate(speech_order(obs))}
    return min(scores, key=lambda p: (-scores[p], order.get(p, len(order)), p))


def _probe_message(obs: Observation, policy: GoodPolicyV9) -> Message | None:
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
    if isinstance(policy, GoodPolicyV9) and override is None and context == "day":
        result = _probe_message(obs, policy)
        if result is not None:
            return result
    if (isinstance(policy, MafiaPolicyV9) and override is None and context == "day" and
            policy.nomination_style == "echo_public" and policy.bluff == "nominate"):
        make = lambda kind, target=None: Message(obs.player, kind, target, None, context, obs.day)
        if rng.random() >= policy.nomination_probability:
            return make("civilian")
        allies = base.teammates(obs)
        pool = [p for p in obs.alive if p not in allies]
        prior = [m.target for m in v4._messages(obs)
                 if m.day == obs.day and m.kind == "nominate" and m.target in pool]
        if prior:
            return make("nominate", prior[-1])
        ranked = deterministic_mafia_ranking(obs, policy)
        return make("nominate", ranked[0]) if ranked else make("civilian")
    return v8.message(obs, policy, rng, context, override)


def _vote_scores(obs: Observation, policy: MafiaPolicyV9, pool) -> dict[int, float]:
    scores = {p: score for p, score in mafia_scores(obs, policy).items() if p in pool}
    allies = base.teammates(obs)
    ally_targets = {target for (day, speaker), target in v4._nominations(obs).items()
                    if day == obs.day and speaker in allies}
    return {p: score + 2.0 * (p in ally_targets) for p, score in scores.items()}


def deterministic_mafia_ranking(obs: Observation, policy: MafiaPolicyV9,
                                candidates: tuple[int, ...] | None = None) -> list[int]:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p not in base.teammates(obs)]
    scores = _vote_scores(obs, policy, pool)
    rank = {p: i for i, p in enumerate(speech_order(obs))}
    return sorted(pool, key=lambda p: (-scores[p], rank.get(p, len(rank)), p))


def _unique_leader(ballots, target) -> bool:
    counts = Counter(value for value in ballots.values() if value is not None)
    return bool(counts) and counts[target] > max((count for p, count in counts.items()
                                                 if p != target), default=0)


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if not isinstance(policy, MafiaPolicyV9):
        return v8.vote(obs, policy, rng, candidates)
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
