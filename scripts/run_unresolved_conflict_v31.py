import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.unresolved_conflict_experiment_v31 import run
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
 print(run(json.loads((ROOT/'configs/unresolved_conflict_v31.json').read_text()),ROOT/'results/v31',a.workers))
