"""Independent integrity audit and sampled deterministic replay for v08."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.crossfit_experiment import (build_spec, evaluate_games, evaluate_probe,
                                            _holdout_good, _probe_policy, _table_policy)
from mafia_lab.experiments import fingerprint
from mafia_lab.simulation import opening
from mafia_lab.statistics import paired_summary, win_summary
from mafia_lab import strategies_v08 as decisions


def intervals_overlap(a, b):
    return max(a[0], b[0]) < min(a[1], b[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "results/v08")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v08_integrity_audit.json")
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    config = json.loads((folder / "source/config.json").read_text())
    table = json.loads((folder / "table_selection_before_holdout.json").read_text())
    probe_selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    matrix = json.loads((folder / "matrix_holdout.json").read_text())
    probe = json.loads((folder / "probe_holdout.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest
    assert fingerprint() == manifest["source_sha256"]
    rules, mafia = build_spec(config)
    by_mafia = {p.name: p for p in mafia}

    cover = list(config["table_crossfit"]["initial_cover_table"])
    police = list(config["table_crossfit"]["initial_police_table"])
    grid = config["table_crossfit"]["probability_grid"]
    spec = config["table_crossfit"]
    seed_intervals, checked_training = [], 0
    for step in table["steps"]:
        assert step["before"] == (cover if step["kind"] == "cover" else police)[step["index"]]
        current = step["before"]
        scores = {float(k): v for k, v in step["fit_scores"].items()}
        proposed = max(grid, key=lambda v: (scores[v]["worst"], scores[v]["mean"],
                                            v == current, -abs(v-current)))
        assert proposed == step["proposed"]
        expected = False
        if proposed != current:
            val = {float(k): v for k, v in step["validate_scores"].items()}
            expected = (val[proposed]["worst"] >= val[current]["worst"] + spec["accept_worst_gain"] and
                        val[proposed]["mean"] >= val[current]["mean"] - spec["mean_noninferiority"])
        assert expected == step["accepted"]
        assert step["chosen"] == (proposed if expected else current)
        for key, n in (("fit_seed_start", spec["fit"]["n"]),
                       ("validate_seed_start", spec["validate"]["n"])):
            interval = (step[key], step[key] + n)
            assert not any(intervals_overlap(interval, old) for old in seed_intervals)
            seed_intervals.append(interval)
        for cell in step["fit_cells"] + step["validate_cells"]:
            assert cell["summary"] == win_summary(cell["raw_outcomes"])
            checked_training += 1
        (cover if step["kind"] == "cover" else police)[step["index"]] = step["chosen"]
    assert cover == table["cover_table"] and police == table["police_table"]

    candidates = config["probe_selection"]["candidates"]
    names = [c["name"] for c in candidates if c["timing"] == "civilian_first"]
    fs = probe_selection["fit_scores"]
    proposed = max(names, key=lambda n: (fs[n]["worst"], fs[n]["mean"], n))
    assert proposed == probe_selection["proposed"]
    vs = probe_selection["validate_scores"]
    accepted = (vs[proposed]["worst"] >= vs["silent"]["worst"] +
                config["probe_selection"]["accept_worst_gain"] and
                vs[proposed]["mean"] >= vs["silent"]["mean"])
    assert accepted == probe_selection["accepted"]
    assert probe_selection["selected"] == (proposed if accepted else "silent")
    for cell in probe_selection["fit_cells"] + probe_selection["validate_cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])

    deterministic_split = 0
    for cell in matrix["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
        if cell["mafia"] in {"combined_det", "origin_det"}:
            deterministic_split += cell["mafia_split_rounds"]
    assert deterministic_split == 0
    for cell in probe["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
        assert cell["activated"] / cell["n"] == cell["activation_rate"]
        assert cell["aligned"] / cell["n"] == cell["alignment_rate"]
    lookup = {(c["candidate"], c["mafia"]): c for c in probe["cells"]}
    recomputed = [{"control": "silent", "treatment": name, "mafia": opponent,
                   "paired": paired_summary(lookup["silent", opponent]["raw_outcomes"],
                                             lookup[name, opponent]["raw_outcomes"])}
                  for opponent in config["probe_selection"]["opponents"]
                  for name in [c["name"] for c in candidates if c["name"] != "silent"]]
    assert recomputed == probe["paired_vs_silent"]

    opening_good = decisions.GoodPolicyV8(**config["probe_selection"]["opening_good"])
    opening_mafia = by_mafia[config["probe_selection"]["opening_mafia"]]
    all_records = (probe_selection["fit_opening_records"] +
                   probe_selection["validate_opening_records"] + probe["opening_records"])
    states = {}
    for record in all_records:
        state = opening(rules, opening_good, opening_mafia, record["seed"], decision_api=decisions)
        assert state.investigations[0].is_mafia
        assert sha256(repr(state).encode()).hexdigest() == record["state_sha256"]
        states[record["seed"]] = state

    replayed = 0
    if args.replay:
        cover = list(config["table_crossfit"]["initial_cover_table"])
        police = list(config["table_crossfit"]["initial_police_table"])
        for step in table["steps"]:
            for phase in ("fit_cells", "validate_cells"):
                cell = step[phase][0]
                value = cell["candidate_value"]
                cv, pv = list(cover), list(police)
                (cv if step["kind"] == "cover" else pv)[step["index"]] = value
                gp = _table_policy(config, cv, pv, cell["good"])
                got = evaluate_games((rules, gp, by_mafia[cell["mafia"]], 1,
                                      cell["seed_start"], False))["raw_outcomes"][0]
                assert got == cell["raw_outcomes"][0]
                replayed += 1
            (cover if step["kind"] == "cover" else police)[step["index"]] = step["chosen"]
        good = {p.name: p for p in _holdout_good(config, table)}
        for cell in matrix["cells"]:
            got = evaluate_games((rules, good[cell["good"]], by_mafia[cell["mafia"]], 1,
                                  cell["seed_start"], True))["raw_outcomes"][0]
            assert got == cell["raw_outcomes"][0]
            replayed += 1
        cmap = {c["name"]: c for c in candidates}
        for cell in probe["cells"]:
            candidate = cmap[cell["candidate"]]
            gp = _probe_policy(config, candidate)
            seed = cell["seeds"][0]
            got = evaluate_probe((candidate, [(seed, states[seed])], gp,
                                  by_mafia[cell["mafia"]]))["raw_outcomes"][0]
            assert got == cell["raw_outcomes"][0]
            replayed += 1

    archived = sorted((folder / "source/mafia_lab").glob("*.py"))
    audit = {"status": "pass", "source_sha256": manifest["source_sha256"],
             "checked_training_cells": checked_training,
             "checked_matrix_cells": len(matrix["cells"]),
             "checked_probe_cells": len(probe["cells"]),
             "checked_openings": len(all_records),
             "checked_coordinate_seed_intervals": len(seed_intervals),
             "deterministic_baseline_split_rounds": deterministic_split,
             "sampled_game_replays": replayed, "selection_paths_recomputed": 2,
             "archived_source_assets": {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
                                        for p in archived},
             "scope": "Integrity and deterministic replay audit, not an independent strategy model."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
