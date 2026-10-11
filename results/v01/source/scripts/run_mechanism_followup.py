"""Separate frozen followup after v01 detected an uninformative floor effect."""
from dataclasses import asdict, replace
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.engine import Rules
from mafia_lab.experiments import fingerprint, metadata, save_report
from mafia_lab.policies import GOOD_POOL, MAFIA_POOL
from mafia_lab.simulation import play
from mafia_lab.statistics import paired_summary, win_summary


def main():
    config = json.loads((ROOT/"configs/mechanism_followup_v01.json").read_text())
    good = next(p for p in GOOD_POOL if p.name == config["good_policy"])
    opponents = [next(p for p in MAFIA_POOL if p.name == name) for name in config["mafia_policies"]]
    n, start = config["n_per_cell"], config["seed_start"]
    package_hash = fingerprint()
    report = metadata(config)
    report["script_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    report["stage"] = "prospectively_frozen_followup_after_primary_floor_effect"
    report["cells"] = []
    data = {}
    for opponent in opponents:
        variants = [
            ("baseline", Rules(), good, opponent),
            ("pk", Rules(tie_rule="pk"), good, opponent),
            ("four_last_words", Rules(last_words_limit=4), good, opponent),
            ("reverse_direction", Rules(direction=-1), good, opponent),
            ("near_inspection", Rules(), replace(good, inspect="near"), opponent),
            ("far_inspection", Rules(), replace(good, inspect="far"), opponent),
            ("near_kill", Rules(), good, replace(opponent, kill="near")),
            ("self25", Rules(), good, replace(opponent, first_self_kill=0.25)),
            ("self50", Rules(), good, replace(opponent, first_self_kill=0.50)),
        ]
        assert [v[0] for v in variants] == config["variants"]
        for name, rules, g, m in variants:
            outcomes = [play(rules, g, m, seed) for seed in range(start,start+n)]
            values = [o.good_win for o in outcomes]
            data[opponent.name, name] = values
            report["cells"].append({"opponent": opponent.name, "variant": name,
                "rules": asdict(rules), "good": asdict(g), "mafia": asdict(m),
                "summary": win_summary(values),
                "paired_vs_same_opponent_baseline": paired_summary(data[opponent.name,"baseline"],values),
                "first_death_counts": dict(Counter(o.first_death_role for o in outcomes)),
                "raw_outcomes": values})
        print(f"completed {opponent.name}",flush=True)
    report["same_kill_rule_bluff_contrasts"] = {
        name: paired_summary(data[opponents[0].name,name],data[opponents[1].name,name])
        for name in ["baseline","self25","self50"]}
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during followup")
    output=ROOT/"results/mechanism_followup_v01.json"
    save_report(output,report)
    print(output)


if __name__ == "__main__":
    main()
