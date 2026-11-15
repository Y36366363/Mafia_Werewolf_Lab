"""v12 first-death declarations and credibility responses.

The policies are deliberately small.  They separate what a dead player says
from how living good players react.  Every target is selected from information
available to that actor; in particular, mafia may select a non-mafia player
but cannot distinguish police from civilians.
"""
from dataclasses import dataclass
from random import Random

from .engine import Message, Observation, Role, speech_order
from .policies import GoodPolicy, MafiaPolicy, teammates


@dataclass(frozen=True)
class GoodPolicyV12(GoodPolicy):
    dead_police_message: str = "truth"  # silent, truth, teammate_clear
    dead_claim_response: str = "trust"  # trust, skeptic
    live_counter: str = "hidden"  # hidden, single, full

    def __post_init__(self):
        super().__post_init__()
        if self.dead_police_message not in {"silent", "truth", "teammate_clear"}:
            raise ValueError("invalid dead-police message")
        if self.dead_claim_response not in {"trust", "skeptic"}:
            raise ValueError("invalid dead-claim response")
        if self.live_counter not in {"hidden", "single", "full"}:
            raise ValueError("invalid live counter")


@dataclass(frozen=True)
class MafiaPolicyV12(MafiaPolicy):
    opening_mode: str = "ordinary"  # ordinary, selfkill
    dead_mafia_message: str = "silent"  # silent, fake_hit, ally_clear, nonally_clear

    def __post_init__(self):
        super().__post_init__()
        if self.opening_mode not in {"ordinary", "selfkill"}:
            raise ValueError("invalid opening mode")
        if self.dead_mafia_message not in {
            "silent", "fake_hit", "ally_clear", "nonally_clear"
        }:
            raise ValueError("invalid dead-mafia message")
        if self.opening_mode == "ordinary" and self.dead_mafia_message != "silent":
            raise ValueError("ordinary opening cannot prescribe dead-mafia words")


def _ordered(obs: Observation, players) -> list[int]:
    allowed = set(players)
    return [p for p in speech_order(obs) if p in allowed]


def _latest_investigation(obs: Observation):
    live_hits = [r for r in obs.investigations if r.is_mafia and r.target in obs.alive]
    return live_hits[-1] if live_hits else (obs.investigations[-1] if obs.investigations else None)


def choose_inspection(obs: Observation, policy: GoodPolicyV12, rng: Random) -> int:
    known = teammates(obs) | {r.target for r in obs.investigations}
    pool = [p for p in obs.alive if p not in known]
    return rng.choice(pool or list(obs.alive))


def choose_kill(obs: Observation, policy: MafiaPolicyV12, rng: Random) -> int:
    allies = teammates(obs).intersection(obs.alive)
    if obs.day == 0 and policy.opening_mode == "selfkill":
        return rng.choice(sorted(allies))
    pool = [p for p in obs.alive if p not in allies]
    claimants = {m.speaker for m in obs.messages if m.kind in {"police", "report"}}
    claimed = [p for p in _ordered(obs, pool) if p in claimants]
    return claimed[0] if claimed else rng.choice(pool)


def _dead_outsider_claim(obs: Observation) -> bool:
    if obs.role != Role.POLICE or not obs.deaths:
        return False
    dead = obs.deaths[0].player
    return dead not in teammates(obs) and any(
        m.speaker == dead and m.context == "last_words" and m.kind == "report"
        for m in obs.messages
    )


