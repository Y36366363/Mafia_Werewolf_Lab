#!/usr/bin/env python3
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.reply_evaluation_v19 import run
if __name__=='__main__':
    print(json.dumps(run(json.loads((ROOT/'configs/reply_v19.json').read_text()),ROOT/'results/v19')))
