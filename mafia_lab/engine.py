"""Immutable referee for the explicitly versioned police/mafia research game.

Seats are zero-based.  Strategies must receive :class:`Observation`, never State.
The caller schedules night, last words, ordinary speech and voting.  A referee
transition validates its own atomic action; it does not select any strategy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
import random
from typing import Mapping, Sequence


class Role(str, Enum):
    POLICE = "police"
    MAFIA = "mafia"
    CIVILIAN = "civilian"


@dataclass(frozen=True)
class Rules:
    police: int = 4
    mafia: int = 4
    civilians: int = 8
    last_words_limit: int = 3
    allow_self_kill: bool = True
    tie_rule: str = "pass"
    direction: int = 1

    def __post_init__(self) -> None:
        counts = (self.police, self.mafia, self.civilians)
        if any(type(n) is not int for n in counts):
            raise ValueError("role counts must be integers")
        if self.police < 1 or self.mafia < 1 or self.civilians < 0:
            raise ValueError("initial game needs police and mafia; civilians may be zero")
        if type(self.last_words_limit) is not int or self.last_words_limit < 0:
            raise ValueError("last_words_limit must be a nonnegative integer")
        if self.tie_rule not in ("pass", "pk"):
            raise ValueError("tie_rule must be 'pass' or 'pk'")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")

    @property
    def n_players(self) -> int:
        return self.police + self.mafia + self.civilians


@dataclass(frozen=True)
class Message:
    speaker: int
    kind: str
    target: int | None = None
    verdict: bool | None = None
    context: str = "day"
    day: int = 0


@dataclass(frozen=True)
class Investigation:
    day: int
    target: int
    is_mafia: bool


@dataclass(frozen=True)
class Death:
    player: int
    day: int
    cause: str
    ordinal: int


@dataclass(frozen=True)
class PublicEvent:
    kind: str
    day: int
    player: int | None = None
    ballots: tuple[tuple[int, int | None], ...] = ()
    candidates: tuple[int, ...] = ()
    outcome: str | None = None


@dataclass(frozen=True)
class State:
    rules: Rules
    roles: tuple[Role, ...]
    alive: tuple[int, ...]
    day: int = 0
    messages: tuple[Message, ...] = ()
    investigations: tuple[Investigation, ...] = ()
    deaths: tuple[Death, ...] = ()
    public_events: tuple[PublicEvent, ...] = ()
    pending_pk: tuple[int, ...] = ()
    last_anchor: int | None = None


@dataclass(frozen=True)
class Observation:
    player: int
    role: Role
    teammates: tuple[int, ...]
    alive: tuple[int, ...]
    day: int
    messages: tuple[Message, ...]
    investigations: tuple[Investigation, ...]
    deaths: tuple[Death, ...]
    public_events: tuple[PublicEvent, ...]
    pending_pk: tuple[int, ...]
    last_anchor: int | None
    rules: Rules
    winner: str | None


def from_roles(roles: Sequence[Role | str], rules: Rules | None = None) -> State:
    """Construct a full referee state; roles are never a strategy argument."""
    converted = tuple(Role(role) for role in roles)
    counts = Counter(converted)
    if rules is None:
        rules = Rules(police=counts[Role.POLICE], mafia=counts[Role.MAFIA],
                      civilians=counts[Role.CIVILIAN])
    if (counts[Role.POLICE], counts[Role.MAFIA], counts[Role.CIVILIAN]) != (
        rules.police, rules.mafia, rules.civilians
    ):
        raise ValueError("roles must match configured initial counts")
    return State(rules=rules, roles=converted, alive=tuple(range(len(converted))))


def deal(rules: Rules, rng: random.Random | None = None) -> State:
    """Uniformly shuffle a role multiset using an explicit RNG when reproducible."""
    roles = ([Role.POLICE] * rules.police + [Role.MAFIA] * rules.mafia
             + [Role.CIVILIAN] * rules.civilians)
    (rng if rng is not None else random.Random()).shuffle(roles)
    return from_roles(roles, rules)


def winner(state: State) -> str | None:
    live_roles = {state.roles[player] for player in state.alive}
    if Role.MAFIA not in live_roles:
        return "good"
    if Role.POLICE not in live_roles:
        return "mafia"
    return None


def _seat(state: State, player: int) -> None:
    if type(player) is not int or not 0 <= player < state.rules.n_players:
        raise ValueError("invalid seat")


def _ongoing(state: State) -> None:
    if winner(state) is not None:
        raise ValueError("game has already ended")


def observe(state: State, player: int) -> Observation:
    """Project state onto legally available information for one player.

    Police know police, mafia know mafia.  A dead police member retains the
    investigation completed on their death night, but receives no later ones.
    Public records never contain hidden roles or inspection targets/results.
    """
    _seat(state, player)
    role = state.roles[player]
    teammates = tuple(i for i, other in enumerate(state.roles)
                      if i != player and other == role) if role != Role.CIVILIAN else ()
    investigations: tuple[Investigation, ...] = ()
    if role == Role.POLICE:
        death_day = next((d.day for d in state.deaths if d.player == player), state.day)
        investigations = tuple(record for record in state.investigations
                               if record.day <= death_day)
    return Observation(player=player, role=role, teammates=teammates,
                       alive=state.alive, day=state.day, messages=state.messages,
                       investigations=investigations, deaths=state.deaths,
                       public_events=state.public_events, pending_pk=state.pending_pk,
                       last_anchor=state.last_anchor, rules=state.rules, winner=winner(state))


def night_targets(state: State, faction: Role | str) -> tuple[int, ...]:
    """Legal targets known to a faction, including self/team inspections."""
    _ongoing(state)
    faction = Role(faction)
    if faction == Role.POLICE:
        return state.alive
    if faction == Role.MAFIA:
        if state.rules.allow_self_kill:
            return state.alive
        return tuple(i for i in state.alive if state.roles[i] != Role.MAFIA)
    raise ValueError("civilians have no night action")


def _eliminate(state: State, player: int, cause: str) -> State:
    death = Death(player, state.day, cause, len(state.deaths) + 1)
    event = PublicEvent(kind="death", day=state.day, player=player, outcome=cause)
    result = replace(state, alive=tuple(i for i in state.alive if i != player),
                     deaths=state.deaths + (death,),
                     public_events=state.public_events + (event,), last_anchor=player,
                     pending_pk=())
    outcome = winner(result)
    if outcome is not None:
        result = replace(result, public_events=result.public_events + (
            PublicEvent(kind="game_over", day=result.day, outcome=outcome),))
    return result


def resolve_night(state: State, kill_target: int, inspect_target: int) -> State:
    """Atomically accept both secret choices, inspect, kill, then check terminal.

    Neither choice can observe the other via this API.  The caller must collect
    each choice from that faction's pre-night Observation before calling it.
    """
    _ongoing(state)
    if state.pending_pk:
        raise ValueError("resolve pending PK before night")
    _seat(state, kill_target)
    _seat(state, inspect_target)
    if kill_target not in night_targets(state, Role.MAFIA):
        raise ValueError("illegal mafia kill target")
    if inspect_target not in night_targets(state, Role.POLICE):
        raise ValueError("illegal police inspection target")
    day = state.day + 1
    record = Investigation(day, inspect_target, state.roles[inspect_target] == Role.MAFIA)
    result = replace(state, day=day, investigations=state.investigations + (record,))
    return _eliminate(result, kill_target, "night")


def last_words_eligible(state: State, player: int) -> bool:
    """Only the most recent death may give one last-words message, before speech."""
    if winner(state) is not None or not state.deaths:
        return False
    death = state.deaths[-1]
    if death.player != player or death.ordinal > state.rules.last_words_limit:
        return False
    if death.day != state.day:
        return False
    if any(m.speaker == player and m.context == "last_words" for m in state.messages):
        return False
    # A night victim's last words precede ordinary daytime speech and voting.
    if death.cause == "night":
        if any(m.day == state.day and m.context in ("day", "pk") for m in state.messages):
            return False
        if any(e.day == state.day and e.kind in ("vote", "pk_vote")
               for e in state.public_events):
            return False
    return True


def add_message(state: State, message: Message) -> State:
    """Append an unverified public statement; any role may bluff any claim."""
    _ongoing(state)
    _seat(state, message.speaker)
    if message.day != state.day:
        raise ValueError("message day does not match state")
    if message.kind not in ("pass", "civilian", "police", "report", "accuse", "nominate"):
        raise ValueError("unknown message template")
    if message.context not in ("day", "last_words", "pk"):
        raise ValueError("unknown message context")
    if message.context == "last_words":
        if not last_words_eligible(state, message.speaker):
            raise ValueError("player is not eligible for last words")
    else:
        if message.speaker not in state.alive:
            raise ValueError("dead players cannot speak outside last words")
        if message.context == "pk" and message.speaker not in state.pending_pk:
            raise ValueError("only PK candidates may give PK speech")
        if message.context == "day" and state.pending_pk:
            raise ValueError("ordinary speech cannot interrupt pending PK")
    if message.target is not None:
        _seat(state, message.target)
    if message.kind in ("report", "accuse", "nominate") and message.target is None:
        raise ValueError("this template needs a target")
    if message.kind == "report":
        if type(message.verdict) is not bool:
            raise ValueError("report needs a boolean verdict (True means mafia)")
    elif message.verdict is not None:
        raise ValueError("only report messages carry verdicts")
    if message.kind in ("pass", "civilian", "police") and message.target is not None:
        raise ValueError("this template has no target")
    return replace(state, messages=state.messages + (message,))


def speech_order(state: State | Observation, anchor: int | None = None,
                 direction: int | None = None) -> tuple[int, ...]:
    """Start next to the last dead seat, move in direction, and skip dead seats."""
    if direction is None:
        direction = state.rules.direction
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if anchor is None:
        anchor = state.last_anchor
    n = state.rules.n_players
    if anchor is None:
        # Seat zero first if no death has established an anchor.
        anchor = (-direction) % n
    if type(anchor) is not int or not 0 <= anchor < n:
        raise ValueError("invalid speech anchor")
    return tuple((anchor + direction * step) % n for step in range(1, n + 1)
                 if (anchor + direction * step) % n in state.alive)


def resolve_votes(state: State, ballots: Mapping[int, int | None], *,
                  pk: bool = False) -> State:
    """Resolve a complete simultaneous ballot; publication occurs only here.

    An abstention is None.  Each live player votes once, never for themselves.
    PK admits only tied first-round candidates.  All-abstain has no candidates
    and therefore never starts a PK.  A second-round tie eliminates nobody.
    """
    _ongoing(state)
    if set(ballots) != set(state.alive) or any(type(i) is not int for i in ballots):
        raise ValueError("ballots must contain exactly all living voters")
    if pk and not state.pending_pk:
        raise ValueError("no pending PK")
    if not pk and state.pending_pk:
        raise ValueError("pending PK needs a PK ballot")
    allowed = state.pending_pk if pk else state.alive
    for voter, target in ballots.items():
        if target is None:
            continue
        _seat(state, target)
        if target == voter or target not in allowed:
            raise ValueError("illegal vote target")
    counts = Counter(target for target in ballots.values() if target is not None)
    leaders = tuple(sorted(target for target, votes in counts.items()
                           if votes == max(counts.values()))) if counts else ()
    event = PublicEvent(kind="pk_vote" if pk else "vote", day=state.day,
                        ballots=tuple(sorted(ballots.items())), candidates=leaders)
    result = replace(state, public_events=state.public_events + (event,), pending_pk=())
    if len(leaders) == 1:
        return _eliminate(result, leaders[0], "vote")
    if len(leaders) > 1 and state.rules.tie_rule == "pk" and not pk:
        return replace(result, pending_pk=leaders)
    return result