def message(obs: Observation, policy: GoodPolicyV12 | MafiaPolicyV12, rng: Random,
            context: str = "day", override: str | None = None) -> Message:
    def make(kind, target=None, verdict=None):
        return Message(obs.player, kind, target, verdict, context, obs.day)

    if isinstance(policy, GoodPolicyV12):
        if obs.role == Role.CIVILIAN:
            return make("civilian")
        if obs.role != Role.POLICE:
            raise TypeError("good policy requires a good observation")
        if context == "last_words":
            if policy.dead_police_message == "silent":
                return make("pass")
            if policy.dead_police_message == "teammate_clear":
                alive_team = _ordered(obs, teammates(obs).intersection(obs.alive))
                return make("report", alive_team[0], False) if alive_team else make("pass")
            report = _latest_investigation(obs)
            return (make("report", report.target, report.is_mafia)
                    if report is not None else make("pass"))
        outsider = _dead_outsider_claim(obs)
        should_counter = outsider and (
            policy.live_counter == "full" or
            (policy.live_counter == "single" and
             obs.player == _ordered(obs, teammates(obs).intersection(obs.alive))[0])
        )
        # After day one, a single living police spokesperson releases the most
        # useful current result so all policies share a playable continuation.
        later_spokesperson = (obs.day > 1 and
            obs.player == _ordered(obs, teammates(obs).intersection(obs.alive))[0])
        if should_counter or later_spokesperson:
            report = _latest_investigation(obs)
            return (make("report", report.target, report.is_mafia)
                    if report is not None else make("police"))
        return make("civilian")

    if not isinstance(policy, MafiaPolicyV12) or obs.role != Role.MAFIA:
        raise TypeError("mafia policy requires a mafia observation")
    if context != "last_words" or policy.dead_mafia_message == "silent":
        return make("civilian")
    allies = teammates(obs).intersection(obs.alive)
    nonallies = [p for p in obs.alive if p not in teammates(obs)]
    if policy.dead_mafia_message == "fake_hit":
        target = rng.choice(nonallies)
        return make("report", target, True)
    if policy.dead_mafia_message == "ally_clear":
        target = rng.choice(sorted(allies))
        return make("report", target, False)
    target = rng.choice(nonallies)
    return make("report", target, False)


def _anchor(obs: Observation, pool: list[int]) -> int | None:
    order = _ordered(obs, pool)
    return order[0] if order else (min(pool) if pool else None)


def _dead_report(obs: Observation):
    dead = obs.deaths[0].player if obs.deaths else None
    reports = [m for m in obs.messages if m.speaker == dead and
               m.context == "last_words" and m.kind == "report"]
    return reports[-1] if reports else None


def vote(obs: Observation, policy: GoodPolicyV12 | MafiaPolicyV12, rng: Random,
         candidates: tuple[int, ...] | None = None) -> int | None:
    pool = [p for p in (obs.alive if candidates is None else candidates)
            if p in obs.alive and p != obs.player]
    if not pool:
        return None
    if isinstance(policy, MafiaPolicyV12):
        pool = [p for p in pool if p not in teammates(obs)]
        if not pool:
            return None
        allied_hits = [m.target for m in obs.messages if m.kind == "report" and m.verdict
                       and m.speaker in teammates(obs) and m.target in pool]
        return allied_hits[-1] if allied_hits else _anchor(obs, pool)
    if not isinstance(policy, GoodPolicyV12):
        raise TypeError("unknown policy")
    if obs.role == Role.POLICE:
        hits = [r.target for r in obs.investigations if r.is_mafia and r.target in pool]
        if hits:
            return hits[-1]
        known_good = teammates(obs) | {r.target for r in obs.investigations if not r.is_mafia}
        pool = [p for p in pool if p not in known_good]
        return _anchor(obs, pool)
    report = _dead_report(obs)
    if report is not None and policy.dead_claim_response == "trust":
        # A civilian knows an accusation against itself is false.
        if report.verdict and report.target in pool:
            return report.target
        if not report.verdict:
            pool = [p for p in pool if p != report.target]
    # A living police counterclaim overrides a dead accusation only for the
    # explicit single/full response protocols.
    live_reports = [m for m in obs.messages if m.kind == "report" and
                    m.speaker in obs.alive and m.speaker != obs.player]
    # The live-counter switch is a day-one response only.  From day two onward
    # every policy accepts the shared continuation spokesperson, so this switch
    # cannot silently alter the rest of the game.
    if live_reports and (obs.day > 1 or policy.live_counter != "hidden"):
        hits = [m.target for m in live_reports if m.verdict and m.target in pool]
        if hits:
            return hits[-1]
    return _anchor(obs, pool)

