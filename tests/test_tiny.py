import unittest
from fractions import Fraction
from itertools import combinations, product

from mafia_lab.tiny import (
    Claim, GOOD_PLANS, MAFIA_PLANS, GoodPlan, chance_scenarios,
    continuation_good_probability, exact_matrix, good_speech, good_vote,
    mafia_speech, observed_state, plurality_elimination, random_vote_baseline,
    run_tiny_benchmark, scenario_payoff, solve_zero_sum,
)


class TinyInformationTests(unittest.TestCase):
    def test_hidden_worlds_have_identical_local_observations(self):
        # Mafia cannot distinguish which surviving opponent is the police.
        left, right = ("M", "P", "C1", "C2"), ("M", "C1", "P", "C2")
        history = (Claim(1, 2, True),)
        a = observed_state(left, 3, 0, 0, history)
        b = observed_state(right, 3, 0, 0, history)
        self.assertEqual(a, b)
        self.assertIsNone(a.inspection)
        for plan in MAFIA_PLANS:
            self.assertEqual(mafia_speech(a, plan), mafia_speech(b, plan))
        # A civilian does not get the police's secret inspection or true role.
        left, right = ("C1", "P", "M", "C2"), ("C1", "M", "P", "C2")
        a = observed_state(left, 3, 2, 0, history)
        b = observed_state(right, 3, 1, 0, history)
        self.assertEqual(a, b)
        for plan in GOOD_PLANS:
            self.assertEqual(good_speech(a, plan), good_speech(b, plan))
            self.assertEqual(good_vote(a, plan), good_vote(b, plan))

    def test_only_police_receive_inspection_and_all_actions_legal(self):
        count = 0
        for roles, victim, check in chance_scenarios():
            count += 1
            for seat in range(4):
                obs = observed_state(roles, victim, check, seat)
                self.assertEqual(obs.inspection is not None, roles[seat] == "P")
                if seat == victim:
                    continue
                for good in GOOD_PLANS:
                    if obs.role != "M":
                        self.assertIn(good_vote(obs, good), obs.targets)
                        speech = good_speech(obs, good)
                        if speech.target is not None:
                            self.assertIn(speech.target, range(4))
                if obs.role == "M":
                    for mafia in MAFIA_PLANS:
                        speech = mafia_speech(obs, mafia)
                        if speech.target is not None:
                            self.assertIn(speech.target, obs.targets)
        self.assertEqual(count, 24 * 3 * 3)

    def test_truthful_check_may_target_dead_civilian(self):
        roles = ("P", "M", "C1", "C2")
        obs = observed_state(roles, 2, 2, 0)
        speech = good_speech(obs, GoodPlan("truth", "pass", "first_claim"))
        self.assertEqual(speech, Claim(0, 2, False))


class TinyGameTests(unittest.TestCase):
    def test_uniform_baseline_matches_independent_analytic_result(self):
        # Police survives 2/3; both good voters independently hit mafia 1/2 each.
        self.assertEqual(random_vote_baseline(), Fraction(2, 3) * Fraction(1, 2) ** 2)

    def test_three_distinct_ballots_tie_without_elimination(self):
        self.assertIsNone(plurality_elimination((1, 2, 0), (0, 1, 2)))

    def test_every_continuation_reaches_exact_terminal_result(self):
        roles = ("P", "M", "C1", "C2")
        # The continuation is only entered with at most three survivors.
        for size in range(1, 4):
            for alive in combinations(range(4), size):
                expected = Fraction(0 if 1 in alive else 1)
                self.assertEqual(continuation_good_probability(roles, alive), expected)

    def test_day_one_only_mafia_elimination_can_win(self):
        roles, victim = ("P", "M", "C1", "C2"), 3
        alive = (0, 1, 2)
        for votes in product((1, 2), (0, 2), (0, 1)):
            out = plurality_elimination(votes, alive)
            actual = continuation_good_probability(roles, tuple(s for s in alive if s != out))
            self.assertEqual(actual, Fraction(int(out == 1)))

    def test_all_policies_lose_when_only_police_dies_first(self):
        roles = ("P", "M", "C1", "C2")
        for g, m in product(GOOD_PLANS, MAFIA_PLANS):
            self.assertEqual(scenario_payoff(roles, 0, 1, g, m), 0)


