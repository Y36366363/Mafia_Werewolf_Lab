"""Run from the repository with python3 -m mafia_lab."""
import argparse
from dataclasses import asdict
import json

from .engine import Rules
from .experiments import analytic_controls, run_suite, save_report
from .policies import GOOD_POOL, MAFIA_POOL
from .simulation import play


def main():
    parser = argparse.ArgumentParser(description="Hidden-role game research CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    suite = sub.add_parser("suite", help="Run frozen experiments and write auditable JSON")
    suite.add_argument("--config", default="configs/experiment_v01.json")
    suite.add_argument("--output", default="results/v01")
    tiny = sub.add_parser("tiny", help="Exact complete tiny variant, restricted policy pool")
    tiny.add_argument("--output", default="results/tiny_exact.json")
    sub.add_parser("controls", help="Reproduce rational probability controls")
    demo = sub.add_parser("demo", help="Run a complete game and print a public transcript")
    demo.add_argument("--seed", type=int, default=20261010)
    demo.add_argument("--police", type=int, default=4)
    demo.add_argument("--mafia", type=int, default=4)
    demo.add_argument("--civilians", type=int, default=8)
    demo.add_argument("--pk", action="store_true")
    demo.add_argument("--good-policy", choices=[p.name for p in GOOD_POOL], default=GOOD_POOL[0].name)
    demo.add_argument("--mafia-policy", choices=[p.name for p in MAFIA_POOL], default=MAFIA_POOL[2].name)
    args = parser.parse_args()
    if args.command == "suite":
        run_suite(args.config, args.output, progress=lambda s: print(s, flush=True))
        print(f"Reports saved to {args.output}")
    elif args.command == "tiny":
        from .tiny import run_tiny_benchmark
        result = run_tiny_benchmark()
        save_report(args.output, result)
        print(f"Exact restricted benchmark saved to {args.output}")
    elif args.command == "controls":
        print(json.dumps(analytic_controls(), indent=2))
    else:
        rules = Rules(args.police, args.mafia, args.civilians, tie_rule="pk" if args.pk else "pass")
        good = next(p for p in GOOD_POOL if p.name == args.good_policy)
        mafia = next(p for p in MAFIA_POOL if p.name == args.mafia_policy)
        result = asdict(play(rules, good, mafia, args.seed, trace=True))
        # Outcome metadata is postgame evaluation; transcript itself has no
        # private roles or inspection results except unverified public claims.
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
