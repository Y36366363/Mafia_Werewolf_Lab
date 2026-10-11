"""Run the 16-player cover, mixing and ballot-history experiment."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from mafia_lab.large_experiment import run_experiment
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,default=ROOT/"configs/large_game_v04.json")
    parser.add_argument("--output",type=Path,default=ROOT/"results/v04")
    parser.add_argument("--workers",type=int,default=2)
    args=parser.parse_args()
    report=run_experiment(json.loads(args.config.read_text()),args.output,args.workers,
                          lambda s:print(s,flush=True))
    print(json.dumps({key:report[key] for key in
                      ("version","executed_games","elapsed_seconds","source_sha256")},
                     ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()
