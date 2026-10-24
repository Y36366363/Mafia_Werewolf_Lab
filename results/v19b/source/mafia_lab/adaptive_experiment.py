"""v07 training-generated local table and public-ballot experiments."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

from .engine import Role, Rules, observe, speech_order
from .experiments import fingerprint, metadata, save_report
from . import strategies_v07 as decisions
from .simulation import continue_game, opening
from .statistics import paired_summary, win_summary


def build_spec(config):
    rules = Rules(**config["rules"])
    if (rules.police, rules.mafia, rules.civilians) != (4, 4, 8):
        raise ValueError("v07 main experiment must use 4 police, 4 mafia, 8 civilians")
    mafia = tuple(decisions.MafiaPolicyV7(**p) for p in config["mafia_candidates"])
    if len({p.name for p in mafia}) != len(mafia):
        raise ValueError("Duplicate mafia policy names")
    names = {p.name for p in mafia}
    if set(config["table_training"]["opponents"]) - names:
        raise ValueError("Unknown table-training opponent")
    if set(config["initiator_experiment"]["opponents"]) - names:
        raise ValueError("Unknown initiator opponent")
    intervals = []
    for block in (config["table_training"], config["holdout"],
                  config["initiator_experiment"]["openings"]):
        n, start = block["n"], block["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int:
            raise ValueError("Invalid sample block")
        current = start, start + block.get("scan_limit", n)
        if any(max(current[0], a) < min(current[1], b) for a, b in intervals):
            raise ValueError("Seed blocks overlap")
        intervals.append(current)
    return rules, mafia


def _run(jobs, workers, fn):
    if workers == 1:
        return list(map(fn, jobs))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fn, jobs, chunksize=1))


def _table_policy(config, cover, police, name="learned_table"):
    return decisions.GoodPolicyV7(**{**config["table_training"]["policy_base"],
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
                ballots = row["payload"]
                mafia_votes = [target for voter, target in ballots.items()
                               if roles[voter] == Role.MAFIA and target is not None]
                if len(mafia_votes) >= 2:
                    eligible_rounds += 1
                    split_rounds += len(set(mafia_votes)) > 1
    return {"good": good.name, "mafia": mafia.name, "n": n, "seed_start": start,
            "raw_outcomes": outcomes, "summary": win_summary(outcomes),
            "mafia_split_rounds": split_rounds, "mafia_multi_vote_rounds": eligible_rounds,
            "mafia_split_rate": split_rounds / eligible_rounds if eligible_rounds else None}


def train_conditional_table(config, rules, mafia_by_name, workers, progress):
    block = config["table_training"]
    cover = list(block["initial_cover_table"])
    police = list(block["initial_police_table"])
    grid = block["probability_grid"]
    steps = []
    for pass_number in range(1, block["max_passes"] + 1):
        changed = False
        coordinates = [("cover", i) for i in range(6)] + [("police", i) for i in range(3)]
        for kind, index in coordinates:
            jobs, labels = [], []
            for value in grid:
                candidate_cover, candidate_police = list(cover), list(police)
                (candidate_cover if kind == "cover" else candidate_police)[index] = value
                policy = _table_policy(config, candidate_cover, candidate_police,
                                       f"train_p{pass_number}_{kind}{index}_{value}")
                for opponent in block["opponents"]:
                    jobs.append((rules, policy, mafia_by_name[opponent], block["n"],
                                 block["seed_start"], False))
                    labels.append((value, opponent))
            cells = _run(jobs, workers, evaluate_games)
            rates = {value: {} for value in grid}
            for (value, opponent), cell in zip(labels, cells):
                rates[value][opponent] = cell["summary"]["rate"]
            scores = {value: {"worst": min(rates[value].values()),
                              "mean": sum(rates[value].values()) / len(rates[value])}
                      for value in grid}
            current = (cover if kind == "cover" else police)[index]
            chosen = max(grid, key=lambda value: (scores[value]["worst"],
                                                   scores[value]["mean"],
                                                   value == current, -abs(value-current)))
            if chosen != current:
                changed = True
                (cover if kind == "cover" else police)[index] = chosen
            steps.append({"pass": pass_number, "kind": kind, "index": index,
                          "before": current, "chosen": chosen, "scores": scores,
                          "rates": rates, "cells": cells})
            progress(f"table pass {pass_number} {kind}[{index}] -> {chosen}")
        if not changed:
            break
    return {"method": "paired-seed coordinate best response over a frozen probability grid",
            "selection_objective": "maximize worst opponent rate, then mean rate",
            "cover_table": cover, "police_table": police, "steps": steps,
            "seed_block": {"n": block["n"], "seed_start": block["seed_start"]},
            "opponents": block["opponents"], "heldout_unread": True}


def _good_holdout_policies(config, learned):
    base = config["holdout_good_base"]
    return (
        decisions.GoodPolicyV7(name="public_base", cover_mode="public",
                               police_nominate_probability=1, **base),
        decisions.GoodPolicyV7(name="confirm_mix", cover_mode="confirm",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        decisions.GoodPolicyV7(name="position_mix", cover_mode="local",
                               local_public_probability=.75,
                               police_nomination_mode="position",
                               police_nominate_probability=.75,
                               inspect_reasoning_probability=.25, **base),
        _table_policy(config, learned["cover_table"], learned["police_table"]),
    )


def _opening_record(state, seed):
    return {"seed": seed, "roles": [r.value for r in state.roles],
            "death": state.deaths[0].player, "check": state.investigations[0].target,
            "state_sha256": sha256(repr(state).encode()).hexdigest()}


def select_hit_openings(config, rules, good, mafia):
    block = config["initiator_experiment"]["openings"]
    selected = []
    for seed in range(block["seed_start"], block["seed_start"] + block["scan_limit"]):
        state = opening(rules, good, mafia, seed, decision_api=decisions)
        if state.investigations[0].is_mafia:
            selected.append((seed, state))
            if len(selected) == block["n"]:
                return selected
    raise RuntimeError("Hit-opening scan limit exhausted")


def evaluate_initiator(job):
    treatment, rule, openings, good, mafia = job
    outcomes, activated, aligned = [], [], []
    for seed, state in openings:
        first = speech_order(state)[0]
        is_active = rule is not None and state.roles[first] == Role.CIVILIAN
        target = decisions.civilian_rule_target(observe(state, first), rule) if is_active else None
        is_aligned = bool(is_active and target == state.investigations[0].target)
        result = continue_game(state, good, mafia, seed, first_last_words="pass",
                               decision_api=decisions, public_ballots=True)
        outcomes.append(result.good_win)
        activated.append(is_active)
        aligned.append(is_aligned)
    def conditional(mask):
        return win_summary([value for value, keep in zip(outcomes, mask) if keep])
    return {"treatment": treatment, "rule": rule, "mafia": mafia.name,
            "n": len(outcomes), "seeds": [seed for seed, _ in openings],
            "raw_outcomes": outcomes, "summary": win_summary(outcomes),
            "activated": sum(activated), "aligned": sum(aligned),
            "conditional_activated": conditional(activated),
            "conditional_aligned": conditional(aligned)}


def initiator_comparisons(cells):
    lookup = {(c["treatment"], c["mafia"]): c["raw_outcomes"] for c in cells}
    return [{"control": "silent", "treatment": treatment, "mafia": mafia,
             "paired": paired_summary(lookup["silent", mafia], lookup[treatment, mafia])}
            for mafia in sorted({c["mafia"] for c in cells})
            for treatment in sorted({c["treatment"] for c in cells}) if treatment != "silent"]


def run_experiment(config, output, workers=4, progress=print):
    rules, mafia = build_spec(config)
    if workers not in (1, 2, 3, 4):
        raise ValueError("workers must be between 1 and 4")
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
    entry = Path(__file__).resolve().parents[1] / "scripts/run_adaptive_v07.py"
    target = output / "source/scripts/run_adaptive_v07.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry, target)
    by_mafia = {p.name: p for p in mafia}

    learned = train_conditional_table(config, rules, by_mafia, workers, progress)
    save_report(output / "table_selection_before_test.json", learned)
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during training")

    good = _good_holdout_policies(config, learned)
    block = config["holdout"]
    jobs = [(rules, g, m, block["n"], block["seed_start"], True) for g in good for m in mafia]
    cells = _run(jobs, workers, evaluate_games)
    holdout = {**metadata(config), "phase": "holdout", "seed_block": block,
               "public_ballots": True, "frozen_table": {"cover": learned["cover_table"],
                                                          "police": learned["police_table"]},
               "cells": cells,
               "matrix": {"good": [p.name for p in good], "mafia": [p.name for p in mafia],
                          "rates": [[cells[i * len(mafia) + j]["summary"]["rate"]
                                     for j in range(len(mafia))] for i in range(len(good))]}}
    save_report(output / "holdout.json", holdout)
    progress(f"holdout: {len(cells)} cells")

    opening_good = decisions.GoodPolicyV7(**config["initiator_experiment"]["opening_good"])
    opening_mafia = by_mafia[config["initiator_experiment"]["opening_mafia"]]
    openings = select_hit_openings(config, rules, opening_good, opening_mafia)
    jobs = []
    for treatment in config["initiator_experiment"]["treatments"]:
        rule = treatment.get("rule")
        gp = decisions.GoodPolicyV7(**{**config["initiator_experiment"]["continuation_good"],
                                       "name": treatment["name"],
                                       "day1_timing": treatment["timing"],
                                       "civilian_first_rule": rule or "next"})
        for opponent in config["initiator_experiment"]["opponents"]:
            jobs.append((treatment["name"], rule, openings, gp, by_mafia[opponent]))
    initiator_cells = _run(jobs, workers, evaluate_initiator)
    initiator = {**metadata(config), "phase": "initiator", "first_last_words": "pass",
                 "public_ballots": True,
                 "opening_records": [_opening_record(state, seed) for seed, state in openings],
                 "cells": initiator_cells, "paired_vs_silent": initiator_comparisons(initiator_cells)}
    save_report(output / "initiator.json", initiator)
    if fingerprint() != package_hash:
        raise RuntimeError("Package changed during evaluation")

    training_games = sum(cell["n"] for step in learned["steps"] for cell in step["cells"])
    files = ["table_selection_before_test.json", "holdout.json", "initiator.json"]
    manifest = {"version": config["version"], "source_sha256": package_hash,
                "elapsed_seconds": time.monotonic() - started,
                "executed_games": training_games + sum(c["n"] for c in cells)
                                  + sum(c["n"] for c in initiator_cells),
                "training_games": training_games,
                "independent_seed_blocks": {"table_training": config["table_training"],
                                             "holdout": config["holdout"],
                                             "initiator": config["initiator_experiment"]["openings"]},
                "files": {name: sha256((output / name).read_bytes()).hexdigest() for name in files},
                "scope": ("4P4M8C public sequential-ballot strategy evaluation, train-generated "
                          "local probability table, and public-only civilian initiators; not full-game GTO")}
    save_report(output / "manifest.json", manifest)
    return manifest
