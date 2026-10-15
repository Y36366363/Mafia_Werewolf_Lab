"""v10 public coordination protocols and targeted mafia response families."""
from collections import Counter
from dataclasses import dataclass
from random import Random

from . import policies as base
from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy
from . import strategies_v04 as v4
from . import strategies_v07 as v7
from . import strategies_v09 as v9


@dataclass(frozen=True)
class GoodPolicyV10(v9.GoodPolicyV9):
    coordination_mode: str = "none"  # none, anchor, pair, deliberative
    police_follow_timing: str = "immediate"  # immediate, public, late, never

    def __post_init__(self):
        super().__post_init__()
        if self.coordination_mode not in {"none", "anchor", "pair", "deliberative"}:
            raise ValueError("invalid coordination mode")
        if self.police_follow_timing not in {"immediate", "public", "late", "never"}:
            raise ValueError("invalid police follow timing")


@dataclass(frozen=True)
class MafiaPolicyV10(v9.MafiaPolicyV9):
    counter_mode: str = "none"  # none, concentration, dispersion, follow
    counter_weight: float = 4.0

    def __post_init__(self):
        super().__post_init__()
        if self.counter_mode not in {"none", "concentration", "dispersion", "follow"}:
            raise ValueError("invalid counter mode")
        if not isinstance(self.counter_weight, (int, float)) or not 0 <= self.counter_weight <= 12:
            raise ValueError("invalid counter weight")


published_ballots = v9.published_ballots
good_history_scores = v9.good_history_scores
choose_inspection = v9.choose_inspection
live_ballots = v9.live_ballots
public_probe_target = v9.public_probe_target


