from itertools import combinations
from random import Random
import unittest

from mafia_lab.engine import from_roles,observe
from mafia_lab import strategies_v14 as v14


class V14StrategyTests(unittest.TestCase):
    def setUp(self):
        self.state=from_roles(["police"]*4+["mafia"]*4+["civilian"]*8)

    def test_all_safe_modes_put_known_nonmafia_first(self):
        obs=observe(self.state,4)
        for mode in sorted(v14.GEOMETRIES-{"random","safe_mix"}):
            target=v14.choose_kill(obs,v14.MafiaPolicyV14(geometry=mode),Random(7))
            order=v14._order_after(obs,target)
            self.assertNotIn(order[0],{4,5,6,7},mode)

    def test_hidden_good_permutation_cannot_change_action(self):
        alternate=from_roles(["civilian"]*4+["mafia"]*4+["police"]*4+["civilian"]*4)
        for mode in sorted(v14.GEOMETRIES):
            policy=v14.MafiaPolicyV14(geometry=mode)
            self.assertEqual(v14.choose_kill(observe(self.state,4),policy,Random(11)),
                             v14.choose_kill(observe(alternate,4),policy,Random(11)))

    def test_geometry_families_do_not_collapse_to_one_rule(self):
        modes=["safe_front","safe_middle","safe_late","safe_sandwich","safe_balanced"]
        distinct={(a,b):False for i,a in enumerate(modes) for b in modes[i+1:]}
        # Across all team geometries every pair must disagree at least once;
        # this guards against renamed duplicate rules, including tie breaks.
        for seats in combinations(range(16),4):
            roles=["civilian"]*16
            for p in seats: roles[p]="mafia"
            for p in [p for p in range(16) if p not in seats][:4]: roles[p]="police"
            state=from_roles(roles)
            actor=seats[0]
            actions={mode:v14.choose_kill(observe(state,actor),
                v14.MafiaPolicyV14(geometry=mode),Random(5)) for mode in modes}
            for pair in distinct:
                distinct[pair] |= actions[pair[0]] != actions[pair[1]]
        self.assertTrue(all(distinct.values()),distinct)

    def test_safe_mix_is_reproducible_and_legal(self):
        obs=observe(self.state,4); policy=v14.MafiaPolicyV14(geometry="safe_mix")
        a=v14.choose_kill(obs,policy,Random(99)); b=v14.choose_kill(obs,policy,Random(99))
        self.assertEqual(a,b); self.assertNotIn(a,{4,5,6,7})


if __name__=="__main__": unittest.main()
