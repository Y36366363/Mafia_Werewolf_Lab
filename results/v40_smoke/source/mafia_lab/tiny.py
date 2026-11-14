"""Exact, terminating 1P/1M/2C benchmark, not unrestricted Mafia GTO.

Pure team plans use only player observations. Mixing those plans secretly across
all good players additionally assumes a team-private ex-ante correlation device.
The exact matrix certificate applies only to this stated restricted benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations, product
import json
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Claim:
    speaker: int
    target: int | None = None
    mafia: bool | None = None

    @property
    def claims_police(self) -> bool:
        return self.target is not None


@dataclass(frozen=True)
class Observation:
    """Everything a player may use; no other player's true role is exposed."""

    seat: int
    role: str
    alive: tuple[int, ...]
    night_victim: int
    inspection: tuple[int, bool] | None
    history: tuple[Claim, ...] = ()

    @property
    def targets(self) -> tuple[int, ...]:
        return tuple(s for s in self.alive if s != self.seat)


@dataclass(frozen=True)
class GoodPlan:
    police_report: str
    civilian_report: str
    response: str

    @property
    def name(self) -> str:
        return f"p:{self.police_report}|c:{self.civilian_report}|vote:{self.response}"


GOOD_PLANS = tuple(
    GoodPlan(p, c, v)
    for p, c, v in product(
        ("truth", "accusation_only", "silent"),
        ("pass", "fake_accusation"),
        ("first_claim", "last_claim", "ignore_claims"),
    )
)
MAFIA_PLANS = (
    "pass", "accuse_first", "accuse_last", "clear_first", "clear_last",
    "counterclaim", "copy_first", "frame_quiet",
)


def observed_state(
    roles: tuple[str, ...], victim: int, check: int, seat: int,
    history: tuple[Claim, ...] = (),
) -> Observation:
    """Trusted chance/engine projection; strategies receive only its result."""
    role = "C" if roles[seat].startswith("C") else roles[seat]
    order = tuple((victim + i) % 4 for i in range(1, 4))
    private = (check, roles[check] == "M") if role == "P" else None
    return Observation(seat, role, order, victim, private, history)


def good_speech(obs: Observation, plan: GoodPlan) -> Claim:
    if obs.role == "P":
        assert obs.inspection is not None
        target, result = obs.inspection
        if plan.police_report == "truth" or (
            plan.police_report == "accusation_only" and result
        ):
            return Claim(obs.seat, target, result)
    elif plan.civilian_report == "fake_accusation":
        return Claim(obs.seat, obs.targets[0], True)
    return Claim(obs.seat)


def mafia_speech(obs: Observation, plan: str) -> Claim:
    assert obs.role == "M"
    first, last = obs.targets[0], obs.targets[-1]
    prior = tuple(c for c in obs.history if c.claims_police)
    if plan == "pass":
        return Claim(obs.seat)
    if plan == "counterclaim":
        return Claim(obs.seat, prior[0].speaker if prior else first, True)
    if plan == "copy_first":
        return (
            Claim(obs.seat, prior[0].target, prior[0].mafia)
            if prior else Claim(obs.seat, first, True)
        )
    if plan == "frame_quiet":
        claimants = {c.speaker for c in prior}
        target = next((s for s in obs.targets if s not in claimants), first)
        return Claim(obs.seat, target, True)
    if plan not in {"accuse_first", "accuse_last", "clear_first", "clear_last"}:
        raise ValueError(f"unknown mafia plan: {plan}")
    target = first if plan.endswith("first") else last
    return Claim(obs.seat, target, plan.startswith("accuse"))


def good_vote(obs: Observation, plan: GoodPlan) -> int:
    candidates = list(obs.targets)
    if obs.role == "P" and obs.inspection is not None:
        target, result = obs.inspection
        if target in candidates:
            if result:
                return target
            candidates.remove(target)
    # Own fabricated statements are not private evidence. Police knowledge above
    # overrides speech; all other unverified statements get only heuristic weight.
    claims = tuple(
        c for c in obs.history
        if c.claims_police and c.speaker != obs.seat
    )
    scores = {s: 0 for s in candidates}
    if claims and plan.response != "ignore_claims":
        selected = claims[0] if plan.response == "first_claim" else claims[-1]
        if selected.target in scores:
            scores[selected.target] += 1 if selected.mafia else -1
    return max(candidates, key=lambda s: scores[s])


def plurality_elimination(votes: tuple[int, ...], alive: tuple[int, ...]) -> int | None:
    if len(votes) != len(alive):
        raise ValueError("one ballot is required per survivor")
    counts = {s: votes.count(s) for s in alive}
    best = max(counts.values())
    winners = [s for s, n in counts.items() if n == best]
    return winners[0] if len(winners) == 1 else None


