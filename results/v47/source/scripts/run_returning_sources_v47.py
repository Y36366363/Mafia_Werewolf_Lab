"""Frozen paired holdout for the two-returning-claimants scenario."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import platform
import shutil
import time

import scipy
from scipy.stats import binomtest

from run_continuation_audit_v45 import verify_parent
from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.returning_sources_v47 import ReturningSourcesAPI, original_pair
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval

CONFIG = ROOT/'configs/returning_sources_v47.json'
CONTRASTS = [('unlinked_new','unlinked_consistent'), ('prepared_new','prepared_consistent')]


class EndOfScreen(Exception):
    pass


class Screen(ReturningSourcesAPI):
    def choose_kill(self, obs, policy, rng):
        if obs.day == 1:
            self.pair = original_pair(obs)
            raise EndOfScreen
        return super().choose_kill(obs,policy,rng)


def screen(spec, q, seed):
    rules, good, (_,mafia,cooperation,relay) = spec
    api = Screen(cooperation,relay,q,None,'novelty')
    start = opening(rules,good,mafia,seed,api)
    try:
        continue_game(start,good,mafia,seed,decision_api=api,public_ballots=True)
    except EndOfScreen:
        return api.pair
    return ()


def play(spec, q, setup, seed, pair, details=False):
    rules, good, (_,mafia,cooperation,relay) = spec
    api = ReturningSourcesAPI(cooperation,relay,q,*setup)
    start = opening(rules,good,mafia,seed,api)
    result = continue_game(start,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    assert api.pair == pair and sorted(roles[s] for s in pair) == ['mafia','police']
    assert api.night_adjustment['victim'] not in pair
    reports = [e['payload'] for e in events if e['day']==2 and e['event']=='message'
               and e['payload']['kind']=='report' and e['payload']['context']=='day']
    assert sorted(m['speaker'] for m in reports) == list(pair)
    assert api.bluff_plan is not None
    prefix = []
    for event in events:
        if event['day']==2 and event['event']=='votes' or event['day']>2:
            break
        prefix.append(event)
    calls = {e['payload']['speaker']:e['payload']['target'] for e in prefix if e['day']==2
             and e['payload'].get('kind')=='accuse' and e['payload']['speaker'] in pair}
    actual = next(e['payload'] for e in events if e['day']==2 and e['event']=='votes')
    counts = Counter()
    for row in api.comparisons:
        assert actual[row['player']]==row['target']
        counts['qualified'] += 1
        counts['fresh_'+str(len(row['fresh']))] += 1
        for key in ('novel','preferred','source'):
            source = row[key]
            if source is not None:
                counts[key+'_'+roles[source]] += 1
        if row['source'] is not None and row['target'] != row['baseline']:
            counts['changed_from_inherited_'+roles[row['source']]] += 1
        for source,flags in row['flags'].items():
            counts.update('flag_'+roles[source]+'_'+flag for flag in flags)
    for source,target in calls.items():
        kind = roles[source]
        counts['call_'+kind] += 1
        counts['own_vote_matches_'+kind] += actual[source]==target
        for voter,vote in actual.items():
            if roles[voter]=='civilian' and voter!=target:
                counts['civil_opportunity_'+kind] += 1
                counts['civil_follow_'+kind] += vote==target
    exile = next((e['payload']['victim'] for e in events if e['day']==2 and e['event']=='day_death'),None)
    row = dict(seed=seed,pair=list(pair),win=result.good_win,trace=hash_events(events),
               opening=hash_events((start.roles,start.deaths,start.investigations)),
               day1=hash_events(e for e in events if e['day']==1),prefix2=hash_events(prefix),
               night=api.night_adjustment,exile=exile,exile_role=roles[exile] if exile is not None else 'none',
               counts=dict(counts),votes=actual,same_report_target=len({m['target'] for m in reports})==1)
    if details:
        row.update(events=events,roles=roles,comparisons=api.comparisons,plan=api.bluff_plan,
                   final=dict(nights=result.nights,deaths=result.deaths))
    return row


def batch(job):
    spec, q, cfg, seeds = job
    selected = []
    for seed in seeds:
        pair = screen(spec,q,seed)
        if pair:
            rows = {arm:play(spec,q,setup,seed,pair) for arm,setup in cfg['arms'].items()}
            selected.append(rows)
    return selected


def summarize(pairs):
    assert pairs
    for group in pairs:
        assert len({(r['seed'],tuple(r['pair']),r['opening'],r['day1'],r['night']['victim']) for r in group.values()}) == 1
    summary = dict(n=len(pairs),arms={},contrasts={})
    for arm in pairs[0]:
        rows = [group[arm] for group in pairs]
        summary['arms'][arm] = dict(wins=sum(r['win'] for r in rows),
            adjusted_nights=sum(r['night']['victim']!=r['night']['original'] for r in rows),
            same_report_target=sum(r['same_report_target'] for r in rows),
            exiles=Counter(r['exile_role'] for r in rows),
            counts=sum((Counter(r['counts']) for r in rows),Counter()))
    for a,b in CONTRASTS:
        left,right = zip(*((r[a],r[b]) for r in pairs))
        assert all(x['prefix2']==y['prefix2'] for x,y in zip(left,right,strict=True))
        first,second = [r['win'] for r in left],[r['win'] for r in right]
        gains = sum(x<y for x,y in zip(first,second,strict=True))
        losses = sum(x>y for x,y in zip(first,second,strict=True))
        result = exact_paired_interval(first,second,len(CONTRASTS))
        for k,name in ((gains,'p_plus'),(losses,'p_minus')):
            other = binomtest(k,len(first)).proportion_ci(1-2*result['tail_alpha'],method='exact')
            assert all(abs(x-y)<1e-10 for x,y in zip(other,result[name]))
        summary['contrasts'][a+'_to_'+b] = dict(gains=gains,losses=losses,precision=result,
            changed_games=sum(x['votes']!=y['votes'] for x,y in zip(left,right,strict=True)),
            changed_ballots=sum(sum(x['votes'][p]!=y['votes'][p] for p in x['votes']) for x,y in zip(left,right,strict=True)),
            changed_exiles=sum(x['exile']!=y['exile'] for x,y in zip(left,right,strict=True)),
            changed_same_loss=sum(x['trace']!=y['trace'] and not x['win'] and not y['win']
                                  for x,y in zip(left,right,strict=True)))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    spec = load_spec(parent)
    parents = verify_parent(cfg['parent_freeze'])
    out = ROOT/('results/v47_smoke' if args.smoke else 'results/v47')
    out.mkdir()
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'mafia_lab/returning_sources_v47.py',
             ROOT/'docs/returning_sources_protocol_v47.md',ROOT/'tests/test_returning_sources_v47.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for rel in hashes:
        dest = out/'source'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest)
    save_json(out/'freeze.json',dict(config=cfg,parents=parents,assets=hashes,q=parent['q'],
                                    python=platform.python_version(),scipy=scipy.__version__))
    run = cfg['smoke' if args.smoke else 'holdout']
    seeds = range(run['seed_start'],run['seed_start']+run['n'])
    start = time.monotonic()
    jobs = [(spec,parent['q'],cfg,seeds[i:i+256]) for i in range(0,len(seeds),256)]
    pairs = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i,rows in enumerate(pool.map(batch,jobs),1):
            pairs.extend(rows)
            if i%4==0:
                print('screened',min(i*256,len(seeds)),'qualified',len(pairs),flush=True)
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in hashes.items())
    summary = summarize(pairs)
    cases = {}
    if not args.smoke:
        selections = {'first':pairs[0],'middle':pairs[len(pairs)//2],'last':pairs[-1]}
        for a,b in CONTRASTS:
            for label,test in [('vote',lambda x,y:x['votes']!=y['votes']),
                               ('gain',lambda x,y:x['win']<y['win']),('loss',lambda x,y:x['win']>y['win'])]:
                selected = next((r for r in pairs if test(r[a],r[b])),None)
                if selected is not None:
                    selections[a+'_'+label] = selected
        for label,selected in selections.items():
            cases[label] = {}
            for arm,row in selected.items():
                rich = play(spec,parent['q'],cfg['arms'][arm],row['seed'],tuple(row['pair']),True)
                assert all(rich[k]==v for k,v in row.items())
                cases[label][arm] = rich
    save_gzip(out/'pairs.json.gz',pairs)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(screened=len(seeds),qualified=len(pairs),games=len(pairs)*len(cfg['arms']),
        replay_executions=sum(map(len,cases.values())),elapsed=time.monotonic()-start,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print('qualified',len(pairs),'wins',{a:r['wins'] for a,r in summary['arms'].items()})


if __name__ == '__main__':
    main()
