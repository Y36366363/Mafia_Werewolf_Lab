"""v10 response learning and restricted empirical matrix equilibrium."""
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import shutil
import time

from .engine import Rules
from .experiments import fingerprint, metadata, save_report
from .simulation import play
from .statistics import paired_summary, win_summary
from .tiny import solve_zero_sum
from . import strategies_v10 as decisions


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v10 main experiment must use 4 police, 4 mafia, 8 civilians")
    good = tuple(decisions.GoodPolicyV10(**p) for p in config["good_candidates"])
    mafia = tuple(decisions.MafiaPolicyV10(**p) for p in config["mafia_candidates"])
    if len({p.name for p in good}) != len(good) or len({p.name for p in mafia}) != len(mafia):
        raise ValueError("duplicate policy name")
    good_names, mafia_names = {p.name for p in good}, {p.name for p in mafia}
    for family, spec in config["response_learning"].items():
        if spec["target_good"] not in good_names or set(spec["candidates"]) - mafia_names:
            raise ValueError(f"unknown response-learning policy in {family}")
    train, holdout = config["train"], config["holdout"]
    if max(train["seed_start"], holdout["seed_start"]) < min(
            train["seed_start"] + train["n"], holdout["seed_start"] + holdout["n"]):
        raise ValueError("train and holdout overlap")
    return rules, good, mafia


