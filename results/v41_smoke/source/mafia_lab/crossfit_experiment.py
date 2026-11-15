"""v08 disjoint-fold table training and unconditional public-probe evaluation."""
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
import shutil
import time

from .engine import Role, Rules, observe, speech_order
from .experiments import fingerprint, metadata, save_report
from . import strategies_v08 as decisions
from .simulation import continue_game, opening
from .statistics import paired_summary, win_summary


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v08 main experiment must use 4 police, 4 mafia, 8 civilians")
    mafia = tuple(decisions.MafiaPolicyV8(**p) for p in config["mafia_candidates"])
    if len({p.name for p in mafia}) != len(mafia):
        raise ValueError("Duplicate mafia policy")
    names = {p.name for p in mafia}
    for group in (config["table_crossfit"]["opponents"], config["probe_selection"]["opponents"]):
        if set(group) - names:
            raise ValueError("Unknown opponent")
    intervals = []
    blocks = [config["table_crossfit"]["fit"], config["table_crossfit"]["validate"],
              config["matrix_holdout"], config["probe_selection"]["fit_openings"],
              config["probe_selection"]["validate_openings"],
              config["probe_selection"]["holdout_openings"]]
    for block in blocks:
        n, start = block["n"], block["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int:
            raise ValueError("Invalid sample block")
        end = start + block.get("scan_limit", n * 18)
        if any(max(start, a) < min(end, b) for a, b in intervals):
            raise ValueError("Potential seed intervals overlap")
        intervals.append((start, end))
    return rules, mafia


def _run(jobs, workers, fn):
    if workers == 1:
        return list(map(fn, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fn, jobs, chunksize=1))


def _table_policy(config, cover, police, name="crossfit_table"):
    return decisions.GoodPolicyV8(**{**config["table_crossfit"]["policy_base"],
                                     "name": name, "cover_mode": "table",
                                     "police_nomination_mode": "table",
                                     "conditional_cover_table": tuple(cover),
                                     "conditional_police_table": tuple(police)})


def evaluate_games(job):
    rules, good, mafia, n, start, trace = job
    outcomes, split_rounds, eligible_rounds = [], 0, 0
    for seed in range(start, start + n):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        roles = state.roles
        result = continue_game(state, good, mafia, seed, decision_api=decisions,
                               public_ballots=True, trace=trace)
        outcomes.append(result.good_win)
        if trace:
            for row in result.transcript:
                if row["event"] not in {"votes", "pk_votes"}:
                    continue
                votes = [target for voter, target in row["payload"].items()
                         if roles[voter] == Role.MAFIA and target is not None]
                if len(votes) >= 2:
                    eligible_rounds += 1
                    split_rounds += len(set(votes)) > 1
    return {"good": good.name, "mafia": mafia.name, "n": n, "seed_start": start,
            "raw_outcomes": outcomes, "summary": win_summary(outcomes),
            "mafia_split_rounds": split_rounds, "mafia_multi_vote_rounds": eligible_rounds,
            "mafia_split_rate": split_rounds / eligible_rounds if eligible_rounds else None}


def _scores(cells, grid, opponents):
    rates = {value: {} for value in grid}
    for value in grid:
        for opponent in opponents:
            cell = next(c for c in cells if c["candidate_value"] == value and c["mafia"] == opponent)
            rates[value][opponent] = cell["summary"]["rate"]
    scores = {value: {"worst": min(rates[value].values()),
                      "mean": sum(rates[value].values()) / len(opponents)} for value in grid}
    return rates, scores


def crossfit_table(config, rules, mafia_by_name, workers, progress):
    spec = config["table_crossfit"]
    cover, police = list(spec["initial_cover_table"]), list(spec["initial_police_table"])
    grid, opponents = spec["probability_grid"], spec["opponents"]
    steps, global_step = [], 0
    for pass_number in range(1, spec["max_passes"] + 1):
        accepted_in_pass = 0
        for kind, index in [("cover", i) for i in range(6)] + [("police", i) for i in range(3)]:
            fit_start = spec["fit"]["seed_start"] + global_step * spec["fit"]["n"]
            validate_start = spec["validate"]["seed_start"] + global_step * spec["validate"]["n"]
            current = (cover if kind == "cover" else police)[index]
            jobs, labels = [], []
            for value in grid:
                cv, pv = list(cover), list(police)
                (cv if kind == "cover" else pv)[index] = value
                gp = _table_policy(config, cv, pv, f"fit_p{pass_number}_{kind}{index}_{value}")
                for opponent in opponents:
                    jobs.append((rules, gp, mafia_by_name[opponent], spec["fit"]["n"], fit_start, False))
                    labels.append((value, opponent))
            fit_cells = _run(jobs, workers, evaluate_games)
            for cell, (value, _) in zip(fit_cells, labels):
                cell["candidate_value"] = value
            fit_rates, fit_scores = _scores(fit_cells, grid, opponents)
            proposed = max(grid, key=lambda value: (fit_scores[value]["worst"],
                                                     fit_scores[value]["mean"],
                                                     value == current, -abs(value-current)))
            validate_values = [current] if proposed == current else [current, proposed]
            jobs, labels = [], []
            for value in validate_values:
                cv, pv = list(cover), list(police)
                (cv if kind == "cover" else pv)[index] = value
                gp = _table_policy(config, cv, pv, f"validate_p{pass_number}_{kind}{index}_{value}")
                for opponent in opponents:
                    jobs.append((rules, gp, mafia_by_name[opponent], spec["validate"]["n"],
                                 validate_start, False))
                    labels.append((value, opponent))
            validate_cells = _run(jobs, workers, evaluate_games)
            for cell, (value, _) in zip(validate_cells, labels):
                cell["candidate_value"] = value
            validate_rates, validate_scores = _scores(validate_cells, validate_values, opponents)
            accepted = False
            if proposed != current:
                old, new = validate_scores[current], validate_scores[proposed]
                accepted = (new["worst"] >= old["worst"] + spec["accept_worst_gain"] and
                            new["mean"] >= old["mean"] - spec["mean_noninferiority"])
            chosen = proposed if accepted else current
            if accepted:
                (cover if kind == "cover" else police)[index] = chosen
                accepted_in_pass += 1
            steps.append({"step": global_step, "pass": pass_number, "kind": kind, "index": index,
                          "before": current, "fit_seed_start": fit_start,
                          "validate_seed_start": validate_start, "proposed": proposed,
                          "accepted": accepted, "chosen": chosen,
                          "fit_rates": fit_rates, "fit_scores": fit_scores,
                          "validate_rates": validate_rates, "validate_scores": validate_scores,
                          "fit_cells": fit_cells, "validate_cells": validate_cells})
            progress(f"crossfit {global_step + 1}: {kind}[{index}] {current} -> {proposed} "
                     f"{'accepted' if accepted else 'rejected'}")
            global_step += 1
        if accepted_in_pass == 0:
            break
    return {"method": "disjoint coordinate fit blocks with independent per-coordinate validation",
            "acceptance": {"worst_gain": spec["accept_worst_gain"],
                           "mean_noninferiority": spec["mean_noninferiority"]},
            "cover_table": cover, "police_table": police, "steps": steps,
            "opponents": opponents, "heldout_unread": True}


def _holdout_good(config, learned):
    base = config["holdout_good_base"]
    return (
        decisions.GoodPolicyV8(name="public_base", cover_mode="public",
                               police_nominate_probability=1, **base),
        decisions.GoodPolicyV8(name="confirm_mix", cover_mode="confirm",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        decisions.GoodPolicyV8(name="position_mix", cover_mode="local",
                               local_public_probability=.75, police_nomination_mode="position",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        _table_policy(config, learned["cover_table"], learned["police_table"]),
    )


def select_hit_openings(rules, good, mafia, block):
    selected = []
    for seed in range(block["seed_start"], block["seed_start"] + block["scan_limit"]):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        if state.investigations[0].is_mafia:
            selected.append((seed, state))
            if len(selected) == block["n"]:
                return selected
    raise RuntimeError("Hit-opening scan exhausted")


def _probe_policy(config, candidate):
    base = config["probe_selection"]["continuation_good"]
    return decisions.GoodPolicyV8(**{**base, "name": candidate["name"],
                                     "day1_timing": candidate["timing"],
                                     "probe_window": candidate.get("window", 1),
                                     "probe_pattern": tuple(candidate.get("pattern", ["next"]))})


def evaluate_probe(job):
    candidate, openings, good, mafia = job
    outcomes, active_mask, aligned_mask, probe_counts = [], [], [], []
    for seed, state in openings:
        order = speech_order(state)
        targets = []
        if candidate["timing"] == "civilian_first":
            for rank, player in enumerate(order[:good.probe_window]):
                if state.roles[player] == Role.CIVILIAN:
                    rule = good.probe_pattern[rank % len(good.probe_pattern)]
                    targets.append(decisions.public_probe_target(observe(state, player), rule))
        active = bool(targets)
        aligned = state.investigations[0].target in targets
        result = continue_game(state, good, mafia, seed, first_last_words="pass",
                               decision_api=decisions, public_ballots=True)
        outcomes.append(result.good_win)
        active_mask.append(active)
        aligned_mask.append(aligned)
        probe_counts.append(len(targets))
    return {"candidate": candidate["name"], "mafia": mafia.name, "n": len(outcomes),
            "seeds": [seed for seed, _ in openings], "raw_outcomes": outcomes,
            "summary": win_summary(outcomes), "activated": sum(active_mask),
            "aligned": sum(aligned_mask), "total_probes": sum(probe_counts),
            "activation_rate": sum(active_mask) / len(outcomes),
            "alignment_rate": sum(aligned_mask) / len(outcomes),
            "mean_probes": sum(probe_counts) / len(outcomes)}


def _probe_cells(candidates, openings, config, mafia_by_name, workers):
    jobs = [({**candidate}, openings, _probe_policy(config, candidate), mafia_by_name[opponent])
            for candidate in candidates for opponent in config["probe_selection"]["opponents"]]
    return _run(jobs, workers, evaluate_probe)


def _candidate_scores(cells, names, opponents):
    lookup = {(c["candidate"], c["mafia"]): c for c in cells}
    return {name: {"worst": min(lookup[name, m]["summary"]["rate"] for m in opponents),
                   "mean": sum(lookup[name, m]["summary"]["rate"] for m in opponents) / len(opponents)}
            for name in names}


def train_probe(config, rules, mafia_by_name, workers, progress):
    spec = config["probe_selection"]
    opening_good = decisions.GoodPolicyV8(**spec["opening_good"])
    opening_mafia = mafia_by_name[spec["opening_mafia"]]
    fit_openings = select_hit_openings(rules, opening_good, opening_mafia, spec["fit_openings"])
    candidates = spec["candidates"]
    fit_cells = _probe_cells(candidates, fit_openings, config, mafia_by_name, workers)
    civilian_names = [c["name"] for c in candidates if c["timing"] == "civilian_first"]
    fit_scores = _candidate_scores(fit_cells, civilian_names, spec["opponents"])
    proposed = max(civilian_names, key=lambda n: (fit_scores[n]["worst"], fit_scores[n]["mean"], n))
    validate_openings = select_hit_openings(rules, opening_good, opening_mafia,
                                            spec["validate_openings"])
    validation_candidates = [next(c for c in candidates if c["name"] == "silent"),
                             next(c for c in candidates if c["name"] == proposed)]
    validate_cells = _probe_cells(validation_candidates, validate_openings, config,
                                  mafia_by_name, workers)
    validate_scores = _candidate_scores(validate_cells, ["silent", proposed], spec["opponents"])
    accepted = (validate_scores[proposed]["worst"] >= validate_scores["silent"]["worst"] +
                spec["accept_worst_gain"] and
                validate_scores[proposed]["mean"] >= validate_scores["silent"]["mean"])
    selected = proposed if accepted else "silent"
    progress(f"probe {proposed} {'accepted' if accepted else 'rejected'}; selected {selected}")
    return {"objective": "unconditional complete-game win rate over all hit openings",
            "fit_scores": fit_scores, "proposed": proposed,
            "validate_scores": validate_scores, "accepted": accepted, "selected": selected,
            "fit_cells": fit_cells, "validate_cells": validate_cells,
            "fit_opening_records": [_opening_record(s, seed) for seed, s in fit_openings],
            "validate_opening_records": [_opening_record(s, seed) for seed, s in validate_openings],
            "holdout_unread": True}


def _opening_record(state, seed):
    return {"seed": seed, "death": state.deaths[0].player,
            "check": state.investigations[0].target,
            "state_sha256": sha256(repr(state).encode()).hexdigest()}


def run_experiment(config, output, workers=4, progress=print):
    rules, mafia = build_spec(config)
    output = Path(output)
    if (output / "manifest.json").exists():
        raise ValueError("Completed result directory exists")
    output.mkdir(parents=True, exist_ok=True)
    package_hash, started = fingerprint(), time.monotonic()
    for src in Path(__file__).parent.glob("*.py"):
        target = output / "source/mafia_lab" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    save_report(output / "source/config.json", config)
    entry = Path(__file__).resolve().parents[1] / "scripts/run_crossfit_v08.py"
    target = output / "source/scripts/run_crossfit_v08.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry, target)
    by_mafia = {p.name: p for p in mafia}

    learned = crossfit_table(config, rules, by_mafia, workers, progress)
    save_report(output / "table_selection_before_holdout.json", learned)
    probe_selection = train_probe(config, rules, by_mafia, workers, progress)
    save_report(output / "probe_selection_before_holdout.json", probe_selection)
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during selection")

    block = config["matrix_holdout"]
    good = _holdout_good(config, learned)
    jobs = [(rules, g, m, block["n"], block["seed_start"], True) for g in good for m in mafia]
    matrix_cells = _run(jobs, workers, evaluate_games)
    matrix = {**metadata(config), "phase": "matrix_holdout", "seed_block": block,
              "cells": matrix_cells,
              "matrix": {"good": [g.name for g in good], "mafia": [m.name for m in mafia],
                         "rates": [[matrix_cells[i*len(mafia)+j]["summary"]["rate"]
                                    for j in range(len(mafia))] for i in range(len(good))]}}
    save_report(output / "matrix_holdout.json", matrix)
    progress(f"matrix holdout: {len(matrix_cells)} cells")

    probe_spec = config["probe_selection"]
    opening_good = decisions.GoodPolicyV8(**probe_spec["opening_good"])
    opening_mafia = by_mafia[probe_spec["opening_mafia"]]
    openings = select_hit_openings(rules, opening_good, opening_mafia,
                                   probe_spec["holdout_openings"])
    probe_cells = _probe_cells(probe_spec["candidates"], openings, config, by_mafia, workers)
    lookup = {(c["candidate"], c["mafia"]): c for c in probe_cells}
    comparisons = [{"control": "silent", "treatment": name, "mafia": opponent,
                    "paired": paired_summary(lookup["silent", opponent]["raw_outcomes"],
                                              lookup[name, opponent]["raw_outcomes"])}
                   for opponent in probe_spec["opponents"]
                   for name in [c["name"] for c in probe_spec["candidates"] if c["name"] != "silent"]]
    probe_holdout = {**metadata(config), "phase": "probe_holdout",
                     "selected_before_holdout": probe_selection["selected"],
                     "opening_records": [_opening_record(s, seed) for seed, s in openings],
                     "cells": probe_cells, "paired_vs_silent": comparisons}
    save_report(output / "probe_holdout.json", probe_holdout)
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during holdout")

    table_training_games = sum(c["n"] for s in learned["steps"]
                               for c in s["fit_cells"] + s["validate_cells"])
    probe_training_games = sum(c["n"] for c in probe_selection["fit_cells"] +
                               probe_selection["validate_cells"])
    files = ["table_selection_before_holdout.json", "probe_selection_before_holdout.json",
             "matrix_holdout.json", "probe_holdout.json"]
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": table_training_games + probe_training_games +
                                  sum(c["n"] for c in matrix_cells + probe_cells),
                "table_training_games": table_training_games,
                "probe_training_games": probe_training_games,
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": ("4P4M8C deterministic shared mafia target, disjoint-fold conditional-table "
                          "selection and unconditional public-probe evaluation; not full-game GTO")}
    save_report(output / "manifest.json", manifest)
    return manifest
