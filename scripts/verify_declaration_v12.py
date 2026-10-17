#!/usr/bin/env python3
"""Audit archived v12 assets, raw summaries, matrix solutions and sampled replays."""
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
    read = lambda n: json.loads((folder/n).read_text())
    manifest, freeze = read("manifest.json"), read("freeze_before_evaluation.json")
    for name, digest in {**manifest["files"], **freeze["source_assets"]}.items():
        assert sha256((folder/name).read_bytes()).hexdigest() == digest, name
    sys.path.insert(0, str(folder/"source"))
    from mafia_lab.declaration_experiment_v12 import (_cell_from_openings, _cell_root,
        _dead_analysis, _matrix, _solution, _frozen_holdout, build_spec)
    from mafia_lab.tiny import solve_zero_sum
    config = read("source/config.json")
    rules, dead, good, mafia = build_spec(config)
    dead_data, train, holdout = read("dead_police.json"), read("selfkill_train.json"), read("selfkill_holdout.json")
    for report in (dead_data, train, holdout):
        for cell in report["cells"]:
            assert cell["win_summary"]["rate"] == mean(cell["raw"]["win"])
            assert all(len(v) == cell["n"] for v in cell["raw"].values())
    assert dead_data["analysis"] == _dead_analysis(dead_data["cells"], config)
    gn, mn = train["matrix"]["good"], train["matrix"]["mafia"]
    for report in (train, holdout):
        matrix = _matrix(report["cells"], gn, mn)
        assert report["matrix"]["rates_exact"] == [[str(v) for v in row] for row in matrix]
        assert report["restricted_empirical_equilibrium"] == _solution(solve_zero_sum(matrix), gn, mn)
    train_solution = read("selection_before_holdout.json")["train_solution"]
    holdout_matrix = _matrix(holdout["cells"], gn, mn)
    assert holdout["frozen_train_mixture_on_holdout"] == _frozen_holdout(holdout_matrix, gn, mn, train_solution)
    # Same pre-night role deal and inspection across every strategy cell.
    roots = train["cells"][0]["root_signatures"]
    assert all(c["root_signatures"] == roots for c in train["cells"])
    roots_h = holdout["cells"][0]["root_signatures"]
    assert all(c["root_signatures"] == roots_h for c in holdout["cells"])
    replays = 0
    if args.replay:
        gmap, mmap = {p.name:p for p in good}, {p.name:p for p in mafia}
        for report in (train, holdout):
            for cell in report["cells"]:
                for i in sorted({0, cell["n"]//2, cell["n"]-1}):
                    reproduced = _cell_root((cell["phase"], rules, gmap[cell["good"]],
                                             mmap[cell["mafia"]], cell["seed_start"]+i, 1))
                    for key in cell["raw"]:
                        assert reproduced["raw"][key][0] == cell["raw"][key][i]
                    assert reproduced["trace_hashes"][0] == cell["trace_hashes"][i]
                    replays += 1
    audit = {"status":"pass", "dead_cells":len(dead_data["cells"]),
             "selfkill_cells":len(train["cells"])+len(holdout["cells"]),
             "archived_assets_checked":len(freeze["source_assets"]),
             "sampled_full_replays":replays,
             "limits":"Archived sampled replays; not an independent simulator or full-game GTO proof."}
    args.output.write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()

