"""Fresh-seed correction for the confounded v13 nomination branch."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

from .engine import Rules
from .experiments import fingerprint
from .position_nomination_experiment_v13 import (
    _cell_nomination, _frozen, _json, _matrix, _report, _run,
    _select_nomination_openings,
)
from . import strategies_v13 as decisions


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v13b is fixed to 4 police, 4 mafia, 8 civilians")
    common_good = dict(reveal="silent", trust="none", dead_police_message="truth",
                       dead_claim_response="trust", live_counter="hidden")
    common_mafia = dict(bluff="none", kill="claims", opening_mode="ordinary",
                        dead_mafia_message="silent")
    good = tuple(decisions.GoodPolicyV13(**common_good, **p)
                 for p in config["nomination_good"])
    mafia = tuple(decisions.MafiaPolicyV13(**common_mafia, **p)
                  for p in config["nomination_mafia"])
    if {p.dead_clear_plan for p in good} != {
        "pass", "truth", "short1", "short3", "decoy_remove", "clear_remove"
    } or {p.shortlist_response for p in mafia} != {"random", "omitted", "removed", "listed"}:
        raise ValueError("v13b policy pool changed")
    if any(p.kill_position != "random" for p in mafia):
        raise ValueError("v13b correction must use random opening kills")
    blocks = [config["train"], config["holdout"]]
    ranges = [(b["seed_start"], b["seed_start"]+b["scan_limit"]) for b in blocks]
    if ranges[0][0] < ranges[1][1] and ranges[1][0] < ranges[0][1]:
        raise ValueError("train and holdout scan blocks overlap")
    return rules, good, mafia


def run_experiment(config, output, workers=4):
    rules, good, mafia = build_spec(config)
    output, root = Path(output), Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError("use a new output directory")
    output.mkdir(parents=True)
    assets = list((root/"mafia_lab").glob("*.py")) + [
        root/"configs/nomination_followup_v13b.json",
        root/"scripts/run_nomination_followup_v13b.py",
        root/"scripts/verify_nomination_followup_v13b.py",
        root/"docs/nomination_followup_protocol_v13b.md",
    ]
    for source in assets:
        target = output/"source"/source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _json(output/"source/config.json", config)
    source_assets = {str(p.relative_to(output)): sha256(p.read_bytes()).hexdigest()
                     for p in (output/"source").rglob("*") if p.is_file()}
    freeze = {"version":config["version"], "source_sha256":fingerprint(),
              "source_assets":source_assets, "expanded":{
                  "good":[asdict(p) for p in good], "mafia":[asdict(p) for p in mafia]},
              "scope":config["scope"]}
    _json(output/"freeze_before_evaluation.json", freeze)
    started = time.monotonic()
    train_openings = _select_nomination_openings(rules, config["train"], good[0], mafia[0])
    train = _report(_run([("train", train_openings, g, m) for g in good for m in mafia],
                         workers, _cell_nomination), good, mafia, "train",
                    cohort="dead_police_clear")
    _json(output/"train.json", train)
    selection = {"holdout_unread":True,
                 "train_solution":train["restricted_empirical_equilibrium"],
                 "scope":"Exact solution of the finite empirical train matrix only."}
    _json(output/"selection_before_holdout.json", selection)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed after train freeze")
    holdout_openings = _select_nomination_openings(
        rules, config["holdout"], good[0], mafia[0])
    holdout = _report(_run([("holdout", holdout_openings, g, m) for g in good for m in mafia],
                           workers, _cell_nomination), good, mafia, "holdout",
                      selection["train_solution"], cohort="dead_police_clear")
    _json(output/"holdout.json", holdout)
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("package changed during holdout")
    files = ["freeze_before_evaluation.json", "train.json",
             "selection_before_holdout.json", "holdout.json"]
    manifest = {"version":config["version"], "source_sha256":freeze["source_sha256"],
                "elapsed_seconds":time.monotonic()-started,
                "games":sum(c["n"] for r in (train, holdout) for c in r["cells"]),
                "files":{n:sha256((output/n).read_bytes()).hexdigest() for n in files},
                "scope":config["scope"]}
    _json(output/"manifest.json", manifest)
    return manifest
