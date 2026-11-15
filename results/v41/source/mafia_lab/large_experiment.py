"""v04: predominantly 16-player evaluation with prospective local mixtures.

All strategies randomize locally from legal observations. No hidden index is
shared across civilians and police. Selection uses only a separate train block.
"""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

from .engine import Rules
from .experiments import fingerprint, metadata, save_report
from . import strategies_v04 as decisions
from .simulation import play
from .statistics import paired_summary, win_summary


def build_spec(config):
    rules = Rules(**config["rules"])
    good = tuple(decisions.GoodPolicyV4(**p) for p in config["good_policies"])
    mafia = tuple(decisions.MafiaPolicyV4(**p) for p in config["mafia_policies"])
    if not good or not mafia:
        raise ValueError("Empty policy pool")
    for group in (good, mafia):
        if len({p.name for p in group}) != len(group):
            raise ValueError("Duplicate policy name")
    intervals=[]
    for key in ("train", "test", "sensitivity"):
        n, start = config[key]["n"], config[key]["seed_start"]
        if type(n) is not int or n < 2 or type(start) is not int or start < 0:
            raise ValueError("Need at least two independent seeds per block")
        interval=(start,start+n)
        if any(max(start,a)<min(start+n,b) for a,b in intervals):
            raise ValueError("Seed block overlap")
        intervals.append(interval)
    for contrast in config["good_contrasts"]:
        if contrast["control"] not in {p.name for p in good} or contrast["treatment"] not in {p.name for p in good}:
            raise ValueError("Unknown good contrast")
    for contrast in config["mafia_contrasts"]:
        if contrast["control"] not in {p.name for p in mafia} or contrast["treatment"] not in {p.name for p in mafia}:
            raise ValueError("Unknown mafia contrast")
    return rules, good, mafia


def select_from_train(rates, good_names, mafia_names, baseline_good=None):
    if len(rates) != len(good_names) or any(len(r) != len(mafia_names) for r in rates):
        raise ValueError("Matrix shape mismatch")
    if any(not 0 <= v <= 1 for r in rates for v in r):
        raise ValueError("Invalid win rate")
    if baseline_good is None:
        baseline_good = "uncovered" if "uncovered" in good_names else min(good_names)
    base = good_names.index(baseline_good)
    worst = min(range(len(mafia_names)),key=lambda j:(rates[base][j],mafia_names[j]))
    response = min(range(len(good_names)),key=lambda i:(-rates[i][worst],good_names[i]))
    second = min(range(len(mafia_names)),key=lambda j:(rates[response][j],mafia_names[j]))
    robust = min(range(len(good_names)),key=lambda i:(-min(rates[i]),good_names[i]))
    robust_worst = min(range(len(mafia_names)),key=lambda j:(rates[robust][j],mafia_names[j]))
    return {"baseline_good":baseline_good,"mafia_response":mafia_names[worst],
            "good_response":good_names[response],"second_mafia_response":mafia_names[second],
            "robust_pure_good":good_names[robust],"robust_train_worst_mafia":mafia_names[robust_worst],
            "tie_break":"lexicographic policy name, after objective"}


def evaluate_cell(job):
    rules, good, mafia, n, start = job
    wins, nights = [], []
    for seed in range(start,start+n):
        outcome=play(rules,good,mafia,seed,decision_api=decisions)
        if outcome.good_win not in (0,1) or not 1 <= outcome.nights < rules.n_players:
            raise RuntimeError("Terminal invariant failed")
        wins.append(outcome.good_win)
        nights.append(outcome.nights)
    return {"good":good.name,"mafia":mafia.name,"rules":asdict(rules),
            "seed_start":start,"n":n,"raw_outcomes":wins,"raw_nights":nights,
            "summary":win_summary(wins)}


def run_cells(jobs,workers,progress):
    if workers == 1:
        for job in jobs:
            yield evaluate_cell(job)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for result in executor.map(evaluate_cell,jobs,chunksize=1):
                yield result


def all_contrasts(cells,config):
    raw={(c["good"],c["mafia"]):c["raw_outcomes"] for c in cells}
    ng=len(config["good_contrasts"])*len(config["mafia_policies"])
    nm=len(config["mafia_contrasts"])*len(config["good_policies"])
    rows=[]
    for kind, own, other in [("good",config["good_contrasts"],config["mafia_policies"]),
                             ("mafia",config["mafia_contrasts"],config["good_policies"])]:
        for comparison in own:
            for p in other:
                a,b=comparison["control"],comparison["treatment"]
                x,y=(raw[a,p["name"]],raw[b,p["name"]]) if kind=="good" else (raw[p["name"],a],raw[p["name"],b])
                stats=paired_summary(x,y)
                # Family-wise bounded interval, conservatively valid even if
                # contrasts share the same seed blocks or correlated arms.
                from math import log, sqrt
                radius=sqrt(2*log(2*(ng+nm)/0.05)/len(x))
                stats["ci95_familywise_hoeffding"]=[max(-1,stats["delta"]-radius),min(1,stats["delta"]+radius)]
                rows.append({"side":kind,"control":a,"treatment":b,"fixed_opponent":p["name"],
                             "paired":stats})
    return rows