def public_coordination_target(obs: Observation, mode: str) -> int | None:
    """One public target computed without role or inspection information."""
    order = [p for p in speech_order(obs) if p in obs.alive]
    if not order:
        return None
    anchor = obs.last_anchor if obs.last_anchor is not None else 0
    candidates = [p for p in order if p != obs.player]
    if not candidates:
        return None
    if mode == "deliberative":
        nominations = [m for m in v4._messages(obs)
                       if m.day == obs.day and m.kind == "nominate" and m.target in obs.alive]
        # The first half proposes public, role-blind alternatives. The second
        # half consolidates on the current plurality with public order tie-breaks.
        rank = order.index(obs.player)
        if rank < max(2, len(order) // 2):
            rules = ("next", "second", "opposite", "hashed")
            return v9.public_probe_target(obs, rules[rank % len(rules)])
        counts = Counter(m.target for m in nominations if m.target != obs.player)
        if counts:
            order_rank = {p: i for i, p in enumerate(order)}
            return min(counts, key=lambda p: (-counts[p], order_rank.get(p, len(order)), p))
        return candidates[0]
    # The first chair target is common to everyone except that target, who uses
    # the public fallback. Pair mode rotates between two adjacent public anchors.
    chair = order[0]
    common = next((p for p in order if p != chair), candidates[0])
    if mode == "anchor":
        return common if common != obs.player else candidates[0]
    pair = [p for p in order if p != chair][:2]
    target = pair[(obs.day + anchor) % len(pair)] if pair else common
    return target if target != obs.player else candidates[0]


def _coordination_message(obs: Observation, policy: GoodPolicyV10) -> Message | None:
    if policy.coordination_mode == "none" or obs.day != 1:
        return None
    make = lambda kind, target=None: Message(obs.player, kind, target, None, "day", obs.day)
    public_target = public_coordination_target(obs, policy.coordination_mode)
    if obs.role == Role.CIVILIAN:
        return make("nominate", public_target) if public_target is not None else make("civilian")
    if obs.role != Role.POLICE:
        return None
    hits = [r.target for r in obs.investigations if r.is_mafia and r.target in obs.alive]
    if not hits or policy.police_follow_timing == "never":
        return make("nominate", public_target) if public_target is not None else make("civilian")
    hit = hits[-1]
    if policy.police_follow_timing == "immediate":
        return make("nominate", hit)
    nominations = [m for m in v4._messages(obs)
                   if m.day == obs.day and m.kind == "nominate"]
    if policy.police_follow_timing == "public":
        return make("nominate", hit) if any(m.target == hit for m in nominations) else make(
            "nominate", public_target)
    team_order = [p for p in speech_order(obs) if p in base.teammates(obs) and p in obs.alive]
    return make("nominate", hit if obs.player == team_order[-1] else public_target)


def _public_actor_features(obs: Observation):
    allies = base.teammates(obs)
    messages = [m for m in v4._messages(obs)
                if m.kind == "nominate" and m.speaker not in allies]
    target_counts = Counter(m.target for m in messages)
    first, seen = {}, Counter()
    repeats, initiates, modal_support = Counter(), Counter(), Counter()
    for index, message in enumerate(messages):
        key = (message.day, message.target)
        if seen[key]:
            repeats[message.speaker] += 1 + index / max(1, len(messages))
        else:
            initiates[message.speaker] += 1
            first[key] = message.speaker
        seen[key] += 1
    modal = {target for target, count in target_counts.items()
             if count == max(target_counts.values(), default=0) and count >= 2}
    for message in messages:
        if message.target in modal:
            modal_support[message.speaker] += 1
    return messages, repeats, initiates, modal_support


def _counter_scores(obs: Observation, policy: MafiaPolicyV10) -> dict[int, float]:
    baseline = v9.mafia_scores(obs, policy)
    _, repeats, initiates, modal_support = _public_actor_features(obs)
    if policy.counter_mode == "concentration":
        signal = modal_support
    elif policy.counter_mode == "dispersion":
        signal = initiates
    elif policy.counter_mode == "follow":
        signal = repeats
    else:
        return baseline
    return {p: baseline.get(p, 0.0) + policy.counter_weight * signal[p] for p in baseline}


def mafia_scores(obs: Observation, policy: MafiaPolicyV10) -> dict[int, float]:
    if obs.role != Role.MAFIA:
        raise ValueError("mafia scores require mafia observation")
    return _counter_scores(obs, policy)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    if not isinstance(policy, MafiaPolicyV10) or policy.counter_mode == "none":
        return v9.choose_kill(obs, policy, rng)
    if obs.day == 0 and obs.rules.allow_self_kill and rng.random() < policy.first_self_kill:
        return rng.choice(sorted(base.teammates(obs).intersection(obs.alive)))
    scores = mafia_scores(obs, policy)
    rank = {p: i for i, p in enumerate(speech_order(obs))}
    return min(scores, key=lambda p: (-scores[p], rank.get(p, len(rank)), p))


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    if isinstance(policy, GoodPolicyV10) and override is None and context == "day":
        result = _coordination_message(obs, policy)
        if result is not None:
            return result
    return v9.message(obs, policy, rng, context, override)


def deterministic_mafia_ranking(obs: Observation, policy: MafiaPolicyV10,
                                candidates: tuple[int, ...] | None = None) -> list[int]:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p not in base.teammates(obs)]
    scores = {p: s for p, s in mafia_scores(obs, policy).items() if p in pool}
    allies = base.teammates(obs)
    ally_targets = {m.target for m in v4._messages(obs)
                    if m.day == obs.day and m.kind == "nominate" and m.speaker in allies}
    scores = {p: score + 2.0 * (p in ally_targets) for p, score in scores.items()}
    rank = {p: i for i, p in enumerate(speech_order(obs))}
    return sorted(pool, key=lambda p: (-scores[p], rank.get(p, len(rank)), p))


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    if (isinstance(policy, GoodPolicyV10) and policy.coordination_mode != "none" and
            obs.day == 1):
        pool = [p for p in (obs.alive if candidates is None else candidates)
                if p in obs.alive and p != obs.player]
        if not pool:
            return None
        if obs.role == Role.POLICE:
            hits = [r.target for r in obs.investigations if r.is_mafia and r.target in pool]
            if hits:
                return hits[-1]
            known_good = base.teammates(obs) | {
                r.target for r in obs.investigations if not r.is_mafia
            }
            pool = [p for p in pool if p not in known_good]
            if not pool:
                return None
        target = public_coordination_target(obs, policy.coordination_mode)
        if target in pool:
            return target
        nominations = Counter(m.target for m in v4._messages(obs)
                              if m.day == obs.day and m.kind == "nominate" and m.target in pool)
        if nominations:
            rank = {p: i for i, p in enumerate(speech_order(obs))}
            return min(nominations, key=lambda p: (-nominations[p], rank.get(p, len(rank)), p))
        return pool[0]
    if not isinstance(policy, MafiaPolicyV10):
        return v9.vote(obs, policy, rng, candidates)
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
    counts = Counter(v for v in proposed.values() if v is not None)
    safe = counts[main] > max((n for p, n in counts.items() if p != main), default=0)
    return ordered[1] if safe else main
