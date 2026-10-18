#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.position_nomination_experiment_v13 import run_experiment

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT/"configs/position_nomination_v13.json")
    parser.add_argument("--output", type=Path, default=ROOT/"results/v13")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run_experiment(json.loads(args.config.read_text()),
                                    args.output, args.workers), indent=2))
