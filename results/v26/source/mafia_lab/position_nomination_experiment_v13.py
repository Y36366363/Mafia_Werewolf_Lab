"""Frozen v13 position and dead-police internal-nomination experiments."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
from statistics import mean
import time

from .engine import Role, Rules, speech_order
from .experiments import fingerprint
from .simulation import opening, continue_game
from .statistics import win_summary
from .tiny import solve_zero_sum
from . import strategies_v13 as decisions


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _hash(value):
    return sha256(repr(value).encode()).hexdigest()


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v13 main experiment is fixed to 4 police, 4 mafia, 8 civilians")
    common_good = dict(reveal="silent", trust="none", dead_police_message="truth",
                       dead_claim_response="trust", live_counter="hidden")
    common_mafia = dict(bluff="none", kill="claims", opening_mode="ordinary",
                        dead_mafia_message="silent")
    position_good = tuple(decisions.GoodPolicyV13(**common_good, **p)
                          for p in config["position_good"])
    position_mafia = tuple(decisions.MafiaPolicyV13(**common_mafia, **p)
                           for p in config["position_mafia"])
    nomination_good = tuple(decisions.GoodPolicyV13(**common_good, **p)
                            for p in config["nomination_good"])
    nomination_mafia = tuple(decisions.MafiaPolicyV13(**common_mafia, **p)
                             for p in config["nomination_mafia"])
    pools = (position_good, position_mafia, nomination_good, nomination_mafia)
    if any(len({p.name for p in pool}) != len(pool) for pool in pools):
        raise ValueError("duplicate policy name")
    if {p.inspect_position for p in position_good} != {"random", "preempt", "reply", "gap"}:
        raise ValueError("position inspection pool changed")
    if {p.kill_position for p in position_mafia} != {"random", "first", "frontload", "bookend"}:
        raise ValueError("position kill pool changed")
    if {p.dead_clear_plan for p in nomination_good} != {
        "pass", "truth", "short1", "short3", "decoy_remove", "clear_remove"
    }:
        raise ValueError("nomination pool changed")
    if {p.shortlist_response for p in nomination_mafia} != {
        "random", "omitted", "removed", "listed"
    }:
        raise ValueError("nomination response pool changed")
    # The scan intervals, rather than only the accepted samples, are reserved.
    ranges = []
    for key in ("position_train", "position_holdout"):
        block = config[key]
        ranges.append((block["seed_start"], block["seed_start"] + block["n"], key))
    for key in ("nomination_train", "nomination_holdout"):
        block = config[key]
        ranges.append((block["seed_start"], block["seed_start"] + block["scan_limit"], key))
    for i, (a0, a1, an) in enumerate(ranges):
        for b0, b1, bn in ranges[i+1:]:
            if a0 < b1 and b0 < a1:
                raise ValueError(f"seed blocks overlap: {an}, {bn}")
    return rules, position_good, position_mafia, nomination_good, nomination_mafia


def _trace_basics(initial, outcome):
    roles = initial.roles
    day1_dead = [e["payload"]["victim"] for e in outcome.transcript
                 if e["day"] == 1 and e["event"] == "day_death"]
    night2 = [e["payload"]["victim"] for e in outcome.transcript
              if e["day"] == 2 and e["event"] == "night_death"]
    exile = roles[day1_dead[0]] if day1_dead else None
    return {
        "win": outcome.good_win,
        "day1_exile_mafia": int(exile == Role.MAFIA),
        "day1_exile_police": int(exile == Role.POLICE),
        "day1_exile_civilian": int(exile == Role.CIVILIAN),
        "day1_no_exile": int(exile is None),
        "night2_kill_police": int(bool(night2) and roles[night2[0]] == Role.POLICE),
    }


def _position_metrics(initial, outcome):
    metrics = _trace_basics(initial, outcome)
    roles = initial.roles
    order = speech_order(initial)
    metrics.update({
        "first_check_mafia": int(initial.investigations[0].is_mafia),
        "first_kill_police": int(roles[initial.deaths[0].player] == Role.POLICE),
        "first_speaker_mafia": int(bool(order) and roles[order[0]] == Role.MAFIA),
        "mafia_in_first4": sum(roles[p] == Role.MAFIA for p in order[:4]),
        "mafia_in_last3": sum(roles[p] == Role.MAFIA for p in order[-3:]),
    })
    return metrics


def _nomination_metrics(initial, outcome):
    metrics = _trace_basics(initial, outcome)
    roles, dead = initial.roles, initial.deaths[0].player
    rows = [m for m in outcome.transcript if m["day"] == 1 and
            m["event"] == "message" and m["payload"]["speaker"] == dead and
            m["payload"]["context"] == "last_words"]
    payload = rows[-1]["payload"] if rows else {}
    targets = payload.get("targets", [])
    removed = payload.get("target") if payload.get("kind") == "shortlist" else None
    final = [p for p in targets if p != removed]
    metrics.update({
        "has_shortlist": int(payload.get("kind") == "shortlist"),
        "listed_mafia": sum(roles[p] == Role.MAFIA for p in targets),
        "listed_police": sum(roles[p] == Role.POLICE for p in targets),
        "final_contains_mafia": int(any(roles[p] == Role.MAFIA for p in final)),
        "removed_police": int(removed is not None and roles[removed] == Role.POLICE),
        "removed_civilian": int(removed is not None and roles[removed] == Role.CIVILIAN),
        "omitted_live_police": sum(roles[p] == Role.POLICE and p not in targets
                                   for p in initial.alive),
    })
    return metrics


def _summarize(raw):
    return {key: mean(values) for key, values in raw.items()}


def _cell_position(job):
    phase, rules, good, mafia, start, n = job
    raw, samples = {}, []
    for index, seed in enumerate(range(start, start+n)):
        state = opening(rules, good, mafia, seed, decisions)
        result = continue_game(state, good, mafia, seed, trace=True,
                               decision_api=decisions, public_ballots=True)
        for key, value in _position_metrics(state, result).items():
            raw.setdefault(key, []).append(value)
        if index in {0, n//2, n-1}:
            samples.append({"index": index, "seed": seed, "opening_hash": _hash(state),
                            "trace_hash": _hash(result.transcript)})
    return {"phase": phase, "good": good.name, "mafia": mafia.name, "n": n,
            "seed_start": start, "raw": raw, "means": _summarize(raw),
            "win_summary": win_summary(raw["win"]), "samples": samples}


def _select_nomination_openings(rules, block, good, mafia):
    selected = []
    for seed in range(block["seed_start"], block["seed_start"] + block["scan_limit"]):
        state = opening(rules, good, mafia, seed, decisions)
        dead = state.deaths[0].player
        if state.roles[dead] == Role.POLICE and not state.investigations[0].is_mafia:
            selected.append((seed, state))
            if len(selected) == block["n"]:
                return selected
    raise RuntimeError("nomination cohort scan exhausted")


def _cell_nomination(job):
    phase, openings, good, mafia = job
    raw, samples = {}, []
    for index, (seed, state) in enumerate(openings):
        result = continue_game(state, good, mafia, seed, trace=True,
                               decision_api=decisions, public_ballots=True)
        for key, value in _nomination_metrics(state, result).items():
            raw.setdefault(key, []).append(value)
        if index in {0, len(openings)//2, len(openings)-1}:
            samples.append({"index": index, "seed": seed, "opening_hash": _hash(state),
                            "trace_hash": _hash(result.transcript)})
    return {"phase": phase, "cohort": "dead_police_clear", "good": good.name,
            "mafia": mafia.name, "n": len(openings), "seeds": [s for s, _ in openings],
            "raw": raw, "means": _summarize(raw), "win_summary": win_summary(raw["win"]),
            "samples": samples}


def _run(jobs, workers, function):
    if workers == 1:
        return list(map(function, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, jobs, chunksize=1))


def _matrix(cells, good_names, mafia_names):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    return [[Fraction(lookup[g, m]["win_summary"]["wins"], lookup[g, m]["n"])
             for m in mafia_names] for g in good_names]


def _solution(matrix, good_names, mafia_names):
    solution = solve_zero_sum(matrix)
    return {"value_exact": str(solution["value"]), "value": float(solution["value"]),
            "good_mixture": {n: str(w) for n, w in zip(good_names, solution["row_probabilities"]) if w},
            "mafia_mixture": {n: str(w) for n, w in zip(mafia_names, solution["column_probabilities"]) if w},
            "lower_exact": str(solution["lower_bound"]),
            "upper_exact": str(solution["upper_bound"]),
            "gap_exact": str(solution["gap"]), "simplex_pivots": solution["pivots"]}


def _frozen(matrix, good_names, mafia_names, artifact):
    row = [Fraction(artifact["good_mixture"].get(n, "0")) for n in good_names]
    col = [Fraction(artifact["mafia_mixture"].get(n, "0")) for n in mafia_names]
    versus_mafia = [sum(row[i]*matrix[i][j] for i in range(len(row)))
                    for j in range(len(col))]
    versus_good = [sum(col[j]*matrix[i][j] for j in range(len(col)))
                   for i in range(len(row))]
    lower, upper = min(versus_mafia), max(versus_good)
    return {"lower_exact": str(lower), "lower": float(lower),
            "upper_exact": str(upper), "upper": float(upper),
            "gap_exact": str(upper-lower), "gap": float(upper-lower),
            "worst_mafia": mafia_names[versus_mafia.index(lower)],
            "best_good": good_names[versus_good.index(upper)],
            "good_mix_vs_mafia": {n: float(v) for n, v in zip(mafia_names, versus_mafia)},
            "good_vs_mafia_mix": {n: float(v) for n, v in zip(good_names, versus_good)}}


def _report(cells, good, mafia, phase, train_solution=None, cohort=None):
    good_names, mafia_names = [p.name for p in good], [p.name for p in mafia]
    matrix = _matrix(cells, good_names, mafia_names)
    report = {"phase": phase, "cohort": cohort, "cells": cells,
              "matrix": {"good": good_names, "mafia": mafia_names,
                         "rates_exact": [[str(v) for v in row] for row in matrix]},
              "restricted_empirical_equilibrium": _solution(matrix, good_names, mafia_names)}
    if train_solution is not None:
        report["frozen_train_mixture_on_holdout"] = _frozen(
            matrix, good_names, mafia_names, train_solution)
    return report


def run_experiment(config, output, workers=4):
    rules, pg, pm, ng, nm = build_spec(config)
    output, root = Path(output), Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    assets = list((root/"mafia_lab").glob("*.py")) + [
        root/"configs/position_nomination_v13.json",
        root/"scripts/run_position_nomination_v13.py",
        root/"scripts/verify_position_nomination_v13.py",
        root/"docs/position_nomination_protocol_v13.md",
    ]
    for source in assets:
        target = output/"source"/source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _json(output/"source/config.json", config)
    source_assets = {str(p.relative_to(output)): sha256(p.read_bytes()).hexdigest()
                     for p in (output/"source").rglob("*") if p.is_file()}
    freeze = {"version": config["version"], "source_sha256": fingerprint(),
              "source_assets": source_assets,
              "expanded": {"position_good": [asdict(p) for p in pg],
                           "position_mafia": [asdict(p) for p in pm],
                           "nomination_good": [asdict(p) for p in ng],
                           "nomination_mafia": [asdict(p) for p in nm]},
              "scope": config["scope"]}
    _json(output/"freeze_before_evaluation.json", freeze)
    started = time.monotonic()

    pb = config["position_train"]
    position_train = _report(_run([
        ("train", rules, g, m, pb["seed_start"], pb["n"]) for g in pg for m in pm
    ], workers, _cell_position), pg, pm, "train")
    _json(output/"position_train.json", position_train)

    nt = config["nomination_train"]
    openings_train = _select_nomination_openings(rules, nt, ng[0], nm[0])
    nomination_train = _report(_run([
        ("train", openings_train, g, m) for g in ng for m in nm
    ], workers, _cell_nomination), ng, nm, "train", cohort="dead_police_clear")
    _json(output/"nomination_train.json", nomination_train)
    selection = {"holdout_unread": True,
                 "position_train_solution": position_train["restricted_empirical_equilibrium"],
                 "nomination_train_solution": nomination_train["restricted_empirical_equilibrium"],
                 "scope": "Exact solutions of two finite empirical train matrices only."}
    _json(output/"selection_before_holdout.json", selection)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed after train freeze")

    ph = config["position_holdout"]
    position_holdout = _report(_run([
        ("holdout", rules, g, m, ph["seed_start"], ph["n"]) for g in pg for m in pm
    ], workers, _cell_position), pg, pm, "holdout", selection["position_train_solution"])
    _json(output/"position_holdout.json", position_holdout)

    nh = config["nomination_holdout"]
    openings_holdout = _select_nomination_openings(rules, nh, ng[0], nm[0])
    nomination_holdout = _report(_run([
        ("holdout", openings_holdout, g, m) for g in ng for m in nm
    ], workers, _cell_nomination), ng, nm, "holdout",
        selection["nomination_train_solution"], cohort="dead_police_clear")
    _json(output/"nomination_holdout.json", nomination_holdout)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed during holdout")

    files = ["freeze_before_evaluation.json", "position_train.json",
             "nomination_train.json", "selection_before_holdout.json",
             "position_holdout.json", "nomination_holdout.json"]
    manifest = {"version": config["version"], "source_sha256": freeze["source_sha256"],
                "elapsed_seconds": time.monotonic()-started,
                "position_games": sum(c["n"] for r in (position_train, position_holdout)
                                      for c in r["cells"]),
                "nomination_games": sum(c["n"] for r in (nomination_train, nomination_holdout)
                                        for c in r["cells"]),
                "files": {n: sha256((output/n).read_bytes()).hexdigest() for n in files},
                "scope": config["scope"]}
    _json(output/"manifest.json", manifest)
    return manifest
