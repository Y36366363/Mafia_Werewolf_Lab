"""Small, inspectable policies. Every decision consumes only an Observation.

These scoring rules are frozen experimental heuristics, not Bayesian or GTO
policies. Candidate randomness is supplied by the runner at each decision.
"""
from dataclasses import dataclass
from random import Random

from .engine import Message, Observation, Role, speech_order


@dataclass(frozen=True)
class GoodPolicy:
    name: str = "hit_trust"
    reveal: str = "hit"  # hit, all, dead, silent, covert
    trust: str = "all"  # all, dead, corroborated, none, nominations
    civilian_message: str = "pass"  # pass, water, fake
    inspect: str = "random"  # random, near, far

    def __post_init__(self):
        for key, legal in {"reveal": {"hit", "all", "dead", "silent", "covert"},
                           "trust": {"all", "dead", "corroborated", "none", "nominations"},
                           "civilian_message": {"pass", "water", "fake"},
                           "inspect": {"random", "near", "far"}}.items():
            if getattr(self, key) not in legal:
                raise ValueError(f"Invalid {key}")


@dataclass(frozen=True)
class MafiaPolicy:
    name: str = "quiet_random"
    bluff: str = "none"  # none, always, reactive, nominate
    kill: str = "random"  # random, claims, near
    first_self_kill: float = 0.0

    def __post_init__(self):
        if self.bluff not in {"none", "always", "reactive", "nominate"}:
            raise ValueError("Invalid bluff")
        if self.kill not in {"random", "claims", "near"}:
            raise ValueError("Invalid kill")
        if not 0 <= self.first_self_kill <= 1:
            raise ValueError("Invalid first_self_kill")


def teammates(obs: Observation) -> set[int]:
    return {obs.player, *obs.teammates}


def choose_best(scores: dict[int, float], rng: Random) -> int | None:
    if not scores:
        return None
    maximum = max(scores.values())
    return rng.choice(sorted(p for p, value in scores.items() if value == maximum))


def latest_reports(obs: Observation) -> list[Message]:
    # Repetition or a second PK speech is not independent corroboration.
    latest = {}
    for message in obs.messages:
        if message.kind == "report":
            latest[message.speaker] = message
    return list(latest.values())


def claimants(obs: Observation) -> set[int]:
    return {m.speaker for m in obs.messages if m.kind in {"police", "report"}}


def _distance(a: int, b: int, n: int) -> int:
    return min((a-b) % n, (b-a) % n)


def choose_inspection(obs: Observation, policy: GoodPolicy, rng: Random) -> int:
    if obs.role != Role.POLICE:
        raise ValueError("Only police can inspect")
    known = {r.target for r in obs.investigations} | teammates(obs)
    pool = [p for p in obs.alive if p not in known]
    if not pool:
        pool = list(obs.alive)
    if policy.inspect == "random":
        return rng.choice(pool)
    n = obs.rules.police + obs.rules.mafia + obs.rules.civilians
    # Team geometry is legitimately known. No target identity is read.
    scores = {p: min(_distance(p, t, n) for t in teammates(obs)) for p in pool}
    if policy.inspect == "near":
        scores = {p: -s for p, s in scores.items()}
    return choose_best(scores, rng)


def choose_kill(obs: Observation, policy: MafiaPolicy, rng: Random) -> int:
    if obs.role != Role.MAFIA:
        raise ValueError("Only mafia can kill")
    allies = teammates(obs)
    if obs.day == 0 and obs.rules.allow_self_kill and rng.random() < policy.first_self_kill:
        return rng.choice(sorted(allies.intersection(obs.alive)))
    pool = [p for p in obs.alive if p not in allies]
    if policy.kill == "random":
        return rng.choice(pool)
    if policy.kill == "claims":
        return choose_best({p: float(p in claimants(obs)) for p in pool}, rng)
    n = obs.rules.police + obs.rules.mafia + obs.rules.civilians
    return choose_best({p: -min(_distance(p, t, n) for t in allies) for p in pool}, rng)


def _spokesperson(obs: Observation) -> int:
    alive_team = teammates(obs).intersection(obs.alive)
    # First faction member in the public speech order. Ring relabelling does
    # not change this convention, and all teammates can compute it privately.
    return next((p for p in speech_order(obs) if p in alive_team), obs.player)


def _covert_target(obs: Observation) -> int | None:
    known_good = teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
    hits = {r.target for r in obs.investigations if r.is_mafia}
    order = speech_order(obs)
    return next((p for p in order if p in hits),
                next((p for p in order if p not in known_good), None))


