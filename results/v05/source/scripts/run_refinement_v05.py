"""Run the v05 16-player strategy-refinement experiment."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from mafia_lab.refinement_experiment import run_experiment
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/refinement_v05.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v05")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = run_experiment(json.loads(args.config.read_text()), args.output, args.workers,
                            lambda text: print(text, flush=True))
    keys = ("version", "executed_games", "elapsed_seconds", "source_sha256")
    print(json.dumps({key: result[key] for key in keys}, indent=2), flush=True)


if __name__ == "__main__":
    main()
