"""Solve the frozen empirical v05 matrix game on train, then evaluate on holdout."""
from fractions import Fraction
import json
from math import log, sqrt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.tiny import solve_zero_sum


def interval(values):
    n = len(values)
    mean = sum(values, Fraction()) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    normal = 1.959963984540054 * sqrt(float(variance / n))
    bounded = sqrt(log(40) / (2 * n))
    return {"n": n, "mean": float(mean),
            "ci95_normal": [max(0, float(mean) - normal), min(1, float(mean) + normal)],
            "ci95_hoeffding": [max(0, float(mean) - bounded), min(1, float(mean) + bounded)]}


def main():
    folder = ROOT / "results/v05"
    train = json.loads((folder / "train.json").read_text())
    test = json.loads((folder / "test.json").read_text())
    good, mafia = train["matrix"]["good"], train["matrix"]["mafia"]
    train_matrix = [[Fraction(cell["summary"]["wins"], cell["n"])
                     for cell in train["cells"][i * len(mafia):(i + 1) * len(mafia)]]
                    for i in range(len(good))]
    solution = solve_zero_sum(train_matrix)
    row, column = solution["row_probabilities"], solution["column_probabilities"]
    cells = {(c["good"], c["mafia"]): c["raw_outcomes"] for c in test["cells"]}
    n = test["seed_block"]["n"]
    row_against_columns = {
        m: sum(row[i] * sum(cells[g, m]) / n for i, g in enumerate(good))
        for m in mafia
    }
    column_against_rows = {
        g: sum(column[j] * sum(cells[g, m]) / n for j, m in enumerate(mafia))
        for g in good
    }
    per_seed = [sum(row[i] * column[j] * cells[g, m][k]
                    for i, g in enumerate(good) for j, m in enumerate(mafia))
                for k in range(n)]
    report = {
        "scope": ("Exact equilibrium of the empirical TRAIN payoff matrix over the frozen finite policy pool. "
                  "It assumes a trusted ex-ante faction-wide policy lottery and is not behavioral-strategy "
                  "GTO, a full-game equilibrium, or a certified unrestricted best response."),
        "selection": "Mixture weights solved from train only; heldout outcomes were not used to choose them.",
        "train_value": float(solution["value"]),
        "train_value_exact": str(solution["value"]),
        "train_certificate": {"lower": str(solution["lower_bound"]),
                              "upper": str(solution["upper_bound"]),
                              "gap": str(solution["gap"]), "pivots": solution["pivots"]},
        "good_mixture": {g: str(row[i]) for i, g in enumerate(good) if row[i]},
        "mafia_mixture": {m: str(column[j]) for j, m in enumerate(mafia) if column[j]},
        "heldout_at_train_mixtures": interval(per_seed),
        "heldout_good_mixture_vs_each_mafia": {m: float(v) for m, v in row_against_columns.items()},
        "heldout_good_mixture_worst_pure_mafia": {
            "name": min(row_against_columns, key=row_against_columns.get),
            "rate": float(min(row_against_columns.values()))},
        "heldout_mafia_mixture_vs_each_good": {g: float(v) for g, v in column_against_rows.items()},
        "heldout_mafia_mixture_best_pure_good": {
            "name": max(column_against_rows, key=column_against_rows.get),
            "rate": float(max(column_against_rows.values()))},
    }
    output = folder / "restricted_matrix_solution.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
