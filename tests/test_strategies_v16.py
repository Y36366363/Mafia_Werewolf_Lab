from random import Random
import unittest

from mafia_lab.engine import Rules, add_message, from_roles, observe, resolve_night, speech_order
from mafia_lab import strategies_v16 as v16


class V16StrategyTests(unittest.TestCase):
    def setUp(self):
        self.rules = Rules(tie_rule="pass")
        self.roles = ["police"] * 4 + ["mafia"] * 4 + ["civilian"] * 8
        self.base = from_roles(self.roles, self.rules)
        self.common_good = dict(
            reveal="silent", trust="none", dead_police_message="truth",
            dead_claim_response="trust", live_counter="hidden",
            inspect_position="gap", dead_clear_plan="truth",
            leadership="nominate", position_model="posterior",
        )

    def good(self, prior="equal", shortlist="hard1"):
        return v16.GoodPolicyV16(name=f"{prior}_{shortlist}", prior_model=prior,
                                 shortlist_rule=shortlist, **self.common_good)

    def mafia(self, mode):
        return v16.MafiaPolicyV16(name=mode, bluff="none", kill="claims",
                                  opening_mode="ordinary", dead_mafia_message="silent",
                                  kill_mode=mode)

    def test_middle_late_mix_selects_only_a_component_action(self):
        obs = observe(self.base, 4)
        mixed = v16.choose_kill(obs, self.mafia("middle_late_mix"), Random(8))
        components = {v16.choose_kill(obs, self.mafia(mode), Random(8))
                      for mode in ("safe_middle", "safe_late")}
        self.assertIn(mixed, components)

    def test_decoy_does_not_read_hidden_good_split(self):
        alternate = from_roles(
            ["civilian"] * 4 + ["mafia"] * 4 + ["police"] * 4 + ["civilian"] * 4,
            self.rules,
        )
        policy = self.mafia("posterior_decoy")
        self.assertEqual(v16.choose_kill(observe(self.base, 4), policy, Random(3)),
                         v16.choose_kill(observe(alternate, 4), policy, Random(3)))

    def test_decoy_uses_late_continuation_after_opening(self):
        state = resolve_night(self.base, 8, 9)
        obs = observe(state, 4)
        decoy = v16.choose_kill(obs, self.mafia("posterior_decoy"), Random(4))
        late = v16.choose_kill(obs, self.mafia("safe_late"), Random(4))
        self.assertEqual(decoy, late)

    def test_robust_score_is_vertex_lower_envelope(self):
        state = resolve_night(self.base, 8, 9)
        obs = observe(state, 0)
        known = {0, 1, 2, 3, 9}
        robust = v16.seat_scores(obs, known, "robust")
        args = (16, 4, 1, 8, tuple(sorted(known)))
        vertices = [v16._posterior_for_mode(*args, mode) for mode in v16.ROBUST_VERTICES]
        for seat in range(16):
            self.assertEqual(robust[seat], min(row[seat] for row in vertices))

    def test_shortlist_lengths_and_adaptive_bounds(self):
        state = resolve_night(self.base, 8, 9)
        for expected, rule in ((1, "hard1"), (2, "list2"), (3, "list3")):
            policy = self.good("robust", rule)
            leader = v16._leader(observe(state, 0))
            call = v16.final_call(observe(state, leader), policy, Random(1))
            self.assertEqual(len(call.targets), expected)
        policy = self.good("robust", "adaptive")
        leader = v16._leader(observe(state, 0))
        size = len(v16.final_call(observe(state, leader), policy, Random(1)).targets)
        self.assertIn(size, {1, 2, 3})

    def test_public_preferences_end_in_one_binding_target(self):
        state = resolve_night(self.base, 8, 9)
        good, mafia = self.good("robust", "list3"), self.mafia("safe_late")
        for player in speech_order(state):
            obs = observe(state, player)
            policy = mafia if obs.role.value == "mafia" else good
            state = add_message(state, v16.message(obs, policy, Random(player), "day"))
        for player in speech_order(state):
            obs = observe(state, player)
            policy = mafia if obs.role.value == "mafia" else good
            msg = v16.final_call(obs, policy, Random(player))
            if msg is not None:
                state = add_message(state, msg)
        self.assertEqual(len(v16._latest_shortlist(observe(state, 0)).targets), 3)
        for player in speech_order(state):
            obs = observe(state, player)
            policy = mafia if obs.role.value == "mafia" else good
            msg = v16.preference(obs, policy, Random(player))
            if msg is not None:
                state = add_message(state, msg)
        selections = []
        for player in speech_order(state):
            obs = observe(state, player)
            policy = mafia if obs.role.value == "mafia" else good
            msg = v16.final_selection(obs, policy, Random(player))
            if msg is not None:
                selections.append(msg)
        self.assertEqual(len(selections), 1)
        self.assertIn(selections[0].target, v16._latest_shortlist(observe(state, 0)).targets)


if __name__ == "__main__":
    unittest.main()
