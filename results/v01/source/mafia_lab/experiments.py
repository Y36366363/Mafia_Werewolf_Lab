"""Frozen-policy Monte Carlo experiments with reusable raw paired outcomes."""
from collections import Counter
from dataclasses import asdict, replace
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform
import time

from .engine import Role, Rules
from .policies import GOOD_POOL, MAFIA_POOL, GoodPolicy, MafiaPolicy
from .simulation import continue_game, opening, play
from .statistics import paired_summary, win_summary


def fingerprint():
    files = sorted(Path(__file__).parent.glob("*.py"))
    contents = b"".join(p.name.encode()+b"\0"+p.read_bytes()+b"\0" for p in files)
    return sha256(contents).hexdigest()


def metadata(config):
    return {"schema_version": 1, "source_sha256": fingerprint(),
            "config_sha256": sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "python": platform.python_version(), "config": config,
            "evidence": "fixed_policy_monte_carlo", "full_game_gto": False,
            "intervals": "Pointwise exploratory 95%; no multiplicity correction. Paired Wald plus conservative Hoeffding.",
            "outcome": "good faction terminal win, 0/1; no rollout truncation"}


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def analytic_controls():
    worlds = list(combinations(range(12), 4))
    rows = []
    for q in map(Fraction, ["0", "1/4", "1/2", "1"]):
        total = dead_mafia = other_mafia = Fraction(0)
        for world in worlds:
            weight = (q/4 if 0 in world else (1-q)/12)/len(worlds)
            total += weight
            dead_mafia += weight*(0 in world)
            other_mafia += weight*(1 in world)
        posterior = dead_mafia/total
        target = other_mafia/total
        assert posterior == 3*q/(2+q)
        assert target == (8+q)/(11*(2+q))
        rows.append({"q": str(q), "dead_mafia_given_nonpolice_death": str(posterior),
                     "other_unknown_alive_mafia": str(target)})
    return {"evidence": "exact_probability", "subsets_per_q": len(worlds),
            "scope": "uniform self/nonself target policy; police observation excludes inspection result",
            "rows": rows}


def branch_experiment(n: int, seed_start: int):
    rules = Rules()
    good = GoodPolicy("dead_report_all_trust", "dead", "all")
    opener_mafia = MafiaPolicy()
    opponents = (MafiaPolicy(), MafiaPolicy("fake_hunt", "always", "claims"))
    config = {"n_openings": n, "seed_start": seed_start, "rules": asdict(rules),
              "good": asdict(good), "opener_mafia": asdict(opener_mafia),
              "continuation_opponents": [asdict(p) for p in opponents],
              "interventions": {"civilian": ["pass", "water"],
                                "police_clear": ["pass", "report"],
                                "police_hit": ["pass", "report"]}}
    report = metadata(config)
    rows = {p.name: {b: [] for b in config["interventions"]} for p in opponents}
    counts = Counter()
    for seed in range(seed_start, seed_start+n):
        state = opening(rules, good, opener_mafia, seed)
        victim_role = state.roles[state.deaths[0].player]
        branch = ("civilian" if victim_role == Role.CIVILIAN else
                  "police_hit" if state.investigations[0].is_mafia else "police_clear")
        counts[branch] += 1
        control, treatment = config["interventions"][branch]
        for opponent in opponents:
            a = continue_game(state, good, opponent, seed, first_last_words=control).good_win
            b = continue_game(state, good, opponent, seed, first_last_words=treatment).good_win
            rows[opponent.name][branch].append([seed, a, b])
    report["opening_branch_counts"] = dict(counts)
    report["comparisons"] = []
    for opponent, branches in rows.items():
        for branch, data in branches.items():
            a, b = [r[1] for r in data], [r[2] for r in data]
            report["comparisons"].append({"opponent": opponent, "branch": branch,
                "control": config["interventions"][branch][0],
                "treatment": config["interventions"][branch][1],
                "control_summary": win_summary(a), "treatment_summary": win_summary(b),
                "paired": paired_summary(a, b), "raw_seed_control_treatment": data})
    return report


def pool_experiment(train_n: int, test_n: int, train_seed: int, test_seed: int,
                    progress=None):
    if set(range(train_seed, train_seed+train_n)) & set(range(test_seed, test_seed+test_n)):
        raise ValueError("Training and test seed ranges overlap")
    rules = Rules()
    config = {"rules": asdict(rules), "train_n_per_cell": train_n, "test_n_per_cell": test_n,
              "train_seed": train_seed, "test_seed": test_seed,
              "good_pool": [asdict(p) for p in GOOD_POOL],
              "mafia_pool": [asdict(p) for p in MAFIA_POOL],
              "selection": "On train only: min column against baseline row; max row against selected column; maximin pure row over all columns"}
    report = metadata(config)
    train, test = [], []
    for i, good in enumerate(GOOD_POOL):
        train_row, test_row = [], []
        for j, mafia in enumerate(MAFIA_POOL):
            train_row.append([play(rules, good, mafia, seed).good_win
                              for seed in range(train_seed, train_seed+train_n)])
            test_row.append([play(rules, good, mafia, seed).good_win
                             for seed in range(test_seed, test_seed+test_n)])
        train.append(train_row)
        test.append(test_row)
        if progress:
            progress(f"strategy pool {i+1}/{len(GOOD_POOL)} good-policy rows evaluated")
    rates = [[sum(cell)/train_n for cell in row] for row in train]
    bad_response = min(range(len(MAFIA_POOL)), key=lambda j: rates[0][j])
    good_response = max(range(len(GOOD_POOL)), key=lambda i: rates[i][bad_response])
    robust_good = max(range(len(GOOD_POOL)), key=lambda i: min(rates[i]))
    report["train_win_rates"] = rates
    report["test_summaries"] = [[win_summary(cell) for cell in row] for row in test]
    report["selection_from_train"] = {
        "baseline_good": GOOD_POOL[0].name, "baseline_mafia": MAFIA_POOL[0].name,
        "mafia_response": MAFIA_POOL[bad_response].name,
        "good_response": GOOD_POOL[good_response].name,
        "robust_pure_good": GOOD_POOL[robust_good].name}
    report["heldout_comparisons"] = {
        "mafia_response_effect_on_good_win": paired_summary(test[0][0], test[0][bad_response]),
        "good_response_effect": paired_summary(test[0][bad_response], test[good_response][bad_response]),
        "robust_good_vs_response": paired_summary(test[0][bad_response], test[robust_good][bad_response])}
    report["raw_train_outcomes"] = train
    report["raw_test_outcomes"] = test
    report["scope_warning"] = "Best responses only within six frozen heuristics each; neither full best response nor equilibrium certification. Pure plan selection adds no secret correlation device."
    return report


