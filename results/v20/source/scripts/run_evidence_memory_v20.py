#!/usr/bin/env python3
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.evidence_experiment_v20 import run
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/v20');parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    print(json.dumps(run(json.loads((ROOT/'configs/evidence_memory_v20.json').read_text()),args.output,args.workers)))
