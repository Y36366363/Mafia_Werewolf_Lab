"""Frozen v12 dead-police intervention and self-kill credibility matrix."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from fractions import Fraction
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
import shutil
from statistics import mean, variance, NormalDist
import time

from .engine import Role, Rules, speech_order
from .experiments import fingerprint
from .simulation import opening, continue_game
from .statistics import paired_summary, win_summary
from .tiny import solve_zero_sum
from . import strategies_v12 as decisions


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _hash(value):
    return sha256(repr(value).encode()).hexdigest()


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v12 is fixed to 4 police, 4 mafia, 8 civilians")
    dead = tuple(decisions.GoodPolicyV12(reveal="silent", trust="none", **p)
                 for p in config["dead_police_policies"])
    good = tuple(decisions.GoodPolicyV12(reveal="silent", trust="none",
                                         dead_police_message="truth", **p)
                 for p in config["good_responses"])
    mafia = tuple(decisions.MafiaPolicyV12(bluff="none", kill="claims", **p)
                  for p in config["mafia_openings"])
    if [p.name for p in dead] != ["silent", "truth", "teammate_clear"]:
        raise ValueError("dead-police policy pool changed")
    if [p.name for p in good] != ["trust_hidden", "skeptic_hidden", "trust_single", "trust_full"]:
        raise ValueError("good response pool changed")
    if [p.name for p in mafia] != ["ordinary", "self_silent", "self_fake_hit",
                                   "self_ally_clear", "self_nonally_clear"]:
        raise ValueError("mafia opening pool changed")
    blocks = [config[k] for k in ("dead_police", "selfkill_train", "selfkill_holdout")]
    ranges = [(b["seed_start"], b["seed_start"] + b["n"]) for b in blocks]
    if any(a[0] < b[1] and b[0] < a[1] for i, a in enumerate(ranges)
           for b in ranges[i+1:]):
        raise ValueError("seed blocks overlap")
    return rules, dead, good, mafia


def _trace_metrics(initial, outcome):
    roles = initial.roles
    day1_votes = next(e["payload"] for e in outcome.transcript
                      if e["day"] == 1 and e["event"] == "votes")
    day1_dead = [e["payload"]["victim"] for e in outcome.transcript
                 if e["day"] == 1 and e["event"] == "day_death"]
    night2 = [e["payload"]["victim"] for e in outcome.transcript
              if e["day"] == 2 and e["event"] == "night_death"]
    first_dead = initial.deaths[0].player
    last_reports = [e["payload"] for e in outcome.transcript
                    if e["day"] == 1 and e["event"] == "message"
                    and e["payload"]["context"] == "last_words"
                    and e["payload"]["kind"] == "report"
                    and e["payload"]["speaker"] == first_dead]
    live_reports = [e["payload"] for e in outcome.transcript
                    if e["day"] == 1 and e["event"] == "message"
                    and e["payload"]["context"] == "day"
                    and e["payload"]["kind"] == "report"]
    report = last_reports[-1] if last_reports else None
    exile_role = roles[day1_dead[0]].value if day1_dead else "none"
    target_role = roles[report["target"]].value if report else "none"
    accused = report["target"] if report and report["verdict"] else None
    informed_dissent = 0
    if accused is not None:
        # Police know whether the dead claimant is a teammate.  An accused
        # civilian additionally knows its own role.  This is an audit metric,
        # not information handed to any strategy.
        dead = initial.deaths[0].player
        if roles[dead] == Role.MAFIA:
            informed_dissent = 4 + int(roles[accused] == Role.CIVILIAN)
    return {
        "win": outcome.good_win,
        "day1_exile_mafia": int(exile_role == "mafia"),
        "day1_exile_police": int(exile_role == "police"),
        "day1_exile_civilian": int(exile_role == "civilian"),
        "day1_no_exile": int(exile_role == "none"),
        "night2_kill_police": int(bool(night2) and roles[night2[0]] == Role.POLICE),
        "day1_live_reports": len(live_reports),
        "dead_report_target_role": target_role,
        "fake_hit_informed_dissenters": informed_dissent,
        "day1_votes_for_dead_report_target": (sum(t == report["target"] for t in day1_votes.values())
                                               if report else 0),
    }


def _cell_from_openings(job):
    phase, cohort, openings, good, mafia = job
    raw, opening_hashes, trace_hashes, examples = {}, [], [], []
    for index, (seed, state) in enumerate(openings):
        outcome = continue_game(state, good, mafia, seed, trace=True,
                                decision_api=decisions, public_ballots=True)
        metrics = _trace_metrics(state, outcome)
        for key, value in metrics.items():
            raw.setdefault(key, []).append(value)
        opening_hashes.append(_hash(state))
        trace_hashes.append(sha256(json.dumps(outcome.transcript, sort_keys=True).encode()).hexdigest())
        if index < 2:
            examples.append({"seed": seed, "roles": [r.value for r in state.roles],
                             "investigation": asdict(state.investigations[0]),
                             "trace": outcome.transcript})
    numeric = {k: mean(v) for k, v in raw.items() if v and isinstance(v[0], (int, float))}
    return {"phase": phase, "cohort": cohort, "good": good.name, "mafia": mafia.name,
            "n": len(openings), "seeds": [s for s, _ in openings], "raw": raw,
            "means": numeric, "win_summary": win_summary(raw["win"]),
            "opening_hashes": opening_hashes, "trace_hashes": trace_hashes,
            "examples": examples}


def _cell_root(job):
    phase, rules, good, mafia, start, n = job
    openings = [(seed, opening(rules, good, mafia, seed, decisions))
                for seed in range(start, start + n)]
    cell = _cell_from_openings((phase, "root", openings, good, mafia))
    cell["seed_start"] = start
    cell["root_signatures"] = [
        _hash(([r.value for r in state.roles], state.investigations[0].target))
        for _, state in openings
    ]
    cell["first_death_roles"] = [state.roles[state.deaths[0].player].value
                                  for _, state in openings]
    return cell


def _run(jobs, workers, function):
    if workers == 1:
        return list(map(function, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, jobs, chunksize=1))


def _select_dead_openings(rules, block, good, mafia):
    selected = {"hit": [], "clear": []}
    stop = block["seed_start"] + block["scan_limit"]
    for seed in range(block["seed_start"], stop):
        state = opening(rules, good, mafia, seed, decisions)
        if state.roles[state.deaths[0].player] != Role.POLICE:
            continue
        cohort = "hit" if state.investigations[0].is_mafia else "clear"
        if len(selected[cohort]) < block["n"]:
            selected[cohort].append((seed, state))
        if all(len(v) == block["n"] for v in selected.values()):
            return selected
    raise RuntimeError("dead-police opening scan exhausted")


def _matrix(cells, good_names, mafia_names):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    return [[Fraction(lookup[g, m]["win_summary"]["wins"], lookup[g, m]["n"])
             for m in mafia_names] for g in good_names]


def _solution(solution, good_names, mafia_names):
    return {"value_exact": str(solution["value"]), "value": float(solution["value"]),
            "good_mixture": {n: str(w) for n, w in zip(good_names, solution["row_probabilities"]) if w},
            "mafia_mixture": {n: str(w) for n, w in zip(mafia_names, solution["column_probabilities"]) if w},
            "lower_exact": str(solution["lower_bound"]), "upper_exact": str(solution["upper_bound"]),
            "gap_exact": str(solution["gap"]), "simplex_pivots": solution["pivots"]}


def _frozen_holdout(matrix, good_names, mafia_names, artifact):
    row = [Fraction(artifact["good_mixture"].get(n, "0")) for n in good_names]
    col = [Fraction(artifact["mafia_mixture"].get(n, "0")) for n in mafia_names]
    vs_m = [sum(row[i] * matrix[i][j] for i in range(len(row))) for j in range(len(col))]
    vs_g = [sum(col[j] * matrix[i][j] for j in range(len(col))) for i in range(len(row))]
    lower, upper = min(vs_m), max(vs_g)
    return {"lower_exact": str(lower), "lower": float(lower),
            "upper_exact": str(upper), "upper": float(upper),
            "gap_exact": str(upper-lower), "gap": float(upper-lower),
            "worst_mafia": mafia_names[vs_m.index(lower)],
            "best_good": good_names[vs_g.index(upper)],
            "good_mix_vs_mafia": {n: float(v) for n, v in zip(mafia_names, vs_m)},
            "good_vs_mafia_mix": {n: float(v) for n, v in zip(good_names, vs_g)}}


def _dead_analysis(cells, config):
    lookup = {(c["cohort"], c["good"]): c for c in cells}
    results = []
    family = len(config["primary_dead_police_contrasts"])
    z = NormalDist().inv_cdf(1 - .05/(2*family))
    for name, cohort, control, treatment in config["primary_dead_police_contrasts"]:
        a, b = lookup[cohort, control]["raw"]["win"], lookup[cohort, treatment]["raw"]["win"]
        paired = paired_summary(a, b)
        diffs = [y-x for x, y in zip(a, b)]
        se = sqrt(variance(diffs)/len(diffs))
        delta = mean(diffs)
        half = sqrt(2*log(2*family/.05)/len(diffs))
        results.append({"name": name, "cohort": cohort, "control": control,
                        "treatment": treatment, "paired": paired,
                        "family_normal_approx": [delta-z*se, delta+z*se],
                        "family_hoeffding": [delta-half, delta+half]})
    return results


def run_experiment(config, output, workers=4):
    rules, dead_policies, good_policies, mafia_policies = build_spec(config)
    output = Path(output)
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    assets = list((root/"mafia_lab").glob("*.py")) + [
        root/"scripts/run_declaration_v12.py", root/"scripts/verify_declaration_v12.py",
        root/"docs/declaration_protocol_v12.md"]
    for source in assets:
        target = output/"source"/source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _json(output/"source/config.json", config)
    source_assets = {str(p.relative_to(output)): sha256(p.read_bytes()).hexdigest()
                     for p in (output/"source").rglob("*") if p.is_file()}
    freeze = {"version": config["version"], "source_sha256": fingerprint(),
              "source_assets": source_assets, "expanded": {
                  "dead_police": [asdict(p) for p in dead_policies],
                  "good": [asdict(p) for p in good_policies],
                  "mafia": [asdict(p) for p in mafia_policies]},
              "scope": config["scope"]}
    _json(output/"freeze_before_evaluation.json", freeze)
    started = time.monotonic()

    ordinary = next(p for p in mafia_policies if p.name == "ordinary")
    selector_good = next(p for p in good_policies if p.name == "trust_hidden")
    cohorts = _select_dead_openings(rules, config["dead_police"], selector_good, ordinary)
    dead_jobs = []
    for cohort, openings in cohorts.items():
        allowed = {"silent", "truth"} if cohort == "hit" else {"silent", "truth", "teammate_clear"}
        for good in dead_policies:
            if good.name in allowed:
                dead_jobs.append(("dead_police", cohort, openings, good, ordinary))
    dead_cells = _run(dead_jobs, workers, _cell_from_openings)
    dead_report = {"config": config, "cells": dead_cells,
                   "analysis": _dead_analysis(dead_cells, config),
                   "opening_records": {k: [{"seed": s, "state_hash": _hash(st)} for s, st in v]
                                       for k, v in cohorts.items()}}
    _json(output/"dead_police.json", dead_report)

    good_names, mafia_names = [p.name for p in good_policies], [p.name for p in mafia_policies]
    reports = {}
    train_solution = None
    for phase, key in (("train", "selfkill_train"), ("holdout", "selfkill_holdout")):
        block = config[key]
        jobs = [(phase, rules, g, m, block["seed_start"], block["n"])
                for g in good_policies for m in mafia_policies]
        cells = _run(jobs, workers, _cell_root)
        matrix = _matrix(cells, good_names, mafia_names)
        diagnostic = _solution(solve_zero_sum(matrix), good_names, mafia_names)
        report = {"config": config, "phase": phase, "cells": cells,
                  "matrix": {"good": good_names, "mafia": mafia_names,
                             "rates_exact": [[str(x) for x in row] for row in matrix]},
                  "restricted_empirical_equilibrium": diagnostic}
        if phase == "train":
            train_solution = diagnostic
            _json(output/"selection_before_holdout.json", {
                "train_solution": train_solution, "holdout_unread": True,
                "scope": "Exact solution of the finite empirical train matrix only."})
        else:
            report["frozen_train_mixture_on_holdout"] = _frozen_holdout(
                matrix, good_names, mafia_names, train_solution)
        _json(output/f"selfkill_{phase}.json", report)
        reports[phase] = report

    files = ["freeze_before_evaluation.json", "dead_police.json", "selfkill_train.json",
             "selection_before_holdout.json", "selfkill_holdout.json"]
    manifest = {"version": config["version"], "source_sha256": freeze["source_sha256"],
                "elapsed_seconds": time.monotonic()-started,
                "dead_police_games": sum(c["n"] for c in dead_cells),
                "selfkill_train_games": sum(c["n"] for c in reports["train"]["cells"]),
                "selfkill_holdout_games": sum(c["n"] for c in reports["holdout"]["cells"]),
                "files": {n: sha256((output/n).read_bytes()).hexdigest() for n in files},
                "scope": config["scope"]}
    _json(output/"manifest.json", manifest)
    return manifest

