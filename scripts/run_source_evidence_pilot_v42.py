"""Run the frozen paired pilot and audit the historical 17 reversals."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import platform
import shutil
import time

from run_paired_source_routing_v40 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval
from mafia_lab.source_evidence_pilot_v42 import SourceEvidencePilotAPI
from scipy.stats import binomtest

CONFIG = ROOT / 'configs/source_evidence_pilot_v42.json'
CONTRASTS = [('late_base', 'late_agreement'), ('late_base', 'late_q0'),
             ('late_base', 'late_q100'), ('self_q50', 'self_q0'), ('self_q50', 'self_q100')]


def play(spec, setup, seed, details=False):
    rules, good, (_, mafia, cooperation, relay) = spec
    _, q, mode, agreement = setup
    api = SourceEvidencePilotAPI(cooperation, relay, q, mode, agreement)
    start = opening(rules, good, mafia, seed, api)
    result = continue_game(start, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    events = result.transcript
    roles = [role.value for role in start.roles]
    counts = Counter()
    for ballot in api.pilot_ballots:
        first2 = ballot['day'] == 2 and ballot['first']
        for source, target in ballot['calls']:
            if roles[source] == 'police':
                counts['follow_opportunities'] += 1
                counts['follows'] += ballot['target'] == target
                if first2:
                    counts['day2_opportunities'] += 1
                    counts['day2_follows'] += ballot['target'] == target
        if ballot['supported']:
            source, target = ballot['supported']
            counts['supported_votes'] += 1
            counts['supported_' + roles[source]] += 1
            if target != ballot['baseline']:
                counts['shadow_moves'] += 1
                old = roles[ballot['baseline']] if ballot['baseline'] is not None else 'none'
                counts[f'shadow_{old}_to_{roles[target]}'] += 1
            counts['actual_moves'] += ballot['target'] != ballot['baseline']
    exiles = {str(e['day']): e['payload']['victim'] for e in events if e['event'] == 'day_death'}
    prefix = [e for e in events if e['day'] == 1]
    draws = [event for event in api.response_audit if event['draw'] is not None]
    row = dict(seed=seed, win=result.good_win, trace=hash_events(events), day1=hash_events(prefix),
               opening=hash_events((start.roles, start.deaths, start.investigations)),
               first_succession=next(iter(api.successions), None), counts=dict(counts),
               exiles=exiles, exile_roles={day: roles[p] for day,p in exiles.items()},
               draws=len(draws), responded=sum(x['reported'] for x in draws),
               police_day1=sum(e['event']=='message' and e['day']==1
                   and e['payload']['context']=='day' and e['payload']['kind']=='report'
                   and roles[e['payload']['speaker']]=='police' for e in events))
    if details:
        row.update(events=events, roles=roles, ballots=api.pilot_ballots)
    return row


def run_arm(args):
    arm, spec, setup, seeds = args
    return arm, [play(spec, setup, seed) for seed in seeds]


def historical_audit(path):
    with gzip.open(path) as stream:
        games = json.load(stream)
    counts = Counter()
    for game in games:
        base = game['arms']['merge_control']
        b = next(i for i,e in enumerate(base['events']) if e['day']==2 and e['event']=='votes')
        old = {v['player']:v for v in base['ballots'] if v['day']==2 and v['round']=='first'}
        for mode in ('source_exile', 'call_mapping'):
            other = game['arms'][mode]
            assert other['events'][:b] == base['events'][:b]
            assert other['events'][b]['event'] == 'votes'
            counts[f'{mode}:same_public_prefix'] += 1
            for v in other['ballots']:
                if v['day'] != 2 or v['round'] != 'first':
                    continue
                previous = old[v['player']]
                assert previous['calls'] == v['calls']
                if previous['target'] == v['target']:
                    continue
                pair = v['pair']
                roles = other['roles']
                assert previous['target'] == v['original'] == pair['calls'][str(pair['source_exile'])]
                assert roles[previous['target']] == 'mafia'
                assert roles[pair['source_exile']] == 'police' and roles[pair['backing']] == 'mafia'
                assert v['reason'] == 'compatible_sources_protocol'
                counts[f'{mode}:changed_civilian_votes'] += 1
                counts[f'{mode}:now_{roles[v["target"]]}'] += 1
    assert len(games) == 17
    return dict(n=len(games), counts=counts)


def summarize(arms):
    summary = {}
    for arm, rows in arms.items():
        summary[arm] = dict(wins=sum(r['win'] for r in rows), draws=sum(r['draws'] for r in rows),
            responded=sum(r['responded'] for r in rows), police_day1=sum(r['police_day1'] for r in rows),
            day1_exiles=Counter(r['exile_roles'].get('1','none') for r in rows),
            day2_exiles=Counter(r['exile_roles'].get('2','none') for r in rows),
            supported_games=sum(bool(r['counts'].get('supported_votes')) for r in rows),
            counts=sum((Counter(r['counts']) for r in rows), Counter()))
    comparisons = {}
    for a,b in CONTRASTS:
        pairs = list(zip(arms[a], arms[b], strict=True))
        for x,y in pairs:
            assert (x['seed'],x['opening']) == (y['seed'],y['opening'])
            if a=='late_base':
                assert x['day1']==y['day1']
                if b!='late_agreement':
                    assert x['draws']==y['draws']==0 and x['trace']==y['trace']
                    assert x['first_succession']==y['first_succession']
        before, after = zip(*((x['win'],y['win']) for x,y in pairs))
        precision = exact_paired_interval(before, after, len(CONTRASTS))
        gains = sum(x < y for x,y in zip(before,after))
        losses = sum(x > y for x,y in zip(before,after))
        for k, direction in ((gains,'p_plus'),(losses,'p_minus')):
            ci = binomtest(k,len(pairs)).proportion_ci(1-2*precision['tail_alpha'], method='exact')
            assert all(abs(u-v)<1e-10 for u,v in zip(ci,precision[direction]))
        comparisons[f'{a}_to_{b}'] = dict(gains=gains, losses=losses, precision=precision,
            changed_traces=sum(x['trace']!=y['trace'] for x,y in pairs),
            changed_day1=sum(x['day1']!=y['day1'] for x,y in pairs),
            changed_first_succession=sum(x['first_succession']!=y['first_succession'] for x,y in pairs),
            changed_day2_exile=sum(x['exiles'].get('2')!=y['exiles'].get('2') for x,y in pairs))
    return dict(arms=summary, comparisons=comparisons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true')
    smoke = parser.parse_args().smoke
    cfg = json.loads(CONFIG.read_text())
    specs = {m: load_spec(dict(cfg,mafia=m)) for m in ('late_copy','self_copy_early')}
    out = ROOT / ('results/v42_smoke' if smoke else 'results/v42')
    out.mkdir()
    parent = ROOT / cfg['parent_freeze']
    previous = json.loads(parent.read_text())['assets']
    assert all(digest(ROOT / rel)==digest(parent.parent/'source'/rel)==h for rel,h in previous.items())
    assets = [CONFIG, Path(__file__).resolve(), ROOT/'mafia_lab/source_evidence_pilot_v42.py',
              ROOT/'docs/source_evidence_pilot_protocol_v42.md', ROOT/'tests/test_source_evidence_pilot_v42.py']
    delta = {str(p.relative_to(ROOT)): digest(p) for p in assets}
    if not smoke:
        for rel in delta:
            path = out / 'source' / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel,path)
    historical = ROOT/'results/v41/v40_losses.json.gz'
    save_json(out/'freeze.json', dict(config=cfg, parent_sha256=digest(parent),
              assets=delta, history_sha256=digest(historical), python=platform.python_version()))
    start = time.monotonic()
    batch = cfg['smoke' if smoke else 'holdout']
    seeds = range(batch['seed_start'],batch['seed_start']+batch['n'])
    with ProcessPoolExecutor(max_workers=4) as executor:
        arms = dict(executor.map(run_arm, (
            (arm,specs[setup[0]],setup,seeds) for arm,setup in cfg['arms'].items())))
    summary = summarize(arms)
    summary.update(n=len(seeds), history=historical_audit(historical))
    cases = {}
    sampled = 0
    if not smoke:
        for arm, rows in arms.items():
            setup = cfg['arms'][arm]
            for index in (0,len(seeds)//2,len(seeds)-1):
                assert play(specs[setup[0]],setup,rows[index]['seed'])==rows[index]
                sampled += 1
        pairs = list(zip(arms['late_base'],arms['late_agreement'],strict=True))
        match = next((p for p in pairs if p[0]['exiles']!=p[1]['exiles']),None)
        if match is None:
            match = next((p for p in pairs if p[0]['trace']!=p[1]['trace']),None)
        if match:
            for arm,row in zip(('late_base','late_agreement'),match,strict=True):
                setup = cfg['arms'][arm]
                details = play(specs[setup[0]],setup,row['seed'],True)
                assert details['trace']==row['trace']
                cases[arm] = details
        assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in delta.items())
    save_gzip(out/'pairs.json.gz',arms)
    save_gzip(out/'case.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(games=len(seeds)*len(arms),elapsed=time.monotonic()-start,
        sampled_replays=sampled,case_replays=len(cases), files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print({k:v['wins'] for k,v in summary['arms'].items()},flush=True)


if __name__=='__main__':
    main()