def message(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    def make(kind, target=None, verdict=None):
        return Message(speaker=obs.player, kind=kind, target=target,
                       verdict=verdict, context=context, day=obs.day)

    others = [p for p in obs.alive if p != obs.player]
    if override == "pass":
        return make("civilian" if obs.role == Role.CIVILIAN else "pass")
    if override == "water":
        return make("nominate", rng.choice(others)) if others else make("pass")
    if obs.role == Role.POLICE:
        if not isinstance(policy, GoodPolicy):
            raise TypeError("Police needs GoodPolicy")
        if policy.reveal == "covert" and override != "report":
            target = _covert_target(obs)
            return make("nominate", target) if target is not None else make("pass")
        if override != "report":
            if policy.reveal == "silent":
                return make("pass")
            if context != "last_words" and (policy.reveal == "dead" or obs.player != _spokesperson(obs)):
                return make("pass")
        reports = list(obs.investigations)
        if not reports:
            return make("pass")
        live_hits = [r for r in reports if r.is_mafia and r.target in obs.alive]
        selected = live_hits[-1] if live_hits else reports[-1]
        if override != "report" and policy.reveal == "hit" and not selected.is_mafia:
            return make("pass")
        return make("report", selected.target, selected.is_mafia)
    if obs.role == Role.CIVILIAN:
        if not isinstance(policy, GoodPolicy):
            raise TypeError("Civilian needs GoodPolicy")
        if policy.civilian_message == "water" and others:
            return make("nominate", rng.choice(others))
        if policy.civilian_message == "fake" and others:
            return make("report", rng.choice(others), True)
        return make("civilian")
    if not isinstance(policy, MafiaPolicy):
        raise TypeError("Mafia needs MafiaPolicy")
    if policy.bluff == "none":
        return make("civilian")
    if policy.bluff == "nominate":
        pool = [p for p in speech_order(obs) if p not in teammates(obs)]
        target = next((p for p in pool if p in claimants(obs)), pool[0] if pool else None)
        return make("nominate", target) if target is not None else make("civilian")
    if context != "last_words" and obs.player != _spokesperson(obs):
        return make("civilian")
    nonallies = [p for p in others if p not in teammates(obs)]
    if policy.bluff == "reactive" and not (claimants(obs) - teammates(obs)):
        return make("civilian")
    target = choose_best({p: float(p in claimants(obs)) for p in nonallies}, rng)
    return make("report", target, True) if target is not None else make("civilian")


def vote(obs: Observation, policy: GoodPolicy | MafiaPolicy, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    if obs.role == Role.MAFIA:
        allies = teammates(obs)
        pool = [p for p in pool if p not in allies]
        if not pool:
            return None
        reports = latest_reports(obs)
        ally_accused = {m.target for m in reports if m.speaker in allies and m.verdict}
        if isinstance(policy, MafiaPolicy) and policy.bluff == "nominate":
            ally_accused |= {m.target for m in obs.messages if m.kind == "nominate"
                            and m.speaker in allies and m.day == obs.day}
        return choose_best({p: 2*float(p in ally_accused) + float(p in claimants(obs))
                            for p in pool}, rng)
    if not isinstance(policy, GoodPolicy):
        raise TypeError("Good role needs GoodPolicy")
    known_good, known_bad = set(), set()
    if obs.role == Role.POLICE:
        known_good |= teammates(obs)
        known_good |= {r.target for r in obs.investigations if not r.is_mafia}
        known_bad |= {r.target for r in obs.investigations if r.is_mafia}
        if policy.reveal == "covert":
            target = _covert_target(obs)
            if target in pool:
                return target
        hits = [p for p in pool if p in known_bad]
        if hits:
            return rng.choice(hits)
        pool = [p for p in pool if p not in known_good]
        if not pool:
            return None
    scores = {p: 0.0 for p in pool}
    reports = latest_reports(obs)
    for report in reports:
        if report.speaker == obs.player:
            # A player's fabricated claim cannot become their own evidence.
            continue
        if obs.role == Role.POLICE and report.speaker not in teammates(obs):
            # Police recognize their faction: an outsider's claimed inspection
            # is not an authentic police result, even in a trust-all citizen model.
            continue
        if report.target not in scores:
            continue
        accepted = policy.trust == "all"
        if policy.trust == "dead":
            accepted = report.speaker not in obs.alive
        elif policy.trust == "corroborated":
            accepted = sum(r.target == report.target and r.verdict == report.verdict
                           for r in reports) >= 2
        # Police can recognize a teammate's authentic statement.
        if obs.role == Role.POLICE and report.speaker in teammates(obs):
            accepted = True
        if accepted:
            scores[report.target] += 2.0 if report.verdict else -1.0
    # A nomination is a weak coordination cue, never treated as an inspection.
    if policy.trust != "none":
        nominations = {m.speaker: m.target for m in obs.messages
                       if m.kind == "nominate" and m.day == obs.day}
        for target in nominations.values():
            if target in scores:
                scores[target] += 0.25
    return choose_best(scores, rng)


GOOD_POOL = (
    GoodPolicy("hit_trust", "hit", "all"),
    GoodPolicy("all_trust", "all", "all"),
    GoodPolicy("dead_only", "dead", "dead"),
    GoodPolicy("hit_skeptic", "hit", "none"),
    GoodPolicy("all_corroborate", "all", "corroborated"),
    GoodPolicy("all_water", "all", "all", "water"),
    GoodPolicy("covert_nomination", "covert", "nominations"),
)
MAFIA_POOL = (
    MafiaPolicy("quiet_random"),
    MafiaPolicy("hunt_claims", "none", "claims"),
    MafiaPolicy("fake_hunt", "always", "claims"),
    MafiaPolicy("counterclaim", "reactive", "claims"),
    MafiaPolicy("self25_fake", "always", "claims", 0.25),
    MafiaPolicy("self50_fake", "always", "claims", 0.50),
    MafiaPolicy("mimic_nomination", "nominate", "claims"),
)
