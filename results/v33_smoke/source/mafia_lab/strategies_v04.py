"""Observation-only mixed cover and public-history response policies.

These are fixed, bounded heuristics, not inferred posteriors or best responses.
Every Bernoulli draw is local to the current actor/turn's supplied RNG. There is
no secret policy index, cross-role communication or shared team lottery.

Good speech: police nominate with p, or h when a checked mafia remains alive;
civilians nominate with c. Both use the same public ``civilian`` declaration
when they do not nominate, avoiding a role-specific pass marker. Public cover
follows current-day nomination plurality
(one latest nomination per other speaker, random ties); absent a cue it uses the
first other living seat in public speech order. ``cover_target='random'`` instead
chooses a uniform other living seat, separating cover from coordination.

Private checked mafia always have voting priority; checked good and police
teammates are never police targets. Covert police rank the remaining unknown
targets by a history score (all zero when reasoning is off). Their original
private-information covert target wins ties if available; otherwise a supplied
local RNG breaks maximum-score ties. Reasoning adds .75 times the target's past
nonabstaining-ballot agreement rate with ANY privately confirmed mafia voter.
It does not activate current public-message scoring for covert police.

Civilian and noncovert police voting starts with accepted report scores (+2
accusation, -1 clearance) and distinct current-day nominations (+.25 each),
excluding the observer's own statements. Noncovert police optionally add the
same police history score. A civilian instead adds at most .5 for repeated
co-voting: max pair agreement rate, multiplied by min(shared rounds,3)/3; at
least two shared rounds are required. This weak bloc suspicion can also penalize
coordinating good players, which is why it has a separate ablation. Inspection
reasoning is independently optional and applies the same police history score.

Mafia candidate scores use known teammate identities solely to exclude allies
and recognize ballots against them. Let C be any public police/report claim,
N the fraction of a player's speaking days containing a nomination, H the mean
over their nomination days of min(other NONALLY speakers nominating the same
target,3)/3, and V the fraction of their nonabstaining published ballots aimed
at a known mafia member. Scores: signals=1[C or N>0]; history=2C+N+H;
votes=2C+2V; combined=2C+N+H+2V. The inference switch affects kill, message target
and vote scores together: it is a multi-action response, not a kill-only change.
Only the latest nomination per speaker/day and last PUBLISHED ballot
per day count; PK repetition does not create extra samples. Public messages and
events dated after the observation are ignored. No hidden death role is read.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite
from random import Random

from . import policies as base
from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy


def _probability(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite probability")


@dataclass(frozen=True)
class GoodPolicyV4(GoodPolicy):
    name: str = "mixed_cover"
    reveal: str = "covert"
    trust: str = "nominations"
    civilian_cover_probability: float = 0.5
    police_nominate_probability: float = 0.5
    hit_nominate_probability: float = 1.0
    vote_reasoning: bool = False
    inspect_reasoning: bool = False
    cover_target: str = "public"

    def __post_init__(self):
        super().__post_init__()
        for name in ("civilian_cover_probability", "police_nominate_probability", "hit_nominate_probability"):
            _probability(getattr(self, name), name)
        if type(self.vote_reasoning) is not bool or type(self.inspect_reasoning) is not bool:
            raise ValueError("reasoning switches must be booleans")
        if self.cover_target not in {"public", "random"}:
            raise ValueError("cover_target must be public or random")


@dataclass(frozen=True)
class MafiaPolicyV4(MafiaPolicy):
    name: str = "adaptive_hunt"
    bluff: str = "nominate"
    kill: str = "signals"
    inference: str = "combined"
    nomination_probability: float = 1.0

    def __post_init__(self):
        super().__post_init__()
        if self.inference not in {"signals", "history", "votes", "combined"}:
            raise ValueError("unknown inference mode")
        _probability(self.nomination_probability, "nomination_probability")


def _messages(obs: Observation):
    return tuple(m for m in obs.messages if m.day <= obs.day)


def _nominations(obs: Observation):
    latest = {}
    for m in _messages(obs):
        if m.kind == "nominate":
            latest[m.day, m.speaker] = m.target
    return latest


def published_ballots(obs: Observation) -> dict[int, dict[int, int | None]]:
    """Public first-round ballots may inform PK; unsubmitted ballots never exist here."""
    rounds = {}
    for event in obs.public_events:
        if event.kind in {"vote", "pk_vote"} and event.day <= obs.day:
            rounds[event.day] = dict(event.ballots)
    return rounds


def mafia_scores(obs: Observation, policy: MafiaPolicyV4) -> dict[int, float]:
    """Expose documented proxy scores for audit, without interpreting them as beliefs."""
    if obs.role != Role.MAFIA:
        raise ValueError("mafia scores require mafia observation")
    allies = base.teammates(obs)
    pool = [p for p in obs.alive if p not in allies]
    messages = _messages(obs)
    claims = {m.speaker for m in messages if m.kind in {"police", "report"}}
    nominations = _nominations(obs)
    speaking_days = defaultdict(set)
    for m in messages:
        speaking_days[m.speaker].add(m.day)
    rounds = published_ballots(obs)
    scores = {}
    for player in pool:
        player_noms = [(day, target) for (day, speaker), target in nominations.items()
                       if speaker == player]
        rate = len(player_noms) / len(speaking_days[player]) if speaking_days[player] else 0.0
        coordinated = sum(min(3, sum(other_day == day and other_speaker != player
                                      and other_speaker not in allies and other_target == target
                                      for (other_day, other_speaker), other_target in nominations.items())) / 3
                          for day, target in player_noms)
        coordinated = coordinated / len(player_noms) if player_noms else 0.0
        votes = [ballots[player] for ballots in rounds.values()
                 if player in ballots and ballots[player] is not None]
        anti_mafia = sum(target in allies for target in votes) / len(votes) if votes else 0.0
        claim = float(player in claims)
        if policy.inference == "signals":
            score = float(bool(claim) or bool(player_noms))
        elif policy.inference == "history":
            score = 2 * claim + rate + coordinated
        elif policy.inference == "votes":
            score = 2 * claim + 2 * anti_mafia
        else:
            score = 2 * claim + rate + coordinated + 2 * anti_mafia
        scores[player] = score
    return scores


def good_history_scores(obs: Observation, pool) -> dict[int, float]:
    """Bounded ballot heuristic: private mafia anchors only for police observers."""
    rounds = tuple(published_ballots(obs).values())
    scores = {p: 0.0 for p in pool}
    if obs.role == Role.POLICE:
        known_mafia = {r.target for r in obs.investigations if r.is_mafia}
        for player in scores:
            votes = [ballots for ballots in rounds if ballots.get(player) is not None]
            matches = sum(any(ally != player and ballots.get(ally) is not None
                              and ballots[ally] == ballots[player] for ally in known_mafia)
                          for ballots in votes)
            scores[player] = 0.75 * matches / len(votes) if votes else 0.0
    elif obs.role == Role.CIVILIAN:
        for player in scores:
            for other in range(obs.rules.n_players):
                if other in {player, obs.player}:
                    continue
                shared = [ballots for ballots in rounds if ballots.get(player) is not None
                          and ballots.get(other) is not None]
                if len(shared) >= 2:
                    agreement = sum(b[player] == b[other] for b in shared) / len(shared)
                    scores[player] = max(scores[player], 0.5 * agreement * min(len(shared), 3) / 3)
    return scores


def _good_scores(obs: Observation, policy: GoodPolicyV4, pool) -> dict[int, float]:
    scores = {p: 0.0 for p in pool}
    allies = base.teammates(obs) if obs.role == Role.POLICE else set()
    latest = {}
    for m in _messages(obs):
        if m.kind == "report" and m.speaker != obs.player:
            latest[m.speaker] = m
    reports = tuple(latest.values())
    for report in reports:
        if report.target not in scores:
            continue
        if obs.role == Role.POLICE and report.speaker not in allies:
            continue
        accepted = policy.trust == "all"
        if policy.trust == "dead":
            accepted = report.speaker not in obs.alive
        elif policy.trust == "corroborated":
            accepted = sum(r.target == report.target and r.verdict == report.verdict
                           for r in reports) >= 2
        if obs.role == Role.POLICE and report.speaker in allies:
            accepted = True
        if accepted:
            scores[report.target] += 2.0 if report.verdict else -1.0
    if policy.trust != "none":
        for (day, speaker), target in _nominations(obs).items():
            if day == obs.day and speaker != obs.player and target in scores:
                scores[target] += 0.25
    if policy.vote_reasoning:
        for player, score in good_history_scores(obs, pool).items():
            scores[player] += score
    return scores


def choose_inspection(obs: Observation, policy: GoodPolicy, rng: Random) -> int:
    if not isinstance(policy, GoodPolicyV4) or not policy.inspect_reasoning:
        return base.choose_inspection(obs, policy, rng)
    if obs.role != Role.POLICE:
        raise ValueError("Only police can inspect")
    known = base.teammates(obs) | {r.target for r in obs.investigations}
    pool = [p for p in obs.alive if p not in known]
    if not pool:
        return base.choose_inspection(obs, policy, rng)
    return base.choose_best(good_history_scores(obs, pool), rng)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    if not isinstance(policy, MafiaPolicyV4):
        return base.choose_kill(obs, policy, rng)
    if obs.role != Role.MAFIA:
        raise ValueError("Only mafia can kill")
    if obs.day == 0 and obs.rules.allow_self_kill and rng.random() < policy.first_self_kill:
        return rng.choice(sorted(base.teammates(obs).intersection(obs.alive)))
    return base.choose_best(mafia_scores(obs, policy), rng)


def _cover_target(obs: Observation, policy: GoodPolicyV4, rng: Random) -> int | None:
    pool = [p for p in obs.alive if p != obs.player]
    if not pool:
        return None
    if policy.cover_target == "random":
        return rng.choice(pool)
    counts = Counter(target for (day, speaker), target in _nominations(obs).items()
                     if day == obs.day and speaker != obs.player and target in pool)
    if counts:
        return base.choose_best(dict(counts), rng)
    return next(p for p in speech_order(obs) if p in pool)


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    def make(kind, target=None, verdict=None):
        return Message(obs.player, kind, target, verdict, context, obs.day)

    if override is not None:
        result = base.message(obs, policy, rng, context, override)
        return make("civilian") if isinstance(policy, GoodPolicyV4) and result.kind == "pass" else result
    if isinstance(policy, GoodPolicyV4):
        if obs.role == Role.POLICE and policy.reveal == "covert":
            live_hits = {r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive}
            probability = policy.hit_nominate_probability if live_hits else policy.police_nominate_probability
            if rng.random() >= probability:
                return make("civilian")
            target = base._covert_target(obs)
            return make("nominate", target) if target is not None else make("civilian")
        if obs.role == Role.CIVILIAN:
            if rng.random() < policy.civilian_cover_probability:
                target = _cover_target(obs, policy, rng)
                return make("nominate", target) if target is not None else make("civilian")
            return make("civilian")
        result = base.message(obs, policy, rng, context)
        return make("civilian") if result.kind == "pass" else result
    if isinstance(policy, MafiaPolicyV4):
        if obs.role != Role.MAFIA:
            raise TypeError("MafiaPolicyV4 needs a mafia observation")
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
    return base.message(obs, policy, rng, context)


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if not isinstance(policy, (GoodPolicyV4, MafiaPolicyV4)):
        return base.vote(obs, policy, rng, candidates)
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if isinstance(policy, MafiaPolicyV4):
        if obs.role != Role.MAFIA:
            raise TypeError("MafiaPolicyV4 needs a mafia observation")
        scores = {p: score for p, score in mafia_scores(obs, policy).items() if p in pool}
        allies = base.teammates(obs)
        ally_targets = {target for (day, speaker), target in _nominations(obs).items()
                        if day == obs.day and speaker in allies}
        for m in _messages(obs):
            if m.day == obs.day and m.kind == "report" and m.verdict and m.speaker in allies:
                ally_targets.add(m.target)
        for player in scores:
            scores[player] += 2.0 * (player in ally_targets)
        return base.choose_best(scores, rng)
    if obs.role not in {Role.POLICE, Role.CIVILIAN}:
        raise TypeError("GoodPolicyV4 needs a good observation")
    if obs.role == Role.POLICE:
        known_good = base.teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
        known_bad = {r.target for r in obs.investigations if r.is_mafia}
        hits = [p for p in speech_order(obs) if p in pool and p in known_bad]
        if hits:
            return hits[0]
        pool = [p for p in pool if p not in known_good]
        if not pool:
            return None
        if policy.reveal == "covert":
            # Keep the same coordination baseline in both ablation arms. In
            # particular, enabling history must not also activate public cues.
            scores = (good_history_scores(obs, pool) if policy.vote_reasoning
                      else {p: 0.0 for p in pool})
            target = base._covert_target(obs)
            if target in scores and scores[target] == max(scores.values()):
                return target
            return base.choose_best(scores, rng)
    return base.choose_best(_good_scores(obs, policy, pool), rng)
