"""Frozen v03 response: hunt public nominators as well as police claimants.

This extends the adversary with one public-information heuristic and evaluates
all prespecified policy pairs to true terminal states using independent new
replicates. Matched arms share seeds; the procedure fits no policy or mixture.
"""

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mafia_lab.engine import Rules
from mafia_lab.experiments import fingerprint, metadata, save_report
from mafia_lab.policies import GoodPolicy, MafiaPolicy
from mafia_lab.simulation import play
from mafia_lab.statistics import paired_summary, win_summary


def build_spec(config):
    """Validate the frozen counter contrasts, including no bundled bluff change."""
    if type(config["n_per_cell"]) is not int or config["n_per_cell"] < 1:
        raise ValueError("n_per_cell must be a positive integer")
    if type(config["seed_start"]) is not int or config["seed_start"] < 0:
        raise ValueError("seed_start must be a nonnegative integer")
    rules = Rules(**config["rules"])
    good = tuple(GoodPolicy(**spec) for spec in config["good_policies"])
    mafia = tuple(MafiaPolicy(**spec) for spec in config["mafia_policies"])
    if not good or not mafia:
        raise ValueError("both policy sets must be nonempty")
    for group in (good, mafia):
        if len({p.name for p in group}) != len(group):
            raise ValueError("policy names must be unique within each faction")
    by_name = {p.name: p for p in mafia}
    for contrast in config["contrasts"]:
        control = by_name[contrast["control"]]
        treatment = by_name[contrast["treatment"]]
        if control.kill != "claims" or treatment.kill != "signals":
            raise ValueError("contrasts must change claims into signals hunting")
        if (control.bluff, control.first_self_kill) != (treatment.bluff, treatment.first_self_kill):
            raise ValueError("paired contrast must hold bluff and self-kill fixed")
    return rules, good, mafia


def run_experiment(config, *, progress=False):
    rules, good_policies, mafia_policies = build_spec(config)
    n = config["n_per_cell"]
    start = config["seed_start"]
    source_hash = fingerprint()
    script_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    report = metadata(config)
    report.update({
        "stage": config["stage"],
        "script_sha256": script_hash,
        "seed_interval_inclusive": [start, start + n - 1],
        "raw_outcome_index": "index i corresponds to seed_start + i in every cell",
        "total_games": len(good_policies) * len(mafia_policies) * n,
        "terminal_validation": "play returns only at terminal; additionally assert binary winner and mandatory-death bound for every game",
        "cells": [],
    })
    raw = {}
    for good in good_policies:
        for mafia in mafia_policies:
            outcomes = [play(rules, good, mafia, seed)
                        for seed in range(start, start + n)]
            if any(o.good_win not in (0, 1) or not 1 <= o.nights < rules.n_players
                   or not 1 <= o.deaths < rules.n_players for o in outcomes):
                raise RuntimeError("terminal outcome or mandatory-death invariant violated")
            values = [o.good_win for o in outcomes]
            raw[good.name, mafia.name] = values
            report["cells"].append({
                "good_policy": good.name,
                "mafia_policy": mafia.name,
                "rules": asdict(rules),
                "good": asdict(good),
                "mafia": asdict(mafia),
                "summary": win_summary(values),
                "first_death_counts": dict(Counter(o.first_death_role for o in outcomes)),
                "first_check_mafia_count": sum(o.first_check_mafia for o in outcomes),
                "raw_outcomes": values,
                "raw_nights": [o.nights for o in outcomes],
                "raw_deaths": [o.deaths for o in outcomes],
            })
            if progress:
                print(f"completed {good.name} / {mafia.name}: {sum(values)}/{n}", flush=True)
    report["paired_contrasts"] = [
        {"good_policy": good.name,
         "control": contrast["control"],
         "treatment": contrast["treatment"],
         "direction": "signals minus claims in good win probability",
         "paired": paired_summary(raw[good.name, contrast["control"]],
                                   raw[good.name, contrast["treatment"]])}
        for good in good_policies for contrast in config["contrasts"]
    ]
    report["matrix"] = {
        "row_good_policies": [p.name for p in good_policies],
        "column_mafia_policies": [p.name for p in mafia_policies],
        "good_win_rates": [[sum(raw[g.name, m.name]) / n for m in mafia_policies]
                           for g in good_policies],
    }
    if fingerprint() != source_hash:
        raise RuntimeError("Package changed during counter experiment")
    if sha256(Path(__file__).read_bytes()).hexdigest() != script_hash:
        raise RuntimeError("Script changed during counter experiment")
    return report


def main():
    config_path = ROOT / "configs/signal_counter_v03.json"
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    report = run_experiment(config, progress=True)
    if config_path.read_bytes() != config_bytes:
        raise RuntimeError("Config changed during counter experiment")
    report["config_file_sha256"] = sha256(config_bytes).hexdigest()
    output = ROOT / "results/signal_counter_v03.json"
    save_report(output, report)
    print(output, flush=True)


if __name__ == "__main__":
    main()
