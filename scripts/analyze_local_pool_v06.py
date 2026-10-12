"""Derive frozen v06 exploratory contrasts without changing selection."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.statistics import paired_summary


def main():
    folder = ROOT / "results/v06"
    test = json.loads((folder / "test.json").read_text())
    cells = {(c["good"], c["mafia"]): c for c in test["cells"]}
    good, mafia = test["matrix"]["good"], test["matrix"]["mafia"]
    pure_min = {g: min(cells[g, m]["summary"]["rate"] for m in mafia) for g in good}
    pure_worst = {g: min(mafia, key=lambda m: cells[g, m]["summary"]["rate"]) for g in good}
    contrasts = []
    good_pairs = [("public_base", n) for n in
                  ("local_cover75", "local_plan_mix", "position_mix", "confirm_cover", "confirm_mix")]
    mafia_pairs = [("combined", n) for n in
                   ("combined_split", "combined_one_decoy", "combined_late_decoy")]
    mafia_pairs += [("origin", n) for n in ("origin_one_decoy", "origin_late_decoy_bait")]
    for a, b in good_pairs:
        for m in mafia:
            contrasts.append({"side": "good", "control": a, "treatment": b,
                              "fixed": m, "paired": paired_summary(
                                  cells[a, m]["raw_outcomes"], cells[b, m]["raw_outcomes"])})
    for a, b in mafia_pairs:
        for g in good:
            contrasts.append({"side": "mafia", "control": a, "treatment": b,
                              "fixed": g, "paired": paired_summary(
                                  cells[g, a]["raw_outcomes"], cells[g, b]["raw_outcomes"])})
    report = {
        "scope": "Exploratory paired contrasts over frozen heldout cells; no post-test promotion.",
        "pure_candidate_heldout_maximin": {"name": max(pure_min, key=pure_min.get),
                                            "rate": max(pure_min.values())},
        "pure_candidate_worst_rates": pure_min,
        "pure_candidate_worst_mafia": pure_worst,
        "contrasts": contrasts,
    }
    (folder / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["pure_candidate_heldout_maximin"], indent=2))


if __name__ == "__main__":
    main()
