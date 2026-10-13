"""Run frozen v08 deterministic-target and crossfit experiments."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from mafia_lab.crossfit_experiment import run_experiment
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/crossfit_v08.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v08")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = run_experiment(json.loads(args.config.read_text()), args.output, args.workers,
                            lambda value: print(value, flush=True))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
