"""Analyze frozen v10 responses and out-of-sample restricted mixtures."""
import json
from fractions import Fraction
from math import log, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "results/v10"
    selection = json.loads((folder / "selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "holdout.json").read_text())
    good, mafia = holdout["matrix"]["good"], holdout["matrix"]["mafia"]
    cells = {(c["good"], c["mafia"]): c for c in holdout["cells"]}
    pure = {}
    for g in good:
        rates = [cells[g, m]["summary"]["rate"] for m in mafia]
        pure[g] = {"worst": min(rates), "mean": sum(rates) / len(rates),
                   "worst_opponent": mafia[rates.index(min(rates))]}

    response_holdout = {}
    config = holdout["config"]
    for family, spec in config["response_learning"].items():
        target = spec["target_good"]
        rates = {m: cells[target, m]["summary"]["rate"] for m in spec["candidates"]}
        selected = selection["response_families"][family]["selected"]
        response_holdout[family] = {"target_good": target, "selected_train": selected,
                                    "selected_holdout": min(rates, key=lambda m: (rates[m], m)),
                                    "rates": rates,
                                    "selection_replicated": selected == min(rates, key=lambda m: (rates[m], m))}

    train_eq = selection["restricted_train_equilibrium"]
    row = {name: float(Fraction(value)) for name, value in train_eq["good_mixture"].items()}
    column = {name: float(Fraction(value)) for name, value in train_eq["mafia_mixture"].items()}
    n = holdout["config"]["holdout"]["n"]
    mixed_vs_mafia = {}
    for m in mafia:
        samples = [sum(row.get(g, 0.0) * cells[g, m]["raw_outcomes"][i] for g in good)
                   for i in range(n)]
        mixed_vs_mafia[m] = sum(samples) / n
    good_vs_mixed = {}
    for g in good:
        samples = [sum(column.get(m, 0.0) * cells[g, m]["raw_outcomes"][i] for m in mafia)
                   for i in range(n)]
        good_vs_mixed[g] = sum(samples) / n
    point_half = sqrt(log(2 / .05) / (2 * n))
    family_half = sqrt(log(2 * (len(good) + len(mafia)) / .05) / (2 * n))
    frozen = holdout["frozen_train_mixture_evaluation"]
    diagnostic = holdout["posthoc_holdout_restricted_equilibrium"]
    report = {
        "scope": "Frozen train selection evaluated on untouched holdout; post-hoc equilibrium is diagnostic only.",
        "response_holdout": response_holdout,
        "pure_holdout_scores": pure,
        "train_restricted_equilibrium": train_eq,
        "frozen_train_mixture_holdout": frozen,
        "posthoc_holdout_restricted_equilibrium": diagnostic,
        "support_comparison": {
            "train_good": list(train_eq["good_mixture"]),
            "holdout_good": list(diagnostic["good_mixture"]),
            "train_mafia": list(train_eq["mafia_mixture"]),
            "holdout_mafia": list(diagnostic["mafia_mixture"]),
        },
        "mixed_payoffs_recomputed_by_seed": {"good_mixture_vs_mafia": mixed_vs_mafia,
                                               "good_vs_mafia_mixture": good_vs_mixed},
        "bounded_mean_half_widths": {"pointwise_95": point_half,
                                     "familywise_95_over_20_response_checks": family_half,
                                     "note": "Hoeffding bounds for each fixed weighted per-seed payoff; matrix selection uncertainty remains."},
        "public_coordination_promotion": {
            "promoted": False,
            "reason": "All three public-deliberation variants have lower holdout worst rates and zero equilibrium support.",
        },
        "interpretation": ("Train equilibrium has an exact zero gap only for the empirical finite matrix. "
                           "The nonzero holdout response gap measures sampling/support drift and is not "
                           "an unrestricted exploitability certificate."),
    }
    (folder / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"responses": response_holdout, "pure": pure,
                      "train_value": train_eq["value"],
                      "holdout_frozen": frozen,
                      "holdout_posthoc_value": diagnostic["value"],
                      "family_half_width": family_half}, indent=2))


if __name__ == "__main__":
    main()
