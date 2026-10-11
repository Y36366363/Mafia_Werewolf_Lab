"""Known police membership constrains interpretation of claimed inspections."""

from random import Random
import unittest

from mafia_lab.engine import Message, add_message, from_roles, observe
from mafia_lab.policies import GoodPolicy, vote


class PoliceClaimConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.state = from_roles([
            "police", "police", "mafia", "civilian", "civilian", "civilian",
        ])
        # Seat 0 knows that seat 2 is not a police teammate. A civilian does not
        # know this roster and may respond to the same unverified public claim.
        self.with_claim = add_message(self.state, Message(2, "report", 4, True))
        self.policy = GoodPolicy("naive_public_trust", "all", "all")

    def test_police_does_not_treat_known_outsider_as_inspection_source(self):
        before = observe(self.state, 0)
        after = observe(self.with_claim, 0)
        self.assertNotIn(2, before.teammates)
        for seed in range(16):
            with self.subTest(seed=seed):
                self.assertEqual(vote(before, self.policy, Random(seed)),
                                 vote(after, self.policy, Random(seed)))

    def test_civilian_can_respond_to_the_same_unverified_claim(self):
        before = observe(self.state, 5)
        after = observe(self.with_claim, 5)
        control = [vote(before, self.policy, Random(seed)) for seed in range(16)]
        treatment = [vote(after, self.policy, Random(seed)) for seed in range(16)]
        self.assertEqual(treatment, [4] * 16)
        self.assertTrue(any(value != 4 for value in control))


if __name__ == "__main__":
    unittest.main()
