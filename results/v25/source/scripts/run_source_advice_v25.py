#!/usr/bin/env python3
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.source_advice_experiment_v25 import run
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'results/v25');p.add_argument('--workers',type=int,default=4);a=p.parse_args()
 print(json.dumps(run(json.loads((ROOT/'configs/source_advice_v25.json').read_text()),a.output,a.workers)))