def continuation_good_probability(roles: tuple[str, ...], alive: tuple[int, ...]) -> Fraction:
    """Exact fixed silent continuation from the next night to a terminal result.

    Mafia uniformly kills a non-mafia survivor. Day ballots are independently
    uniform among other survivors. With at most P/M/C, termination takes at most
    two further nights and the surviving-mafia win probability is exactly one.
    """
    if not any(roles[s] == "M" for s in alive):
        return Fraction(1)
    if not any(roles[s] == "P" for s in alive):
        return Fraction(0)
    targets = tuple(s for s in alive if roles[s] != "M")
    result = Fraction(0)
    for killed in targets:
        after_night = tuple(s for s in alive if s != killed)
        if not any(roles[s] == "P" for s in after_night):
            continue
        ballots = tuple(tuple(t for t in after_night if t != s) for s in after_night)
        combinations = 1
        for choices in ballots:
            combinations *= len(choices)
        day_total = Fraction(0)
        for votes in product(*ballots):
            out = plurality_elimination(votes, after_night)
            after_day = tuple(s for s in after_night if s != out)
            day_total += continuation_good_probability(roles, after_day)
        result += day_total / combinations
    return result / len(targets)


def scenario_payoff(
    roles: tuple[str, ...], victim: int, check: int,
    good_plan: GoodPlan, mafia_plan: str,
) -> Fraction:
    if roles[victim] == "P":
        return Fraction(0)
    order = tuple((victim + i) % 4 for i in range(1, 4))
    history: tuple[Claim, ...] = ()
    for seat in order:
        obs = observed_state(roles, victim, check, seat, history)
        speech = (
            mafia_speech(obs, mafia_plan) if obs.role == "M"
            else good_speech(obs, good_plan)
        )
        history += (speech,)
    votes = tuple(
        observed_state(roles, victim, check, seat, history).targets[0]
        if roles[seat] == "M" else good_vote(
            observed_state(roles, victim, check, seat, history), good_plan,
        )
        for seat in order
    )
    eliminated = plurality_elimination(votes, order)
    alive = tuple(s for s in order if s != eliminated)
    return continuation_good_probability(roles, alive)


def chance_scenarios():
    """24 labelled deals times 3 uniform checks times 3 uniform night kills."""
    for roles in permutations(("P", "M", "C1", "C2")):
        police, mafia = roles.index("P"), roles.index("M")
        for victim in range(4):
            if victim == mafia:
                continue
            for check in range(4):
                if check != police:
                    yield roles, victim, check


def exact_matrix() -> list[list[Fraction]]:
    scenarios = tuple(chance_scenarios())
    return [
        [
            sum(
                (scenario_payoff(r, v, c, good, mafia) for r, v, c in scenarios),
                Fraction(0),
            ) / len(scenarios)
            for mafia in MAFIA_PLANS
        ]
        for good in GOOD_PLANS
    ]


def random_vote_baseline() -> Fraction:
    """Full chance/ballot enumeration independent of the analytic 1/6 result."""
    total = Fraction(0)
    scenarios = tuple(chance_scenarios())
    for roles, victim, _ in scenarios:
        if roles[victim] == "P":
            continue
        alive = tuple(s for s in range(4) if s != victim)
        total += sum(
            (
                continuation_good_probability(
                    roles,
                    tuple(s for s in alive if s != plurality_elimination(votes, alive)),
                )
                for votes in product(*(tuple(t for t in alive if t != s) for s in alive))
            ),
            Fraction(0),
        ) / 8
    return total / len(scenarios)


