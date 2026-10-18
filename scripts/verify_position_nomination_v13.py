#!/usr/bin/env python3
"""Audit archived v13 assets, matrices, conditions and sampled replays."""
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
    read = lambda name: json.loads((folder/name).read_text())
    manifest, freeze = read("manifest.json"), read("freeze_before_evaluation.json")
    for name, digest in manifest["files"].items():
        assert sha256((folder/name).read_bytes()).hexdigest() == digest, name
    for name, digest in freeze["source_assets"].items():
        assert sha256((folder/name).read_bytes()).hexdigest() == digest, name
    sys.path.insert(0, str(folder/"source"))
    from mafia_lab.position_nomination_experiment_v13 import (
        build_spec, _matrix, _solution, _frozen, _cell_position, _cell_nomination,
        _select_nomination_openings,
    )
    from mafia_lab.engine import Role
    config = read("source/config.json")
    rules, pg, pm, ng, nm = build_spec(config)
    reports = {name: read(name+".json") for name in (
        "position_train", "position_holdout", "nomination_train", "nomination_holdout")}
    selection = read("selection_before_holdout.json")
    for report in reports.values():
        gn, mn = report["matrix"]["good"], report["matrix"]["mafia"]
        for cell in report["cells"]:
            assert all(len(values) == cell["n"] for values in cell["raw"].values())
            assert cell["means"] == {key: mean(values) for key, values in cell["raw"].items()}
        matrix = _matrix(report["cells"], gn, mn)
        assert report["matrix"]["rates_exact"] == [[str(v) for v in row] for row in matrix]
        assert report["restricted_empirical_equilibrium"] == _solution(matrix, gn, mn)
    for family in ("position", "nomination"):
        holdout = reports[family+"_holdout"]
        matrix = _matrix(holdout["cells"], holdout["matrix"]["good"],
                         holdout["matrix"]["mafia"])
        expected = _frozen(matrix, holdout["matrix"]["good"], holdout["matrix"]["mafia"],
                           selection[family+"_train_solution"])
        assert holdout["frozen_train_mixture_on_holdout"] == expected
    # Every conditional cell must use the same selected legal opening cohort.
    for phase in ("train", "holdout"):
        report = reports["nomination_"+phase]
        seeds = report["cells"][0]["seeds"]
        assert all(cell["seeds"] == seeds for cell in report["cells"])
        block = config["nomination_"+phase]
        openings = _select_nomination_openings(rules, block, ng[0], nm[0])
        assert [seed for seed, _ in openings] == seeds
        assert all(state.roles[state.deaths[0].player] == Role.POLICE and
                   not state.investigations[0].is_mafia for _, state in openings)
    replays = 0
    if args.replay:
        pgm, pmm = {p.name:p for p in pg}, {p.name:p for p in pm}
        ngm, nmm = {p.name:p for p in ng}, {p.name:p for p in nm}
        for family in ("position", "nomination"):
            for phase in ("train", "holdout"):
                report = reports[f"{family}_{phase}"]
                for cell in report["cells"]:
                    if family == "position":
                        for sample in cell["samples"]:
                            replay = _cell_position((phase, rules, pgm[cell["good"]],
                                                     pmm[cell["mafia"]], sample["seed"], 1))
                            for key in cell["raw"]:
                                assert replay["raw"][key][0] == cell["raw"][key][sample["index"]]
                            assert replay["samples"][0]["trace_hash"] == sample["trace_hash"]
                            replays += 1
                    else:
                        for sample in cell["samples"]:
                            seed = sample["seed"]
                            state = _select_nomination_openings(
                                rules, {"n":1, "seed_start":seed, "scan_limit":1},
                                ng[0], nm[0])[0][1]
                            replay = _cell_nomination((phase, [(seed, state)], ngm[cell["good"]],
                                                       nmm[cell["mafia"]]))
                            for key in cell["raw"]:
                                assert replay["raw"][key][0] == cell["raw"][key][sample["index"]]
                            assert replay["samples"][0]["trace_hash"] == sample["trace_hash"]
                            replays += 1
    audit = {"status":"pass", "cells_checked":sum(len(r["cells"]) for r in reports.values()),
             "archived_assets_checked":len(freeze["source_assets"]),
             "sampled_full_replays":replays,
             "limits":"Sampled archived replay and arithmetic audit; not an independent simulator or full-game GTO proof."}
    args.output.write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
