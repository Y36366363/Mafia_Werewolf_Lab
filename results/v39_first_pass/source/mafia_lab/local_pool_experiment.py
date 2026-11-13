"""Prospective v06 local-mixture, timing and incremental-pool experiments."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

from .engine import Role, Rules, observe, speech_order
from .experiments import fingerprint, metadata, save_report
from . import strategies_v06 as decisions
from .simulation import continue_game, opening
from .statistics import paired_summary, win_summary
from .tiny import solve_zero_sum


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v06 primary experiment must use 4 police, 4 mafia, 8 civilians")
    good = tuple(decisions.GoodPolicyV6(**p) for p in config["good_candidates"])
    mafia = tuple(decisions.MafiaPolicyV6(**p) for p in config["mafia_candidates"])
    for pool in (good, mafia):
        if not pool or len({p.name for p in pool}) != len(pool):
            raise ValueError("Policy pools must be nonempty and uniquely named")
    good_names, mafia_names = {p.name for p in good}, {p.name for p in mafia}
    if set(config["initial_pool"]["good"]) - good_names:
        raise ValueError("Unknown initial good policy")
    if set(config["initial_pool"]["mafia"]) - mafia_names:
        raise ValueError("Unknown initial mafia policy")
    intervals = []
    for block in (config["matrix_train"], config["matrix_test"],
                  config["timing"]["hit_openings"], config["timing"]["aligned_openings"]):
        n, start = block["n"], block["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int or start < 0:
            raise ValueError("Invalid sample block")
        current = start, start + block.get("scan_limit", n)
        if any(max(current[0], a) < min(current[1], b) for a, b in intervals):
            raise ValueError("Potential seed scan intervals overlap")
        intervals.append(current)
    return rules, good, mafia


def evaluate_matrix_cell(job):
    rules, good, mafia, n, start = job
    outcomes = []
    for seed in range(start, start + n):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        outcomes.append(continue_game(state, good, mafia, seed,
                                      decision_api=decisions).good_win)
    return {"good": good.name, "mafia": mafia.name, "n": n, "seed_start": start,
            "raw_outcomes": outcomes, "summary": win_summary(outcomes)}


def _run(jobs, workers, fn):
    if workers == 1:
        return list(map(fn, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fn, jobs, chunksize=1))


def _matrix(cells, good, mafia):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    return [[Fraction(lookup[g, m]["summary"]["wins"], lookup[g, m]["n"])
             for m in mafia] for g in good]


def _solve_subset(full, all_good, all_mafia, selected_good, selected_mafia):
    gi = [all_good.index(name) for name in selected_good]
    mi = [all_mafia.index(name) for name in selected_mafia]
    solution = solve_zero_sum([[full[i][j] for j in mi] for i in gi])
    return solution


def incremental_pool(train_cells, config):
    """Train-only double-oracle analogue over a frozen finite candidate matrix."""
    good = [p["name"] for p in config["good_candidates"]]
    mafia = [p["name"] for p in config["mafia_candidates"]]
    full = _matrix(train_cells, good, mafia)
    selected_good = list(config["initial_pool"]["good"])
    selected_mafia = list(config["initial_pool"]["mafia"])
    tolerance = Fraction(str(config["expansion"]["tolerance"]))
    history = []
    for iteration in range(1, config["expansion"]["max_rounds"] + 1):
        solution = _solve_subset(full, good, mafia, selected_good, selected_mafia)
        mi = [mafia.index(name) for name in selected_mafia]
        outside_good = [name for name in good if name not in selected_good]
        good_values = {
            name: sum(solution["column_probabilities"][j] * full[good.index(name)][col]
                      for j, col in enumerate(mi)) for name in outside_good
        }
        best_good = max(outside_good, key=lambda n: (good_values[n], n)) if outside_good else None
        add_good = best_good if best_good is not None and good_values[best_good] > solution["value"] + tolerance else None
        if add_good:
            selected_good.append(add_good)

        after_good = _solve_subset(full, good, mafia, selected_good, selected_mafia)
        gi = [good.index(name) for name in selected_good]
        outside_mafia = [name for name in mafia if name not in selected_mafia]
        mafia_values = {
            name: sum(after_good["row_probabilities"][i] * full[row][mafia.index(name)]
                      for i, row in enumerate(gi)) for name in outside_mafia
        }
        best_mafia = min(outside_mafia, key=lambda n: (mafia_values[n], n)) if outside_mafia else None
        add_mafia = (best_mafia if best_mafia is not None and
                     mafia_values[best_mafia] < after_good["value"] - tolerance else None)
        if add_mafia:
            selected_mafia.append(add_mafia)
        final = _solve_subset(full, good, mafia, selected_good, selected_mafia)
        history.append({
            "round": iteration, "start_value": str(solution["value"]),
            "good_response": best_good, "good_response_value": (
                str(good_values[best_good]) if best_good else None), "added_good": add_good,
            "mafia_response": best_mafia, "mafia_response_value": (
                str(mafia_values[best_mafia]) if best_mafia else None), "added_mafia": add_mafia,
            "end_value": str(final["value"]), "good_pool": list(selected_good),
            "mafia_pool": list(selected_mafia),
        })
        if add_good is None and add_mafia is None:
            break
    solution = _solve_subset(full, good, mafia, selected_good, selected_mafia)
    return {"method": "train-only finite-candidate double-oracle analogue",
            "tolerance": str(tolerance), "history": history,
            "good_pool": selected_good, "mafia_pool": selected_mafia,
            "train_value": str(solution["value"]),
            "good_weights": {name: str(weight) for name, weight in
                             zip(selected_good, solution["row_probabilities"]) if weight},
            "mafia_weights": {name: str(weight) for name, weight in
                              zip(selected_mafia, solution["column_probabilities"]) if weight}}


def evaluate_frozen_pool(test_cells, expansion):
    cells = {(c["good"], c["mafia"]): c["raw_outcomes"] for c in test_cells}
    row = {name: Fraction(weight) for name, weight in expansion["good_weights"].items()}
    column = {name: Fraction(weight) for name, weight in expansion["mafia_weights"].items()}
    n = len(next(iter(cells.values())))
    per_seed = [sum(gw * mw * cells[g, m][k] for g, gw in row.items()
                    for m, mw in column.items()) for k in range(n)]
    mean = sum(per_seed, Fraction()) / n
    row_vs_each = {m: sum(gw * sum(cells[g, m]) / n for g, gw in row.items())
                   for m in sorted({m for _, m in cells})}
    column_vs_each = {g: sum(mw * sum(cells[g, m]) / n for m, mw in column.items())
                      for g in sorted({g for g, _ in cells})}
    return {"selection": "weights and pool chosen from train only",
            "heldout_value": float(mean), "heldout_value_exact": str(mean),
            "heldout_good_mix_vs_each_mafia": {k: float(v) for k, v in row_vs_each.items()},
            "heldout_worst_pure_mafia": min(row_vs_each, key=row_vs_each.get),
            "heldout_worst_rate": float(min(row_vs_each.values())),
            "heldout_mafia_mix_vs_each_good": {k: float(v) for k, v in column_vs_each.items()},
            "heldout_best_pure_good": max(column_vs_each, key=column_vs_each.get),
            "heldout_best_rate": float(max(column_vs_each.values()))}


def _opening_record(state, seed):
    return {"seed": seed, "roles": [r.value for r in state.roles],
            "death": state.deaths[0].player, "death_role": state.roles[state.deaths[0].player].value,
            "check": state.investigations[0].target,
            "state_sha256": sha256(repr(state).encode()).hexdigest()}


def select_timing_openings(rules, good, mafia, block, aligned=False):
    selected = []
    for seed in range(block["seed_start"], block["seed_start"] + block["scan_limit"]):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        if not state.investigations[0].is_mafia:
            continue
        if aligned:
            first = speech_order(state)[0]
            if state.roles[first] != Role.CIVILIAN:
                continue
            if decisions.civilian_first_alignment(observe(state, first)) != state.investigations[0].target:
                continue
        selected.append((seed, state))
        if len(selected) == block["n"]:
            return selected
    raise RuntimeError("Timing opening scan limit exhausted")


def evaluate_timing_cell(job):
    cohort, openings, good, mafia = job
    outcomes = [continue_game(state, good, mafia, seed, first_last_words="pass",
                              decision_api=decisions).good_win for seed, state in openings]
    return {"cohort": cohort, "timing": good.day1_timing, "mafia": mafia.name,
            "n": len(outcomes), "seeds": [seed for seed, _ in openings],
            "raw_outcomes": outcomes, "summary": win_summary(outcomes)}


def timing_comparisons(cells):
    lookup = {(c["cohort"], c["timing"], c["mafia"]): c["raw_outcomes"] for c in cells}
    rows = []
    for cohort in sorted({c["cohort"] for c in cells}):
        timings = sorted({c["timing"] for c in cells if c["cohort"] == cohort})
        reference = "early"
        for mafia in sorted({c["mafia"] for c in cells if c["cohort"] == cohort}):
            for timing in timings:
                if timing != reference:
                    rows.append({"cohort": cohort, "mafia": mafia, "control": reference,
                                 "treatment": timing,
                                 "paired": paired_summary(lookup[cohort, reference, mafia],
                                                           lookup[cohort, timing, mafia])})
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
    started = time.monotonic()
    for src in Path(__file__).parent.glob("*.py"):
        target = output / "source/mafia_lab" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    save_report(output / "source/config.json", config)
    entrypoint = Path(__file__).resolve().parents[1] / "scripts/run_local_pool_v06.py"
    target = output / "source/scripts/run_local_pool_v06.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entrypoint, target)

    good_names, mafia_names = [p.name for p in good], [p.name for p in mafia]
    reports = {}
    for phase, key in (("train", "matrix_train"), ("test", "matrix_test")):
        block = config[key]
        jobs = [(rules, g, m, block["n"], block["seed_start"]) for g in good for m in mafia]
        cells = _run(jobs, workers, evaluate_matrix_cell)
        report = {**metadata(config), "phase": phase, "seed_block": block, "cells": cells,
                  "matrix": {"good": good_names, "mafia": mafia_names,
                             "rates": [[float(v) for v in row]
                                       for row in _matrix(cells, good_names, mafia_names)]}}
        if phase == "train":
            expansion = incremental_pool(cells, config)
            report["incremental_pool"] = expansion
            save_report(output / "selection_before_test.json",
                        {"selection": expansion, "chosen_from": "train only; test unread"})
        else:
            report["selection_from_train"] = expansion
            report["frozen_pool_heldout"] = evaluate_frozen_pool(cells, expansion)
        save_report(output / f"{phase}.json", report)
        reports[phase] = report
        progress(f"{phase}: {len(cells)} cells")
        if fingerprint() != package_hash:
            raise RuntimeError("Package changed during evaluation")

    base_good = decisions.GoodPolicyV6(**config["timing"]["opening_good"])
    base_mafia = decisions.MafiaPolicyV6(**config["timing"]["opening_mafia"])
    hit = select_timing_openings(rules, base_good, base_mafia,
                                 config["timing"]["hit_openings"])
    aligned = select_timing_openings(rules, base_good, base_mafia,
                                     config["timing"]["aligned_openings"], aligned=True)
    by_mafia = {p.name: p for p in mafia}
    jobs = []
    for cohort, openings, modes in (("first_check_mafia", hit, ["early", "late", "silent"]),
                                    ("civilian_aligned", aligned,
                                     ["early", "late", "silent", "civilian_first"])):
        for mode in modes:
            policy = decisions.GoodPolicyV6(**{**config["timing"]["continuation_good"],
                                               "name": f"timing_{mode}",
                                               "day1_timing": mode})
            for name in config["timing"]["mafia_policies"]:
                jobs.append((cohort, openings, policy, by_mafia[name]))
    timing_cells = _run(jobs, workers, evaluate_timing_cell)
    timing_report = {**metadata(config), "phase": "timing", "first_last_words": "pass",
                     "opening_policy": {"good": asdict(base_good), "mafia": asdict(base_mafia)},
                     "opening_records": {"first_check_mafia": [_opening_record(s, seed) for seed, s in hit],
                                         "civilian_aligned": [_opening_record(s, seed) for seed, s in aligned]},
                     "cells": timing_cells, "paired_vs_early": timing_comparisons(timing_cells),
                     "selection_note": "Aligned cohort is selected by referee only for causal intervention eligibility."}
    save_report(output / "timing.json", timing_report)
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during evaluation")

    files = ["train.json", "test.json", "timing.json", "selection_before_test.json"]
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": sum(c["n"] for r in reports.values() for c in r["cells"])
                                  + sum(c["n"] for c in timing_cells),
                "independent_seed_blocks": {k: config[k] for k in ("matrix_train", "matrix_test")}
                                           | {"timing_hit": config["timing"]["hit_openings"],
                                              "timing_aligned": config["timing"]["aligned_openings"]},
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": ("4P4M8C finite observation-only local policy pool and fixed-opening timing "
                          "interventions; candidate-pool response coverage, not full-game GTO or CFR convergence")}
    save_report(output / "manifest.json", manifest)
    return manifest
