#!/usr/bin/env python3
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.restatement_experiment_v23 import run
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'results/v23');p.add_argument('--workers',type=int,default=4);args=p.parse_args()
    print(json.dumps(run(json.loads((ROOT/'configs/restatement_response_v23.json').read_text()),args.output,args.workers)))
