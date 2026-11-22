"""Freeze and run two paired interventions in each fixed opponent condition."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import platform
import shutil
import time

import scipy
from scipy.stats import binomtest

from run_continuation_audit_v45 import verify_parent
from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from run_returning_sources_v47 import play as play_v47, screen
from mafia_lab.novelty_ablation_v48 import NoveltyAblationAPI
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


CONFIG = ROOT/'configs/novelty_ablation_v48.json'
CONTRASTS = (('novelty','neutral'), ('neutral','challenge'))


def play(spec, q, opponent, receiver, seed, pair, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = NoveltyAblationAPI(cooperation,relay,q,opponent,receiver)
    start = opening(rules,good,mafia,seed,api)
    result = continue_game(start,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    assert api.pair == pair and sorted(roles[p] for p in pair) == ['mafia','police']
    assert api.night_adjustment['victim'] not in pair
    reports = [e['payload']['speaker'] for e in events if e['day']==2 and e['event']=='message'
               and e['payload']['kind']=='report' and e['payload']['context']=='day']
    assert sorted(reports) == list(pair)
    vote_index = next(i for i,e in enumerate(events) if e['day']==2 and e['event']=='votes')
    votes = events[vote_index]['payload']
    exits = {e['day']:e['payload']['victim'] for e in events if e['event']=='day_death'}
    counts = Counter()
    for row in api.comparisons:
        assert votes[row['player']]==row['target']
        counts['eligible'] += 1
        counts['fresh_'+str(len(row['fresh']))] += 1
        if row['novel'] is not None:
            counts['novel_'+roles[row['novel']]] += 1
            counts['novel_would_change'] += row['novelty_target'] != row['baseline']
        if row['supported'] is not None:
            counts['supported_'+roles[row['supported']]] += 1
            nom = row['calls'][row['supported']]
            if nom != row['baseline']:
                counts['challenge_would_change_'+roles[row['supported']]] += 1
        positive = sum(bool(x) for x in row['challenges'].values())
        counts['num_challenged_'+str(positive)] += 1
    calls = {e['payload']['speaker']:e['payload']['target'] for e in events[:vote_index]
             if e['day']==2 and e['payload'].get('kind')=='accuse' and e['payload']['speaker'] in pair}
    for source,target in calls.items():
        role = roles[source]
        counts['source_vote_matches_'+role] += votes[source]==target
        for player, vote in votes.items():
            if roles[player]=='civilian' and player!=target:
                counts['civil_opportunities_'+role] += 1
                counts['civil_follows_'+role] += vote==target
    exile = exits.get(2)
    row = dict(seed=seed,pair=list(pair),win=result.good_win,trace=hash_events(events),
        opening=hash_events((start.roles,start.deaths,start.investigations)),
        day1=hash_events(e for e in events if e['day']==1),prefix2=hash_events(events[:vote_index]),
        night=api.night_adjustment,votes=votes,d2_exile=exile,
        d2_role=roles[exile] if exile is not None else 'none',counts=dict(counts))
    if details:
        row.update(events=events,roles=roles,comparisons=api.comparisons,plan=api.bluff_plan,
                   exit_roles={d:roles[p] for d,p in exits.items()}, exits=exits)
    return row


def batch(job):
    spec, q, config, seeds = job
    pairs = []
    for seed in seeds:
        pair = screen(spec,q,seed)
        if pair:
            pairs.append({opp:{r:play(spec,q,opp,r,seed,pair) for r in config['receivers']}
                          for opp in config['opponents']})
    return pairs


def summarize(pairs, cfg):
    out = dict(n=len(pairs),opponents={})
    assert pairs
    for group in pairs:
        rows = [r for arm in group.values() for r in arm.values()]
        assert len({(r['seed'],tuple(r['pair']),r['opening'],r['day1'],r['night']['victim']) for r in rows})==1
        for arm in group.values():
            assert len({r['prefix2'] for r in arm.values()})==1
            assert len({r['counts'].get('eligible',0) for r in arm.values()})==1
    for opp in cfg['opponents']:
        arms, comparisons = {}, {}
        for receiver in cfg['receivers']:
            rows = [p[opp][receiver] for p in pairs]
            arms[receiver] = dict(wins=sum(r['win'] for r in rows),
                adjusted_nights=sum(r['night']['victim']!=r['night']['original'] for r in rows),
                exiles=Counter(r['d2_role'] for r in rows), counts=sum((Counter(r['counts']) for r in rows),Counter()))
        for a,b in CONTRASTS:
            selected = [(p[opp][a],p[opp][b]) for p in pairs]
            before,after = zip(*((x['win'],y['win']) for x,y in selected))
            gains = sum(x<y for x,y in zip(before,after,strict=True))
            losses = sum(x>y for x,y in zip(before,after,strict=True))
            precision = exact_paired_interval(before,after,len(CONTRASTS)*len(cfg['opponents']))
            for count, key in ((gains,'p_plus'),(losses,'p_minus')):
                ci = binomtest(count,len(selected)).proportion_ci(1-2*precision['tail_alpha'],method='exact')
                assert all(abs(x-y)<1e-10 for x,y in zip(ci,precision[key]))
            assert all(x['votes']!=y['votes'] or x['trace']==y['trace'] for x,y in selected)
            comparisons[a+'_to_'+b] = dict(gains=gains,losses=losses,precision=precision,
                changed_games=sum(x['votes']!=y['votes'] for x,y in selected),
                changed_ballots=sum(sum(v!=y['votes'][p] for p,v in x['votes'].items()) for x,y in selected),
                changed_exiles=sum(x['d2_exile']!=y['d2_exile'] for x,y in selected),
                same_loss_changed=sum(not x['win'] and not y['win'] and x['trace']!=y['trace'] for x,y in selected),
                day2_transitions=Counter(x['d2_role']+'→'+y['d2_role'] for x,y in selected))
        out['opponents'][opp] = dict(arms=arms,comparisons=comparisons)
    return out


def replay_cases(spec,q,cfg,pairs):
    cases = {}
    checks = 0
    for opp in cfg['opponents']:
        for group in (pairs[0],pairs[len(pairs)//2],pairs[-1]):
            for receiver,row in group[opp].items():
                reproduced = play(spec,q,opp,receiver,row['seed'],tuple(row['pair']))
                assert row==reproduced
                checks += 1
            v = group[opp]['novelty']
            old = play_v47(spec,q,(opp,'novelty'),v['seed'],tuple(v['pair']))
            assert old['trace']==v['trace'] and old['win']==v['win']
        for a,b in CONTRASTS:
            selected = [(p[opp][a],p[opp][b]) for p in pairs]
            for label,predicate in [('vote',lambda x,y:x['votes']!=y['votes']),
                                    ('gain',lambda x,y:x['win']<y['win']),
                                    ('loss',lambda x,y:x['win']>y['win'])]:
                found = next(((x,y) for x,y in selected if predicate(x,y)),None)
                if found is None:
                    continue
                cases[opp+'_'+a+'_'+b+'_'+label] = {}
                for r,v in zip((a,b),found,strict=True):
                    rich = play(spec,q,opp,r,v['seed'],tuple(v['pair']),True)
                    assert all(rich[key]==value for key,value in v.items())
                    cases[opp+'_'+a+'_'+b+'_'+label][r] = rich
    return cases,checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    spec, q = load_spec(parent), parent['q']
    parents = verify_parent(cfg['parent_freeze'])
    out = ROOT/('results/v48_smoke' if args.smoke else 'results/v48')
    out.mkdir()
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'mafia_lab/novelty_ablation_v48.py',
             ROOT/'docs/novelty_ablation_protocol_v48.md',ROOT/'tests/test_novelty_ablation_v48.py']
    assets = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for rel in assets:
        dest = out/'source'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest)
    save_json(out/'freeze.json',dict(config=cfg,parents=parents,assets=assets,q=q,
                                    python=platform.python_version(),scipy=scipy.__version__))
    run = cfg['smoke' if args.smoke else 'holdout']
    seeds = range(run['seed_start'],run['seed_start']+run['n'])
    start = time.monotonic()
    jobs = [(spec,q,cfg,seeds[i:i+256]) for i in range(0,len(seeds),256)]
    pairs = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i,rows in enumerate(pool.map(batch,jobs),1):
            pairs.extend(rows)
            if i%4==0:
                print('screened',min(i*256,len(seeds)),'qualified',len(pairs),flush=True)
    summary = summarize(pairs,cfg)
    cases, checks = ({},0) if args.smoke else replay_cases(spec,q,cfg,pairs)
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in assets.items())
    save_gzip(out/'pairs.json.gz',pairs)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(screened=len(seeds),qualified=len(pairs),
        games=len(pairs)*len(cfg['opponents'])*len(cfg['receivers']),sample_replays=checks,
        v47_compatibility_checks=0 if args.smoke else 3*len(cfg['opponents']),
        case_replays=sum(map(len,cases.values())),elapsed=time.monotonic()-start,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print('qualified',len(pairs),'wins',{o:{r:v['wins'] for r,v in obs['arms'].items()}
                                          for o,obs in summary['opponents'].items()})


if __name__=='__main__':
    main()
