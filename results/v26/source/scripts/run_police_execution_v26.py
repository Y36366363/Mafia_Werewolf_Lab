#!/usr/bin/env python3
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.police_execution_experiment_v26 import run
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'results/v26');p.add_argument('--workers',type=int,default=4);a=p.parse_args()
 print(json.dumps(run(json.loads((ROOT/'configs/police_execution_v26.json').read_text()),a.output,a.workers)))