def run_experiment(config,output,workers=2,progress=print):
    rules,good,mafia=build_spec(config)
    if workers not in (1,2,3,4):
        raise ValueError("workers must be between 1 and 4")
    output=Path(output)
    if (output/"manifest.json").exists():
        raise ValueError("Completed result directory exists; use a new output path")
    output.mkdir(parents=True,exist_ok=True)
    package_hash=fingerprint()
    for src in Path(__file__).parent.glob("*.py"):
        target=output/"source/mafia_lab"/src.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,target)
    save_report(output/"source/config.json",config)
    entrypoint=Path(__file__).resolve().parents[1]/"scripts/run_large_game_v04.py"
    source_assets={"source/config.json":sha256((output/"source/config.json").read_bytes()).hexdigest()}
    if entrypoint.exists():
        target=output/"source/scripts/run_large_game_v04.py"
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(entrypoint,target)
        source_assets[str(target.relative_to(output))]=sha256(target.read_bytes()).hexdigest()
    started=time.monotonic()
    base=metadata(config)
    base["intervals"]="Pointwise Wilson and paired normal/Hoeffding; additional familywise 95% Hoeffding for prespecified test contrasts only."
    names_g,names_m=[p.name for p in good],[p.name for p in mafia]
    results={}
    for phase in ("train","test"):
        block=config[phase]
        jobs=[(rules,g,m,block["n"],block["seed_start"]) for g in good for m in mafia]
        cells=[]
        for cell in run_cells(jobs,workers,progress):
            cells.append(cell)
            if len(cells)%len(mafia)==0:
                progress(f"{phase}: {len(cells)}/{len(jobs)} policy cells complete")
        report={**base,"phase":phase,"cells":cells,
                "seed_block":block,"matrix":{"good":names_g,"mafia":names_m,
                   "rates":[[cells[i*len(mafia)+j]["summary"]["rate"] for j in range(len(mafia))]
                            for i in range(len(good))]}}
        if phase=="train":
            selection=select_from_train(report["matrix"]["rates"],names_g,names_m)
            report["selection"]=selection
            # Write the selected policies before computing a single test game.
            save_report(output/"selection_before_test.json",{**base,"selection":selection,
                        "chosen_from":"train only; test not yet run"})
        else:
            report["selection_from_train"]=selection
            report["all_prespecified_contrasts"]=all_contrasts(cells,config)
            raw={(c["good"],c["mafia"]):c["raw_outcomes"] for c in cells}
            comparisons=[("respond_to_mafia",selection["baseline_good"],selection["mafia_response"],selection["good_response"],selection["mafia_response"]),
                         ("mafia_counter_response",selection["good_response"],selection["mafia_response"],selection["good_response"],selection["second_mafia_response"]),
                         ("robust_at_train_worst",selection["baseline_good"],selection["robust_train_worst_mafia"],selection["robust_pure_good"],selection["robust_train_worst_mafia"])]
            report["selected_heldout_comparisons"]=[{"name":label,"control":[ga,ma],"treatment":[gb,mb],
                    "paired":paired_summary(raw[ga,ma],raw[gb,mb])} for label,ga,ma,gb,mb in comparisons]
        if fingerprint()!=package_hash:
            raise RuntimeError("Package changed during evaluation")
        save_report(output/f"{phase}.json",report)
        results[phase]=report
    # Configuration, policy identities and sample sizes all selected before
    # held-out data. No test winner is used to choose sensitivity policies.
    chosen_good=sorted({selection["baseline_good"],selection["robust_pure_good"]})
    chosen_mafia=sorted({"signal_mimic",selection["robust_train_worst_mafia"]})
    by_g,by_m={p.name:p for p in good},{p.name:p for p in mafia}
    block=config["sensitivity"]
    jobs=[(Rules(**r["rules"]),by_g[g],by_m[m],block["n"],block["seed_start"])
          for r in block["rule_variants"] for g in chosen_good for m in chosen_mafia]
    cells=list(run_cells(jobs,workers,progress))
    report={**base,"phase":"sensitivity","seed_block":block,"cells":cells,
            "selection_from_train":selection,"chosen_good":chosen_good,"chosen_mafia":chosen_mafia}
    if fingerprint()!=package_hash:
        raise RuntimeError("Package changed during sensitivity evaluation")
    save_report(output/"sensitivity.json",report)
    files=["train.json","test.json","sensitivity.json","selection_before_test.json"]
    manifest={"version":config["version"],"source_sha256":package_hash,
              "source_assets":source_assets,
              "config":config,"elapsed_seconds":time.monotonic()-started,
              "executed_games":sum(c["n"] for r in results.values() for c in r["cells"])+sum(c["n"] for c in cells),
              "independent_seed_blocks":{k:config[k] for k in ("train","test","sensitivity")},
              "files":{name:sha256((output/name).read_bytes()).hexdigest() for name in files},
              "scope":"Frozen local behavioral mixtures and finite heuristic pool responses; not GTO or exact best response"}
    save_report(output/"manifest.json",manifest)
    return manifest
