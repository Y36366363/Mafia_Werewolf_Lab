"""Cross-check archived pairs and summarize warning and timing coverage."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json

from run_report_timing_v46 import ROOT, digest, load_spec, save_json, summarize
from mafia_lab.engine import Role
from mafia_lab.hit_candidates_v37 import explain
from mafia_lab.paired_source_routing_v40 import current_calls
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.report_timing_v46 import ReportTimingAPI, common_hit
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_evidence_pilot_v42 import AMBIGUOUS


def read_gzip(path):
    with gzip.open(path, 'rt') as handle:
        return json.load(handle)


class DistinctAudit(ReportTimingAPI):
    """Read only the same civilian prefix after producing the actual ballot."""

    def vote(self, obs, policy, rng, candidates=None):
        actual = super().vote(obs, policy, rng, candidates)
        if obs.role != Role.CIVILIAN or obs.day < 2 or candidates is not None:
            return actual
        info = explain(obs, policy, retain=True)
        if info['known_bad'] or info['reason'] not in AMBIGUOUS or common_hit(obs, info) is not None:
            return actual
        calls = current_calls(obs)
        sources = info['proposal_sources']
        if (len(sources)!=2 or any(calls.get(s) not in info['proposals'][str(s)] for s in sources)
                or calls[sources[0]] == calls[sources[1]]):
            return actual
        reports = {m.speaker:m for m in obs.messages if m.day == obs.day and m.context == 'day'
                   and m.kind == 'report' and m.speaker in sources}
        past = [m for m in obs.messages if m.day < obs.day]
        returning = all(any(m.speaker == s and m.context == 'day' and m.kind in {'police','report'}
                            for m in past) for s in sources)
        old_targets = {m.target for m in past if m.kind == 'report'}
        fresh = [m for m in reports.values() if m.target not in old_targets]
        category = 'returning' if returning else 'not_both_returning'
        self.scope[category+'_fresh_'+str(len(fresh))] += 1
        if self.example is None and returning and len(fresh) == 2:
            self.example = dict(day=obs.day, reports=[(m.speaker,m.target,m.verdict) for m in fresh],
                                calls={s:calls[s] for s in sources})
        return actual


def distinct_batch(job):
    spec, q, rows = job
    rules, good, (_,mafia,cooperation,relay) = spec
    counts = Counter()
    first = None
    for row in rows:
        seed = row['seed']
        api = DistinctAudit(cooperation,relay,q,False,'distinct',False)
        api.scope = Counter()
        api.example = None
        state = opening(rules,good,mafia,seed,api)
        result = continue_game(state,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
        assert hash_events(result.transcript) == row['trace'] and result.good_win == row['win']
        counts.update(api.scope)
        if first is None and api.example is not None:
            first = dict(seed=seed, **api.example)
    return counts, first


def main():
    path = ROOT/'results/v46'
    manifest = json.loads((path/'manifest.json').read_text())
    freeze = json.loads((path/'freeze.json').read_text())
    cfg = freeze['config']
    assert all(digest(path/name)==value for name,value in manifest['files'].items())
    assert all(digest(ROOT/rel)==digest(path/'source'/rel)==h for rel,h in freeze['assets'].items())
    assert all(digest(ROOT/rel)==h for rel,h in freeze['parents'].items())
    arms = read_gzip(path/'pairs.json.gz')
    for rows in arms.values():
        for row in rows:
            row['exiles'] = {int(day):seat for day,seat in row['exiles'].items()}
            row['exile_roles'] = {int(day):role for day,role in row['exile_roles'].items()}
    assert json.loads(json.dumps(summarize(arms,cfg['comparisons']))) == json.loads((path/'summary.json').read_text())
    start = cfg['holdout']['seed_start']
    assert all([r['seed'] for r in rows]==list(range(start,start+cfg['holdout']['n'])) for rows in arms.values())
    cases = read_gzip(path/'cases.json.gz')
    reference = ROOT/'results/v44/pairs.json.gz'
    assert digest(reference) == freeze['reference_sha256']
    old = {row['seed']:row for row in read_gzip(reference)['copy_both']}
    historical = {}
    for seed, pair in cases['historical'].items():
        a,b = pair['greedy'],pair['lookahead']
        assert a['trace']==old[int(seed)]['trace']
        historical[seed] = dict(warnings=b['warnings'], day2=[a['exiles'].get('2'),b['exiles'].get('2')],
                                 day3=[a['exile_roles'].get('3'),b['exile_roles'].get('3')],
                                 wins=[a['win'],b['win']])
    assert sorted(map(int,historical)) == sorted(cfg['reference_seeds'])
    warned = [(a,b) for a,b in zip(arms['greedy'],arms['lookahead'],strict=True) if a['warnings']]
    warning_outcomes = dict(n=len(warned),
        changed_day2_exiles=sum(a['exiles'].get(2)!=b['exiles'].get(2) for a,b in warned),
        day2_mafia=[sum(pair[i]['exile_roles'].get(2)=='mafia' for pair in warned) for i in (0,1)],
        day3_succession=[sum(pair[i]['day3_succession'] for pair in warned) for i in (0,1)],
        day3_mafia=[sum(pair[i]['exile_roles'].get(3)=='mafia' for pair in warned) for i in (0,1)],
        wins=[sum(pair[i]['win'] for pair in warned) for i in (0,1)])
    coverage = {}
    for name,rows in arms.items():
        events = sum((Counter(row['counts']) for row in rows),Counter())
        cover = {key:sum(bool(row['counts'].get(key)) for row in rows) for key in events
                 if key.startswith(('report_','eligible_','changed_'))}
        coverage[name] = cover
    fresh = {name:{arm:dict(seed=row['seed'],win=row['win'],exiles=row['exiles'],
                           exile_roles=row['exile_roles']) for arm,row in entries.items()}
             for name,entries in cases['fresh'].items()}
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    spec = load_spec(parent)
    distinct = arms['distinct_control']
    scope = Counter()
    example = None
    batches = [(spec,freeze['q'],distinct[i:i+256]) for i in range(0,len(distinct),256)]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for counts, candidate in pool.map(distinct_batch,batches):
            scope.update(counts)
            if example is None and candidate is not None:
                example = candidate
    summary = dict(raw_and_intervals_verified=True, historical=historical,
                   warned_pairs=warning_outcomes, game_coverage=coverage, fresh_cases=fresh,
                   distinct_read_only_replays=len(distinct), distinct_ballot_scope=scope,
                   distinct_returning_example=example)
    save_json(path/'analysis.json', summary)
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
