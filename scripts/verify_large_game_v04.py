"""Independent v04 artifact audit, recalculating summaries from terminal records.

This module does not import experiment selection or statistical-report helpers.
It checks reporting/provenance, not unrestricted best responses or game GTO.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isclose, log, sqrt
from pathlib import Path
import argparse
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(actual, expected, label="value"):
    require(isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            f"{label}: {actual} != {expected}")


def package_digest(directory):
    return sha256(b"".join(
        path.name.encode() + b"\0" + path.read_bytes() + b"\0"
        for path in sorted(Path(directory).glob("*.py"))
    )).hexdigest()


def validate_interval(start, n, label):
    require(type(start) is int and start >= 0, f"{label}: invalid seed start")
    require(type(n) is int and n > 0, f"{label}: invalid replicate count")
    return start, start + n - 1


def validate_disjoint(intervals):
    ordered = sorted((lo, hi, label) for label, (lo, hi) in intervals.items())
    for left, right in zip(ordered, ordered[1:]):
        require(left[1] < right[0], f"seed overlap: {left[2]} / {right[2]}")


def validate_wins(values, summary, expected_n):
    require(len(values) == expected_n, "raw outcome count does not match seed block")
    require(all(type(value) is int and value in (0, 1) for value in values),
            "terminal outcomes must be binary integers")
    n, wins = len(values), sum(values)
    require(summary["n"] == n and summary["wins"] == wins,
            "reported denominator/wins mismatch")
    rate, z = wins/n, 1.959963984540054
    equal(summary["rate"], rate, "win rate")
    denominator = 1 + z*z/n
    center = (rate + z*z/(2*n)) / denominator
    radius = z * sqrt(rate*(1-rate)/n + z*z/(4*n*n)) / denominator
    interval = [max(0, center-radius), min(1, center+radius)]
    require(len(summary["ci95_wilson"]) == 2, "invalid Wilson interval")
    for actual, expected in zip(summary["ci95_wilson"], interval):
        equal(actual, expected, "Wilson bound")
    return rate


def validate_pair(control, treatment, summary):
    require(len(control) == len(treatment) == summary["n"], "paired sample mismatch")
    n = len(control)
    require(n > 0, "empty paired sample")
    difference = [b-a for a, b in zip(control, treatment)]
    mean = sum(difference)/n
    equal(summary["delta"], mean, "paired effect")
    for name, sign in (("improved", 1), ("worsened", -1), ("unchanged", 0)):
        require(summary[name] == difference.count(sign), f"paired {name} mismatch")
    if n > 1:
        require(len(summary["ci95_normal"]) == 2, "invalid normal interval")
        half = 1.959963984540054 * sqrt(sum((d-mean)**2 for d in difference)/(n*(n-1)))
        expected = [max(-1, mean-half), min(1, mean+half)]
        for actual, expected in zip(summary["ci95_normal"], expected):
            equal(actual, expected, "paired normal bound")
    else:
        require(summary["ci95_normal"] is None, "n=1 normal interval must be null")
    half = sqrt(2*log(40)/n)
    require(len(summary["ci95_hoeffding"]) == 2, "invalid Hoeffding interval")
    for actual, expected in zip(summary["ci95_hoeffding"],
                                [max(-1, mean-half), min(1, mean+half)]):
        equal(actual, expected, "paired Hoeffding bound")


def pure_selection(rates, good_names, mafia_names, baseline_good=None):
    """Independent named pure-plan selection with lexicographic tie breaks."""
    require(len(rates) == len(good_names), "wrong matrix row count")
    require(all(len(row) == len(mafia_names) for row in rates), "wrong matrix column count")
    if baseline_good is None:
        baseline_good = "uncovered" if "uncovered" in good_names else min(good_names)
    baseline_i = good_names.index(baseline_good)
    mafia_j = min(range(len(mafia_names)), key=lambda j: (rates[baseline_i][j], mafia_names[j]))
    response_i = min(range(len(good_names)), key=lambda i: (-rates[i][mafia_j], good_names[i]))
    second_j = min(range(len(mafia_names)), key=lambda j: (rates[response_i][j], mafia_names[j]))
    robust_i = min(range(len(good_names)), key=lambda i: (-min(rates[i]), good_names[i]))
    worst_j = min(range(len(mafia_names)), key=lambda j: (rates[robust_i][j], mafia_names[j]))
    return {
        "baseline_good": baseline_good,
        "mafia_response": mafia_names[mafia_j],
        "good_response": good_names[response_i],
        "second_mafia_response": mafia_names[second_j],
        "robust_pure_good": good_names[robust_i],
        "robust_train_worst_mafia": mafia_names[worst_j],
        "tie_break": "lexicographic policy name, after objective",
    }


def validate_directory(directory, *, replay=False):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    config = manifest["config"]
    archived = directory / "source"
    assets = manifest["source_assets"]
    allowed_assets = {"source/config.json", "source/scripts/run_large_game_v04.py"}
    require("source/config.json" in assets and set(assets) <= allowed_assets,
            "invalid source asset path set")
    entrypoint = directory / "source/scripts/run_large_game_v04.py"
    require(entrypoint.exists() == ("source/scripts/run_large_game_v04.py" in assets),
            "archived entrypoint missing or absent from asset manifest")
    for filename, expected_digest in assets.items():
        require(sha256((directory / filename).read_bytes()).hexdigest() == expected_digest,
                f"{filename}: source asset SHA256 mismatch")
    require(json.loads((archived / "config.json").read_text()) == config,
            "archived config differs from manifest")
    require(package_digest(archived / "mafia_lab") == manifest["source_sha256"],
            "archived package SHA256 mismatch")
    config_hash = sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    reports = {}
    expected_files = {"train.json", "test.json", "sensitivity.json", "selection_before_test.json"}
    require(set(manifest["files"]) == expected_files, "unexpected artifact set")
    for filename, expected_digest in manifest["files"].items():
        data = (directory / filename).read_bytes()
        require(sha256(data).hexdigest() == expected_digest, f"{filename}: SHA256 mismatch")
        report = json.loads(data)
        require(report["config"] == config, f"{filename}: config mismatch")
        require(report["config_sha256"] == config_hash, f"{filename}: config SHA256 mismatch")
        require(report["source_sha256"] == manifest["source_sha256"], f"{filename}: source generation mismatch")
        require(report["full_game_gto"] is False, "finite-policy report cannot claim full GTO")
        reports[filename[:-5]] = report
    intervals = {phase: validate_interval(config[phase]["seed_start"], config[phase]["n"], phase)
                 for phase in ("train", "test", "sensitivity")}
    validate_disjoint(intervals)
    require(manifest["independent_seed_blocks"] == {phase: config[phase] for phase in intervals},
            "manifest seed block mismatch")
    good_names = [p["name"] for p in config["good_policies"]]
    mafia_names = [p["name"] for p in config["mafia_policies"]]
    require(len(set(good_names)) == len(good_names) and len(set(mafia_names)) == len(mafia_names),
            "duplicate policy names")
    checked_cells = executed_games = paired_checks = 0
    replays = []
    cells_by_phase = {}

    def validate_cell(cell, phase, rules):
        nonlocal checked_cells, executed_games
        n, start = config[phase]["n"], config[phase]["seed_start"]
        require(cell["n"] == n and cell["seed_start"] == start, "cell pairing/seed index mismatch")
        require(cell["rules"] == rules, "cell rules mismatch")
        rate = validate_wins(cell["raw_outcomes"], cell["summary"], n)
        n_players = sum(rules[key] for key in ("police", "mafia", "civilians"))
        require(len(cell["raw_nights"]) == n and all(
            type(k) is int and 1 <= k < n_players for k in cell["raw_nights"]
        ), "terminal mandatory-death bound mismatch")
        checked_cells += 1
        executed_games += n
        if replay:
            for index in sorted({0, n-1}):
                replays.append({"rules": rules, "good": cell["good"], "mafia": cell["mafia"],
                                "seed": start+index, "expected_win": cell["raw_outcomes"][index],
                                "expected_nights": cell["raw_nights"][index]})
        return rate

    rates_by_phase = {}
    for phase in ("train", "test"):
        report = reports[phase]
        require(report["phase"] == phase and report["seed_block"] == config[phase], "phase block mismatch")
        matrix = report["matrix"]
        require(matrix["good"] == good_names and matrix["mafia"] == mafia_names, "matrix labels mismatch")
        cells = {(c["good"], c["mafia"]): c for c in report["cells"]}
        require(len(cells) == len(report["cells"]) == len(good_names)*len(mafia_names),
                "duplicate, missing, or extra matrix cell")
        require(set(cells) == {(g, m) for g in good_names for m in mafia_names}, "wrong matrix arms")
        rates = []
        for i, g in enumerate(good_names):
            row = []
            for j, m in enumerate(mafia_names):
                rate = validate_cell(cells[g, m], phase, config["rules"])
                equal(matrix["rates"][i][j], rate, "matrix rate")
                row.append(rate)
            rates.append(row)
        rates_by_phase[phase], cells_by_phase[phase] = rates, cells
    selection = pure_selection(rates_by_phase["train"], good_names, mafia_names)
    require(reports["train"]["selection"] == selection, "selection not reproduced from train-only matrix")
    require(reports["selection_before_test"]["selection"] == selection, "pre-test selection differs")
    require(reports["test"]["selection_from_train"] == selection, "heldout selection differs")
    require(reports["sensitivity"]["selection_from_train"] == selection, "sensitivity selection differs")
    require(reports["selection_before_test"]["chosen_from"] == "train only; test not yet run",
            "missing prospective selection declaration")
    raw_test = {key: c["raw_outcomes"] for key, c in cells_by_phase["test"].items()}
    expected_contrasts = {
        ("good", contrast["control"], contrast["treatment"], m)
        for contrast in config["good_contrasts"] for m in mafia_names
    } | {
        ("mafia", contrast["control"], contrast["treatment"], g)
        for contrast in config["mafia_contrasts"] for g in good_names
    }
    contrasts = reports["test"]["all_prespecified_contrasts"]
    found = {(r["side"], r["control"], r["treatment"], r["fixed_opponent"]) for r in contrasts}
    require(found == expected_contrasts and len(found) == len(contrasts), "prespecified contrast family mismatch")
    for contrast in contrasts:
        side, a, b, other = (contrast[k] for k in ("side", "control", "treatment", "fixed_opponent"))
        first, second = (raw_test[a, other], raw_test[b, other]) if side == "good" else (raw_test[other, a], raw_test[other, b])
        stats = contrast["paired"]
        validate_pair(first, second, stats)
        radius = sqrt(2*log(2*len(contrasts)/0.05)/len(first))
        require(len(stats["ci95_familywise_hoeffding"]) == 2, "invalid familywise interval")
        for actual, expected in zip(stats["ci95_familywise_hoeffding"],
                                    [max(-1, stats["delta"]-radius), min(1, stats["delta"]+radius)]):
            equal(actual, expected, "familywise Hoeffding bound")
        paired_checks += 1
    s = selection
    expected_selected = {
        "respond_to_mafia": ([s["baseline_good"], s["mafia_response"]], [s["good_response"], s["mafia_response"]]),
        "mafia_counter_response": ([s["good_response"], s["mafia_response"]], [s["good_response"], s["second_mafia_response"]]),
        "robust_at_train_worst": ([s["baseline_good"], s["robust_train_worst_mafia"]], [s["robust_pure_good"], s["robust_train_worst_mafia"]]),
    }
    selected_rows = reports["test"]["selected_heldout_comparisons"]
    require({r["name"] for r in selected_rows} == set(expected_selected) and len(selected_rows) == 3,
            "selected contrast set mismatch")
    for row in selected_rows:
        a, b = expected_selected[row["name"]]
        require(row["control"] == a and row["treatment"] == b, "heldout contrast was not selected from training")
        validate_pair(raw_test[tuple(a)], raw_test[tuple(b)], row["paired"])
        paired_checks += 1
    sensitivity = reports["sensitivity"]
    chosen_good = sorted({s["baseline_good"], s["robust_pure_good"]})
    chosen_mafia = sorted({"signal_mimic", s["robust_train_worst_mafia"]})
    require(sensitivity["phase"] == "sensitivity" and sensitivity["seed_block"] == config["sensitivity"],
            "sensitivity phase block mismatch")
    require(sensitivity["chosen_good"] == chosen_good and sensitivity["chosen_mafia"] == chosen_mafia,
            "sensitivity policies not derived from training")
    signature = lambda rules: json.dumps(rules, sort_keys=True)
    expected_sensitivity = {
        (signature(v["rules"]), g, m)
        for v in config["sensitivity"]["rule_variants"] for g in chosen_good for m in chosen_mafia
    }
    found = {(signature(c["rules"]), c["good"], c["mafia"]) for c in sensitivity["cells"]}
    require(found == expected_sensitivity and len(found) == len(sensitivity["cells"]),
            "sensitivity arm coverage mismatch")
    for cell in sensitivity["cells"]:
        validate_cell(cell, "sensitivity", cell["rules"])
    require(manifest["executed_games"] == executed_games, "executed game count mismatch")
    if replay:
        replay_archived(archived, config, replays)
    return {
        "status": "passed", "source_sha256": manifest["source_sha256"],
        "config_sha256": config_hash, "checked_source_assets": len(assets), "checked_cells": checked_cells,
        "checked_paired_contrasts": paired_checks, "executed_games": executed_games,
        "distinct_seed_units": sum(config[phase]["n"] for phase in intervals),
        "seed_intervals_inclusive": intervals,
        "archived_game_replays": len(replays),
        "selection_reproduced_from_train_only": selection,
        "scope": "Independent raw-outcome, statistics, hash, seed-partition and selection audit; replay uses archived runner; no unrestricted equilibrium certificate",
    }


def replay_archived(archived, config, jobs):
    code = r'''
import json, sys
from pathlib import Path
payload=json.load(sys.stdin)
sys.path.insert(0,payload["archived_source"])
from mafia_lab.engine import Rules
from mafia_lab import strategies_v04 as decisions
from mafia_lab.simulation import play
good={p["name"]:decisions.GoodPolicyV4(**p) for p in payload["config"]["good_policies"]}
mafia={p["name"]:decisions.MafiaPolicyV4(**p) for p in payload["config"]["mafia_policies"]}
for job in payload["jobs"]:
    result=play(Rules(**job["rules"]),good[job["good"]],mafia[job["mafia"]],job["seed"],trace=True,decision_api=decisions)
    assert result.good_win==job["expected_win"],job
    assert result.nights==job["expected_nights"],job
    terminal=result.transcript[-1]
    assert terminal["event"]=="terminal",job
    assert (terminal["payload"]["winner"]=="good")==bool(job["expected_win"]),job
print(len(payload["jobs"]))
'''
    payload = {"archived_source": str(archived), "config": config, "jobs": jobs}
    process = subprocess.run([sys.executable, "-c", code], input=json.dumps(payload),
                             capture_output=True, text=True, check=False)
    require(process.returncode == 0, f"archived replay failed: {process.stderr}")
    require(process.stdout.strip() == str(len(jobs)), "replay count mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default=str(ROOT / "results/v04"))
    parser.add_argument("--replay", action="store_true", help="Replay first/last seed in every archived cell")
    parser.add_argument("--output", help="Optional audit JSON path")
    args = parser.parse_args()
    report = validate_directory(args.directory, replay=args.replay)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
