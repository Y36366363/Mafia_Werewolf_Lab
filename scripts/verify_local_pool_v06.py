"""Independent structural/statistical audit and sampled replay for frozen v06."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.engine import Role, Rules, observe, speech_order
from mafia_lab.experiments import fingerprint
from mafia_lab.local_pool_experiment import (build_spec, incremental_pool,
                                              timing_comparisons)
from mafia_lab.simulation import continue_game, opening
from mafia_lab.statistics import win_summary
from mafia_lab import strategies_v06 as decisions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "results/v06")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v06_integrity_audit.json")
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    config = json.loads((folder / "source/config.json").read_text())
    train = json.loads((folder / "train.json").read_text())
    test = json.loads((folder / "test.json").read_text())
    timing = json.loads((folder / "timing.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest
    assert fingerprint() == manifest["source_sha256"]
    rules, good, mafia = build_spec(config)
    assert len(train["cells"]) == len(test["cells"]) == len(good) * len(mafia)
    checked_cells = 0
    for report in (train, test):
        for cell in report["cells"]:
            assert cell["summary"] == win_summary(cell["raw_outcomes"])
            assert len(cell["raw_outcomes"]) == cell["n"]
            checked_cells += 1
    recomputed = incremental_pool(train["cells"], config)
    assert recomputed == train["incremental_pool"]
    selection = json.loads((folder / "selection_before_test.json").read_text())
    assert selection["selection"] == recomputed == test["selection_from_train"]
    assert timing_comparisons(timing["cells"]) == timing["paired_vs_early"]
    base_good = decisions.GoodPolicyV6(**config["timing"]["opening_good"])
    base_mafia = decisions.MafiaPolicyV6(**config["timing"]["opening_mafia"])
    opening_count = 0
    for cohort, records in timing["opening_records"].items():
        for record in records:
            state = opening(rules, base_good, base_mafia, record["seed"], decision_api=decisions)
            assert sha256(repr(state).encode()).hexdigest() == record["state_sha256"]
            assert state.investigations[0].is_mafia
            if cohort == "civilian_aligned":
                first = speech_order(state)[0]
                assert state.roles[first] == Role.CIVILIAN
                assert decisions.civilian_first_alignment(observe(state, first)) == state.investigations[0].target
            opening_count += 1
    archived = sorted((folder / "source/mafia_lab").glob("*.py"))
    source_assets = {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest() for p in archived}
    replayed = 0
    if args.replay:
        by_good, by_mafia = {p.name: p for p in good}, {p.name: p for p in mafia}
        for report in (train, test):
            for cell in report["cells"]:
                seed = cell["seed_start"]
                state = opening(rules, by_good[cell["good"]], by_mafia[cell["mafia"]],
                                seed, decision_api=decisions)
                got = continue_game(state, by_good[cell["good"]], by_mafia[cell["mafia"]],
                                    seed, decision_api=decisions).good_win
                assert got == cell["raw_outcomes"][0]
                replayed += 1
        lookup = {(c["cohort"], c["timing"], c["mafia"]): c for c in timing["cells"]}
        state_by_seed = {}
        for records in timing["opening_records"].values():
            for record in records:
                state_by_seed[record["seed"]] = opening(
                    rules, base_good, base_mafia, record["seed"], decision_api=decisions)
        for key, cell in lookup.items():
            seed = cell["seeds"][0]
            gp = decisions.GoodPolicyV6(**{**config["timing"]["continuation_good"],
                                           "name": f"timing_{cell['timing']}",
                                           "day1_timing": cell["timing"]})
            got = continue_game(state_by_seed[seed], gp, by_mafia[cell["mafia"]], seed,
                                first_last_words="pass", decision_api=decisions).good_win
            assert got == cell["raw_outcomes"][0]
            replayed += 1
    audit = {"status": "pass", "source_sha256": manifest["source_sha256"],
             "checked_cells": checked_cells, "checked_timing_cells": len(timing["cells"]),
             "checked_openings": opening_count, "archived_source_assets": source_assets,
             "sampled_game_replays": replayed,
             "selection_recomputed_from_train_only": True,
             "scope": "Integrity and deterministic replay audit; not an independent strategy model."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
