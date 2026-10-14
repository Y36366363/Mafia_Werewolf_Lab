#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.replication_experiment import run_experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/replication_v09.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v09")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    print(json.dumps(run_experiment(config, args.output, args.workers), indent=2))


if __name__ == "__main__":
    main()
