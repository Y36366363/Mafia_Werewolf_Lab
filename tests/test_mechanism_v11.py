from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import unittest

from mafia_lab.engine import from_roles, resolve_night, observe, add_message, Message
from mafia_lab import strategies_v10 as v10, strategies_v11 as v11
from mafia_lab.mechanism_experiment_v11 import build_spec, evaluate_cell, analyze, contrast_summary
from mafia_lab.simulation import opening

ROOT = Path(__file__).resolve().parents[1]


class MechanismV11Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'configs/mechanism_v11.json').read_text())

    def signal_state(self):
        s = resolve_night(from_roles(['mafia']*4+['police']*4+['civilian']*8),15,10)
        for speaker, kind, target in [(4,'nominate',8),(5,'nominate',8),(6,'police',None)]:
            s = add_message(s, Message(speaker,kind,target,context='day',day=1))
        return s

    def test_channel_switch_changes_only_named_action(self):
        obs = observe(self.signal_state(),0)
        expected = {'none':(6,6), 'vote':(6,4), 'kill':(4,6), 'both':(4,4)}
        for channel, targets in expected.items():
            policy = v11.MafiaPolicyV11(signal_channels=channel)
            self.assertEqual((v11.choose_kill(obs,policy,Random(1)),v11.vote(obs,policy,Random(1))),targets)
        messages = [v11.message(obs,v11.MafiaPolicyV11(signal_channels=c),Random(1)) for c in expected]
        self.assertTrue(all(m == messages[0] for m in messages))

    def test_hidden_role_permutation_does_not_change_mafia_action(self):
        s = self.signal_state()
        roles = list(s.roles); roles[4],roles[9] = roles[9],roles[4]
        other = replace(s,roles=tuple(roles))
        a,b=observe(s,0),observe(other,0)
        self.assertEqual(a,b)
        for channel in self.config['channels']:
            policy=v11.MafiaPolicyV11(signal_channels=channel)
            self.assertEqual(v11.choose_kill(a,policy,Random(1)),v11.choose_kill(b,policy,Random(1)))
            self.assertEqual(v11.vote(a,policy,Random(1)),v11.vote(b,policy,Random(1)))

    def test_zero_signal_night_ties_identical_across_all_channels(self):
        rules,good,mafia=build_spec(self.config)
        for seed in range(88000000,88000008):
            states=[opening(rules,g,m,seed,v11) for g in good for m in mafia]
            self.assertTrue(all(s==states[0] for s in states))

    def test_both_matches_v10_concentration_policy(self):
        obs=observe(self.signal_state(),0)
        new=v11.MafiaPolicyV11(signal_channels='both')
        old=v10.MafiaPolicyV10(counter_mode='concentration',counter_weight=2)
        self.assertEqual(v11.choose_kill(obs,new,Random(2)),v10.choose_kill(obs,old,Random(2)))
        self.assertEqual(v11.vote(obs,new,Random(2)),v10.vote(obs,old,Random(2)))

    def test_same_board_and_budget_contract_rejects_bundled_change(self):
        bad=deepcopy(self.config)
        bad['good_candidates'][0]['inspect_reasoning_probability']=.25
        with self.assertRaises(ValueError):build_spec(bad)
        with self.assertRaises(ValueError):v11.MafiaPolicyV11(counter_mode='none')
        with self.assertRaises(ValueError):v11.MafiaPolicyV11(signal_channels='secret')

    def test_paired_smoke_and_future_action_invariance(self):
        config=deepcopy(self.config); config['evaluation']={'n':4,'seed_start':88000100}
        rules,good,mafia=build_spec(config)
        cells=[evaluate_cell((rules,g,m,88000100,4)) for g in good for m in mafia]
        report=analyze(cells,config)
        self.assertEqual(len(report['primary']),8)
        self.assertTrue(all(report['integrity'].values()))
        bad=deepcopy(cells); bad[1]['opening_hashes'][0]='corrupt'
        with self.assertRaises(ValueError):analyze(bad,config)

    def test_hoeffding_width_accounts_for_interaction_range(self):
        simple=contrast_summary([0,1,-1,0],2)
        interaction=contrast_summary([0,1,-1,0],4)
        self.assertAlmostEqual(interaction['ci95_family_hoeffding'][1],2*simple['ci95_family_hoeffding'][1])
        self.assertGreater(simple['ci95_family_hoeffding'][1],0)


if __name__ == '__main__':unittest.main()
