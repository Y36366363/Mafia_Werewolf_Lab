"""Derive v08 holdout contrasts without changing the frozen policies."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.statistics import paired_summary


def main():
    folder = ROOT / "results/v08"
    table = json.loads((folder / "table_selection_before_holdout.json").read_text())
    probe_selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    matrix = json.loads((folder / "matrix_holdout.json").read_text())
    probe = json.loads((folder / "probe_holdout.json").read_text())

    cells = {(c["good"], c["mafia"]): c for c in matrix["cells"]}
    good, mafia = matrix["matrix"]["good"], matrix["matrix"]["mafia"]
    scores = {g: {"worst": min(cells[g, m]["summary"]["rate"] for m in mafia),
                  "mean": sum(cells[g, m]["summary"]["rate"] for m in mafia) / len(mafia)}
              for g in good}
    contrasts = []
    for control, treatment in (("combined_det", "combined_det_one_decoy"),
                               ("combined_det", "combined_det_live_margin"),
                               ("combined_det", "combined_det_live_final"),
                               ("origin_det", "origin_det_live_margin")):
        for fixed in good:
            contrasts.append({"side": "mafia", "control": control,
                              "treatment": treatment, "fixed": fixed,
                              "paired": paired_summary(cells[fixed, control]["raw_outcomes"],
                                                        cells[fixed, treatment]["raw_outcomes"])})
    for control in ("confirm_mix", "position_mix"):
        for fixed in mafia:
            contrasts.append({"side": "good", "control": control,
                              "treatment": "crossfit_table", "fixed": fixed,
                              "paired": paired_summary(cells[control, fixed]["raw_outcomes"],
                                                        cells["crossfit_table", fixed]["raw_outcomes"])})

    pcells = {(c["candidate"], c["mafia"]): c for c in probe["cells"]}
    opponents = sorted({c["mafia"] for c in probe["cells"]})
    names = list(dict.fromkeys(c["candidate"] for c in probe["cells"]))
    probe_scores = {}
    for name in names:
        rates = [pcells[name, m]["summary"]["rate"] for m in opponents]
        example = pcells[name, opponents[0]]
        probe_scores[name] = {
            "worst": min(rates), "mean": sum(rates) / len(rates),
            "activation_rate": example["activation_rate"],
            "alignment_rate": example["alignment_rate"],
            "coverage_x_alignment_given_active": example["alignment_rate"],
            "mean_probes": example["mean_probes"],
        }

    deterministic = [c for c in matrix["cells"]
                     if c["mafia"] in {"combined_det", "origin_det"}]
    report = {
        "scope": "Post-freeze analysis of untouched v08 holdouts; no retuning.",
        "table_selection": {
            "steps": len(table["steps"]),
            "accepted": sum(s["accepted"] for s in table["steps"]),
            "final_cover_table": table["cover_table"],
            "final_police_table": table["police_table"],
        },
        "matrix_scores": scores,
        "heldout_pure_maximin": {"name": max(scores, key=lambda g: scores[g]["worst"]),
                                  "rate": max(v["worst"] for v in scores.values())},
        "matrix_contrasts": contrasts,
        "deterministic_baseline_split_rounds": sum(c["mafia_split_rounds"] for c in deterministic),
        "probe_selected_before_holdout": probe["selected_before_holdout"],
        "probe_training_selection": {"proposed": probe_selection["proposed"],
                                     "accepted": probe_selection["accepted"]},
        "probe_holdout_scores": probe_scores,
        "probe_paired_vs_silent": probe["paired_vs_silent"],
    }
    (folder / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"pure_maximin": report["heldout_pure_maximin"],
                      "accepted_table_updates": report["table_selection"]["accepted"],
                      "selected_probe": report["probe_selected_before_holdout"],
                      "selected_probe_holdout": probe_scores[probe["selected_before_holdout"]]}, indent=2))


if __name__ == "__main__":
    main()
