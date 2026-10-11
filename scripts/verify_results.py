"""Verify frozen artifacts and recompute reported statistics from raw outcomes.

No game is replayed. This checks provenance and reporting consistency; the
separate unit/cross-model tests check the actual game and solver semantics.
"""
from hashlib import sha256
import json
from math import isclose, log, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {"hashes": 0, "win_summaries": 0, "paired_summaries": 0, "raw_games": 0}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(a, b):
    require(isclose(a, b, abs_tol=1e-12), f"numeric mismatch: {a} != {b}")


def digest(data, expected):
    require(sha256(data).hexdigest() == expected, "SHA256 mismatch")
    CHECKS["hashes"] += 1


def source_digest(path, expected):
    content = b"".join(p.name.encode()+b"\0"+p.read_bytes()+b"\0"
                       for p in sorted(path.glob("*.py")))
    digest(content, expected)


def read(path):
    return json.loads(path.read_text())


def validate_wins(raw, summary):
    require(all(type(x) is int and x in (0,1) for x in raw), "nonbinary outcome")
    n = len(raw)
    require(n == summary["n"] and sum(raw) == summary["wins"], "denominator/wins mismatch")
    CHECKS["win_summaries"] += 1
    if not n:
        require(summary["rate"] is None, "empty-sample rate must be null")
        return
    p, z = sum(raw)/n, 1.959963984540054
    equal(p, summary["rate"])
    den = 1+z*z/n
    midpoint = (p+z*z/(2*n))/den
    radius = z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    for a,b in zip([max(0,midpoint-radius),min(1,midpoint+radius)], summary["ci95_wilson"]):
        equal(a,b)


def validate_pair(a, b, summary):
    require(len(a) == len(b) == summary["n"], "paired denominator mismatch")
    d = [y-x for x,y in zip(a,b)]
    n = len(d)
    CHECKS["paired_summaries"] += 1
    if not n:
        require(summary["delta"] is None, "empty-sample delta must be null")
        return
    mu = sum(d)/n
    equal(mu, summary["delta"])
    for key,val in [("improved",1),("worsened",-1),("unchanged",0)]:
        require(summary[key] == d.count(val), "discordant count mismatch")
    if n > 1:
        radius = 1.959963984540054*sqrt(sum((x-mu)**2 for x in d)/(n*(n-1)))
        for a,b in zip([max(-1,mu-radius), min(1,mu+radius)], summary["ci95_normal"]):
            equal(a,b)
    radius = sqrt(2*log(40)/n)
    for a,b in zip([max(-1,mu-radius), min(1,mu+radius)], summary["ci95_hoeffding"]):
        equal(a,b)