def _run(jobs, workers):
    if workers == 1:
        return list(map(evaluate_cell, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(evaluate_cell, jobs, chunksize=1))


def evaluate_cell(job):
    phase, rules, good, mafia, n, start = job
    outcomes = [play(rules, good, mafia, seed, decision_api=decisions,
                     public_ballots=True).good_win for seed in range(start, start + n)]
    return {"phase": phase, "good": good.name, "mafia": mafia.name, "n": n,
            "seed_start": start, "raw_outcomes": outcomes, "summary": win_summary(outcomes)}


def _matrix(cells, good_names, mafia_names):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    return [[Fraction(lookup[g, m]["summary"]["wins"], lookup[g, m]["n"])
             for m in mafia_names] for g in good_names]


def _solution_artifact(solution, good_names, mafia_names):
    return {"value_exact": str(solution["value"]), "value": float(solution["value"]),
            "good_mixture": {name: str(weight) for name, weight in
                             zip(good_names, solution["row_probabilities"]) if weight},
            "mafia_mixture": {name: str(weight) for name, weight in
                              zip(mafia_names, solution["column_probabilities"]) if weight},
            "lower_exact": str(solution["lower_bound"]),
            "upper_exact": str(solution["upper_bound"]),
            "gap_exact": str(solution["gap"]), "simplex_pivots": solution["pivots"]}


def _fraction_map(names, mapping):
    return [Fraction(mapping.get(name, "0")) for name in names]


def evaluate_frozen_mixture(matrix, good_names, mafia_names, artifact):
    row = _fraction_map(good_names, artifact["good_mixture"])
    column = _fraction_map(mafia_names, artifact["mafia_mixture"])
    vs_columns = [sum(row[i] * matrix[i][j] for i in range(len(good_names)))
                  for j in range(len(mafia_names))]
    vs_rows = [sum(column[j] * matrix[i][j] for j in range(len(mafia_names)))
               for i in range(len(good_names))]
    joint = sum(row[i] * column[j] * matrix[i][j]
                for i in range(len(good_names)) for j in range(len(mafia_names)))
    return {"joint": float(joint), "joint_exact": str(joint),
            "fixed_good_mixture_lower": float(min(vs_columns)),
            "fixed_good_mixture_lower_exact": str(min(vs_columns)),
            "worst_holdout_mafia": mafia_names[vs_columns.index(min(vs_columns))],
            "fixed_mafia_mixture_upper": float(max(vs_rows)),
            "fixed_mafia_mixture_upper_exact": str(max(vs_rows)),
            "best_holdout_good": good_names[vs_rows.index(max(vs_rows))],
            "out_of_sample_gap": float(max(vs_rows) - min(vs_columns)),
            "out_of_sample_gap_exact": str(max(vs_rows) - min(vs_columns)),
            "good_mixture_vs_each_mafia": {name: float(value)
                                           for name, value in zip(mafia_names, vs_columns)},
            "each_good_vs_mafia_mixture": {name: float(value)
                                           for name, value in zip(good_names, vs_rows)}}


def run_experiment(config, output, workers=4, progress=print):
    rules, good, mafia = build_spec(config)
    output = Path(output)
    if (output / "manifest.json").exists():
        raise ValueError("completed result directory exists")
    output.mkdir(parents=True, exist_ok=True)
    package_hash, started = fingerprint(), time.monotonic()
    for src in Path(__file__).parent.glob("*.py"):
        target = output / "source/mafia_lab" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    save_report(output / "source/config.json", config)
    entry = Path(__file__).resolve().parents[1] / "scripts/run_equilibrium_v10.py"
    target = output / "source/scripts/run_equilibrium_v10.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry, target)

    train = config["train"]
    train_cells = _run([("train", rules, g, m, train["n"], train["seed_start"])
                        for g in good for m in mafia], workers)
    good_names, mafia_names = [p.name for p in good], [p.name for p in mafia]
    lookup = {(c["good"], c["mafia"]): c for c in train_cells}
    selected_responses = {}
    for family, spec in config["response_learning"].items():
        target_good = spec["target_good"]
        selected = min(spec["candidates"],
                       key=lambda name: (lookup[target_good, name]["summary"]["rate"], name))
        selected_responses[family] = {
            "target_good": target_good, "selected": selected,
            "candidate_rates": {name: lookup[target_good, name]["summary"]["rate"]
                                for name in spec["candidates"]}}
    train_matrix = _matrix(train_cells, good_names, mafia_names)
    solution = _solution_artifact(solve_zero_sum(train_matrix), good_names, mafia_names)
    selection = {"phase": "before_holdout", "response_families": selected_responses,
                 "restricted_train_equilibrium": solution,
                 "matrix": {"good": good_names, "mafia": mafia_names,
                            "rates_exact": [[str(v) for v in row] for row in train_matrix]},
                 "cells": train_cells, "holdout_unread": True,
                 "scope": "Exact equilibrium of empirical train matrix over frozen finite policies."}
    save_report(output / "selection_before_holdout.json", selection)
    progress(f"train matrix: {len(train_cells)} cells; responses and mixture frozen")
    if fingerprint() != package_hash:
        raise RuntimeError("package changed during selection")

    holdout = config["holdout"]
    holdout_cells = _run([("holdout", rules, g, m, holdout["n"], holdout["seed_start"])
                          for g in good for m in mafia], workers)
    holdout_matrix = _matrix(holdout_cells, good_names, mafia_names)
    lookup_h = {(c["good"], c["mafia"]): c for c in holdout_cells}
    frozen_eval = evaluate_frozen_mixture(holdout_matrix, good_names, mafia_names, solution)
    # This post-hoc solution diagnoses matrix drift; it never changes the frozen promotion decision.
    diagnostic = _solution_artifact(solve_zero_sum(holdout_matrix), good_names, mafia_names)
    paired = [{"control": control, "treatment": treatment, "mafia": m,
               "paired": paired_summary(lookup_h[control, m]["raw_outcomes"],
                                         lookup_h[treatment, m]["raw_outcomes"])}
              for control, treatment in (("crossfit_table", "coord_deliberative_immediate"),
                                         ("probe_w8_diverse", "coord_deliberative_immediate"))
              for m in mafia_names]
    report = {**metadata(config), "phase": "holdout", "cells": holdout_cells,
              "matrix": {"good": good_names, "mafia": mafia_names,
                         "rates_exact": [[str(v) for v in row] for row in holdout_matrix]},
              "frozen_train_mixture_evaluation": frozen_eval,
              "posthoc_holdout_restricted_equilibrium": diagnostic,
              "paired_public_coordination_contrasts": paired}
    save_report(output / "holdout.json", report)
    if fingerprint() != package_hash:
        raise RuntimeError("package changed during holdout")

    files = ["selection_before_holdout.json", "holdout.json"]
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": sum(c["n"] for c in train_cells + holdout_cells),
                "train_games": sum(c["n"] for c in train_cells),
                "holdout_games": sum(c["n"] for c in holdout_cells),
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": ("4P4M8C learned finite counter families and restricted empirical matrix "
                          "equilibrium; fixed-policy evaluation, not full-game GTO")}
    save_report(output / "manifest.json", manifest)
    return manifest
