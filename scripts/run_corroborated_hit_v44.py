"""Run the six frozen v44 arms and save paired terminal and process outcomes."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import shutil
import time

from scipy.stats import binomtest

from run_paired_source_routing_v40 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.corroborated_hit_v44 import CorroboratedHitAPI
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval

CONFIG = ROOT / 'configs/corroborated_hit_v44.json'
CONTRASTS = [('copy_base', 'copy_shared'), ('copy_base', 'copy_coordinate'),
             ('copy_shared', 'copy_both'), ('copy_coordinate', 'copy_both'),
             ('old_base', 'old_shared')]


def play(spec, q, setup, seed, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = CorroboratedHitAPI(cooperation, relay, q, *setup)
    start = opening(rules, good, mafia, seed, api)
    result = continue_game(start, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    counts = Counter()
    for row in api.common_events:
        phase = 'day2_' if row['day'] == 2 and row['first'] else ''
        role = roles[row['target']]
        counts[phase+'common_'+role] += 1
        if row['target'] != row['baseline']:
            counts[phase+'possible_change_'+role] += 1
            if row['actual'] != row['baseline']:
                counts[phase+'actual_change_'+role] += 1
    for row in api.pilot_ballots:
        for source, target in row['calls']:
            if roles[source] == 'police':
                counts['opportunities'] += 1
                counts['follows'] += row['target'] == target
                if row['day'] == 2 and row['first']:
                    counts['day2_opportunities'] += 1
                    counts['day2_follows'] += row['target'] == target
    for row in api.call_events:
        counts['eligible_calls'] += 1
        counts['preferred_change'] += row['original'] != row['preferred']
        counts['changed_calls'] += row['original'] != row['target']
        counts['projected_gain'] += row['predicted'][row['target']] - row['predicted'][row['original']]
        counts['day2_changed_calls'] += row['day'] == 2 and row['original'] != row['target']
    counts['police_alignment_checks'] = len(api.police_checks)
    counts['pk'] = sum(e['event'] == 'pk_votes' for e in events)
    exiles = {e['day']: e['payload']['victim'] for e in events if e['event'] == 'day_death'}
    prefix = []
    for e in events:
        if e['day'] > 2 or e['day'] == 2 and e['event'] == 'votes':
            break
        prefix.append(e)
    row = dict(seed=seed, win=result.good_win, trace=hash_events(events), counts=dict(counts),
               opening=hash_events((start.roles, start.deaths, start.investigations)),
               day1=hash_events(e for e in events if e['day'] == 1), first2=hash_events(prefix),
               exile=exiles, exile_roles={d: roles[p] for d,p in exiles.items()})
    if details:
        row.update(events=events, roles=roles, votes=api.pilot_ballots, common=api.common_events,
                   calls=api.call_events, police_checks=api.police_checks)
    return row


def run_arm(args):
    arm, spec, q, setup, seeds = args
    rows = [play(spec,q,setup,seed) for seed in seeds]
    print(arm,len(rows),flush=True)
    return arm, rows


def summarize(arms, setups):
    for group in zip(*arms.values(), strict=True):
        assert len({(x['seed'],x['opening'],x['day1']) for x in group}) == 1
    totals = {}
    for arm, rows in arms.items():
        totals[arm] = dict(wins=sum(row['win'] for row in rows),
            day2=Counter(r['exile_roles'].get(2,'none') for r in rows),
            counts=sum((Counter(r['counts']) for r in rows),Counter()))
    contrasts = {}
    for a,b in CONTRASTS:
        pairs = list(zip(arms[a],arms[b],strict=True))
        if setups[a][2] == setups[b][2] is False:
            # The civilian toggle changes actual ballots. It has no effect on
            # the base police caller's diagnostics or published speech.
            for x,y in pairs:
                assert x['first2'] == y['first2']
                assert x['counts'].get('day2_opportunities',0) == y['counts'].get('day2_opportunities',0)
        else:
            # A coordinating caller can respond to the civilian toggle by
            # anticipating it. That response is part of the joint policy.
            assert setups[a][0] == setups[b][0]
        before = [x['win'] for x,_ in pairs]
        after = [y['win'] for _,y in pairs]
        ci = exact_paired_interval(before,after,len(CONTRASTS))
        gains = sum(x < y for x,y in zip(before,after))
        losses = sum(x > y for x,y in zip(before,after))
        for count,key in ((gains,'p_plus'),(losses,'p_minus')):
            check = binomtest(count,len(pairs)).proportion_ci(1-2*ci['tail_alpha'],method='exact')
            assert all(abs(x-y)<1e-10 for x,y in zip(check,ci[key]))
        contrasts[a+'_to_'+b] = dict(gains=gains,losses=losses,precision=ci,
            changed_traces=sum(x['trace']!=y['trace'] for x,y in pairs),
            changed_prefixes=sum(x['first2']!=y['first2'] for x,y in pairs),
            day2_transitions=Counter(x['exile_roles'].get(2,'none')+'_to_'+y['exile_roles'].get(2,'none')
                                     for x,y in pairs))
    return dict(n=len(next(iter(arms.values()))),arms=totals,contrasts=contrasts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    smoke = parser.parse_args().smoke
    cfg = json.loads(CONFIG.read_text())
    spec = load_spec(cfg)
    out = ROOT/('results/v44_smoke' if smoke else 'results/v44')
    out.mkdir()
    parents = {rel:digest(ROOT/rel) for rel in cfg['parents']}
    for rel in parents:
        parent = ROOT/rel
        archive = json.loads(parent.read_text())
        references = dict(archive.get('parents',{}))
        if 'parent_sha256' in archive:
            references[archive['config']['parent_freeze']] = archive['parent_sha256']
        assert all(digest(ROOT/path)==expected for path,expected in references.items())
        for path,expected in archive['assets'].items():
            assert digest(ROOT/path)==digest(parent.parent/'source'/path)==expected
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'mafia_lab/corroborated_hit_v44.py',
             ROOT/'tests/test_corroborated_hit_v44.py',ROOT/'docs/corroborated_hit_protocol_v44.md']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    if not smoke:
        for path in hashes:
            target = out/'source'/path
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/path,target)
    save_json(out/'freeze.json',dict(config=cfg,assets=hashes,parents=parents,python=platform.python_version()))
    start = time.monotonic()
    batch = cfg['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'],batch['seed_start']+batch['n'])
    with ProcessPoolExecutor(max_workers=4) as pool:
        arms = dict(pool.map(run_arm, ((a,spec,cfg['q'],setup,seeds) for a,setup in cfg['arms'].items())))
    summary = summarize(arms,cfg['arms'])
    cases = {}
    checks = 0
    if not smoke:
        for arm,setup in cfg['arms'].items():
            for i in (0,len(seeds)//2,len(seeds)-1):
                assert play(spec,cfg['q'],setup,seeds[i])==arms[arm][i]
                checks += 1
        indices = {
            'public_hit': next((i for i,(a,b) in enumerate(zip(arms['copy_base'],arms['copy_shared']))
                                if a['exile'].get(2)!=b['exile'].get(2)),None),
            'coordination': next((i for i,b in enumerate(arms['copy_coordinate'])
                                  if b['counts'].get('day2_changed_calls')),None),
        }
        for name, index in indices.items():
            if index is not None:
                cases[name] = {}
                for arm in ('copy_base','copy_shared','copy_coordinate','copy_both'):
                    detail = play(spec,cfg['q'],cfg['arms'][arm],seeds[index],True)
                    assert detail['trace']==arms[arm][index]['trace']
                    cases[name][arm] = detail
        old_case = 225000005
        cases['v43_replay'] = {arm:play(spec,cfg['q'],cfg['arms'][arm],old_case,True)
                              for arm in ('copy_base','copy_shared')}
        assert all(digest(ROOT/path)==digest(out/'source'/path)==expected for path,expected in hashes.items())
    save_gzip(out/'pairs.json.gz',arms)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(games=len(seeds)*len(arms),elapsed=time.monotonic()-start,
              sample_replays=checks,case_replays=sum(map(len,cases.values())),
              files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print({a:d['wins'] for a,d in summary['arms'].items()})


if __name__=='__main__':
    main()