def solve_zero_sum(matrix: Sequence[Sequence[Fraction]]) -> dict:
    """Exact rational simplex; good maximizes and mafia minimizes row payoff.

    Returns Fraction value, row_probabilities, column_probabilities, lower_bound,
    upper_bound, gap, plus integer pivots. Bounds are recomputed directly against
    every supplied pure strategy, independently of the tableau objective.
    """
    if not matrix or not matrix[0]:
        raise ValueError("matrix must be nonempty")
    rows, cols = len(matrix), len(matrix[0])
    if any(len(r) != cols for r in matrix):
        raise ValueError("matrix must be rectangular")
    a = [[Fraction(v) for v in row] for row in matrix]
    offset = max(Fraction(1), Fraction(1) - min(min(r) for r in a))
    # Max 1'y subject to (A+offset)y <= 1. Positive RHS gives a feasible slack
    # basis, so phase I is unnecessary. Bland's rule prevents degenerate cycles.
    tableau = [
        [a[i][j] + offset for j in range(cols)]
        + [Fraction(i == k) for k in range(rows)] + [Fraction(1)]
        for i in range(rows)
    ]
    tableau.append([-Fraction(1)] * cols + [Fraction(0)] * (rows + 1))
    basis = [cols + i for i in range(rows)]
    pivots = 0
    while True:
        entering = next((j for j, v in enumerate(tableau[-1][:-1]) if v < 0), None)
        if entering is None:
            break
        eligible = [i for i in range(rows) if tableau[i][entering] > 0]
        if not eligible:
            raise ArithmeticError("unexpected unbounded positive matrix game")
        leaving = min(
            eligible,
            key=lambda i: (tableau[i][-1] / tableau[i][entering], basis[i]),
        )
        scale = tableau[leaving][entering]
        tableau[leaving] = [v / scale for v in tableau[leaving]]
        for i in range(rows + 1):
            if i != leaving:
                factor = tableau[i][entering]
                tableau[i] = [
                    v - factor * p for v, p in zip(tableau[i], tableau[leaving])
                ]
        basis[leaving] = entering
        pivots += 1
        if pivots > 100_000:
            raise ArithmeticError("simplex pivot limit exceeded")
    weight = tableau[-1][-1]
    column_raw = [Fraction(0)] * cols
    for i, variable in enumerate(basis):
        if variable < cols:
            column_raw[variable] = tableau[i][-1]
    row = [tableau[-1][cols + i] / weight for i in range(rows)]
    column = [v / weight for v in column_raw]
    lower = min(sum(row[i] * a[i][j] for i in range(rows)) for j in range(cols))
    upper = max(sum(column[j] * a[i][j] for j in range(cols)) for i in range(rows))
    value = Fraction(1) / weight - offset
    if sum(row) != 1 or sum(column) != 1 or min(row + column) < 0:
        raise ArithmeticError("invalid equilibrium distributions")
    if lower != value or upper != value:
        raise ArithmeticError("independent restricted best-response check failed")
    return {
        "value": value, "row_probabilities": row, "column_probabilities": column,
        "lower_bound": lower, "upper_bound": upper, "gap": upper - lower,
        "pivots": pivots,
    }


def run_tiny_benchmark(output_path: str | Path | None = None) -> dict:
    matrix = exact_matrix()
    solution = solve_zero_sum(matrix)
    baseline = random_vote_baseline()
    report = {
        "model": "tiny_1p1m2c_full_terminal_restricted_policy_pool_v1",
        "scope": "Exact restricted correlated-team-plan benchmark; not full-game GTO",
        "extra_coordination_assumption": (
            "A trusted device privately supplies the same ex-ante good-plan index "
            "to all good players, without revealing teammates. This device is not "
            "part of the ordinary game. Independent local mixtures are not solved."
        ),
        "selected_solution_requires_private_correlation": (
            sum(v > 0 for v in solution["row_probabilities"]) > 1
        ),
        "chance_scenarios": 216,
        "good_plans": [p.name for p in GOOD_PLANS],
        "mafia_plans": list(MAFIA_PLANS),
        "payoff_matrix_exact": [[str(v) for v in r] for r in matrix],
        "random_vote_baseline_exact": str(baseline),
        "random_vote_baseline_analytic_exact": "1/6",
        "value_exact": str(solution["value"]),
        "value": float(solution["value"]),
        "good_mixture": {
            GOOD_PLANS[i].name: str(v)
            for i, v in enumerate(solution["row_probabilities"]) if v
        },
        "mafia_mixture": {
            MAFIA_PLANS[j]: str(v)
            for j, v in enumerate(solution["column_probabilities"]) if v
        },
        "certificate": {
            "arithmetic": "Python fractions.Fraction simplex and direct pure best responses",
            "scope": "Only the supplied 18 x 8 matrix with fixed uniform first-night actions",
            "lower_bound_exact": str(solution["lower_bound"]),
            "upper_bound_exact": str(solution["upper_bound"]),
            "restricted_gap_exact": str(solution["gap"]),
            "simplex_pivots": solution["pivots"],
        },
        "first_night": {
            "inspection": "Uniform among the police player's three other seats",
            "kill": "Uniform among the mafia player's three other seats",
            "dead_civilian_message": "PASS",
            "speech_direction": "Clockwise, first survivor after the night victim",
        },
        "restricted_actions": {
            "mafia_day_one_ballot": "Always first other survivor in speech order",
            "mafia_ballot_invariance": (
                "Good wins only when both good survivors vote mafia; either legal "
                "mafia ballot then loses, and every other good ballot pair loses."
            ),
            "night_actions_optimized": False,
            "pk": False,
            "abstention": False,
            "self_kill": "Omitted: with one mafia, self-kill immediately loses",
            "dead_civilian_nomination": False,
        },
        "continuation": (
            "After day 1, all speech is PASS, votes are independent uniform non-self, "
            "and mafia kills uniformly among non-mafia survivors; all paths terminate "
            "by night 3. A good win requires eliminating mafia on day 1."
        ),
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(run_tiny_benchmark(), indent=2, ensure_ascii=False))