class ExactMatrixTests(unittest.TestCase):
    def test_matching_pennies_and_negative_entries(self):
        result = solve_zero_sum([[1, -1], [-1, 1]])
        self.assertEqual(result["value"], 0)
        self.assertEqual(result["row_probabilities"], [Fraction(1, 2)] * 2)
        self.assertEqual(result["column_probabilities"], [Fraction(1, 2)] * 2)
        self.assertEqual(result["gap"], 0)

    def test_rps(self):
        result = solve_zero_sum([[0, -1, 1], [1, 0, -1], [-1, 1, 0]])
        self.assertEqual(result["row_probabilities"], [Fraction(1, 3)] * 3)
        self.assertEqual(result["column_probabilities"], [Fraction(1, 3)] * 3)
        self.assertEqual(result["value"], 0)

    def test_rectangular_and_degenerate_games(self):
        for matrix, value in [([[2, 2, 2], [1, 1, 1]], 2), ([[0, 0], [0, 0]], 0), ([[Fraction(1, 7)]], Fraction(1, 7))]:
            result = solve_zero_sum(matrix)
            self.assertEqual(result["value"], value)
            self.assertEqual(result["gap"], 0)

    def test_bad_matrices_rejected(self):
        for matrix in ([], [[]], [[1], [1, 2]]):
            with self.assertRaises(ValueError):
                solve_zero_sum(matrix)

    def test_every_pure_best_response_certified(self):
        matrix = exact_matrix()
        result = solve_zero_sum(matrix)
        p, q = result["row_probabilities"], result["column_probabilities"]
        value = result["value"]
        for j in range(len(MAFIA_PLANS)):
            self.assertGreaterEqual(sum(p[i] * matrix[i][j] for i in range(len(p))), value)
        for i in range(len(GOOD_PLANS)):
            self.assertLessEqual(sum(q[j] * matrix[i][j] for j in range(len(q))), value)
        self.assertEqual(value, Fraction(8, 27))

    def test_counterstrategy_reverses_truthful_claim_advantage(self):
        matrix = exact_matrix()
        truth = GOOD_PLANS.index(GoodPlan("truth", "pass", "first_claim"))
        robust = GOOD_PLANS.index(GoodPlan("truth", "pass", "ignore_claims"))
        passive, counter = MAFIA_PLANS.index("pass"), MAFIA_PLANS.index("accuse_last")
        self.assertGreater(matrix[truth][passive], matrix[robust][passive])
        self.assertLess(matrix[truth][counter], matrix[robust][counter])

    def test_optional_scipy_independent_lp_crosscheck(self):
        try:
            import numpy as np
            from scipy.optimize import linprog
        except ImportError:
            self.skipTest("SciPy is optional; exact stdlib certificate remains available")
        matrix = exact_matrix()
        a = np.asarray([[float(v) for v in r] for r in matrix])
        n, m = a.shape
        # Good maximizes v subject to p'A >= v, sum p=1.
        objective = np.r_[np.zeros(n), -1.0]
        result = linprog(
            objective, A_ub=np.c_[-a.T, np.ones(m)], b_ub=np.zeros(m),
            A_eq=np.array([np.r_[np.ones(n), 0.0]]), b_eq=[1.0],
            bounds=[(0, None)] * n + [(None, None)], method="highs",
        )
        self.assertTrue(result.success)
        self.assertAlmostEqual(-result.fun, float(solve_zero_sum(matrix)["value"]), places=12)

    def test_report_labels_matrix_scope_and_coordination_assumption(self):
        report = run_tiny_benchmark()
        self.assertIn("not full-game GTO", report["scope"])
        self.assertIn("not part of", report["extra_coordination_assumption"])
        self.assertEqual(report["certificate"]["restricted_gap_exact"], "0")


if __name__ == "__main__":
    unittest.main()
