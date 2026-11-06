"""Frozen v16 robust-prior and variable-shortlist experiment."""
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
from .statistics import paired_summary, win_summary
from .position_repair_experiment_v14 import _matrix, _solution, _frozen
from .strategies_v16 import GoodPolicyV16, MafiaPolicyV16
from . import strategies_v16 as decisions


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _hash(value):
    return sha256(repr(value).encode()).hexdigest()


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v16 is fixed to 4 police, 4 mafia, 8 civilians")
    common_good = dict(
        reveal="silent", trust="none", dead_police_message="truth",
        dead_claim_response="trust", live_counter="hidden",
        inspect_position="gap", dead_clear_plan="truth",
        leadership="nominate", position_model="posterior",
    )
    common_mafia = dict(bluff="none", kill="claims", opening_mode="ordinary",
                        dead_mafia_message="silent")
    good = tuple(GoodPolicyV16(**common_good, **row) for row in config["good"])
    mafia = tuple(MafiaPolicyV16(**common_mafia, **row) for row in config["mafia"])
    calibration = MafiaPolicyV16(**common_mafia, **config["calibration_mafia"])
    expected_good = [f"{prior}_{rule}" for prior in ("equal", "robust")
                     for rule in ("hard1", "list2", "list3", "adaptive")]
    if [p.name for p in good] != expected_good:
        raise ValueError("v16 good pool changed")
    if [p.name for p in mafia] != [
        "safe_middle", "safe_late", "middle_late_mix", "posterior_decoy"
    ]:
        raise ValueError("v16 mafia pool changed")
    for left, right in ((config["train"], config["holdout"]),
                        (config["train"], config["calibration"]),
                        (config["holdout"], config["calibration"])):
        if left["seed_start"] < right["seed_start"] + right["n"] and \
           right["seed_start"] < left["seed_start"] + left["n"]:
            raise ValueError("v16 seed blocks overlap")
    return rules, good, mafia, calibration


def _metrics(initial, outcome):
    roles = initial.roles
    day1 = [e for e in outcome.transcript if e["day"] == 1]
    calls = [e["payload"] for e in day1 if e["event"] == "final_call"
             and e["payload"]["kind"] == "shortlist"]
    finals = [e["payload"] for e in day1 if e["event"] == "final_selection"]
    preferences = [e["payload"] for e in day1 if e["event"] == "preference"]
    day_deaths = [e["payload"]["victim"] for e in day1 if e["event"] == "day_death"]
    shortlist = calls[-1]["targets"] if calls else []
    target = finals[-1]["target"] if finals else None
    exile = day_deaths[0] if day_deaths else None
    eligible = roles[initial.deaths[0].player] != Role.POLICE
    return {
        "win": outcome.good_win,
        "leader_eligible": int(eligible),
        "eligible_hit": int(eligible and initial.investigations[0].is_mafia),
        "eligible_clear": int(eligible and not initial.investigations[0].is_mafia),
        "first_kill_police": int(not eligible),
        "first_check_mafia": int(initial.investigations[0].is_mafia),
        "first_speaker_mafia": int(roles[speech_order(initial)[0]] == Role.MAFIA),
        "shortlist_size": len(shortlist),
        "preference_count": len(preferences),
        "final_target_exists": int(target is not None),
        "final_target_mafia": int(target is not None and roles[target] == Role.MAFIA),
        "final_shifted_from_private_top": int(bool(shortlist) and target != shortlist[0]),
        "day1_exile_mafia": int(exile is not None and roles[exile] == Role.MAFIA),
        "day1_exile_police": int(exile is not None and roles[exile] == Role.POLICE),
        "day1_exile_civilian": int(exile is not None and roles[exile] == Role.CIVILIAN),
        "day1_no_exile": int(exile is None),
    }


def _branches(raw):
    masks = {
        "all": [True] * len(raw["win"]),
        "leader_eligible": [bool(x) for x in raw["leader_eligible"]],
        "eligible_hit": [bool(x) for x in raw["eligible_hit"]],
        "eligible_clear": [bool(x) for x in raw["eligible_clear"]],
    }
    result = {}
    for name, mask in masks.items():
        wins = [x for x, keep in zip(raw["win"], mask) if keep]
        targets = [x for x, keep in zip(raw["final_target_mafia"], mask) if keep]
        result[name] = {
            "win": win_summary(wins) if wins else {"n": 0, "wins": 0, "rate": None},
            "final_target_mafia_rate": mean(targets) if targets else None,
            "n": len(wins),
        }
    return result