def audit_suite(version):
    directory = ROOT/"results"/version
    manifest = read(directory/"manifest.json")
    source_digest(directory/"source/mafia_lab", manifest["source_sha256"])
    require(read(directory/f"source/configs/experiment_{version}.json") == manifest["config"],
            "archived config differs from manifest")
    for name, expected in manifest["files"].items():
        path = directory/name
        digest(path.read_bytes(), expected)
        result = read(path)
        if "source_sha256" in result:
            require(result["source_sha256"] == manifest["source_sha256"], "mixed source generations")
            digest(json.dumps(result["config"], sort_keys=True).encode(), result["config_sha256"])
    for row in read(directory/"small_games.json")["configurations"]:
        validate_wins(row["raw_outcomes"], row["summary"])
        CHECKS["raw_games"] += len(row["raw_outcomes"])
    for row in read(directory/"first_day_branches.json")["comparisons"]:
        a,b = [v[1] for v in row["raw_seed_control_treatment"]], [v[2] for v in row["raw_seed_control_treatment"]]
        validate_wins(a,row["control_summary"])
        validate_wins(b,row["treatment_summary"])
        validate_pair(a,b,row["paired"])
        CHECKS["raw_games"] += len(a)+len(b)
    pool = read(directory/"strategy_pool.json")
    train, test = pool["raw_train_outcomes"], pool["raw_test_outcomes"]
    for i,row in enumerate(test):
        for j,values in enumerate(row):
            validate_wins(values,pool["test_summaries"][i][j])
            equal(sum(train[i][j])/len(train[i][j]),pool["train_win_rates"][i][j])
            CHECKS["raw_games"] += len(values)+len(train[i][j])
    selection = pool["selection_from_train"]
    good = [p["name"] for p in pool["config"]["good_pool"]]
    mafia = [p["name"] for p in pool["config"]["mafia_pool"]]
    rates = pool["train_win_rates"]
    j = min(range(len(mafia)),key=lambda x:rates[0][x])
    i = max(range(len(good)),key=lambda x:rates[x][j])
    robust = max(range(len(good)),key=lambda x:min(rates[x]))
    require((selection["mafia_response"],selection["good_response"],selection["robust_pure_good"])
            == (mafia[j],good[i],good[robust]),"response selection not reproduced from training data")
    pairs=pool["heldout_comparisons"]
    validate_pair(test[0][0],test[0][j],pairs["mafia_response_effect_on_good_win"])
    validate_pair(test[0][j],test[i][j],pairs["good_response_effect"])
    validate_pair(test[0][j],test[robust][j],pairs["robust_good_vs_response"])
    mechanism = read(directory/"mechanisms.json")
    base = mechanism["variants"][0]["raw_outcomes"]
    for row in mechanism["variants"]:
        validate_wins(row["raw_outcomes"],row["summary"])
        validate_pair(base,row["raw_outcomes"],row["paired_vs_baseline"])
        CHECKS["raw_games"] += len(row["raw_outcomes"])


def main():
    for version in ("v01","v02"):
        audit_suite(version)
    followup = read(ROOT/"results/mechanism_followup_v01.json")
    source_digest(ROOT/"results/v01/source/mafia_lab",followup["source_sha256"])
    digest((ROOT/"results/v01/source/scripts/run_mechanism_followup.py").read_bytes(),followup["script_sha256"])
    digest(json.dumps(followup["config"],sort_keys=True).encode(),followup["config_sha256"])
    for row in followup["cells"]:
        validate_wins(row["raw_outcomes"],row["summary"])
        CHECKS["raw_games"] += len(row["raw_outcomes"])
    signal=read(ROOT/"results/signal_counter_v03.json")
    source_digest(ROOT/"results/v03_source/mafia_lab",signal["source_sha256"])
    digest((ROOT/"results/v03_source/scripts/run_signal_counter.py").read_bytes(),signal["script_sha256"])
    digest((ROOT/"results/v03_source/configs/signal_counter_v03.json").read_bytes(),signal["config_file_sha256"])
    digest(json.dumps(signal["config"],sort_keys=True).encode(),signal["config_sha256"])
    cells={}
    for row in signal["cells"]:
        key=(row["good_policy"],row["mafia_policy"])
        cells[key]=row["raw_outcomes"]
        validate_wins(row["raw_outcomes"],row["summary"])
        CHECKS["raw_games"] += len(row["raw_outcomes"])
    for row in signal["paired_contrasts"]:
        validate_pair(cells[row["good_policy"],row["control"]],
                      cells[row["good_policy"],row["treatment"]],row["paired"])
    matrix=signal["matrix"]
    for i,g in enumerate(matrix["row_good_policies"]):
        for j,m in enumerate(matrix["column_mafia_policies"]):
            equal(sum(cells[g,m])/len(cells[g,m]),matrix["good_win_rates"][i][j])
    result={"status":"passed","checks":CHECKS,
            "scope":"artifact/source integrity, reported raw-game denominators, selected responses and statistics; not a new equilibrium or replay certificate",
            "independent_units":"Seeds shared across arms; raw_games counts terminal executions, not independent observations"}
    (ROOT/"results/final_integrity_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
