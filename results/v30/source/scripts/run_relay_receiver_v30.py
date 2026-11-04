import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.relay_receiver_experiment_v30 import run
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);a=p.parse_args()
 print(run(json.loads((ROOT/'configs/relay_receiver_v30.json').read_text()),ROOT/'results/v30',a.workers))
