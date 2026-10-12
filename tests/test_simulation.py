from dataclasses import replace
from fractions import Fraction
from random import Random
import unittest

from mafia_lab.engine import (Message, Role, Rules, add_message, from_roles,
                              observe, resolve_night)
from mafia_lab.experiments import analytic_controls, branch_experiment, pool_experiment
from mafia_lab.policies import (GOOD_POOL, MAFIA_POOL, GoodPolicy, MafiaPolicy,
                                choose_inspection, choose_kill, message, vote)
from mafia_lab.simulation import continue_game, decision_rng, opening, play
from mafia_lab.statistics import paired_summary, win_summary


class SimulationTests(unittest.TestCase):
    def test_all_policy_pairs_terminate_across_scales(self):
        for rules in [Rules(1,1,2), Rules(2,1,3), Rules(2,2,4,tie_rule="pk"), Rules()]:
            for i, g in enumerate(GOOD_POOL):
                for j, m in enumerate(MAFIA_POOL):
                    outcome = play(rules, g, m, 17000+7*i+j)
                    self.assertIn(outcome.good_win, (0,1))
                    self.assertLessEqual(outcome.nights, rules.n_players-1)

    def test_reproducible_and_fork_does_not_mutate(self):
        rules, good, mafia = Rules(), GOOD_POOL[0], MAFIA_POOL[0]
        state = opening(rules, good, mafia, 99)
        original = state
        a = continue_game(state, good, mafia, 99)
        b = continue_game(state, good, mafia, 99)
        self.assertEqual(a,b)
        self.assertEqual(state,original)
        self.assertEqual(state.messages,())

    def test_public_sequential_ballots_are_reproducible(self):
        rules, good, mafia = Rules(), GOOD_POOL[0], MAFIA_POOL[0]
        a = play(rules, good, mafia, 109, trace=True, public_ballots=True)
        b = play(rules, good, mafia, 109, trace=True, public_ballots=True)
        self.assertEqual(a, b)
        self.assertIn(a.good_win, (0, 1))
        pk = play(replace(rules, tie_rule="pk"), good, mafia, 109,
                  trace=True, public_ballots=True)
        self.assertIn(pk.good_win, (0, 1))

    def test_same_observation_same_policy_distribution(self):
        # Civilian seat 3 cannot tell swapped police/mafia at 0/1 apart.
        a = observe(from_roles(["police","mafia","civilian","civilian"]),3)
        b = observe(from_roles(["mafia","police","civilian","civilian"]),3)
        self.assertEqual(a,b)
        for g in GOOD_POOL:
            for seed in range(20):
                self.assertEqual(message(a,g,Random(seed)),message(b,g,Random(seed)))
                self.assertEqual(vote(a,g,Random(seed)),vote(b,g,Random(seed)))

    def test_night_policies_cannot_see_unknown_roles(self):
        # Police0's mate set and all observations unchanged, mafia swaps1/2.
        a = observe(from_roles(["police","mafia","civilian","civilian"]),0)
        b = observe(from_roles(["police","civilian","mafia","civilian"]),0)
        self.assertEqual(a,b)
        for seed in range(20):
            self.assertEqual(choose_inspection(a,GOOD_POOL[0],Random(seed)),
                             choose_inspection(b,GOOD_POOL[0],Random(seed)))
        a = observe(from_roles(["mafia","police","civilian","civilian"]),0)
        b = observe(from_roles(["mafia","civilian","police","civilian"]),0)
        self.assertEqual(a,b)
        for m in MAFIA_POOL:
            self.assertEqual(choose_kill(a,m,Random(7)),choose_kill(b,m,Random(7)))

    def test_repeated_claims_not_independent_corroboration(self):
        state = resolve_night(from_roles(["police","police","mafia","civilian","civilian","civilian"]),5,4)
        for _ in range(2):
            state = add_message(state,Message(2,"report",3,True,day=1))
        obs = observe(state,4)
        g = GoodPolicy(trust="corroborated")
        outcomes = {vote(obs,g,Random(seed)) for seed in range(20)}
        self.assertGreater(len(outcomes),1)

    def test_fresh_rng_key_not_affected_by_other_draws(self):
        a=decision_rng(3,1,"vote",2).random()
        for _ in range(20):
            decision_rng(3,1,"speech",2).random()
        self.assertEqual(a,decision_rng(3,1,"vote",2).random())

    def test_own_fabricated_report_is_not_evidence(self):
        state = resolve_night(from_roles(["police","police","mafia","civilian","civilian","civilian"]),5,4)
        before = observe(state,4)
        state = add_message(state,Message(4,"report",3,True,day=1))
        after = observe(state,4)
        for seed in range(20):
            self.assertEqual(vote(before,GOOD_POOL[0],Random(seed)),
                             vote(after,GOOD_POOL[0],Random(seed)))

    def test_probability_controls(self):
        report=analytic_controls()
        self.assertEqual(report["subsets_per_q"],495)
        self.assertEqual(report["rows"][1]["dead_mafia_given_nonpolice_death"],"1/3")

    def test_paired_intervals(self):
        stats=paired_summary([0,0,1,1],[1,0,1,0])
        self.assertEqual(stats["delta"],0)
        self.assertEqual((stats["improved"],stats["worsened"]),(1,1))
        zero=paired_summary([0]*20,[0]*20)
        self.assertGreater(zero["ci95_hoeffding"][1],0)
        self.assertEqual(win_summary([])["rate"],None)

    def test_branches_pair_identical_seeds(self):
        report=branch_experiment(24,99000)
        self.assertEqual(sum(report["opening_branch_counts"].values()),24)
        for row in report["comparisons"]:
            self.assertEqual(row["control_summary"]["n"],row["treatment_summary"]["n"])
            self.assertEqual(row["paired"]["n"],len(row["raw_seed_control_treatment"]))

    def test_holdout_leakage_guard(self):
        with self.assertRaises(ValueError):
            pool_experiment(20,20,10,25)


if __name__ == "__main__":
    unittest.main()