def evaluate_cell(job):
    phase, rules, good, mafia, start, n = job
    raw, samples = {}, []
    for index, seed in enumerate(range(start, start + n)):
        state = opening(rules, good, mafia, seed, decisions)
        outcome = continue_game(state, good, mafia, seed, trace=True,
                                decision_api=decisions, public_ballots=True)
        for key, value in _metrics(state, outcome).items():
            raw.setdefault(key, []).append(value)
        if index in {0, n // 2, n - 1}:
            samples.append({"index": index, "seed": seed, "opening_hash": _hash(state),
                            "trace_hash": _hash(outcome.transcript)})
    return {"phase": phase, "good": good.name, "mafia": mafia.name, "n": n,
            "seed_start": start, "raw": raw,
            "means": {k: mean(v) for k, v in raw.items()},
            "win_summary": win_summary(raw["win"]), "branches": _branches(raw),
            "samples": samples}


def _run(jobs, workers):
    if workers == 1:
        return list(map(evaluate_cell, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(evaluate_cell, jobs, chunksize=1))


def _paired(cells, control, treatment, mafia, branch, metric):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    a, b = lookup[control, mafia], lookup[treatment, mafia]
    mask = ([True] * a["n"] if branch == "all"
            else [bool(x) for x in a["raw"][branch]])
    other = ([True] * b["n"] if branch == "all"
             else [bool(x) for x in b["raw"][branch]])
    if mask != other:
        raise RuntimeError("branch membership changed across paired intervention")
    av = [x for x, keep in zip(a["raw"][metric], mask) if keep]
    bv = [x for x, keep in zip(b["raw"][metric], mask) if keep]
    return paired_summary(av, bv)


def _contrasts(cells, good, mafia):
    rows = []
    mafia_names = [p.name for p in mafia]
    rules = ("hard1", "list2", "list3", "adaptive")
    pairs = []
    for rule in rules:
        pairs.append((f"robust_minus_equal_{rule}", f"equal_{rule}", f"robust_{rule}"))
    for prior in ("equal", "robust"):
        for rule in ("list2", "list3", "adaptive"):
            pairs.append((f"{prior}_{rule}_minus_hard1", f"{prior}_hard1", f"{prior}_{rule}"))
    for name, control, treatment in pairs:
        for m in mafia_names:
            for branch in ("all", "leader_eligible", "eligible_hit", "eligible_clear"):
                rows.append({"name": name, "control": control, "treatment": treatment,
                             "mafia": m, "branch": branch,
                             "win": _paired(cells, control, treatment, m, branch, "win"),
                             "final_target_mafia": _paired(
                                 cells, control, treatment, m, branch, "final_target_mafia")})
    return rows


def _report(cells, good, mafia, phase, train_solution=None):
    gn, mn = [p.name for p in good], [p.name for p in mafia]
    matrix = _matrix(cells, gn, mn)
    result = {"phase": phase, "cells": cells,
              "matrix": {"good": gn, "mafia": mn,
                         "rates_exact": [[str(v) for v in row] for row in matrix]},
              "restricted_empirical_equilibrium": _solution(matrix, gn, mn),
              "predeclared_paired_contrasts": _contrasts(cells, good, mafia)}
    if train_solution is not None:
        result["frozen_train_mixture_on_holdout"] = _frozen(matrix, gn, mn, train_solution)
    return result


def run_experiment(config, output, workers=4):
    rules, good, mafia, calibration_mafia = build_spec(config)
    output, root = Path(output), Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    assets = list((root / "mafia_lab").glob("*.py")) + [
        root / "configs/robust_shortlist_v16.json",
        root / "scripts/run_robust_shortlist_v16.py",
        root / "scripts/verify_robust_shortlist_v16.py",
        root / "docs/robust_shortlist_protocol_v16.md",
    ]
    for source in assets:
        target = output / "source" / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _json(output / "source/config.json", config)
    source_assets = {str(p.relative_to(output)): sha256(p.read_bytes()).hexdigest()
                     for p in (output / "source").rglob("*") if p.is_file()}
    freeze = {"version": config["version"], "source_sha256": fingerprint(),
              "source_assets": source_assets,
              "expanded": {"good": [asdict(p) for p in good],
                           "mafia": [asdict(p) for p in mafia],
                           "calibration_mafia": asdict(calibration_mafia)},
              "scope": config["scope"]}
    _json(output / "freeze_before_evaluation.json", freeze)
    started = time.monotonic()
    train_cfg = config["train"]
    train_cells = _run([("train", rules, g, m, train_cfg["seed_start"], train_cfg["n"])
                        for g in good for m in mafia], workers)
    train_report = _report(train_cells, good, mafia, "train")
    _json(output / "train.json", train_report)
    selection = {"holdout_unread": True,
                 "train_solution": train_report["restricted_empirical_equilibrium"],
                 "candidate_pool_frozen": {"good": [p.name for p in good],
                                           "mafia": [p.name for p in mafia]},
                 "random_kill_role": "calibration only",
                 "scope": "Finite empirical train matrix only."}
    _json(output / "selection_before_holdout.json", selection)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed after train freeze")
    hold_cfg = config["holdout"]
    hold_cells = _run([("holdout", rules, g, m, hold_cfg["seed_start"], hold_cfg["n"])
                       for g in good for m in mafia], workers)
    hold_report = _report(hold_cells, good, mafia, "holdout", selection["train_solution"])
    _json(output / "holdout.json", hold_report)
    cal_cfg = config["calibration"]
    cal_cells = _run([("calibration", rules, g, calibration_mafia,
                       cal_cfg["seed_start"], cal_cfg["n"]) for g in good], workers)
    calibration = {"phase": "random_kill_calibration", "cells": cal_cells,
                   "scope": "Independent baseline only; excluded from restricted equilibrium and selection."}
    _json(output / "calibration.json", calibration)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed during frozen evaluation")
    files = ["freeze_before_evaluation.json", "train.json",
             "selection_before_holdout.json", "holdout.json", "calibration.json"]
    manifest = {"version": config["version"], "source_sha256": freeze["source_sha256"],
                "elapsed_seconds": time.monotonic() - started,
                "games": sum(c["n"] for c in train_cells + hold_cells + cal_cells),
                "files": {name: sha256((output / name).read_bytes()).hexdigest()
                          for name in files}, "scope": config["scope"]}
    _json(output / "manifest.json", manifest)
    return manifest
