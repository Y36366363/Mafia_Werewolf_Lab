"""Frozen v14 root experiment for non-exposing mafia kill geometry."""
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
from .strategies_v13 import GoodPolicyV13
from .strategies_v14 import MafiaPolicyV14
from . import strategies_v14 as decisions


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _hash(value):
    return sha256(repr(value).encode()).hexdigest()


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v14 is fixed to 4 police, 4 mafia, 8 civilians")
    common_good = dict(reveal="silent", trust="none", dead_police_message="truth",
                       dead_claim_response="trust", live_counter="hidden")
    common_mafia = dict(bluff="none", kill="claims", opening_mode="ordinary",
                        dead_mafia_message="silent")
    good = tuple(GoodPolicyV13(**common_good, **p) for p in config["good"])
    mafia = tuple(MafiaPolicyV14(**common_mafia, **p) for p in config["mafia"])
    if [p.name for p in good] != ["inspect_random", "inspect_preempt",
                                  "inspect_reply", "inspect_gap"]:
        raise ValueError("v14 good pool changed")
    if [p.name for p in mafia] != ["kill_random", "safe_front", "safe_middle",
            "safe_late", "safe_sandwich", "safe_balanced", "safe_mix"]:
        raise ValueError("v14 mafia pool changed")
    good_names, mafia_names = {p.name for p in good}, {p.name for p in mafia}
    if len(good_names) != len(good) or len(mafia_names) != len(mafia):
        raise ValueError("duplicate policy name")
    for _, control, treatment in config["primary_contrasts"]:
        if control not in mafia_names or treatment not in mafia_names:
            raise ValueError("unknown contrast policy")
    train, holdout = config["train"], config["holdout"]
    if train["seed_start"] < holdout["seed_start"] + holdout["n"] and \
       holdout["seed_start"] < train["seed_start"] + train["n"]:
        raise ValueError("train and holdout seeds overlap")
    return rules, good, mafia


def _metrics(initial, outcome):
    roles, order = initial.roles, speech_order(initial)
    day1_dead = [e["payload"]["victim"] for e in outcome.transcript
                 if e["day"] == 1 and e["event"] == "day_death"]
    night2 = [e["payload"]["victim"] for e in outcome.transcript
              if e["day"] == 2 and e["event"] == "night_death"]
    exile = day1_dead[0] if day1_dead else None
    return {
        "win": outcome.good_win,
        "first_check_mafia": int(initial.investigations[0].is_mafia),
        "first_kill_police": int(roles[initial.deaths[0].player] == Role.POLICE),
        "first_speaker_mafia": int(bool(order) and roles[order[0]] == Role.MAFIA),
        "mafia_positions_2_4": sum(roles[p] == Role.MAFIA for p in order[1:4]),
        "mafia_positions_4_8": sum(roles[p] == Role.MAFIA for p in order[3:8]),
        "mafia_last4": sum(roles[p] == Role.MAFIA for p in order[-4:]),
        "day1_exile_mafia": int(exile is not None and roles[exile] == Role.MAFIA),
        "day1_exile_police": int(exile is not None and roles[exile] == Role.POLICE),
        "day1_exile_civilian": int(exile is not None and roles[exile] == Role.CIVILIAN),
        "day1_no_exile": int(exile is None),
        "day1_anchor_exiled": int(exile is not None and bool(order) and exile == order[0]),
        "night2_kill_police": int(bool(night2) and roles[night2[0]] == Role.POLICE),
    }


