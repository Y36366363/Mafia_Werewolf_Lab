"""v05 strategy refinements: role-separated ballots and sequencing counters.

This module keeps the v04 information contract.  The new good-side switches
separate police ballot reasoning, civilian ballot reasoning and inspection
reasoning.  The new mafia ``origin`` score distinguishes the first public
nominator of a target from later followers; ``split`` voting deliberately
disperses mafia ballots over high-scoring non-allies.  These are fixed legal
heuristics, not calibrated beliefs or best responses.
"""
from dataclasses import dataclass, replace
from random import Random

from . import policies as base
from .engine import Message, Observation, Role
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4


@dataclass(frozen=True)
class GoodPolicyV5(v4.GoodPolicyV4):
    police_vote_reasoning: bool = False
    civilian_vote_reasoning: bool = False

    def __post_init__(self):
        super().__post_init__()
        if type(self.police_vote_reasoning) is not bool or type(self.civilian_vote_reasoning) is not bool:
            raise ValueError("role-separated reasoning switches must be booleans")


@dataclass(frozen=True)
class MafiaPolicyV5(v4.MafiaPolicyV4):
    vote_style: str = "coordinate"

    def __post_init__(self):
        # Skip v04's narrower inference validation while retaining base checks.
        MafiaPolicy.__post_init__(self)
        if self.inference not in {"signals", "history", "votes", "combined", "origin"}:
            raise ValueError("unknown inference mode")
        v4._probability(self.nomination_probability, "nomination_probability")
        if self.vote_style not in {"coordinate", "split"}:
            raise ValueError("vote_style must be coordinate or split")


published_ballots = v4.published_ballots
good_history_scores = v4.good_history_scores


def _origin_scores(obs: Observation) -> dict[int, float]:
    allies = base.teammates(obs)
    pool = [p for p in obs.alive if p not in allies]
    messages = v4._messages(obs)
    nominations = v4._nominations(obs)
    claims = {m.speaker for m in messages if m.kind in {"police", "report"}}
    speaking_days = {}
    for m in messages:
        speaking_days.setdefault(m.speaker, set()).add(m.day)
    first = {}
    for m in messages:
        if m.kind == "nominate":
            first.setdefault((m.day, m.target), m.speaker)
    ballots = tuple(published_ballots(obs).values())
    scores = {}
    for player in pool:
        player_noms = [(day, target) for (day, speaker), target in nominations.items()
                       if speaker == player]
        opportunities = len(speaking_days.get(player, ()))
        initiate = sum(first.get((day, target)) == player for day, target in player_noms)
        follow = len(player_noms) - initiate
        initiate_rate = initiate / opportunities if opportunities else 0.0
        follow_rate = follow / opportunities if opportunities else 0.0
        votes = [round_[player] for round_ in ballots
                 if player in round_ and round_[player] is not None]
        anti_mafia = sum(target in allies for target in votes) / len(votes) if votes else 0.0
        scores[player] = (2.0 * (player in claims) + 2.0 * initiate_rate +
                          0.5 * follow_rate + 2.0 * anti_mafia)
    return scores


def mafia_scores(obs: Observation, policy: MafiaPolicyV5) -> dict[int, float]:
    if obs.role != Role.MAFIA:
        raise ValueError("mafia scores require mafia observation")
    return _origin_scores(obs) if policy.inference == "origin" else v4.mafia_scores(obs, policy)


def choose_inspection(obs: Observation, policy: GoodPolicy, rng: Random) -> int:
    return v4.choose_inspection(obs, policy, rng)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    if not isinstance(policy, MafiaPolicyV5):
        return v4.choose_kill(obs, policy, rng)
    if obs.role != Role.MAFIA:
        raise ValueError("Only mafia can kill")
    if obs.day == 0 and obs.rules.allow_self_kill and rng.random() < policy.first_self_kill:
        return rng.choice(sorted(base.teammates(obs).intersection(obs.alive)))
    return base.choose_best(mafia_scores(obs, policy), rng)


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if not isinstance(policy, MafiaPolicyV5):
        return v4.message(obs, policy, rng, context, override)
    make = lambda kind, target=None, verdict=None: Message(
        obs.player, kind, target, verdict, context, obs.day)
    if override is not None:
        return v4.message(obs, policy, rng, context, override)
    if obs.role != Role.MAFIA:
        raise TypeError("MafiaPolicyV5 needs a mafia observation")
    if policy.bluff == "none":
        return make("civilian")
    if policy.bluff == "nominate":
        if rng.random() >= policy.nomination_probability:
            return make("civilian")
        target = base.choose_best(mafia_scores(obs, policy), rng)
        return make("nominate", target) if target is not None else make("civilian")
    if context != "last_words" and obs.player != base._spokesperson(obs):
        return make("civilian")
    if policy.bluff == "reactive" and not (base.claimants(obs) - base.teammates(obs)):
        return make("civilian")
    target = base.choose_best(mafia_scores(obs, policy), rng)
    return make("report", target, True) if target is not None else make("civilian")


def _mafia_vote_scores(obs: Observation, policy: MafiaPolicyV5, pool) -> dict[int, float]:
    scores = {p: score for p, score in mafia_scores(obs, policy).items() if p in pool}
    allies = base.teammates(obs)
    ally_targets = {target for (day, speaker), target in v4._nominations(obs).items()
                    if day == obs.day and speaker in allies}
    for m in v4._messages(obs):
        if m.day == obs.day and m.kind == "report" and m.verdict and m.speaker in allies:
            ally_targets.add(m.target)
    return {player: score + 2.0 * (player in ally_targets) for player, score in scores.items()}


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if isinstance(policy, GoodPolicyV5):
        enabled = (policy.police_vote_reasoning if obs.role == Role.POLICE
                   else policy.civilian_vote_reasoning)
        # ``replace`` keeps the V5 class, which v04 accepts as its base class.
        return v4.vote(obs, replace(policy, vote_reasoning=enabled), rng, candidates)
    if not isinstance(policy, MafiaPolicyV5):
        return v4.vote(obs, policy, rng, candidates)
    if obs.role != Role.MAFIA:
        raise TypeError("MafiaPolicyV5 needs a mafia observation")
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player and p not in base.teammates(obs)]
    if not pool:
        return None
    scores = _mafia_vote_scores(obs, policy, pool)
    if policy.vote_style == "coordinate":
        return base.choose_best(scores, rng)
    ordered = sorted(pool, key=lambda p: (-scores[p], p))
    alive_allies = sorted(base.teammates(obs).intersection(obs.alive))
    return ordered[alive_allies.index(obs.player) % len(ordered)]