def mechanism_experiment(n: int, seed_start: int):
    base_rules = Rules()
    good = GoodPolicy("all_trust", "all", "all")
    mafia = MafiaPolicy("fake_hunt", "always", "claims")
    variants = [
        ("baseline", base_rules, good, mafia),
        ("pk", replace(base_rules, tie_rule="pk"), good, mafia),
        ("four_last_words", replace(base_rules, last_words_limit=4), good, mafia),
        ("reverse_direction", replace(base_rules, direction=-1), good, mafia),
        ("near_inspection", base_rules, replace(good, inspect="near"), mafia),
        ("far_inspection", base_rules, replace(good, inspect="far"), mafia),
        ("near_kill", base_rules, good, replace(mafia, kill="near")),
        ("self25", base_rules, good, replace(mafia, first_self_kill=0.25)),
        ("self50", base_rules, good, replace(mafia, first_self_kill=0.50)),
        ("no_bluff", base_rules, good, replace(mafia, bluff="none")),
        ("self25_no_bluff", base_rules, good, replace(mafia, bluff="none", first_self_kill=0.25)),
    ]
    config = {"n_per_variant": n, "seed_start": seed_start,
              "variants": [{"name": name, "rules": asdict(r), "good": asdict(g),
                            "mafia": asdict(m)} for name, r, g, m in variants]}
    report = metadata(config)
    report["variants"] = []
    baseline = None
    values_by_name = {}
    for name, rules, g, m in variants:
        outcomes = [play(rules, g, m, seed) for seed in range(seed_start, seed_start+n)]
        values = [x.good_win for x in outcomes]
        values_by_name[name] = values
        if baseline is None:
            baseline = values
        report["variants"].append({"name": name, "summary": win_summary(values),
            "paired_vs_baseline": paired_summary(baseline, values),
            "first_death_counts": dict(Counter(o.first_death_role for o in outcomes)),
            "raw_outcomes": values})
    report["selfkill_contrasts"] = {
        "with_bluff": paired_summary(values_by_name["baseline"], values_by_name["self25"]),
        "without_bluff": paired_summary(values_by_name["no_bluff"], values_by_name["self25_no_bluff"])}
    report["scope_warning"] = "Root-value comparisons; opening-changing variants are not conditioned on first-death role. Fixed policies only, no reoptimization."
    return report


def small_game_simulations(n: int, seed_start: int):
    report = metadata({"n_per_configuration": n, "seed_start": seed_start,
                       "policies": [asdict(GOOD_POOL[0]), asdict(MAFIA_POOL[2])]})
    report["configurations"] = []
    for p, m, c in [(1,1,2), (2,1,3), (2,2,4)]:
        rules = Rules(p,m,c)
        outcomes = [play(rules, GOOD_POOL[0], MAFIA_POOL[2], s)
                    for s in range(seed_start, seed_start+n)]
        report["configurations"].append({"rules": asdict(rules),
            "summary": win_summary([o.good_win for o in outcomes]),
            "max_nights": max(o.nights for o in outcomes),
            "raw_outcomes": [o.good_win for o in outcomes]})
    return report


def run_suite(config_path, output_dir, progress=print):
    config = json.loads(Path(config_path).read_text())
    for field in ("branch_n", "train_n", "test_n", "mechanism_n", "small_n"):
        if type(config[field]) is not int or config[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    frozen_source = fingerprint()
    from .tiny import run_tiny_benchmark
    reports = {"tiny_exact": run_tiny_benchmark(), "analytic_controls": analytic_controls()}
    for name, report in reports.items():
        save_report(output/f"{name}.json", report)
    jobs = [
        ("small_games", lambda: small_game_simulations(config["small_n"], config["small_seed"])),
        ("first_day_branches", lambda: branch_experiment(config["branch_n"], config["branch_seed"])),
        ("strategy_pool", lambda: pool_experiment(config["train_n"], config["test_n"],
                                                  config["train_seed"], config["test_seed"], progress)),
        ("mechanisms", lambda: mechanism_experiment(config["mechanism_n"], config["mechanism_seed"])),
    ]
    for name, job in jobs:
        progress(f"running {name}")
        report = job()
        if fingerprint() != frozen_source or report.get("source_sha256") != frozen_source:
            raise RuntimeError("Package changed during evaluation; rerun the frozen suite")
        save_report(output/f"{name}.json", report)
        reports[name] = report
        progress(f"saved {name}")
    manifest = {"config": config, "source_sha256": frozen_source,
                "elapsed_seconds": time.monotonic()-started,
                "files": {f"{name}.json": sha256((output/f"{name}.json").read_bytes()).hexdigest()
                          for name in reports}}
    save_report(output/"manifest.json", manifest)
    return reports
