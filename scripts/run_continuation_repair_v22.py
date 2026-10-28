#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.continuation_repair_v22 import run
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/v22');parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    print(json.dumps(run(json.loads((ROOT/'configs/continuation_repair_v22.json').read_text()),args.output,args.workers)))
