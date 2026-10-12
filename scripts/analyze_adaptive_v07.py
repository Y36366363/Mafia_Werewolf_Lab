"""Derive v07 holdout contrasts and training diagnostics."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.statistics import paired_summary


def main():
    folder = ROOT / "results/v07"
    holdout = json.loads((folder / "holdout.json").read_text())
    initiator = json.loads((folder / "initiator.json").read_text())
    training = json.loads((folder / "table_selection_before_test.json").read_text())
    cells = {(c["good"], c["mafia"]): c for c in holdout["cells"]}
    good, mafia = holdout["matrix"]["good"], holdout["matrix"]["mafia"]
    worst = {g: min(cells[g, m]["summary"]["rate"] for m in mafia) for g in good}
    contrasts = []
    for a, b in (("combined", "combined_one_decoy"),
                 ("combined", "combined_live_margin"),
                 ("combined", "combined_live_final"),
                 ("origin", "origin_live_margin")):
        for g in good:
            contrasts.append({"side": "mafia", "control": a, "treatment": b, "fixed": g,
                              "paired": paired_summary(cells[g, a]["raw_outcomes"],
                                                        cells[g, b]["raw_outcomes"])})
    for a, b in (("confirm_mix", "learned_table"), ("position_mix", "learned_table")):
        for m in mafia:
            contrasts.append({"side": "good", "control": a, "treatment": b, "fixed": m,
                              "paired": paired_summary(cells[a, m]["raw_outcomes"],
                                                        cells[b, m]["raw_outcomes"])})
    initial_step = training["steps"][0]
    initial_value = str(initial_step["before"])
    initial_rates = initial_step["rates"][initial_value]
    final_step = training["steps"][-1]
    final_value = str(final_step["chosen"])
    final_rates = final_step["rates"][final_value]
    rule_cells = [c for c in initiator["cells"] if c["rule"] is not None]
    rule_coverage = {}
    for rule in sorted({c["rule"] for c in rule_cells}):
        sample = next(c for c in rule_cells if c["rule"] == rule)
        rule_coverage[rule] = {"n": sample["n"], "activated": sample["activated"],
                               "aligned": sample["aligned"],
                               "activation_rate": sample["activated"] / sample["n"],
                               "alignment_rate": sample["aligned"] / sample["n"]}
    report = {"scope": "Exploratory analysis of frozen holdout; no retuning.",
              "heldout_pure_maximin": {"name": max(worst, key=worst.get),
                                        "rate": max(worst.values())},
              "heldout_worst_rates": worst,
              "holdout_contrasts": contrasts,
              "training_initial_table_rates": initial_rates,
              "training_initial_worst": min(initial_rates.values()),
              "training_final_table_rates": final_rates,
              "training_final_worst": min(final_rates.values()),
              "initiator_rule_coverage": rule_coverage}
    (folder / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"maximin": report["heldout_pure_maximin"],
                      "rule_coverage": rule_coverage}, indent=2))


if __name__ == "__main__":
    main()
