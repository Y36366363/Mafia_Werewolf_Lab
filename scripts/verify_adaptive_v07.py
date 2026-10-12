"""Independent integrity audit and sampled replay for v07."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.adaptive_experiment import (build_spec, evaluate_games,
                                            _good_holdout_policies, _table_policy)
from mafia_lab.engine import Role, observe, speech_order
from mafia_lab.experiments import fingerprint
from mafia_lab.simulation import continue_game, opening
from mafia_lab.statistics import paired_summary, win_summary
from mafia_lab import strategies_v07 as decisions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "results/v07")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v07_integrity_audit.json")
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    config = json.loads((folder / "source/config.json").read_text())
    training = json.loads((folder / "table_selection_before_test.json").read_text())
    holdout = json.loads((folder / "holdout.json").read_text())
    initiator = json.loads((folder / "initiator.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest
    assert fingerprint() == manifest["source_sha256"]
    rules, mafia = build_spec(config)
    by_mafia = {p.name: p for p in mafia}

    cover = list(config["table_training"]["initial_cover_table"])
    police = list(config["table_training"]["initial_police_table"])
    checked_training_cells = 0
    for step in training["steps"]:
        assert step["before"] == (cover if step["kind"] == "cover" else police)[step["index"]]
        scores = step["scores"]
        current = step["before"]
        chosen = max(config["table_training"]["probability_grid"],
                     key=lambda value: (scores[str(value)]["worst"], scores[str(value)]["mean"],
                                        value == current, -abs(value-current)))
        assert chosen == step["chosen"]
        for cell in step["cells"]:
            assert cell["summary"] == win_summary(cell["raw_outcomes"])
            checked_training_cells += 1
        (cover if step["kind"] == "cover" else police)[step["index"]] = chosen
    assert cover == training["cover_table"] and police == training["police_table"]

    for cell in holdout["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
        assert cell["mafia_split_rounds"] <= cell["mafia_multi_vote_rounds"]
    records = initiator["opening_records"]
    opening_good = decisions.GoodPolicyV7(**config["initiator_experiment"]["opening_good"])
    opening_mafia = by_mafia[config["initiator_experiment"]["opening_mafia"]]
    states = {}
    for record in records:
        state = opening(rules, opening_good, opening_mafia, record["seed"], decision_api=decisions)
        assert sha256(repr(state).encode()).hexdigest() == record["state_sha256"]
        assert state.investigations[0].is_mafia
        states[record["seed"]] = state
    lookup = {(c["treatment"], c["mafia"]): c for c in initiator["cells"]}
    recomputed_pairs = [{"control": "silent", "treatment": treatment, "mafia": opponent,
                         "paired": paired_summary(lookup["silent", opponent]["raw_outcomes"],
                                                   lookup[treatment, opponent]["raw_outcomes"])}
                        for opponent in sorted({c["mafia"] for c in initiator["cells"]})
                        for treatment in sorted({c["treatment"] for c in initiator["cells"]})
                        if treatment != "silent"]
    assert recomputed_pairs == initiator["paired_vs_silent"]

    replayed = 0
    if args.replay:
        # Replay one candidate from each coordinate step using its recorded pre-update table.
        cover = list(config["table_training"]["initial_cover_table"])
        police = list(config["table_training"]["initial_police_table"])
        for step in training["steps"]:
            value = config["table_training"]["probability_grid"][0]
            candidate_cover, candidate_police = list(cover), list(police)
            (candidate_cover if step["kind"] == "cover" else candidate_police)[step["index"]] = value
            gp = _table_policy(config, candidate_cover, candidate_police,
                               f"train_p{step['pass']}_{step['kind']}{step['index']}_{value}")
            recorded = next(c for c in step["cells"] if c["good"] == gp.name)
            got = evaluate_games((rules, gp, by_mafia[recorded["mafia"]], 1,
                                  recorded["seed_start"], False))["raw_outcomes"][0]
            assert got == recorded["raw_outcomes"][0]
            (cover if step["kind"] == "cover" else police)[step["index"]] = step["chosen"]
            replayed += 1
        good = {p.name: p for p in _good_holdout_policies(config, training)}
        for cell in holdout["cells"]:
            got = evaluate_games((rules, good[cell["good"]], by_mafia[cell["mafia"]], 1,
                                  cell["seed_start"], True))["raw_outcomes"][0]
            assert got == cell["raw_outcomes"][0]
            replayed += 1
        treatments = {t["name"]: t for t in config["initiator_experiment"]["treatments"]}
        for cell in initiator["cells"]:
            spec = treatments[cell["treatment"]]
            gp = decisions.GoodPolicyV7(**{**config["initiator_experiment"]["continuation_good"],
                                           "name": spec["name"], "day1_timing": spec["timing"],
                                           "civilian_first_rule": spec.get("rule", "next")})
            seed = cell["seeds"][0]
            got = continue_game(states[seed], gp, by_mafia[cell["mafia"]], seed,
                                first_last_words="pass", decision_api=decisions,
                                public_ballots=True).good_win
            assert got == cell["raw_outcomes"][0]
            replayed += 1
    archived = sorted((folder / "source/mafia_lab").glob("*.py"))
    audit = {"status": "pass", "source_sha256": manifest["source_sha256"],
             "checked_training_cells": checked_training_cells,
             "checked_holdout_cells": len(holdout["cells"]),
             "checked_initiator_cells": len(initiator["cells"]),
             "checked_openings": len(records), "sampled_game_replays": replayed,
             "selection_path_recomputed": True,
             "archived_source_assets": {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
                                        for p in archived},
             "scope": "Integrity and deterministic replay audit, not an independent strategy model."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
