"""Frozen 2x4 paired intervention and post-game metrics for v11."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from hashlib import sha256
import json
from math import log, sqrt
from pathlib import Path
from statistics import mean, variance, NormalDist

from .engine import Role, Rules
from .experiments import fingerprint
from .simulation import opening, continue_game
from .statistics import win_summary
from .strategies_v10 import GoodPolicyV10
from . import strategies_v11 as decisions


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def build_spec(config):
    rules = Rules(**config["rules"])
    if asdict(rules) != dict(police=4, mafia=4, civilians=8, last_words_limit=3,
                             allow_self_kill=True, tie_rule="pass", direction=1):
        raise ValueError("v11 rules are fixed")
    good = [GoodPolicyV10(**item) for item in config["good_candidates"]]
    if [g.name for g in good] != ["anchor", "diverse"]:
        raise ValueError("v11 has exactly two good protocols")
    comparable = [{k: v for k, v in asdict(g).items() if k not in {"name", "probe_pattern"}}
                  for g in good]
    if comparable[0] != comparable[1]:
        raise ValueError("protocols may differ only in target pattern")
    if config["channels"] != ["none", "vote", "kill", "both"]:
        raise ValueError("v11 channels are fixed")
    if config["primary_family_size"] != 8 or config["alpha"] != 0.05:
        raise ValueError("v11 analysis family is fixed")
    for key in ("n", "seed_start"):
        if type(config["evaluation"][key]) is not int or config["evaluation"][key] < 1:
            raise ValueError("positive integer evaluation settings required")
    mafia = [decisions.MafiaPolicyV11(name=c, signal_channels=c, **config["counter"])
             for c in config["channels"]]
    return rules, good, mafia


def trace_metrics(initial, outcome):
    """Truth labels are used ONLY after play, never provided to a policy."""
    roles = initial.roles
    votes = next(e["payload"] for e in outcome.transcript
                 if e["day"] == 1 and e["event"] == "votes")
    good_votes = [t for p, t in votes.items() if roles[int(p)] != Role.MAFIA]
    counts = Counter(t for t in good_votes if t is not None)
    day_deaths = [e["payload"]["victim"] for e in outcome.transcript
                  if e["day"] == 1 and e["event"] == "day_death"]
    night2 = [e["payload"]["victim"] for e in outcome.transcript
              if e["day"] == 2 and e["event"] == "night_death"]
    # In 4P4M8C neither faction can be eliminated before night 2, even after
    # two police deaths on day 1. Therefore this trace has an unconditional N2.
    if len(night2) != 1:
        raise ValueError("v11 night-two availability invariant violated")
    civilian_msgs = [e["payload"] for e in outcome.transcript
                    if e["day"] == 1 and e["event"] == "message"
                    and e["payload"]["context"] == "day"
                    and e["payload"]["kind"] == "nominate"
                    and roles[e["payload"]["speaker"]] == Role.CIVILIAN]
    return {
        "win": outcome.good_win,
        "day1_good_vote_concentration": max(counts.values(), default=0) / len(good_votes),
        "day1_exile_mafia": int(bool(day_deaths) and roles[day_deaths[0]] == Role.MAFIA),
        "day1_exile_police": int(bool(day_deaths) and roles[day_deaths[0]] == Role.POLICE),
        "day1_no_exile": int(not day_deaths),
        "night2_kill_police": int(roles[night2[0]] == Role.POLICE),
        "day1_civilian_nominations": len(civilian_msgs),
        "day1_civilian_targets": len({m["target"] for m in civilian_msgs}),
    }


def evaluate_cell(job):
    rules, good, mafia, start, n = job
    raw, opening_hashes, speech_hashes, trace_hashes, examples = {}, [], [], [], []
    for seed in range(start, start + n):
        initial = opening(rules, good, mafia, seed, decisions)
        outcome = continue_game(initial, good, mafia, seed, trace=True,
                                decision_api=decisions, public_ballots=True)
        values = trace_metrics(initial, outcome)
        for key, value in values.items():
            raw.setdefault(key, []).append(value)
        opening_hashes.append(sha256(repr(initial).encode()).hexdigest())
        # Daytime-death last words occur after the intervention; exclude them.
        before_vote = []
        for event in outcome.transcript:
            if event["event"] == "votes":
                break
            before_vote.append(event)
        speech_hashes.append(sha256(json.dumps(before_vote, sort_keys=True).encode()).hexdigest())
        trace_hashes.append(sha256(json.dumps(outcome.transcript, sort_keys=True).encode()).hexdigest())
        if seed < start + 2:
            examples.append({"seed": seed, "roles": [r.value for r in initial.roles],
                             "inspection": asdict(initial.investigations[0]),
                             "trace": outcome.transcript})
    return {"good": good.name, "channel": mafia.signal_channels, "seed_start": start,
            "n": n, "raw": raw, "opening_hashes": opening_hashes,
            "day1_prevote_hashes": speech_hashes, "trace_hashes": trace_hashes,
            "examples": examples, "win_summary": win_summary(raw["win"]),
            "means": {k: mean(v) for k, v in raw.items()}}


def contrast_summary(samples, width, family=8, alpha=.05):
    n = len(samples)
    delta = mean(samples)
    se = sqrt(variance(samples) / n) if n > 1 else 0.0
    z = NormalDist().inv_cdf(1 - alpha / (2 * family))
    half = width * sqrt(log(2 * family / alpha) / (2 * n))
    return {"delta": delta, "n": n, "se": se,
            "ci95_pointwise_normal": [delta - 1.959963984540054 * se,
                                       delta + 1.959963984540054 * se],
            "ci95_family_normal_approx": [delta - z * se, delta + z * se],
            "ci95_family_hoeffding": [delta - half, delta + half],
            "range_width": width}


def analyze(cells, config):
    lookup = {(c["good"], c["channel"]): c for c in cells}
    n = config["evaluation"]["n"]
    first = cells[0]["opening_hashes"]
    if any(c["opening_hashes"] != first for c in cells):
        raise ValueError("the eight conditions do not share identical first-night states")
    for good in ("anchor", "diverse"):
        ref = lookup[good, "none"]
        for channel in config["channels"]:
            c = lookup[good, channel]
            if c["day1_prevote_hashes"] != ref["day1_prevote_hashes"]:
                raise ValueError("channel switch changes pre-vote speech")
        # Future night-only intervention cannot change day-one metrics.
        for a, b in (("none", "kill"), ("vote", "both")):
            for key in ref["raw"]:
                if key.startswith("day1_"):
                    if lookup[good,a]["raw"][key] != lookup[good,b]["raw"][key]:
                        raise ValueError("future night channel changed past day-one metric")
    if lookup["anchor", "none"]["raw"]["day1_civilian_nominations"] != lookup["diverse", "none"]["raw"]["day1_civilian_nominations"]:
        raise ValueError("civilian nomination budget differs")
    def linear(terms, metric="win"):
        return [sum(weight * lookup[g,c]["raw"][metric][i] for g,c,weight in terms)
                for i in range(n)]
    terms = {"anchor_minus_diverse_none": [("anchor","none",1),("diverse","none",-1)]}
    for g in ("anchor", "diverse"):
        for c in ("vote", "kill", "both"):
            terms[f"{g}_{c}_minus_none"] = [(g,c,1),(g,"none",-1)]
    terms["interaction_both_minus_none"] = [("anchor","both",1),("anchor","none",-1),
                                            ("diverse","both",-1),("diverse","none",1)]
    primary = {name: {"terms": t, **contrast_summary(linear(t), sum(abs(w) for _,_,w in t))}
               for name,t in terms.items()}
    descriptive = {}
    for channel in config["channels"]:
        t = [("anchor",channel,1),("diverse",channel,-1)]
        descriptive[channel] = {metric: mean(linear(t, metric)) for metric in cells[0]["raw"]}
    return {"primary": primary, "descriptive_anchor_minus_diverse": descriptive,
            "integrity": {"identical_openings_all_8": True, "identical_prevote_within_good": True,
                          "night_channel_preserves_day1": True, "civilian_budget_matched": True},
            "scope": config["scope"],
            "inference": "Eight prespecified win contrasts; Hoeffding simultaneous bounds are conservative. Normal Bonferroni intervals are approximate. Other metrics are descriptive; no mediation or general identity-leakage claim."}


def run_experiment(config, output, workers=4):
    import shutil
    import time
    rules, good, mafia = build_spec(config)
    output = Path(output)
    if output.exists():
        raise ValueError("use a new output directory; no overwrite or rerun in place")
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    sources = list((root / "mafia_lab").glob("*.py")) + [
        root / "scripts/run_mechanism_v11.py", root / "scripts/verify_mechanism_v11.py",
        root / "docs/mechanism_protocol_v11.md"]
    for path in sources:
        target = output / "source" / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    write_json(output / "source/config.json", config)
    source_assets = {str(p.relative_to(output)): digest(p)
                     for p in (output / "source").rglob("*") if p.is_file()}
    freeze = {"version": config["version"], "source_sha256": fingerprint(),
              "source_assets": source_assets, "phase": "frozen_before_evaluation",
              "training_or_selection": False, "evaluation": config["evaluation"],
              "expanded_good": [asdict(p) for p in good], "expanded_mafia": [asdict(p) for p in mafia]}
    write_json(output / "freeze_before_evaluation.json", freeze)
    started = time.monotonic()
    jobs = [(rules,g,m,config["evaluation"]["seed_start"],config["evaluation"]["n"])
            for g in good for m in mafia]
    if workers == 1:
        cells = list(map(evaluate_cell, jobs))
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            cells = list(executor.map(evaluate_cell, jobs))
    if fingerprint() != freeze["source_sha256"]:
        raise RuntimeError("source changed during evaluation")
    write_json(output / "evaluation.json", {"config": config, "cells": cells})
    write_json(output / "analysis.json", analyze(cells, config))
    manifest = {"version": config["version"], "executed_games": sum(c["n"] for c in cells),
                "unique_seed_units": config["evaluation"]["n"], "elapsed_seconds": time.monotonic()-started,
                "files": {name: digest(output/name) for name in
                          ("freeze_before_evaluation.json","evaluation.json","analysis.json")},
                "scope": config["scope"]}
    write_json(output / "manifest.json", manifest)
    return manifest
