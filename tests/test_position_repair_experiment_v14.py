import json
from pathlib import Path
import unittest

from mafia_lab.position_repair_experiment_v14 import build_spec,evaluate_cell,_matrix,_solution


class PositionRepairExperimentV14Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(Path("configs/position_repair_v14.json").read_text())
        cls.rules,cls.good,cls.mafia=build_spec(cls.config)

    def test_new_disjoint_seed_blocks_and_main_board(self):
        self.assertEqual((self.rules.police,self.rules.mafia,self.rules.civilians),(4,4,8))
        self.assertGreaterEqual(self.config["train"]["seed_start"],128000000)
        self.assertGreaterEqual(self.config["holdout"]["seed_start"],129000000)

    def test_small_matrix_runs_and_solves(self):
        cells=[evaluate_cell(("smoke",self.rules,g,m,127000000,8))
               for g in self.good for m in self.mafia]
        matrix=_matrix(cells,[p.name for p in self.good],[p.name for p in self.mafia])
        solution=_solution(matrix,[p.name for p in self.good],[p.name for p in self.mafia])
        self.assertEqual(len(matrix),4); self.assertEqual(len(matrix[0]),7)
        self.assertEqual(solution["gap_exact"],"0")

    def test_safe_cells_remove_mafia_anchor_in_smoke(self):
        for mafia in self.mafia[1:6]:
            cell=evaluate_cell(("smoke",self.rules,self.good[-1],mafia,127100000,32))
            self.assertEqual(cell["means"]["first_speaker_mafia"],0)


if __name__=="__main__": unittest.main()
