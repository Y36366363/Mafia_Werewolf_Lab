#!/usr/bin/env python3
"""Verify raw metrics, frozen assets, paired analysis and sampled full replays."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    p.add_argument("--replay", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    folder = a.folder.resolve()
    read = lambda name: json.loads((folder/name).read_text())
    manifest, freeze = read("manifest.json"), read("freeze_before_evaluation.json")
    for name, expected in {**manifest["files"], **freeze["source_assets"]}.items():
        assert sha256((folder/name).read_bytes()).hexdigest() == expected, name
    # Import archived execution code, not the current workspace package.
    sys.path.insert(0, str(folder/"source"))
    from mafia_lab.mechanism_experiment_v11 import build_spec, evaluate_cell, analyze
    from mafia_lab.statistics import win_summary
    from mafia_lab.experiments import fingerprint
    assert fingerprint() == freeze["source_sha256"]
    data, saved_analysis = read("evaluation.json"), read("analysis.json")
    config, cells = data["config"], data["cells"]
    assert config == read("source/config.json")
    rules, good, mafia = build_spec(config)
    assert freeze["expanded_good"] == json.loads(json.dumps([asdict(g) for g in good]))
    assert freeze["expanded_mafia"] == json.loads(json.dumps([asdict(m) for m in mafia]))
    assert len(cells) == 8
    assert {(c["good"],c["channel"]) for c in cells} == {(g.name,m.signal_channels) for g in good for m in mafia}
    assert manifest["executed_games"] == 8*config["evaluation"]["n"]
    assert manifest["unique_seed_units"] == config["evaluation"]["n"]
    for c in cells:
        n = config["evaluation"]["n"]
        assert c["n"] == n and c["seed_start"] == config["evaluation"]["seed_start"]
        for key, values in c["raw"].items():
            assert len(values) == n and c["means"][key] == mean(values)
            if key in {"win","day1_exile_mafia","day1_exile_police","day1_no_exile","night2_kill_police"}:
                assert set(values) <= {0,1}
        for i in range(n):
            assert sum(c["raw"][k][i] for k in ("day1_exile_mafia","day1_exile_police","day1_no_exile")) <= 1
            assert 0 <= c["raw"]["day1_good_vote_concentration"][i] <= 1
            assert 0 <= c["raw"]["day1_civilian_targets"][i] <= c["raw"]["day1_civilian_nominations"][i] <= 8
        assert c["win_summary"] == win_summary(c["raw"]["win"])
        assert all(len(c[k]) == n for k in ("opening_hashes","day1_prevote_hashes","trace_hashes"))
    assert json.loads(json.dumps(analyze(cells,config))) == saved_analysis
    # Independently recompute contrast signs and means from the raw vectors.
    lookup = {(c["good"],c["channel"]):c for c in cells}
    for contrast in saved_analysis["primary"].values():
        direct = sum(weight*sum(lookup[g,ch]["raw"]["win"])/config["evaluation"]["n"]
                     for g,ch,weight in contrast["terms"])
        assert direct == contrast["delta"]
    replays = 0
    if a.replay:
        gm, mm = {g.name:g for g in good}, {m.signal_channels:m for m in mafia}
        for c in cells:
            for index in sorted({0,c["n"]//2,c["n"]-1}):
                reproduced = evaluate_cell((rules,gm[c["good"]],mm[c["channel"]],c["seed_start"]+index,1))
                for key in c["raw"]:
                    assert reproduced["raw"][key][0] == c["raw"][key][index]
                for key in ("opening_hashes","day1_prevote_hashes","trace_hashes"):
                    assert reproduced[key][0] == c[key][index]
                replays += 1
    audit = {"status":"pass", "cells":8, "seed_units":config["evaluation"]["n"],
             "executed_games":manifest["executed_games"], "primary_contrasts":8,
             "archived_assets_checked":len(freeze["source_assets"]),
             "archived_full_trace_replays":replays, "integrity":saved_analysis["integrity"],
             "limits":"Sampled archived replays, not an independent simulator or all-game rerun; no full-game GTO claim."}
    a.output.write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps(audit,indent=2))


if __name__ == "__main__":
    main()
