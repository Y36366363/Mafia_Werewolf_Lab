"""Compare two returning-source receivers and one alternative mafia call."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import shutil
import time

import scipy
from scipy.stats import binomtest

from run_continuation_audit_v45 import verify_parent
from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from run_novelty_ablation_v48 import play as play_v48
from run_returning_sources_v47 import EndOfScreen, screen
from mafia_lab.adaptive_counter_v49 import AdaptiveCounterAPI
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.returning_sources_v47 import original_pair
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


CONFIG = ROOT/'configs/adaptive_counter_v49.json'
CONTRASTS = (('original_neutral','original_evidence'), ('counter_neutral','counter_evidence'),
             ('counter_neutral','counter_backed'))


class CounterScreen(AdaptiveCounterAPI):
    def choose_kill(self, obs, policy, rng):
        if obs.day == 1:
            self.pair = original_pair(obs)
            raise EndOfScreen
        return super().choose_kill(obs,policy,rng)


def with_counter_screen(spec, q, seed):
    rules, good, (_,mafia,cooperation,relay) = spec
    api = CounterScreen(cooperation,relay,q,True,'neutral',False)
    start = opening(rules,good,mafia,seed,api)
    try:
        continue_game(start,good,mafia,seed,decision_api=api,public_ballots=True)
    except EndOfScreen:
        pass
    return api.pair, len(api.counter_ballots), sum(r['source']!=r['baseline'] for r in api.counter_ballots)


def play(spec, q, setup, seed, pair, details=False):
    rules, good, (_,mafia,cooperation,relay) = spec
    api = AdaptiveCounterAPI(cooperation,relay,q,*setup)
    start = opening(rules,good,mafia,seed,api)
    result = continue_game(start,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    assert api.pair==pair and sorted(roles[p] for p in pair)==['mafia','police']
    assert api.night_adjustment['victim'] not in pair
    reports = [e['payload']['speaker'] for e in events if e['day']==2 and e['event']=='message'
               and e['payload']['kind']=='report' and e['payload']['context']=='day']
    assert sorted(reports)==list(pair)
    first_vote = next(e['payload'] for e in events if e['day']==1 and e['event']=='votes')
    assert all(first_vote[r['voter']]==r['source'] and r in api.counter_speeches
               for r in (dict(voter=b['voter'],source=b['source']) for b in api.counter_ballots))
    vote_index = next(i for i,e in enumerate(events) if e['day']==2 and e['event']=='votes')
    votes = events[vote_index]['payload']
    exiles = {e['day']:e['payload']['victim'] for e in events if e['event']=='day_death'}
    counts = Counter()
    for row in api.comparisons:
        assert votes[row['player']]==row['target']
        counts['eligible'] += 1
        if row['supported'] is not None:
            side = roles[row['supported']]
            counts['supports_'+side] += 1
            counts['changes_'+side] += row['target']!=row['baseline']
        counts['challenged_'+str(sum(bool(x) for x in row['challenges'].values()))] += 1
    call = api.bluff_plan['call']
    assert all(vote==call for p,vote in votes.items() if roles[p]=='mafia')
    counts['civil_votes_for_bluff_call'] = sum(vote==call for p,vote in votes.items() if roles[p]=='civilian')
    counts['counter_nomination'] = len(api.counter_speeches)
    counts['counter_ballot'] = len(api.counter_ballots)
    counts['counter_ballot_changed'] = sum(r['source']!=r['baseline'] for r in api.counter_ballots)
    exile = exiles.get(2)
    row = dict(seed=seed,pair=list(pair),win=result.good_win,trace=hash_events(events),
        opening=hash_events((start.roles,start.deaths,start.investigations)),
        day1=hash_events(e for e in events if e['day']==1),prefix2=hash_events(events[:vote_index]),
        night=api.night_adjustment,votes=votes,d2_exile=exile,d2_role=roles[exile] if exile is not None else 'none',
        counts=dict(counts),alternative=api.alternative,bluff_plan=api.bluff_plan)
    if details:
        row.update(events=events,roles=roles,comparisons=api.comparisons,counters=api.counter_ballots,
                   exiles=exiles,exile_roles={d:roles[p] for d,p in exiles.items()})
    return row


def batch(job):
    spec,q,cfg,seeds = job
    pairs,flow = [], []
    for seed in seeds:
        baseline = screen(spec,q,seed)
        revised,turns,moved = with_counter_screen(spec,q,seed)
        flow.append(dict(seed=seed,baseline=baseline,revised=revised,counter_ballots=turns,counter_changed=moved))
        if baseline and baseline==revised:
            pairs.append({arm:play(spec,q,setup,seed,baseline) for arm,setup in cfg['arms'].items()})
    return pairs,flow


def pair_stats(pairs):
    before,after = zip(*((x['win'],y['win']) for x,y in pairs))
    gains = sum(not a and b for a,b in zip(before,after,strict=True))
    losses = sum(a and not b for a,b in zip(before,after,strict=True))
    ci = exact_paired_interval(before,after,len(CONTRASTS))
    for count,key in ((gains,'p_plus'),(losses,'p_minus')):
        ref = binomtest(count,len(pairs)).proportion_ci(1-2*ci['tail_alpha'],method='exact')
        assert all(abs(a-b)<1e-10 for a,b in zip(ref,ci[key]))
    return dict(gains=gains,losses=losses,precision=ci,
        changed_games=sum(x['votes']!=y['votes'] for x,y in pairs),
        changed_ballots=sum(sum(v!=y['votes'][p] for p,v in x['votes'].items()) for x,y in pairs),
        changed_exiles=sum(x['d2_exile']!=y['d2_exile'] for x,y in pairs),
        same_loss_changed=sum(not x['win'] and not y['win'] and x['trace']!=y['trace'] for x,y in pairs),
        day2_transitions=Counter(x['d2_role']+'→'+y['d2_role'] for x,y in pairs))


def summarize(pairs, flow):
    selection = Counter()
    for row in flow:
        a,b = row['baseline'],row['revised']
        label = ('same_pair' if a==b else 'different_pair') if a and b else (
            'original_only' if a else 'counter_only' if b else 'neither')
        selection[label] += 1
        selection['n_games_counter_'+label] += bool(row['counter_ballots'])
        selection['n_games_changed_'+label] += bool(row['counter_changed'])
    assert selection['same_pair']==len(pairs)
    for group in pairs:
        assert len({(r['seed'],tuple(r['pair']),r['opening']) for r in group.values()})==1
        for a,b in CONTRASTS[:2]:
            assert group[a]['prefix2']==group[b]['prefix2']
            assert group[a]['votes']!=group[b]['votes'] or group[a]['trace']==group[b]['trace']
        a,b = group['counter_neutral'],group['counter_backed']
        assert a['alternative']==b['alternative'] and a['night']==b['night'] and a['day1']==b['day1']
        assert all(a['bluff_plan'][k]==b['bluff_plan'][k] for k in ('source','target','hit'))
        if a['alternative'] is None:
            assert a['trace']==b['trace']
        else:
            assert not b['bluff_plan']['hit'] and a['bluff_plan']['call']==a['alternative']['rival']
            assert b['bluff_plan']['call']==a['alternative']['target']
    totals = {}
    for arm in pairs[0]:
        rows = [g[arm] for g in pairs]
        totals[arm] = dict(wins=sum(r['win'] for r in rows),
            day2=Counter(r['d2_role'] for r in rows), counts=sum((Counter(r['counts']) for r in rows),Counter()),
            modified_nights=sum(r['night']['victim']!=r['night']['original'] for r in rows),
            games_with_signal=sum(bool(r['counts'].get('supports_police') or r['counts'].get('supports_mafia')) for r in rows))
    effects = {a+'_to_'+b:pair_stats([(r[a],r[b]) for r in pairs]) for a,b in CONTRASTS}
    candidate_pairs = [(p['counter_neutral'],p['counter_backed']) for p in pairs
                       if p['counter_neutral']['alternative'] is not None]
    conditional = dict(n=len(candidate_pairs),
        wins=[sum(pair[i]['win'] for pair in candidate_pairs) for i in (0,1)],
        exits=[Counter(pair[i]['d2_role'] for pair in candidate_pairs) for i in (0,1)],
        call_exiled=[sum(pair[i]['d2_exile']==pair[i]['bluff_plan']['call'] for pair in candidate_pairs) for i in (0,1)],
        civilian_follow=[sum(pair[i]['counts']['civil_votes_for_bluff_call'] for pair in candidate_pairs) for i in (0,1)],
        challenger_survives=[sum(pair[i]['d2_exile']!=pair[i]['bluff_plan']['source'] for pair in candidate_pairs) for i in (0,1)])
    return dict(n=len(pairs),selection=selection,arms=totals,effects=effects,backed_eligible=conditional)


def detailed_checks(spec,q,cfg,pairs):
    checks = 0
    cases = {}
    for group in (pairs[0],pairs[len(pairs)//2],pairs[-1]):
        for arm,row in group.items():
            assert play(spec,q,cfg['arms'][arm],row['seed'],tuple(row['pair']))==row
            checks += 1
        for arm,receiver in (('original_neutral','neutral'),('original_evidence','challenge')):
            row = group[arm]
            old = play_v48(spec,q,'prepared',receiver,row['seed'],tuple(row['pair']))
            assert row['trace']==old['trace'] and row['win']==old['win']
    for a,b in CONTRASTS:
        for label,predicate in [('vote',lambda x,y:x['votes']!=y['votes']),
                                ('gain',lambda x,y:x['win']<y['win']),('loss',lambda x,y:x['win']>y['win'])]:
            group = next((row for row in pairs if predicate(row[a],row[b])),None)
            if group is None:
                continue
            case = {}
            for arm in (a,b):
                row = group[arm]
                case[arm] = play(spec,q,cfg['arms'][arm],row['seed'],tuple(row['pair']),True)
                assert all(case[arm][key]==value for key,value in row.items())
            cases[b+'_'+label] = case
    return cases,checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    spec,q = load_spec(parent),parent['q']
    parents = verify_parent(cfg['parent_freeze'])
    out = ROOT/('results/v49_smoke' if args.smoke else 'results/v49')
    out.mkdir()
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'mafia_lab/adaptive_counter_v49.py',
             ROOT/'docs/adaptive_counter_protocol_v49.md',ROOT/'tests/test_adaptive_counter_v49.py']
    assets = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for rel in assets:
        dest = out/'source'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest)
    save_json(out/'freeze.json',dict(config=cfg,parents=parents,assets=assets,q=q,
                                    python=platform.python_version(),scipy=scipy.__version__))
    run = cfg['smoke' if args.smoke else 'holdout']
    seeds = range(run['seed_start'],run['seed_start']+run['n'])
    jobs = [(spec,q,cfg,seeds[i:i+256]) for i in range(0,len(seeds),256)]
    pairs,flow = [],[]
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i,(games,selection) in enumerate(pool.map(batch,jobs),1):
            pairs.extend(games)
            flow.extend(selection)
            if i%4==0:
                print('screened',len(flow),'qualified',len(pairs),flush=True)
    summary = summarize(pairs,flow)
    cases, checks = ({},0) if args.smoke else detailed_checks(spec,q,cfg,pairs)
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in assets.items())
    save_gzip(out/'pairs.json.gz',pairs)
    save_gzip(out/'screen.json.gz',flow)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(screened=len(flow),qualified=len(pairs),
        games=len(pairs)*len(cfg['arms']),sample_replays=checks,v48_compatibility=0 if args.smoke else 6,
        case_replays=sum(map(len,cases.values())),elapsed=time.monotonic()-start,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print('qualified',len(pairs),'wins',{arm:r['wins'] for arm,r in summary['arms'].items()})


if __name__=='__main__':
    main()
