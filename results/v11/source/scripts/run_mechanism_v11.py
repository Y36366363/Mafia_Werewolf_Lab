#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.mechanism_experiment_v11 import run_experiment

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=ROOT/"configs/mechanism_v11.json")
    p.add_argument("--output", type=Path, default=ROOT/"results/v11")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    print(json.dumps(run_experiment(json.loads(a.config.read_text()), a.output, a.workers), indent=2))
