"""Integrity audit and sampled replay for the frozen v09 experiment."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.experiments import fingerprint
from mafia_lab.replication_experiment import (build_spec, evaluate_game_cell,
                                               evaluate_probe_cell, _good_policies,
                                               _probe_policy, _scores)
from mafia_lab.statistics import paired_summary, win_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "results/v09")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v09_integrity_audit.json")
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    config = json.loads((folder / "source/config.json").read_text())
    replication = json.loads((folder / "replication.json").read_text())
    selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "probe_holdout.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest
    assert fingerprint() == manifest["source_sha256"]
    rules, mafia = build_spec(config)
    by_mafia = {p.name: p for p in mafia}
    good = {p.name: p for p in _good_policies(config)}

    deterministic_split = 0
    for cell in replication["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
        assert cell["mafia_split_rounds"] <= cell["mafia_multi_vote_rounds"]
        if cell["mafia"] in {"combined_det", "origin_det", "echo_det", "echo_mimic_det"}:
            deterministic_split += cell["mafia_split_rounds"]
    assert deterministic_split == 0

    spec = config["probe_selection"]
    candidates = spec["candidates"]
    opponents = spec["opponents"]
    fold_scores = []
    for fold in range(len(spec["fit_folds"])):
        cells = [c for c in selection["fit_cells"] if c["fold"] == fold]
        for cell in cells:
            assert cell["summary"] == win_summary(cell["raw_outcomes"])
        fold_scores.append(_scores(cells, candidates, opponents))
    assert fold_scores == selection["fold_scores"]
    probe_names = [c["name"] for c in candidates if c["timing"] == "civilian_first"]
    stability = {name: {"min_fold_worst": min(s[name]["worst"] for s in fold_scores),
                        "mean_fold_worst": sum(s[name]["worst"] for s in fold_scores) /
                                           len(fold_scores),
                        "mean": sum(s[name]["mean"] for s in fold_scores) / len(fold_scores)}
                 for name in probe_names}
    assert stability == selection["stability_scores"]
    proposed = max(probe_names, key=lambda name: (stability[name]["min_fold_worst"],
                                                   stability[name]["mean_fold_worst"],
                                                   stability[name]["mean"], name))
    assert proposed == selection["proposed"]
    validation_candidates = [next(c for c in candidates if c["name"] == name)
                             for name in ("silent", "early", proposed)]
    for cell in selection["validate_cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
    validate_scores = _scores(selection["validate_cells"], validation_candidates, opponents)
    assert validate_scores == selection["validate_scores"]
    comparator = max(("silent", "early"),
                     key=lambda name: (validate_scores[name]["worst"], validate_scores[name]["mean"]))
    assert comparator == selection["validation_comparator"]
    accepted = (validate_scores[proposed]["worst"] >= validate_scores[comparator]["worst"] +
                spec["accept_worst_gain"] and
                validate_scores[proposed]["mean"] >= validate_scores[comparator]["mean"] -
                spec["mean_noninferiority"])
    assert accepted == selection["accepted"]
    assert selection["selected"] == (proposed if accepted else comparator)

    for cell in holdout["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
        assert cell["activated"] / cell["n"] == cell["activation_rate"]
        assert cell["aligned"] / cell["n"] == cell["alignment_rate"]
        assert cell["total_probes"] / cell["n"] == cell["mean_probes"]
        assert cell["total_unique_targets"] / cell["n"] == cell["mean_unique_targets"]
    lookup = {(c["candidate"], c["mafia"]): c for c in holdout["cells"]}
    recomputed = [{"control": control, "treatment": treatment, "mafia": opponent,
                   "paired": paired_summary(lookup[control, opponent]["raw_outcomes"],
                                             lookup[treatment, opponent]["raw_outcomes"])}
                  for opponent in opponents for control in ("silent", "early")
                  for treatment in [c["name"] for c in candidates
                                    if c["name"] not in {"silent", "early"}]]
    assert recomputed == holdout["paired_comparisons"]

    replayed = 0
    if args.replay:
        for cell in replication["cells"]:
            got = evaluate_game_cell((cell["block"], rules, good[cell["good"]],
                                      by_mafia[cell["mafia"]], 1, cell["seed_start"]))
            assert got["raw_outcomes"][0] == cell["raw_outcomes"][0]
            replayed += 1
        candidate_map = {c["name"]: c for c in candidates}
        for cell in selection["fit_cells"] + selection["validate_cells"] + holdout["cells"]:
            candidate = candidate_map[cell["candidate"]]
            gp = _probe_policy(config, candidate)
            got = evaluate_probe_cell((cell["phase"], cell["fold"], rules, candidate, gp,
                                       by_mafia[cell["mafia"]], 1, cell["seed_start"]))
            assert got["raw_outcomes"][0] == cell["raw_outcomes"][0]
            replayed += 1

    archived = sorted((folder / "source/mafia_lab").glob("*.py"))
    audit = {"status": "pass", "source_sha256": manifest["source_sha256"],
             "checked_replication_cells": len(replication["cells"]),
             "checked_probe_fit_cells": len(selection["fit_cells"]),
             "checked_probe_validation_cells": len(selection["validate_cells"]),
             "checked_probe_holdout_cells": len(holdout["cells"]),
             "checked_external_seed_blocks": (len(config["replication"]["blocks"]) +
                                               len(spec["fit_folds"]) + 2),
             "deterministic_baseline_split_rounds": deterministic_split,
             "selection_path_recomputed": True, "sampled_game_replays": replayed,
             "archived_source_assets": {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
                                        for p in archived},
             "scope": "Integrity and deterministic replay audit, not an independent strategy model."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
