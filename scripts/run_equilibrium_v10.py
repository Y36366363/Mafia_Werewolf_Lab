#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.equilibrium_experiment import run_experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/equilibrium_v10.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v10")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run_experiment(json.loads(args.config.read_text()), args.output,
                                    args.workers), indent=2))


if __name__ == "__main__":
    main()
