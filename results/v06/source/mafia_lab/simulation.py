"""Complete-game runner with reproducible, decision-keyed randomness."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from random import Random
from . import policies as default_decisions

from .engine import (Role, Rules, State, add_message, deal, last_words_eligible,
                     observe, resolve_night, resolve_votes, speech_order, winner)
from .policies import GoodPolicy, MafiaPolicy


def decision_rng(seed: int, day: int, phase: str, actor: int = -1) -> Random:
    key = f"{seed}/{day}/{phase}/{actor}".encode()
    return Random(int.from_bytes(sha256(key).digest()[:8], "big"))


@dataclass(frozen=True)
class Outcome:
    good_win: int
    nights: int
    deaths: int
    first_death_role: str
    first_check_mafia: bool
    transcript: tuple[dict, ...] = ()


def night(state: State, good: GoodPolicy, mafia: MafiaPolicy, seed: int,
          decision_api=default_decisions) -> State:
    # Runner selects a faction representative using referee state. The policy
    # gets only that representative's observation; no hidden labels are passed.
    police = next(p for p in state.alive if state.roles[p] == Role.POLICE)
    killer = next(p for p in state.alive if state.roles[p] == Role.MAFIA)
    checked = decision_api.choose_inspection(observe(state, police), good,
                                decision_rng(seed, state.day, "inspection"))
    killed = decision_api.choose_kill(observe(state, killer), mafia,
                         decision_rng(seed, state.day, "kill"))
    # Both actions were chosen from the same pre-night state.
    return resolve_night(state, killed, checked)


def opening(rules: Rules, good: GoodPolicy, mafia: MafiaPolicy, seed: int,
            decision_api=default_decisions) -> State:
    state = deal(rules, decision_rng(seed, 0, "deal"))
    return night(state, good, mafia, seed, decision_api)


def continue_game(state: State, good: GoodPolicy, mafia: MafiaPolicy, seed: int,
                  first_last_words: str | None = None, trace: bool = False,
                  decision_api=default_decisions) -> Outcome:
    """Resume just after a night; intervention applies ONLY first-night victim.

    first_last_words is pass/water/report, not a referee role or branch label.
    Experiment selection happens before this call and never enters policies.
    """
    if not state.deaths or state.day < 1:
        raise ValueError("Continuation must start after a night")
    first_role = state.roles[state.deaths[0].player].value
    first_check = state.investigations[0].is_mafia
    trace_rows = []

    def record(event, payload):
        if trace:
            trace_rows.append({"day": state.day, "event": event, "payload": payload})

    def speak(player, context, override=None):
        nonlocal state
        obs = observe(state, player)
        policy = mafia if obs.role == Role.MAFIA else good
        msg = decision_api.message(obs, policy, decision_rng(seed, state.day, context, player),
                      context=context, override=override)
        state = add_message(state, msg)
        if trace:
            record("message", asdict(msg))

    def last_words(override=None):
        victim = state.deaths[-1].player
        if last_words_eligible(state, victim):
            speak(victim, "last_words", override)

    while winner(state) is None:
        if state.day > len(state.roles):
            # At least one mandatory night death: truncation would be a bug.
            raise RuntimeError("Termination invariant violated")
        record("night_death", {"victim": state.deaths[-1].player})
        last_words(first_last_words if state.day == 1 else None)
        for player in speech_order(state):
            speak(player, "day")
        # All votes consume one common history; publish after collection.
        ballots = {}
        for player in state.alive:
            obs = observe(state, player)
            policy = mafia if obs.role == Role.MAFIA else good
            ballots[player] = decision_api.vote(obs, policy, decision_rng(seed, state.day, "vote", player))
        before = len(state.deaths)
        state = resolve_votes(state, ballots)
        record("votes", ballots)
        if state.pending_pk:
            for player in speech_order(state):
                if player in state.pending_pk:
                    speak(player, "pk")
            ballots = {}
            for player in state.alive:
                obs = observe(state, player)
                policy = mafia if obs.role == Role.MAFIA else good
                ballots[player] = decision_api.vote(obs, policy, decision_rng(seed, state.day, "pk_vote", player),
                                       candidates=state.pending_pk)
            state = resolve_votes(state, ballots, pk=True)
            record("pk_votes", ballots)
        if len(state.deaths) > before:
            record("day_death", {"victim": state.deaths[-1].player})
            if winner(state) is None:
                last_words()
        if winner(state) is None:
            state = night(state, good, mafia, seed, decision_api)
    record("terminal", {"winner": winner(state)})
    return Outcome(int(winner(state) == "good"), state.day, len(state.deaths),
                   first_role, first_check, tuple(trace_rows))


def play(rules: Rules, good: GoodPolicy, mafia: MafiaPolicy, seed: int,
         trace: bool = False, decision_api=default_decisions) -> Outcome:
    return continue_game(opening(rules, good, mafia, seed, decision_api), good, mafia, seed,
                         trace=trace, decision_api=decision_api)
