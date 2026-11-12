"""v09 outer replication and natural-opening probe counter experiment."""
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
import shutil
import time

from .engine import Role, Rules, observe, speech_order
from .experiments import fingerprint, metadata, save_report
from .simulation import continue_game, opening
from .statistics import paired_summary, win_summary
from . import strategies_v09 as decisions


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v09 main experiment must use 4 police, 4 mafia, 8 civilians")
    mafia = tuple(decisions.MafiaPolicyV9(**p) for p in config["mafia_candidates"])
    if len({p.name for p in mafia}) != len(mafia):
        raise ValueError("duplicate mafia policy")
    names = {p.name for p in mafia}
    if set(config["probe_selection"]["opponents"]) - names:
        raise ValueError("unknown probe opponent")
    blocks = list(config["replication"]["blocks"]) + list(config["probe_selection"]["fit_folds"])
    blocks += [config["probe_selection"]["validate"], config["probe_selection"]["holdout"]]
    intervals = []
    for block in blocks:
        n, start = block["n"], block["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int:
            raise ValueError("invalid seed block")
        interval = (start, start + n)
        if any(max(interval[0], a) < min(interval[1], b) for a, b in intervals):
            raise ValueError("seed blocks overlap")
        intervals.append(interval)
    return rules, mafia


def _run(jobs, workers, fn):
    if workers == 1:
        return list(map(fn, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fn, jobs, chunksize=1))


def _good_policies(config):
    base = config["good_base"]
    learned = config["frozen_v08_table"]
    return (
        decisions.GoodPolicyV9(name="public_base", cover_mode="public",
                               police_nominate_probability=1, **base),
        decisions.GoodPolicyV9(name="confirm_mix", cover_mode="confirm",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        decisions.GoodPolicyV9(name="position_mix", cover_mode="local",
                               local_public_probability=.75, police_nomination_mode="position",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        decisions.GoodPolicyV9(name="crossfit_table", cover_mode="table",
                               police_nomination_mode="table",
                               conditional_cover_table=tuple(learned["cover"]),
                               conditional_police_table=tuple(learned["police"]),
                               inspect_reasoning_probability=.25, **base),
    )


def evaluate_game_cell(job):
    block_name, rules, good, mafia, n, start = job
    outcomes, split, eligible = [], 0, 0
    for seed in range(start, start + n):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        roles = state.roles
        result = continue_game(state, good, mafia, seed, decision_api=decisions,
                               public_ballots=True, trace=True)
        outcomes.append(result.good_win)
        for row in result.transcript:
            if row["event"] not in {"votes", "pk_votes"}:
                continue
            votes = [target for voter, target in row["payload"].items()
                     if roles[voter] == Role.MAFIA and target is not None]
            if len(votes) >= 2:
                eligible += 1
                split += len(set(votes)) > 1
    return {"block": block_name, "good": good.name, "mafia": mafia.name,
            "n": n, "seed_start": start, "raw_outcomes": outcomes,
            "summary": win_summary(outcomes), "mafia_split_rounds": split,
            "mafia_multi_vote_rounds": eligible,
            "mafia_split_rate": split / eligible if eligible else None}


def _probe_policy(config, candidate):
    return decisions.GoodPolicyV9(**{**config["probe_selection"]["continuation_good"],
                                     "name": candidate["name"],
                                     "day1_timing": candidate["timing"],
                                     "probe_window": candidate.get("window", 1),
                                     "probe_pattern": tuple(candidate.get("pattern", ["next"]))})


def evaluate_probe_cell(job):
    phase, fold, rules, candidate, good, mafia, n, start = job
    outcomes, active, aligned, probe_counts, unique_counts = [], [], [], [], []
    strata = {}
    for seed in range(start, start + n):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        targets = []
        if candidate["timing"] == "civilian_first":
            order = speech_order(state)
            for rank, player in enumerate(order[:good.probe_window]):
                if state.roles[player] == Role.CIVILIAN:
                    rule = good.probe_pattern[rank % len(good.probe_pattern)]
                    targets.append(decisions.public_probe_target(observe(state, player), rule))
        hit = state.investigations[0].is_mafia
        is_aligned = hit and state.investigations[0].target in targets
        result = continue_game(state, good, mafia, seed, first_last_words="pass",
                               decision_api=decisions, public_ballots=True)
        outcomes.append(result.good_win)
        active.append(bool(targets))
        aligned.append(is_aligned)
        probe_counts.append(len(targets))
        unique_counts.append(len(set(targets)))
        victim = state.roles[state.deaths[0].player].value
        for key in (f"check_{'hit' if hit else 'clear'}", f"death_{victim}",
                    f"{'hit' if hit else 'clear'}_death_{victim}"):
            strata.setdefault(key, []).append(result.good_win)
    return {"phase": phase, "fold": fold, "candidate": candidate["name"],
            "mafia": mafia.name, "n": n, "seed_start": start,
            "raw_outcomes": outcomes, "summary": win_summary(outcomes),
            "activated": sum(active), "aligned": sum(aligned),
            "total_probes": sum(probe_counts), "total_unique_targets": sum(unique_counts),
            "activation_rate": sum(active) / n, "alignment_rate": sum(aligned) / n,
            "mean_probes": sum(probe_counts) / n,
            "mean_unique_targets": sum(unique_counts) / n,
            "strata": {key: win_summary(values) for key, values in sorted(strata.items())}}


def _probe_jobs(phase, fold, block, rules, candidates, opponents, config, by_mafia):
    return [(phase, fold, rules, candidate, _probe_policy(config, candidate),
             by_mafia[opponent], block["n"], block["seed_start"])
            for candidate in candidates for opponent in opponents]


def _scores(cells, candidates, opponents):
    names = [c["name"] for c in candidates]
    lookup = {(c["candidate"], c["mafia"]): c for c in cells}
    return {name: {"worst": min(lookup[name, m]["summary"]["rate"] for m in opponents),
                   "mean": sum(lookup[name, m]["summary"]["rate"] for m in opponents) /
                           len(opponents)} for name in names}


def select_probe(config, rules, by_mafia, workers, progress):
    spec = config["probe_selection"]
    candidates, opponents = spec["candidates"], spec["opponents"]
    fit_cells, fold_scores = [], []
    for fold, block in enumerate(spec["fit_folds"]):
        cells = _run(_probe_jobs("fit", fold, block, rules, candidates, opponents,
                                config, by_mafia), workers, evaluate_probe_cell)
        fit_cells.extend(cells)
        fold_scores.append(_scores(cells, candidates, opponents))
        progress(f"probe fit fold {fold + 1}/{len(spec['fit_folds'])}")
    probe_names = [c["name"] for c in candidates if c["timing"] == "civilian_first"]
    stability = {name: {"min_fold_worst": min(s[name]["worst"] for s in fold_scores),
                        "mean_fold_worst": sum(s[name]["worst"] for s in fold_scores) /
                                           len(fold_scores),
                        "mean": sum(s[name]["mean"] for s in fold_scores) / len(fold_scores)}
                 for name in probe_names}
    proposed = max(probe_names, key=lambda name: (stability[name]["min_fold_worst"],
                                                   stability[name]["mean_fold_worst"],
                                                   stability[name]["mean"], name))
    controls = [next(c for c in candidates if c["name"] == name)
                for name in ("silent", "early")]
    proposed_spec = next(c for c in candidates if c["name"] == proposed)
    validation_candidates = controls + [proposed_spec]
    block = spec["validate"]
    validate_cells = _run(_probe_jobs("validate", None, block, rules, validation_candidates,
                                     opponents, config, by_mafia), workers, evaluate_probe_cell)
    validate_scores = _scores(validate_cells, validation_candidates, opponents)
    comparator = max(("silent", "early"),
                     key=lambda name: (validate_scores[name]["worst"], validate_scores[name]["mean"]))
    old, new = validate_scores[comparator], validate_scores[proposed]
    accepted = (new["worst"] >= old["worst"] + spec["accept_worst_gain"] and
                new["mean"] >= old["mean"] - spec["mean_noninferiority"])
    selected = proposed if accepted else comparator
    progress(f"probe {proposed} vs {comparator}: {'accepted' if accepted else 'rejected'}")
    return {"objective": "natural-opening min-fold worst-opponent root win rate",
            "fold_scores": fold_scores, "stability_scores": stability,
            "proposed": proposed, "validation_comparator": comparator,
            "validate_scores": validate_scores, "accepted": accepted,
            "selected": selected, "fit_cells": fit_cells,
            "validate_cells": validate_cells, "holdout_unread": True}


def run_experiment(config, output, workers=4, progress=print):
    rules, mafia = build_spec(config)
    output = Path(output)
    if (output / "manifest.json").exists():
        raise ValueError("completed result directory exists")
    output.mkdir(parents=True, exist_ok=True)
    package_hash, started = fingerprint(), time.monotonic()
    for src in Path(__file__).parent.glob("*.py"):
        target = output / "source/mafia_lab" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    save_report(output / "source/config.json", config)
    entry = Path(__file__).resolve().parents[1] / "scripts/run_replication_v09.py"
    target = output / "source/scripts/run_replication_v09.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry, target)
    by_mafia = {p.name: p for p in mafia}

    good = _good_policies(config)
    jobs = [(block["name"], rules, g, m, block["n"], block["seed_start"])
            for block in config["replication"]["blocks"] for g in good for m in mafia]
    replication_cells = _run(jobs, workers, evaluate_game_cell)
    replication = {**metadata(config), "phase": "outer_replication",
                   "blocks": config["replication"]["blocks"],
                   "cells": replication_cells,
                   "matrix": {"good": [g.name for g in good],
                              "mafia": [m.name for m in mafia]}}
    save_report(output / "replication.json", replication)
    progress(f"outer replication: {len(replication_cells)} cells")

    selection = select_probe(config, rules, by_mafia, workers, progress)
    save_report(output / "probe_selection_before_holdout.json", selection)
    if fingerprint() != package_hash:
        raise RuntimeError("package changed during selection")

    spec = config["probe_selection"]
    holdout_cells = _run(_probe_jobs("holdout", None, spec["holdout"], rules,
                                    spec["candidates"], spec["opponents"], config,
                                    by_mafia), workers, evaluate_probe_cell)
    lookup = {(c["candidate"], c["mafia"]): c for c in holdout_cells}
    pairs = [{"control": control, "treatment": treatment, "mafia": opponent,
              "paired": paired_summary(lookup[control, opponent]["raw_outcomes"],
                                        lookup[treatment, opponent]["raw_outcomes"])}
             for opponent in spec["opponents"]
             for control in ("silent", "early")
             for treatment in [c["name"] for c in spec["candidates"]
                               if c["name"] not in {"silent", "early"}]]
    holdout = {**metadata(config), "phase": "natural_opening_probe_holdout",
               "selected_before_holdout": selection["selected"],
               "seed_block": spec["holdout"], "cells": holdout_cells,
               "paired_comparisons": pairs}
    save_report(output / "probe_holdout.json", holdout)
    if fingerprint() != package_hash:
        raise RuntimeError("package changed during holdout")

    files = ["replication.json", "probe_selection_before_holdout.json", "probe_holdout.json"]
    replication_games = sum(c["n"] for c in replication_cells)
    probe_training_games = sum(c["n"] for c in selection["fit_cells"] + selection["validate_cells"])
    probe_holdout_games = sum(c["n"] for c in holdout_cells)
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": replication_games + probe_training_games + probe_holdout_games,
                "replication_games": replication_games,
                "probe_training_games": probe_training_games,
                "probe_holdout_games": probe_holdout_games,
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": ("4P4M8C multi-block outer replication and natural-opening public-probe "
                          "evaluation against public echo counters; not full-game GTO")}
    save_report(output / "manifest.json", manifest)
    return manifest
