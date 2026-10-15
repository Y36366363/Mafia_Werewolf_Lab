"""Integrity, selection, equilibrium, and replay audit for v10."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.equilibrium_experiment import (build_spec, evaluate_cell, _matrix,
                                               _solution_artifact, evaluate_frozen_mixture)
from mafia_lab.experiments import fingerprint
from mafia_lab.statistics import paired_summary, win_summary
from mafia_lab.tiny import solve_zero_sum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "results/v10")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/v10_integrity_audit.json")
    args = parser.parse_args()
    folder = args.folder
    manifest = json.loads((folder / "manifest.json").read_text())
    config = json.loads((folder / "source/config.json").read_text())
    selection = json.loads((folder / "selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "holdout.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((folder / name).read_bytes()).hexdigest() == digest
    assert fingerprint() == manifest["source_sha256"]
    rules, good, mafia = build_spec(config)
    by_good, by_mafia = {p.name: p for p in good}, {p.name: p for p in mafia}
    good_names, mafia_names = list(by_good), list(by_mafia)

    for cell in selection["cells"] + holdout["cells"]:
        assert cell["summary"] == win_summary(cell["raw_outcomes"])
    lookup = {(c["good"], c["mafia"]): c for c in selection["cells"]}
    for family, spec in config["response_learning"].items():
        target = spec["target_good"]
        rates = {m: lookup[target, m]["summary"]["rate"] for m in spec["candidates"]}
        selected = min(spec["candidates"], key=lambda name: (rates[name], name))
        saved = selection["response_families"][family]
        assert saved["selected"] == selected and saved["candidate_rates"] == rates

    train_matrix = _matrix(selection["cells"], good_names, mafia_names)
    train_solution = _solution_artifact(solve_zero_sum(train_matrix), good_names, mafia_names)
    assert train_solution == selection["restricted_train_equilibrium"]
    assert train_solution["gap_exact"] == "0"
    holdout_matrix = _matrix(holdout["cells"], good_names, mafia_names)
    frozen = evaluate_frozen_mixture(holdout_matrix, good_names, mafia_names, train_solution)
    assert frozen == holdout["frozen_train_mixture_evaluation"]
    diagnostic = _solution_artifact(solve_zero_sum(holdout_matrix), good_names, mafia_names)
    assert diagnostic == holdout["posthoc_holdout_restricted_equilibrium"]
    assert diagnostic["gap_exact"] == "0"
    lookup_h = {(c["good"], c["mafia"]): c for c in holdout["cells"]}
    recomputed = [{"control": control, "treatment": treatment, "mafia": m,
                   "paired": paired_summary(lookup_h[control, m]["raw_outcomes"],
                                             lookup_h[treatment, m]["raw_outcomes"])}
                  for control, treatment in (("crossfit_table", "coord_deliberative_immediate"),
                                             ("probe_w8_diverse", "coord_deliberative_immediate"))
                  for m in mafia_names]
    assert recomputed == holdout["paired_public_coordination_contrasts"]

    replayed = 0
    if args.replay:
        for cell in selection["cells"] + holdout["cells"]:
            got = evaluate_cell((cell["phase"], rules, by_good[cell["good"]],
                                 by_mafia[cell["mafia"]], 1, cell["seed_start"]))
            assert got["raw_outcomes"][0] == cell["raw_outcomes"][0]
            replayed += 1
    archived = sorted((folder / "source/mafia_lab").glob("*.py"))
    audit = {"status": "pass", "source_sha256": manifest["source_sha256"],
             "checked_train_cells": len(selection["cells"]),
             "checked_holdout_cells": len(holdout["cells"]),
             "checked_response_families": len(config["response_learning"]),
             "train_equilibrium_gap_exact": train_solution["gap_exact"],
             "holdout_posthoc_gap_exact": diagnostic["gap_exact"],
             "frozen_mixture_bounds_recomputed": True,
             "sampled_game_replays": replayed,
             "archived_source_assets": {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest()
                                        for p in archived},
             "scope": "Integrity and empirical restricted-matrix audit, not a full-game GTO certificate."}
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
