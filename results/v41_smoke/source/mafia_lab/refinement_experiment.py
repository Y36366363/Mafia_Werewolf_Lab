"""Prospective v05 16-player refinement experiment with branch records."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
import shutil
import time

from .engine import Rules
from .experiments import fingerprint, metadata, save_report
from . import strategies_v05 as decisions
from .simulation import continue_game, opening
from .statistics import paired_summary, win_summary
from .large_experiment import select_from_train


def build_spec(config):
    rules = Rules(**config["rules"])
    good = tuple(decisions.GoodPolicyV5(**p) for p in config["good_policies"])
    mafia = tuple(decisions.MafiaPolicyV5(**p) for p in config["mafia_policies"])
    if not good or not mafia:
        raise ValueError("Empty policy pool")
    for group in (good, mafia):
        if len({p.name for p in group}) != len(group):
            raise ValueError("Duplicate policy name")
    intervals = []
    for key in ("train", "test", "sensitivity"):
        n, start = config[key]["n"], config[key]["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int or start < 0:
            raise ValueError("Need at least two independent seeds per block")
        current = (start, start + n)
        if any(max(current[0], a) < min(current[1], b) for a, b in intervals):
            raise ValueError("Seed block overlap")
        intervals.append(current)
    good_names, mafia_names = {p.name for p in good}, {p.name for p in mafia}
    for contrast in config["good_contrasts"]:
        if {contrast["control"], contrast["treatment"]} - good_names:
            raise ValueError("Unknown good contrast")
    for contrast in config["mafia_contrasts"]:
        if {contrast["control"], contrast["treatment"]} - mafia_names:
            raise ValueError("Unknown mafia contrast")
    if config["baseline_good"] not in good_names or config["sensitivity_reference_mafia"] not in mafia_names:
        raise ValueError("Unknown baseline or sensitivity reference")
    return rules, good, mafia


def _branch_summaries(wins, death_roles, check_hits):
    rows = {}
    for label, mask in {
        "first_dead_police": [r == "police" for r in death_roles],
        "first_dead_civilian": [r == "civilian" for r in death_roles],
        "first_check_mafia": list(check_hits),
        "first_check_good": [not value for value in check_hits],
    }.items():
        sample = [win for win, keep in zip(wins, mask) if keep]
        rows[label] = win_summary(sample)
    return rows


def evaluate_cell(job):
    rules, good, mafia, n, start = job
    wins, nights, roles, hits = [], [], [], []
    for seed in range(start, start + n):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        result = continue_game(state, good, mafia, seed, decision_api=decisions)
        if result.good_win not in (0, 1) or not 1 <= result.nights < rules.n_players:
            raise RuntimeError("Terminal invariant failed")
        wins.append(result.good_win)
        nights.append(result.nights)
        roles.append(result.first_death_role)
        hits.append(result.first_check_mafia)
    return {"good": good.name, "mafia": mafia.name, "rules": asdict(rules),
            "seed_start": start, "n": n, "raw_outcomes": wins, "raw_nights": nights,
            "raw_first_death_role": roles, "raw_first_check_mafia": hits,
            "summary": win_summary(wins), "conditional": _branch_summaries(wins, roles, hits)}


def run_cells(jobs, workers):
    if workers == 1:
        yield from map(evaluate_cell, jobs)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            yield from executor.map(evaluate_cell, jobs, chunksize=1)


def all_contrasts(cells, config):
    raw = {(c["good"], c["mafia"]): c["raw_outcomes"] for c in cells}
    family_n = (len(config["good_contrasts"]) * len(config["mafia_policies"]) +
                len(config["mafia_contrasts"]) * len(config["good_policies"]))
    rows = []
    for side, contrasts, opponents in (
        ("good", config["good_contrasts"], config["mafia_policies"]),
        ("mafia", config["mafia_contrasts"], config["good_policies"]),
    ):
        for comparison in contrasts:
            for opponent in opponents:
                a, b, fixed = comparison["control"], comparison["treatment"], opponent["name"]
                x, y = ((raw[a, fixed], raw[b, fixed]) if side == "good"
                        else (raw[fixed, a], raw[fixed, b]))
                stats = paired_summary(x, y)
                radius = sqrt(2 * log(2 * family_n / 0.05) / len(x))
                stats["ci95_familywise_hoeffding"] = [
                    max(-1, stats["delta"] - radius), min(1, stats["delta"] + radius)]
                rows.append({"side": side, "control": a, "treatment": b,
                             "fixed_opponent": fixed, "paired": stats})
    return rows


def run_experiment(config, output, workers=4, progress=print):
    rules, good, mafia = build_spec(config)
    if workers not in (1, 2, 3, 4):
        raise ValueError("workers must be between 1 and 4")
    output = Path(output)
    if (output / "manifest.json").exists():
        raise ValueError("Completed result directory exists; use a new output path")
    output.mkdir(parents=True, exist_ok=True)
    package_hash = fingerprint()
    for src in Path(__file__).parent.glob("*.py"):
        target = output / "source/mafia_lab" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    save_report(output / "source/config.json", config)
    entrypoint = Path(__file__).resolve().parents[1] / "scripts/run_refinement_v05.py"
    target = output / "source/scripts/run_refinement_v05.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entrypoint, target)
    source_assets = {str(path.relative_to(output)): sha256(path.read_bytes()).hexdigest()
                     for path in (output / "source/config.json", target)}
    started = time.monotonic()
    base = metadata(config)
    base["intervals"] = ("Pointwise Wilson and paired normal/Hoeffding; familywise 95% "
                         "Hoeffding applies only to prespecified test contrasts.")
    names_g, names_m = [p.name for p in good], [p.name for p in mafia]
    results = {}
    for phase in ("train", "test"):
        block = config[phase]
        jobs = [(rules, g, m, block["n"], block["seed_start"]) for g in good for m in mafia]
        cells = []
        for cell in run_cells(jobs, workers):
            cells.append(cell)
            if len(cells) % len(mafia) == 0:
                progress(f"{phase}: {len(cells)}/{len(jobs)} cells")
        rates = [[cells[i * len(mafia) + j]["summary"]["rate"] for j in range(len(mafia))]
                 for i in range(len(good))]
        report = {**base, "phase": phase, "seed_block": block, "cells": cells,
                  "matrix": {"good": names_g, "mafia": names_m, "rates": rates}}
        if phase == "train":
            selection = select_from_train(rates, names_g, names_m, config["baseline_good"])
            report["selection"] = selection
            save_report(output / "selection_before_test.json",
                        {**base, "selection": selection,
                         "chosen_from": "train only; test not yet run"})
        else:
            report["selection_from_train"] = selection
            report["all_prespecified_contrasts"] = all_contrasts(cells, config)
            raw = {(c["good"], c["mafia"]): c["raw_outcomes"] for c in cells}
            comparisons = [
                ("respond_to_mafia", selection["baseline_good"], selection["mafia_response"],
                 selection["good_response"], selection["mafia_response"]),
                ("mafia_counter_response", selection["good_response"], selection["mafia_response"],
                 selection["good_response"], selection["second_mafia_response"]),
                ("robust_at_train_worst", selection["baseline_good"], selection["robust_train_worst_mafia"],
                 selection["robust_pure_good"], selection["robust_train_worst_mafia"]),
            ]
            report["selected_heldout_comparisons"] = [
                {"name": label, "control": [ga, ma], "treatment": [gb, mb],
                 "paired": paired_summary(raw[ga, ma], raw[gb, mb])}
                for label, ga, ma, gb, mb in comparisons]
        if fingerprint() != package_hash:
            raise RuntimeError("Package changed during evaluation")
        save_report(output / f"{phase}.json", report)
        results[phase] = report
    chosen_good = sorted({selection["baseline_good"], selection["robust_pure_good"]})
    chosen_mafia = sorted({config["sensitivity_reference_mafia"],
                           selection["robust_train_worst_mafia"]})
    by_g, by_m = {p.name: p for p in good}, {p.name: p for p in mafia}
    block = config["sensitivity"]
    jobs = [(Rules(**variant["rules"]), by_g[g], by_m[m], block["n"], block["seed_start"])
            for variant in block["rule_variants"] for g in chosen_good for m in chosen_mafia]
    cells = list(run_cells(jobs, workers))
    sensitivity = {**base, "phase": "sensitivity", "seed_block": block, "cells": cells,
                   "selection_from_train": selection, "chosen_good": chosen_good,
                   "chosen_mafia": chosen_mafia}
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during sensitivity evaluation")
    save_report(output / "sensitivity.json", sensitivity)
    files = ["train.json", "test.json", "sensitivity.json", "selection_before_test.json"]
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "source_assets": source_assets, "config": config,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": sum(c["n"] for report in results.values() for c in report["cells"])
                                  + sum(c["n"] for c in cells),
                "independent_seed_blocks": {k: config[k] for k in ("train", "test", "sensitivity")},
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": "Finite observation-only heuristic pool; not GTO, equilibrium, or unrestricted response"}
    save_report(output / "manifest.json", manifest)
    return manifest
