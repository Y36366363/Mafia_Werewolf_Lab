"""Derive v09 replication and mechanism contrasts from frozen results."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.statistics import paired_summary


def main():
    folder = ROOT / "results/v09"
    replication = json.loads((folder / "replication.json").read_text())
    selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "probe_holdout.json").read_text())
    blocks = [b["name"] for b in replication["blocks"]]
    good, mafia = replication["matrix"]["good"], replication["matrix"]["mafia"]
    cells = {(c["block"], c["good"], c["mafia"]): c for c in replication["cells"]}

    block_scores, block_winners = {}, {}
    for block in blocks:
        block_scores[block] = {}
        for g in good:
            rates = [cells[block, g, m]["summary"]["rate"] for m in mafia]
            block_scores[block][g] = {"worst": min(rates), "mean": sum(rates) / len(rates),
                                      "worst_opponent": mafia[rates.index(min(rates))]}
        block_winners[block] = max(good, key=lambda g: (block_scores[block][g]["worst"],
                                                        block_scores[block][g]["mean"]))

    pooled_cells, pooled_scores = {}, {}
    for g in good:
        for m in mafia:
            raw = sum((cells[b, g, m]["raw_outcomes"] for b in blocks), [])
            pooled_cells[g, m] = raw
        rates = [sum(pooled_cells[g, m]) / len(pooled_cells[g, m]) for m in mafia]
        pooled_scores[g] = {"worst": min(rates), "mean": sum(rates) / len(rates),
                            "worst_opponent": mafia[rates.index(min(rates))]}
    replication_contrasts = []
    for control in ("confirm_mix", "position_mix"):
        for m in mafia:
            replication_contrasts.append({"control": control, "treatment": "crossfit_table",
                                          "mafia": m,
                                          "paired": paired_summary(pooled_cells[control, m],
                                                                    pooled_cells["crossfit_table", m])})

    pcells = {(c["candidate"], c["mafia"]): c for c in holdout["cells"]}
    opponents = list(dict.fromkeys(c["mafia"] for c in holdout["cells"]))
    candidates = list(dict.fromkeys(c["candidate"] for c in holdout["cells"]))
    probe_scores, strata_effects = {}, []
    for name in candidates:
        rates = [pcells[name, m]["summary"]["rate"] for m in opponents]
        example = pcells[name, opponents[0]]
        probe_scores[name] = {"worst": min(rates), "mean": sum(rates) / len(rates),
                              "worst_opponent": opponents[rates.index(min(rates))],
                              "activation_rate": example["activation_rate"],
                              "alignment_rate": example["alignment_rate"],
                              "mean_probes": example["mean_probes"],
                              "mean_unique_targets": example["mean_unique_targets"]}
        if name not in {"silent", "early"}:
            for m in opponents:
                for stratum in ("check_hit", "check_clear"):
                    strata_effects.append({"control": "silent", "treatment": name,
                                           "mafia": m, "stratum": stratum,
                                           "control_rate": pcells["silent", m]["strata"][stratum]["rate"],
                                           "treatment_rate": pcells[name, m]["strata"][stratum]["rate"],
                                           "delta": (pcells[name, m]["strata"][stratum]["rate"] -
                                                     pcells["silent", m]["strata"][stratum]["rate"])})

    report = {
        "scope": "Post-freeze analysis of v09 outer blocks and untouched holdout; no retuning.",
        "replication_block_scores": block_scores,
        "replication_block_winners": block_winners,
        "crossfit_table_block_wins": sum(v == "crossfit_table" for v in block_winners.values()),
        "replication_pooled_scores": pooled_scores,
        "replication_pooled_winner": max(good, key=lambda g: pooled_scores[g]["worst"]),
        "replication_contrasts": replication_contrasts,
        "probe_selection": {"proposed": selection["proposed"],
                            "comparator": selection["validation_comparator"],
                            "accepted": selection["accepted"], "selected": selection["selected"]},
        "probe_holdout_scores": probe_scores,
        "probe_paired_comparisons": holdout["paired_comparisons"],
        "probe_strata_effects_vs_silent": strata_effects,
        "same_window_controls": {
            name: {"unique_targets": probe_scores[name]["mean_unique_targets"],
                   "alignment_rate": probe_scores[name]["alignment_rate"],
                   "worst": probe_scores[name]["worst"], "mean": probe_scores[name]["mean"]}
            for name in ("probe_w8_diverse", "probe_w8_anchor", "probe_w8_pair")},
        "interpretation": ("Clear-check gains show that public probes mostly act as a coordination/search "
                           "device in this policy model; alignment is not the sole mechanism."),
    }
    (folder / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"block_winners": block_winners,
                      "pooled_winner": report["replication_pooled_winner"],
                      "pooled_scores": pooled_scores,
                      "selected_probe": selection["selected"],
                      "probe_scores": probe_scores}, indent=2))


if __name__ == "__main__":
    main()
