#!/usr/bin/env python3
"""Audit v17 frozen assets, arithmetic, branch pairing, and sampled replays."""
import argparse, json, sys
from hashlib import sha256
from pathlib import Path
from statistics import mean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    read = lambda name: json.loads((folder / name).read_text())
    manifest, freeze = read("manifest.json"), read("freeze_before_evaluation.json")
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest, name
    for name, digest in freeze["source_assets"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest, name
    sys.path.insert(0, str(folder / "source"))
    from mafia_lab.timed_nomination_experiment_v17 import (
        build_spec, evaluate_cell, _matrix, _solution, _frozen, _contrasts, _branches,
    )
    config = read("source/config.json")
    rules, good, mafia, calibration_mafia = build_spec(config)
    train, holdout, calibration = read("train.json"), read("holdout.json"), read("calibration.json")
    selection = read("selection_before_holdout.json")
    for report in (train, holdout):
        gn, mn = report["matrix"]["good"], report["matrix"]["mafia"]
        for cell in report["cells"]:
            assert all(len(v) == cell["n"] for v in cell["raw"].values())
            assert cell["means"] == {k: mean(v) for k, v in cell["raw"].items()}
            assert cell["branches"] == _branches(cell["raw"])
        matrix = _matrix(report["cells"], gn, mn)
        assert report["matrix"]["rates_exact"] == [[str(v) for v in row] for row in matrix]
        assert report["restricted_empirical_equilibrium"] == _solution(matrix, gn, mn)
        assert report["predeclared_paired_contrasts"] == _contrasts(report["cells"], good, mafia)
    hold_matrix = _matrix(holdout["cells"], holdout["matrix"]["good"],
                          holdout["matrix"]["mafia"])
    assert holdout["frozen_train_mixture_on_holdout"] == _frozen(
        hold_matrix, holdout["matrix"]["good"], holdout["matrix"]["mafia"],
        selection["train_solution"])
    for cell in calibration["cells"]:
        assert cell["mafia"] == calibration_mafia.name
        assert all(len(v) == cell["n"] for v in cell["raw"].values())
        assert cell["means"] == {k: mean(v) for k, v in cell["raw"].items()}
        assert cell["branches"] == _branches(cell["raw"])
    replayed = 0
    if args.replay:
        gm, mm = {p.name: p for p in good}, {p.name: p for p in mafia}
        groups = [(train, mm), (holdout, mm),
                  (calibration, {calibration_mafia.name: calibration_mafia})]
        for report, use_mafia in groups:
            for cell in report["cells"]:
                for sample in cell["samples"]:
                    reproduced = evaluate_cell((cell["phase"], rules, gm[cell["good"]],
                                                use_mafia[cell["mafia"]], sample["seed"], 1))
                    for key in cell["raw"]:
                        assert reproduced["raw"][key][0] == cell["raw"][key][sample["index"]]
                    assert reproduced["samples"][0]["trace_hash"] == sample["trace_hash"]
                    replayed += 1
    audit = {"status": "pass",
             "cells_checked": len(train["cells"]) + len(holdout["cells"]) + len(calibration["cells"]),
             "archived_assets_checked": len(freeze["source_assets"]),
             "sampled_full_replays": replayed,
             "limits": "Archived arithmetic and sampled replay audit; not an independent simulator, unrestricted deviation search, or full-game GTO proof."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
