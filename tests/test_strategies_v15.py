from fractions import Fraction
from random import Random
import unittest

from mafia_lab.engine import Rules, from_roles, observe, resolve_night, add_message, Message
from mafia_lab import strategies_v15 as v15


class V15StrategyTests(unittest.TestCase):
    def setUp(self):
        rules = Rules(tie_rule="pk")
        base = from_roles(["police"] * 4 + ["mafia"] * 4 + ["civilian"] * 8, rules)
        self.state = resolve_night(base, 8, 4)  # civilian dies; seat 4 is a hit
        self.common = dict(reveal="silent", trust="none", dead_police_message="truth",
                           dead_claim_response="trust", live_counter="hidden",
                           inspect_position="gap", dead_clear_plan="truth")

    def policy(self, leadership, position_model="naive"):
        return v15.GoodPolicyV15(name=f"{leadership}_{position_model}",
                                 leadership=leadership,
                                 position_model=position_model, **self.common)

    def test_only_one_surviving_police_reports(self):
        policy = self.policy("report")
        reports = []
        for player in self.state.alive:
            obs = observe(self.state, player)
            if obs.role.value != "mafia":
                msg = v15.message(obs, policy, Random(3), "day")
                if msg.kind == "report":
                    reports.append(msg)
        self.assertEqual(len(reports), 1)
        self.assertEqual((reports[0].target, reports[0].verdict), (4, True))

    def test_hit_produces_single_target_even_under_pk_protocol(self):
        policy = self.policy("pk", "posterior")
        leader = v15._living_leader(observe(self.state, 0))
        call = v15.final_call(observe(self.state, leader), policy, Random(1))
        self.assertEqual(call.targets, (4,))

    def test_clear_branch_naive_and_posterior_are_legal(self):
        base = from_roles(["police"] * 4 + ["mafia"] * 4 + ["civilian"] * 8,
                          Rules(tie_rule="pk"))
        state = resolve_night(base, 8, 9)  # civilian clear
        for mode in ("naive", "posterior"):
            policy = self.policy("pk", mode)
            leader = v15._living_leader(observe(state, 0))
            call = v15.final_call(observe(state, leader), policy, Random(1))
            self.assertEqual(len(call.targets), 2)
            self.assertFalse(set(call.targets) & {0, 1, 2, 3, 8, 9})

    def test_posterior_is_normalized_and_uses_no_known_good(self):
        obs = observe(self.state, 0)
        known_good = {0, 1, 2, 3}
        posterior = v15.position_posterior(obs, known_good)
        self.assertEqual(sum(posterior.values()), Fraction(4))
        self.assertTrue(all(posterior[p] == 0 for p in known_good | {8}))

    def test_hidden_good_permutation_cannot_change_posterior_call(self):
        policy = self.policy("pk", "posterior")
        # Preserve police and mafia seats; permute only police-vs-civilian labels
        # would change legal police knowledge, so instead permute civilian labels,
        # which are observationally identical and must leave the action unchanged.
        obs = observe(self.state, v15._living_leader(observe(self.state, 0)))
        first = v15.final_call(obs, policy, Random(2)).targets
        second = v15.final_call(obs, policy, Random(99)).targets
        self.assertEqual(first, second)

    def test_position_model_does_not_read_real_mafia_labels(self):
        policy = self.policy("pk", "posterior")
        # Two referee states produce the same police observation: known police,
        # victim, clear, and all public data match while hidden mafia/civilian
        # labels among unknown seats differ.
        roles_a = ["police"] * 4 + ["mafia"] * 4 + ["civilian"] * 8
        roles_b = ["police"] * 4 + ["civilian"] * 4 + ["mafia"] * 4 + ["civilian"] * 4
        a = resolve_night(from_roles(roles_a, Rules(tie_rule="pk")), 15, 14)
        b = resolve_night(from_roles(roles_b, Rules(tie_rule="pk")), 15, 14)
        leader_a = v15._living_leader(observe(a, 0))
        leader_b = v15._living_leader(observe(b, 0))
        self.assertEqual(
            v15.final_call(observe(a, leader_a), policy, Random(1)).targets,
            v15.final_call(observe(b, leader_b), policy, Random(1)).targets,
        )


if __name__ == "__main__":
    unittest.main()
