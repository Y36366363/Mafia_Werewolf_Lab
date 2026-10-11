"""Independent audit of v05 raw outcomes, selection, branches and archive replay."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_large_game_v04 import (
    equal, package_digest, pure_selection, require, validate_disjoint,
    validate_interval, validate_pair, validate_wins,
)


def _summary(values):
    n, wins = len(values), sum(values)
    if not n:
        return {"n": 0, "wins": 0, "rate": None, "ci95_wilson": None}
    p, z = wins / n, 1.959963984540054
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return {"n": n, "wins": wins, "rate": p,
            "ci95_wilson": [max(0, center - half), min(1, center + half)]}


def _equal_summary(actual, expected, label):
    require(actual["n"] == expected["n"] and actual["wins"] == expected["wins"],
            f"{label}: count mismatch")
    if expected["n"]:
        equal(actual["rate"], expected["rate"], label)
        for a, b in zip(actual["ci95_wilson"], expected["ci95_wilson"]):
            equal(a, b, label)
    else:
        require(actual["rate"] is None and actual["ci95_wilson"] is None,
                f"{label}: empty summary mismatch")


def validate_directory(directory, replay=False):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    config = manifest["config"]
    archived = directory / "source"
    expected_assets = {"source/config.json", "source/scripts/run_refinement_v05.py"}
    require(set(manifest["source_assets"]) == expected_assets, "source asset set mismatch")
    for name, digest in manifest["source_assets"].items():
        require(sha256((directory / name).read_bytes()).hexdigest() == digest,
                f"{name}: source asset hash mismatch")
    require(json.loads((archived / "config.json").read_text()) == config,
            "archived config mismatch")
    require(package_digest(archived / "mafia_lab") == manifest["source_sha256"],
            "archived package hash mismatch")
    expected_files = {"train.json", "test.json", "sensitivity.json", "selection_before_test.json"}
    require(set(manifest["files"]) == expected_files, "artifact set mismatch")
    reports = {}
    config_hash = sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    for name, digest in manifest["files"].items():
        data = (directory / name).read_bytes()
        require(sha256(data).hexdigest() == digest, f"{name}: artifact hash mismatch")
        report = json.loads(data)
        require(report["config"] == config and report["config_sha256"] == config_hash,
                f"{name}: embedded config mismatch")
        require(report["source_sha256"] == manifest["source_sha256"],
                f"{name}: source generation mismatch")
        require(report["full_game_gto"] is False, "finite pool cannot claim GTO")
        reports[name[:-5]] = report
    intervals = {phase: validate_interval(config[phase]["seed_start"], config[phase]["n"], phase)
                 for phase in ("train", "test", "sensitivity")}
    validate_disjoint(intervals)
    require(manifest["independent_seed_blocks"] == {p: config[p] for p in intervals},
            "seed manifest mismatch")
    good_names = [p["name"] for p in config["good_policies"]]
    mafia_names = [p["name"] for p in config["mafia_policies"]]
    checked_cells = executed = paired_checks = branch_checks = 0
    replay_jobs = []
    cells_by_phase = {}

    def validate_cell(cell, phase, expected_rules):
        nonlocal checked_cells, executed, branch_checks
        n, start = config[phase]["n"], config[phase]["seed_start"]
        require(cell["n"] == n and cell["seed_start"] == start, "cell seed mismatch")
        require(cell["rules"] == expected_rules, "cell rules mismatch")
        validate_wins(cell["raw_outcomes"], cell["summary"], n)
        require(len(cell["raw_nights"]) == n and all(1 <= k < 16 for k in cell["raw_nights"]),
                "terminal night bound mismatch")
        roles, hits = cell["raw_first_death_role"], cell["raw_first_check_mafia"]
        require(len(roles) == len(hits) == n, "branch record length mismatch")
        require(set(roles) <= {"police", "civilian"}, "unexpected first death role")
        require(all(type(value) is bool for value in hits), "invalid inspection branch")
        masks = {
            "first_dead_police": [r == "police" for r in roles],
            "first_dead_civilian": [r == "civilian" for r in roles],
            "first_check_mafia": hits,
            "first_check_good": [not value for value in hits],
        }
        for label, mask in masks.items():
            _equal_summary(cell["conditional"][label],
                           _summary([w for w, keep in zip(cell["raw_outcomes"], mask) if keep]), label)
            branch_checks += 1
        checked_cells += 1
        executed += n
        if replay:
            for index in sorted({0, n - 1}):
                replay_jobs.append({"rules": expected_rules, "good": cell["good"],
                                    "mafia": cell["mafia"], "seed": start + index,
                                    "win": cell["raw_outcomes"][index],
                                    "nights": cell["raw_nights"][index],
                                    "role": roles[index], "hit": hits[index]})

    rates_by_phase = {}
    for phase in ("train", "test"):
        report = reports[phase]
        require(report["phase"] == phase and report["seed_block"] == config[phase],
                "phase metadata mismatch")
        cells = {(c["good"], c["mafia"]): c for c in report["cells"]}
        require(set(cells) == {(g, m) for g in good_names for m in mafia_names},
                "matrix cell coverage mismatch")
        matrix = report["matrix"]
        require(matrix["good"] == good_names and matrix["mafia"] == mafia_names,
                "matrix labels mismatch")
        rates = []
        for i, good in enumerate(good_names):
            row = []
            for j, mafia in enumerate(mafia_names):
                cell = cells[good, mafia]
                validate_cell(cell, phase, config["rules"])
                rate = sum(cell["raw_outcomes"]) / cell["n"]
                equal(matrix["rates"][i][j], rate, "matrix rate")
                row.append(rate)
            rates.append(row)
        rates_by_phase[phase], cells_by_phase[phase] = rates, cells
    selection = pure_selection(rates_by_phase["train"], good_names, mafia_names,
                               config["baseline_good"])
    for label in (reports["train"]["selection"], reports["test"]["selection_from_train"],
                  reports["sensitivity"]["selection_from_train"],
                  reports["selection_before_test"]["selection"]):
        require(label == selection, "train-only selection mismatch")
    raw = {key: cell["raw_outcomes"] for key, cell in cells_by_phase["test"].items()}
    expected = ({("good", c["control"], c["treatment"], m)
                 for c in config["good_contrasts"] for m in mafia_names} |
                {("mafia", c["control"], c["treatment"], g)
                 for c in config["mafia_contrasts"] for g in good_names})
    rows = reports["test"]["all_prespecified_contrasts"]
    require({(r["side"], r["control"], r["treatment"], r["fixed_opponent"])
             for r in rows} == expected and len(rows) == len(expected), "contrast family mismatch")
    for row in rows:
        side, a, b, other = (row[k] for k in ("side", "control", "treatment", "fixed_opponent"))
        x, y = ((raw[a, other], raw[b, other]) if side == "good"
                else (raw[other, a], raw[other, b]))
        validate_pair(x, y, row["paired"])
        radius = sqrt(2 * log(2 * len(rows) / 0.05) / len(x))
        expected_ci = [max(-1, row["paired"]["delta"] - radius),
                       min(1, row["paired"]["delta"] + radius)]
        for actual, wanted in zip(row["paired"]["ci95_familywise_hoeffding"], expected_ci):
            equal(actual, wanted, "familywise interval")
        paired_checks += 1
    for row in reports["test"]["selected_heldout_comparisons"]:
        validate_pair(raw[tuple(row["control"])], raw[tuple(row["treatment"])], row["paired"])
        paired_checks += 1
    sensitivity = reports["sensitivity"]
    chosen_good = sorted({selection["baseline_good"], selection["robust_pure_good"]})
    chosen_mafia = sorted({config["sensitivity_reference_mafia"],
                           selection["robust_train_worst_mafia"]})
    require(sensitivity["chosen_good"] == chosen_good and sensitivity["chosen_mafia"] == chosen_mafia,
            "sensitivity selection mismatch")
    signature = lambda rules: json.dumps(rules, sort_keys=True)
    expected_sensitivity = {(signature(v["rules"]), g, m)
                            for v in config["sensitivity"]["rule_variants"]
                            for g in chosen_good for m in chosen_mafia}
    found = {(signature(c["rules"]), c["good"], c["mafia"]) for c in sensitivity["cells"]}
    require(found == expected_sensitivity, "sensitivity coverage mismatch")
    for cell in sensitivity["cells"]:
        validate_cell(cell, "sensitivity", cell["rules"])
    require(manifest["executed_games"] == executed, "executed game count mismatch")
    if replay:
        replay_archived(archived, config, replay_jobs)
    matrix_path = directory / "restricted_matrix_solution.json"
    matrix_check = validate_matrix_solution(matrix_path, reports["train"], reports["test"])
    return {"status": "passed", "source_sha256": manifest["source_sha256"],
            "checked_cells": checked_cells, "checked_branch_summaries": branch_checks,
            "checked_paired_contrasts": paired_checks, "executed_games": executed,
            "distinct_seed_units": sum(config[p]["n"] for p in intervals),
            "archived_game_replays": len(replay_jobs),
            "restricted_matrix_solution": matrix_check,
            "selection_reproduced_from_train_only": selection,
            "scope": "Independent outcomes, branches, statistics, hashes, selection and archived replay; no GTO certificate"}


def validate_matrix_solution(path, train, test):
    require(path.exists(), "restricted matrix solution missing")
    report = json.loads(path.read_text())
    good, mafia = train["matrix"]["good"], train["matrix"]["mafia"]
    row = [Fraction(report["good_mixture"].get(name, "0")) for name in good]
    column = [Fraction(report["mafia_mixture"].get(name, "0")) for name in mafia]
    require(sum(row) == sum(column) == 1 and min(row + column) >= 0,
            "invalid restricted mixture")
    matrix = [[Fraction(train["cells"][i * len(mafia) + j]["summary"]["wins"],
                        train["cells"][i * len(mafia) + j]["n"])
               for j in range(len(mafia))] for i in range(len(good))]
    lower = min(sum(row[i] * matrix[i][j] for i in range(len(good)))
                for j in range(len(mafia)))
    upper = max(sum(column[j] * matrix[i][j] for j in range(len(mafia)))
                for i in range(len(good)))
    value = Fraction(report["train_value_exact"])
    require(lower == upper == value, "restricted train equilibrium certificate failed")
    raw = {(c["good"], c["mafia"]): c["raw_outcomes"] for c in test["cells"]}
    n = test["seed_block"]["n"]
    row_values = {m: sum(row[i] * sum(raw[g, m]) / n for i, g in enumerate(good))
                  for m in mafia}
    column_values = {g: sum(column[j] * sum(raw[g, m]) / n for j, m in enumerate(mafia))
                     for g in good}
    for name, expected in row_values.items():
        equal(report["heldout_good_mixture_vs_each_mafia"][name], float(expected), "heldout row mixture")
    for name, expected in column_values.items():
        equal(report["heldout_mafia_mixture_vs_each_good"][name], float(expected), "heldout column mixture")
    worst = min(row_values, key=row_values.get)
    best = max(column_values, key=column_values.get)
    require(report["heldout_good_mixture_worst_pure_mafia"]["name"] == worst, "wrong heldout worst column")
    require(report["heldout_mafia_mixture_best_pure_good"]["name"] == best, "wrong heldout best row")
    per_seed = [sum(row[i] * column[j] * raw[g, m][k]
                    for i, g in enumerate(good) for j, m in enumerate(mafia))
                for k in range(n)]
    mean = sum(per_seed, Fraction()) / n
    equal(report["heldout_at_train_mixtures"]["mean"], float(mean), "heldout mixed mean")
    return {"sha256": sha256(path.read_bytes()).hexdigest(), "train_exact_gap": "0",
            "heldout_seed_values": n}


def replay_archived(archived, config, jobs):
    code = r'''
import json,sys
payload=json.load(sys.stdin)
sys.path.insert(0,payload["source"])
from mafia_lab.engine import Rules
from mafia_lab import strategies_v05 as d
from mafia_lab.simulation import opening,continue_game
good={p["name"]:d.GoodPolicyV5(**p) for p in payload["config"]["good_policies"]}
mafia={p["name"]:d.MafiaPolicyV5(**p) for p in payload["config"]["mafia_policies"]}
for j in payload["jobs"]:
 s=opening(Rules(**j["rules"]),good[j["good"]],mafia[j["mafia"]],j["seed"],decision_api=d)
 r=continue_game(s,good[j["good"]],mafia[j["mafia"]],j["seed"],decision_api=d)
 assert (r.good_win,r.nights,r.first_death_role,r.first_check_mafia)==(j["win"],j["nights"],j["role"],j["hit"]),j
print(len(payload["jobs"]))
'''
    payload = {"source": str(archived), "config": config, "jobs": jobs}
    process = subprocess.run([sys.executable, "-c", code], input=json.dumps(payload),
                             text=True, capture_output=True, check=False)
    require(process.returncode == 0, f"archive replay failed: {process.stderr}")
    require(process.stdout.strip() == str(len(jobs)), "archive replay count mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=str(ROOT / "results/v05"))
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = validate_directory(args.directory, args.replay)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
