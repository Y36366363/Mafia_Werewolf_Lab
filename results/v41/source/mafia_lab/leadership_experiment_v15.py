"""Frozen v15 experiment for living-police leadership and position response."""
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
from .strategies_v15 import GoodPolicyV15
from .strategies_v14 import MafiaPolicyV14
from . import strategies_v15 as decisions


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _hash(value):
    return sha256(repr(value).encode()).hexdigest()


def build_spec(config, *, confirmation=False):
    rules = Rules(**config["confirmation_rules" if confirmation else "rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v15 is fixed to 4 police, 4 mafia, 8 civilians")
    common_good = dict(reveal="silent", trust="none", dead_police_message="truth",
                       dead_claim_response="trust", live_counter="hidden",
                       inspect_position="gap", dead_clear_plan="truth")
    common_mafia = dict(bluff="none", kill="claims", opening_mode="ordinary",
                        dead_mafia_message="silent")
    good_rows = config["confirmation_good"] if confirmation else config["good"]
    good = tuple(GoodPolicyV15(**common_good, **p) for p in good_rows)
    mafia = tuple(MafiaPolicyV14(**common_mafia, **p) for p in config["mafia"])
    if not confirmation and [p.name for p in good] != [
        "hidden_naive", "report_only", "nominate_naive", "nominate_position",
        "pk_naive", "pk_position"
    ]:
        raise ValueError("v15 good pool changed")
    if [p.name for p in mafia] != [
        "kill_random", "safe_middle", "safe_late", "safe_mix"
    ]:
        raise ValueError("v15 mafia pool changed")
    if len({p.name for p in good}) != len(good):
        raise ValueError("duplicate good policy")
    return rules, good, mafia


def _metrics(initial, outcome):
    roles, order = initial.roles, speech_order(initial)
    day1_dead = [e["payload"]["victim"] for e in outcome.transcript
                 if e["day"] == 1 and e["event"] == "day_death"]
    exile = day1_dead[0] if day1_dead else None
    day1_messages = [e["payload"] for e in outcome.transcript
                     if e["day"] == 1 and e["event"] in {"message", "final_call"}]
    reports = [m for m in day1_messages if m["kind"] == "report"
               and m["context"] == "day"]
    calls = [m for m in day1_messages if m["kind"] == "shortlist"
             and m["context"] == "day"]
    leader_eligible = roles[initial.deaths[0].player] != Role.POLICE
    return {
        "win": outcome.good_win,
        "leader_eligible": int(leader_eligible),
        "eligible_hit": int(leader_eligible and initial.investigations[0].is_mafia),
        "eligible_clear": int(leader_eligible and not initial.investigations[0].is_mafia),
        "first_check_mafia": int(initial.investigations[0].is_mafia),
        "first_kill_police": int(not leader_eligible),
        "first_speaker_mafia": int(bool(order) and roles[order[0]] == Role.MAFIA),
        "day1_live_report": int(bool(reports)),
        "day1_shortlist_size": len(calls[-1]["targets"]) if calls else 0,
        "day1_pk": int(any(e["day"] == 1 and e["event"] == "pk_votes"
                           for e in outcome.transcript)),
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
        wins = [value for value, keep in zip(raw["win"], mask) if keep]
        result[name] = win_summary(wins) if wins else {"n": 0, "wins": 0, "rate": None}
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


def _contrasts(cells, config):
    lookup = {(c["good"], c["mafia"]): c for c in cells}
    rows = []
    for name, control, treatment in config["primary_contrasts"]:
        for mafia in config["contrast_mafia"]:
            a, b = lookup[control, mafia], lookup[treatment, mafia]
            # Identical inspection and mafia policy make these branch masks
            # exactly pairable across the two leadership interventions.
            for branch in ("all", "leader_eligible", "eligible_hit", "eligible_clear"):
                mask = ([True] * a["n"] if branch == "all"
                        else [bool(x) for x in a["raw"][branch]])
                other = ([True] * b["n"] if branch == "all"
                         else [bool(x) for x in b["raw"][branch]])
                if mask != other:
                    raise RuntimeError("paired branch membership changed across intervention")
                av = [x for x, keep in zip(a["raw"]["win"], mask) if keep]
                bv = [x for x, keep in zip(b["raw"]["win"], mask) if keep]
                rows.append({"name": name, "mafia": mafia, "branch": branch,
                             "n": len(av), "paired_win": paired_summary(av, bv)})
    return rows


def _report(cells, good, mafia, phase, config, train_solution=None):
    gn, mn = [p.name for p in good], [p.name for p in mafia]
    matrix = _matrix(cells, gn, mn)
    result = {"phase": phase, "cells": cells,
              "matrix": {"good": gn, "mafia": mn,
                         "rates_exact": [[str(v) for v in row] for row in matrix]},
              "restricted_empirical_equilibrium": _solution(matrix, gn, mn),
              "predeclared_paired_contrasts": _contrasts(cells, config)}
    if train_solution is not None:
        result["frozen_train_mixture_on_holdout"] = _frozen(
            matrix, gn, mn, train_solution)
    return result


def _confirmation(cells, config):
    reference = config["v14_reference"]
    rows = []
    for cell in cells:
        old = Fraction(reference[cell["mafia"]])
        new = Fraction(cell["win_summary"]["wins"], cell["n"])
        rows.append({"mafia": cell["mafia"], "n": cell["n"],
                     "v14_rate_exact": str(old), "new_rate_exact": str(new),
                     "delta_exact": str(new - old), "new_summary": cell["win_summary"]})
    random_rate = next(Fraction(r["new_rate_exact"]) for r in rows
                       if r["mafia"] == "kill_random")
    for row in rows:
        row["new_minus_random_exact"] = str(Fraction(row["new_rate_exact"]) - random_rate)
    return {"phase": "independent_confirmation", "cells": cells,
            "comparisons": rows,
            "scope": "Fresh fixed-policy replication; no candidate selection or equilibrium claim."}


def run_experiment(config, output, workers=4):
    rules, good, mafia = build_spec(config)
    confirm_rules, confirm_good, confirm_mafia = build_spec(config, confirmation=True)
    output, root = Path(output), Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    assets = list((root / "mafia_lab").glob("*.py")) + [
        root / "configs/leadership_v15.json", root / "scripts/run_leadership_v15.py",
        root / "scripts/verify_leadership_v15.py", root / "docs/leadership_protocol_v15.md"]
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
                           "mafia": [asdict(p) for p in mafia]}, "scope": config["scope"]}
    _json(output / "freeze_before_evaluation.json", freeze)
    started = time.monotonic()
    train_cfg = config["train"]
    train_cells = _run([("train", rules, g, m, train_cfg["seed_start"], train_cfg["n"])
                        for g in good for m in mafia], workers)
    train_report = _report(train_cells, good, mafia, "train", config)
    _json(output / "train.json", train_report)
    selection = {"holdout_unread": True,
                 "train_solution": train_report["restricted_empirical_equilibrium"],
                 "candidate_pool_frozen": {"good": [p.name for p in good],
                                           "mafia": [p.name for p in mafia]},
                 "scope": "Finite empirical train matrix only."}
    _json(output / "selection_before_holdout.json", selection)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed after train freeze")
    hold_cfg = config["holdout"]
    hold_cells = _run([("holdout", rules, g, m, hold_cfg["seed_start"], hold_cfg["n"])
                       for g in good for m in mafia], workers)
    hold_report = _report(hold_cells, good, mafia, "holdout", config,
                          selection["train_solution"])
    _json(output / "holdout.json", hold_report)
    confirm_cfg = config["confirmation"]
    confirm_cells = _run([("confirmation", confirm_rules, confirm_good[0], m,
                           confirm_cfg["seed_start"], confirm_cfg["n"])
                          for m in confirm_mafia], workers)
    _json(output / "confirmation.json", _confirmation(confirm_cells, config))
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed during frozen evaluation")
    files = ["freeze_before_evaluation.json", "train.json",
             "selection_before_holdout.json", "holdout.json", "confirmation.json"]
    manifest = {"version": config["version"], "source_sha256": freeze["source_sha256"],
                "elapsed_seconds": time.monotonic() - started,
                "games": sum(c["n"] for c in train_cells + hold_cells + confirm_cells),
                "files": {n: sha256((output / n).read_bytes()).hexdigest() for n in files},
                "scope": config["scope"]}
    _json(output / "manifest.json", manifest)
    return manifest
