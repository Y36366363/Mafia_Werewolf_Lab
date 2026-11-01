#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.gold_relay_experiment_v27 import run
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'results/v27');p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    print(json.dumps(run(json.loads((ROOT/'configs/gold_relay_v27.json').read_text()),a.output,a.workers)))