def evaluate_cell(job):
    phase, rules, good, mafia, start, n = job
    raw, samples = {}, []
    for index, seed in enumerate(range(start, start+n)):
        state = opening(rules, good, mafia, seed, decisions)
        outcome = continue_game(state, good, mafia, seed, trace=True,
                                decision_api=decisions, public_ballots=True)
        for key, value in _metrics(state, outcome).items():
            raw.setdefault(key, []).append(value)
        if index in {0, n//2, n-1}:
            samples.append({"index":index, "seed":seed, "opening_hash":_hash(state),
                            "trace_hash":_hash(outcome.transcript)})
    return {"phase":phase, "good":good.name, "mafia":mafia.name,
            "n":n, "seed_start":start, "raw":raw,
            "means":{k:mean(v) for k,v in raw.items()},
            "win_summary":win_summary(raw["win"]), "samples":samples}


def _run(jobs, workers):
    if workers == 1:
        return list(map(evaluate_cell, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(evaluate_cell, jobs, chunksize=1))


def _matrix(cells, good_names, mafia_names):
    lookup = {(c["good"],c["mafia"]):c for c in cells}
    return [[Fraction(lookup[g,m]["win_summary"]["wins"], lookup[g,m]["n"])
             for m in mafia_names] for g in good_names]


def _solution(matrix, good_names, mafia_names):
    result = solve_zero_sum(matrix)
    return {"value_exact":str(result["value"]), "value":float(result["value"]),
            "good_mixture":{n:str(w) for n,w in zip(good_names,result["row_probabilities"]) if w},
            "mafia_mixture":{n:str(w) for n,w in zip(mafia_names,result["column_probabilities"]) if w},
            "lower_exact":str(result["lower_bound"]),
            "upper_exact":str(result["upper_bound"]),
            "gap_exact":str(result["gap"]), "simplex_pivots":result["pivots"]}


def _frozen(matrix, good_names, mafia_names, artifact):
    row = [Fraction(artifact["good_mixture"].get(n,"0")) for n in good_names]
    col = [Fraction(artifact["mafia_mixture"].get(n,"0")) for n in mafia_names]
    versus_mafia = [sum(row[i]*matrix[i][j] for i in range(len(row)))
                    for j in range(len(col))]
    versus_good = [sum(col[j]*matrix[i][j] for j in range(len(col)))
                   for i in range(len(row))]
    lower, upper = min(versus_mafia), max(versus_good)
    return {"lower_exact":str(lower), "lower":float(lower),
            "upper_exact":str(upper), "upper":float(upper),
            "gap_exact":str(upper-lower), "gap":float(upper-lower),
            "worst_mafia":mafia_names[versus_mafia.index(lower)],
            "best_good":good_names[versus_good.index(upper)],
            "good_mix_vs_mafia":{n:float(v) for n,v in zip(mafia_names,versus_mafia)},
            "good_vs_mafia_mix":{n:float(v) for n,v in zip(good_names,versus_good)}}


def _contrasts(cells, config):
    lookup = {(c["good"],c["mafia"]):c for c in cells}
    good = "inspect_gap"
    family = len(config["primary_contrasts"])
    z = NormalDist().inv_cdf(1-.05/(2*family))
    rows = []
    for name, control, treatment in config["primary_contrasts"]:
        a, b = lookup[good,control], lookup[good,treatment]
        metrics = {}
        for key in ("win", "first_speaker_mafia", "day1_exile_mafia",
                    "day1_exile_police", "day1_exile_civilian",
                    "day1_anchor_exiled", "night2_kill_police"):
            metrics[key] = paired_summary(a["raw"][key], b["raw"][key])
        diffs = [y-x for x,y in zip(a["raw"]["win"],b["raw"]["win"])]
        delta = mean(diffs)
        se = sqrt(variance(diffs)/len(diffs)) if len(diffs)>1 else 0
        half = sqrt(2*log(2*family/.05)/len(diffs))
        rows.append({"name":name, "good":good, "control":control,
                     "treatment":treatment, "metrics":metrics,
                     "win_family_normal_approx":[delta-z*se,delta+z*se],
                     "win_family_hoeffding":[delta-half,delta+half]})
    return rows


def _report(cells, good, mafia, phase, config, train_solution=None):
    gn, mn = [p.name for p in good], [p.name for p in mafia]
    matrix = _matrix(cells,gn,mn)
    report = {"phase":phase, "cells":cells,
              "matrix":{"good":gn,"mafia":mn,
                        "rates_exact":[[str(v) for v in row] for row in matrix]},
              "restricted_empirical_equilibrium":_solution(matrix,gn,mn),
              "predeclared_gap_row_contrasts":_contrasts(cells,config)}
    if train_solution is not None:
        report["frozen_train_mixture_on_holdout"] = _frozen(matrix,gn,mn,train_solution)
    return report


def run_experiment(config, output, workers=4):
    rules, good, mafia = build_spec(config)
    output, root = Path(output), Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    assets = list((root/"mafia_lab").glob("*.py")) + [
        root/"configs/position_repair_v14.json", root/"scripts/run_position_repair_v14.py",
        root/"scripts/verify_position_repair_v14.py", root/"docs/position_repair_protocol_v14.md"]
    for source in assets:
        target = output/"source"/source.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    _json(output/"source/config.json",config)
    source_assets = {str(p.relative_to(output)):sha256(p.read_bytes()).hexdigest()
                     for p in (output/"source").rglob("*") if p.is_file()}
    freeze = {"version":config["version"],"source_sha256":fingerprint(),
              "source_assets":source_assets,
              "expanded":{"good":[asdict(p) for p in good],
                          "mafia":[asdict(p) for p in mafia]},"scope":config["scope"]}
    _json(output/"freeze_before_evaluation.json",freeze)
    started=time.monotonic()
    train=config["train"]
    train_report=_report(_run([("train",rules,g,m,train["seed_start"],train["n"])
        for g in good for m in mafia],workers),good,mafia,"train",config)
    _json(output/"train.json",train_report)
    selection={"holdout_unread":True,
               "train_solution":train_report["restricted_empirical_equilibrium"],
               "scope":"Exact solution of the finite empirical train matrix only."}
    _json(output/"selection_before_holdout.json",selection)
    if fingerprint()!=freeze["source_sha256"]:
        raise RuntimeError("package changed after train freeze")
    holdout=config["holdout"]
    holdout_report=_report(_run([("holdout",rules,g,m,holdout["seed_start"],holdout["n"])
        for g in good for m in mafia],workers),good,mafia,"holdout",config,
        selection["train_solution"])
    _json(output/"holdout.json",holdout_report)
    if fingerprint()!=freeze["source_sha256"]:
        raise RuntimeError("package changed during holdout")
    files=["freeze_before_evaluation.json","train.json",
           "selection_before_holdout.json","holdout.json"]
    manifest={"version":config["version"],"source_sha256":freeze["source_sha256"],
              "elapsed_seconds":time.monotonic()-started,
              "games":sum(c["n"] for r in (train_report,holdout_report) for c in r["cells"]),
              "files":{n:sha256((output/n).read_bytes()).hexdigest() for n in files},
              "scope":config["scope"]}
    _json(output/"manifest.json",manifest)
    return manifest
