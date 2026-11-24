"""Frozen matched evaluation and read-only audit of singleton claims."""
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

from run_adaptive_counter_v49 import EndOfScreen, play as play_v49
from run_continuation_audit_v45 import verify_parent
from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.current_support_v50 import CurrentSupportMixin
from mafia_lab.engine import speech_order
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.response_cost_v50 import ResponseCostAPI
from mafia_lab.returning_sources_v47 import original_pair
from mafia_lab.simulation import continue_game, opening
from mafia_lab.source_advice_experiment_v25 import exact_paired_interval


CONFIG = ROOT/'configs/response_cost_v50.json'
PACES = ('original','always','protected')
CONTRASTS = tuple((p+'_neutral',p+'_evidence') for p in PACES) + (('protected_neutral','protected_current'),)


class StudyAPI(CurrentSupportMixin, ResponseCostAPI):
    def __init__(self, cooperation, relay, q, pace, receiver, live_redirect):
        super().__init__(cooperation,relay,q,pace,receiver)
        self.live_redirect = live_redirect
        self.live_alternative = None


class Screen(StudyAPI):
    def __init__(self,*args):
        super().__init__(*args)
        self.first_view = None
        self.first_votes = {}

    def vote(self,obs,policy,rng,candidates=None):
        result = super().vote(obs,policy,rng,candidates)
        if obs.day==1 and candidates is None:
            if self.first_view is None:
                self.first_view = obs
            self.first_votes[obs.player] = result
        return result

    def choose_kill(self,obs,policy,rng):
        if obs.day==1:
            self.pair = original_pair(obs)
            raise EndOfScreen
        return super().choose_kill(obs,policy,rng)


def singleton(view, votes, roles):
    if view is None:
        return dict(status='no_first_ballot')
    reports = [m for m in view.messages if m.day==1 and m.kind=='report']
    if len({m.speaker for m in reports}) != 1:
        return dict(status='not_single_source')
    hit = next((m for m in reports if m.context=='day' and m.verdict is True and m.speaker in view.alive
                and m.target in view.alive and m.target!=m.speaker),None)
    if hit is None:
        return dict(status='single_without_live_hit')
    order = speech_order(view)
    opportunity = order.index(hit.speaker)<order.index(hit.target)
    nomination = any(m.day==1 and m.kind=='nominate' and m.context=='day' and m.speaker==hit.target
                     and m.target==hit.speaker for m in view.messages[view.messages.index(hit)+1:])
    return dict(status='single_live_hit',source_role=roles[hit.speaker],target_role=roles[hit.target],
                opportunity=opportunity,nomination=nomination,paid=nomination and votes.get(hit.target)==hit.speaker)


def screen(spec,q,seed,pace):
    rules,good,(_,mafia,cooperation,relay) = spec
    api = Screen(cooperation,relay,q,pace,'neutral',False)
    start = opening(rules,good,mafia,seed,api)
    try:
        continue_game(start,good,mafia,seed,decision_api=api,public_ballots=True)
    except EndOfScreen:
        pass
    audit = singleton(api.first_view,api.first_votes,[r.value for r in start.roles]) if pace=='original' else None
    return api.pair,audit


def play(spec,q,setup,seed,pair,details=False):
    rules,good,(_,mafia,cooperation,relay) = spec
    api = StudyAPI(cooperation,relay,q,*setup)
    start = opening(rules,good,mafia,seed,api)
    result = continue_game(start,good,mafia,seed,trace=True,decision_api=api,public_ballots=True)
    events = result.transcript
    roles = [r.value for r in start.roles]
    assert api.pair==pair and sorted(roles[p] for p in pair)==['mafia','police']
    first = next(e['payload'] for e in events if e['event']=='votes' and e['day']==1)
    second = next(i for i,e in enumerate(events) if e['event']=='votes' and e['day']==2)
    votes = events[second]['payload']
    reports = [e['payload']['speaker'] for e in events[:second] if e['day']==2 and e['event']=='message'
               and e['payload']['kind']=='report' and e['payload']['context']=='day']
    assert sorted(reports)==list(pair)
    for row in api.counter_attempts:
        assert first[row['voter']]==(row['baseline'] if row['blocked'] else row['source'])
    source = api.bluff_plan['source']
    call = next(e['payload']['target'] for e in events[:second] if e['day']==2
                and e['payload'].get('kind')=='accuse' and e['payload']['speaker']==source)
    assert all(v==call for p,v in votes.items() if roles[p]=='mafia')
    exiles = {e['day']:e['payload']['victim'] for e in events if e['event']=='day_death'}
    counts = Counter(nominated=len(api.counter_speeches),attempted=len(api.counter_attempts),
        follows_call=sum(v==call for p,v in votes.items() if roles[p]=='civilian'),
        costly=sum(r['costly'] for r in api.counter_attempts),blocked=sum(r['blocked'] for r in api.counter_attempts),
        fulfilled=len(api.counter_ballots),redirected=sum(r['source']!=r['baseline'] for r in api.counter_ballots))
    for row in api.comparisons:
        assert votes[row['player']]==row['target']
        counts['eligible'] += 1
        counts['challenged_'+str(sum(bool(x) for x in row['challenges'].values()))] += 1
        if row['supported'] is not None:
            role = roles[row['supported']]
            counts['supports_'+role] += 1
            counts['changes_'+role] += row['target']!=row['baseline']
    row = dict(seed=seed,pair=list(pair),win=result.good_win,trace=hash_events(events),
        opening=hash_events((start.roles,start.deaths,start.investigations)),
        prefix=hash_events(events[:second]),night=api.night_adjustment,
        plan=api.bluff_plan,call=call,alternative=api.live_alternative,votes=votes,
        exit=exiles.get(2),role=roles[exiles[2]] if 2 in exiles else 'none',counts=dict(counts))
    if details:
        row.update(events=events,roles=roles,exiles=exiles,comparisons=api.comparisons,attempts=api.counter_attempts)
    return row


def batch(job):
    spec,q,cfg,seeds = job
    pairs,flow = [],[]
    for seed in seeds:
        original,audit = screen(spec,q,seed,'original')
        always,_ = screen(spec,q,seed,'always')
        protected,_ = screen(spec,q,seed,'protect_lead')
        flow.append(dict(seed=seed,original=original,always=always,protected=protected,audit=audit))
        if original and original==always==protected:
            pairs.append({arm:play(spec,q,setup,seed,original) for arm,setup in cfg['arms'].items()})
    return pairs,flow


def compare(rows):
    before,after = zip(*((x['win'],y['win']) for x,y in rows))
    gains = sum(a<b for a,b in zip(before,after,strict=True))
    losses = sum(a>b for a,b in zip(before,after,strict=True))
    ci = exact_paired_interval(before,after,len(CONTRASTS))
    for count,key in ((gains,'p_plus'),(losses,'p_minus')):
        ref = binomtest(count,len(rows)).proportion_ci(1-2*ci['tail_alpha'],method='exact')
        assert all(abs(a-b)<1e-10 for a,b in zip(ref,ci[key]))
    return dict(gains=gains,losses=losses,ci=ci,changed_votes=sum(x['votes']!=y['votes'] for x,y in rows),
        ballots=sum(sum(v!=y['votes'][p] for p,v in x['votes'].items()) for x,y in rows),
        changed_exiles=sum(x['exit']!=y['exit'] for x,y in rows))


def summarize(pairs,flow):
    selection,audit = Counter(),Counter()
    for row in flow:
        label = '/'.join(p for p in PACES if row[p]) or 'neither'
        selection[label] += 1
        if all(row[p] for p in PACES) and len({tuple(row[p]) for p in PACES})>1:
            selection['different_pair'] += 1
        info = row['audit']
        audit[info['status']] += 1
        if info['status']=='single_live_hit':
            key = info['source_role']+'→'+info['target_role']
            audit[key] += 1
            audit[key+'_opportunity'] += info['opportunity']
            audit[key+'_fulfilled'] += info['paid']
    assert selection['original/always/protected']-selection['different_pair']==len(pairs)
    for group in pairs:
        assert len({(r['seed'],r['opening'],tuple(r['pair'])) for r in group.values()})==1
        for a,b in CONTRASTS[:3]:
            assert group[a]['prefix']==group[b]['prefix']
            assert group[a]['votes']!=group[b]['votes'] or group[a]['trace']==group[b]['trace']
        a,b = group['protected_neutral'],group['protected_current']
        assert a['alternative']==b['alternative'] and a['plan']==b['plan'] and a['night']==b['night']
        if a['alternative'] is None:
            assert a['trace']==b['trace']
        else:
            assert a['call']==a['alternative']['rival'] and b['call']==a['alternative']['target']
    arms = {}
    for arm in pairs[0]:
        rows = [g[arm] for g in pairs]
        arms[arm] = dict(wins=sum(r['win'] for r in rows),roles=Counter(r['role'] for r in rows),
            counts=sum((Counter(r['counts']) for r in rows),Counter()),
            opportunities=sum(bool(r['counts']['attempted']) for r in rows),
            protected_games=sum(bool(r['counts']['blocked']) for r in rows),
            modified_nights=sum(r['night']['original']!=r['night']['victim'] for r in rows))
    effects = {a+'_'+b:compare([(g[a],g[b]) for g in pairs]) for a,b in CONTRASTS}
    choices = [g for g in pairs if g['protected_neutral']['alternative'] is not None]
    current = {'n':len(choices)}
    for arm in ('protected_neutral','protected_current'):
        rows = [g[arm] for g in choices]
        current[arm] = dict(wins=sum(r['win'] for r in rows),follow=sum(r['counts']['follows_call'] for r in rows),
            call_exiled=sum(r['exit']==r['call'] for r in rows),exile_roles=Counter(r['role'] for r in rows),
            clear_games=sum(not g[arm]['plan']['hit'] for g in pairs))
    strata = {}
    for label,gate in [('blocked',lambda g:g['protected_neutral']['counts']['blocked']>0),
                       ('other',lambda g:g['protected_neutral']['counts']['blocked']==0)]:
        rows = [g for g in pairs if gate(g)]
        strata[label] = dict(n=len(rows),net={p:sum(g[p+'_evidence']['win']-g[p+'_neutral']['win'] for g in rows)
                                           for p in PACES})
    return dict(n=len(pairs),selection=selection,singleton=audit,arms=arms,effects=effects,current=current,strata=strata)


def cases_for(spec,q,cfg,pairs):
    cases = {}
    for group in (pairs[0],pairs[len(pairs)//2],pairs[-1]):
        for arm,row in group.items():
            assert play(spec,q,cfg['arms'][arm],row['seed'],tuple(row['pair']))==row
            if arm.startswith(('original','always')):
                counter,receiver,_ = cfg['arms'][arm]
                old = play_v49(spec,q,(counter=='always',receiver,False),row['seed'],tuple(row['pair']))
                assert old['trace']==row['trace']
    tests = [('cost',lambda g:g['protected_neutral']['counts']['blocked']>0,
              ('always_neutral','protected_neutral','always_evidence','protected_evidence')),
             ('current',lambda g:g['protected_neutral']['alternative'] is not None,
              ('protected_neutral','protected_current'))]
    for a,b in CONTRASTS:
        for label,predicate in [('gain',lambda x,y:x['win']<y['win']),('loss',lambda x,y:x['win']>y['win'])]:
            tests.append((b+'_'+label,lambda g,a=a,b=b,p=predicate:p(g[a],g[b]),(a,b)))
    for label,predicate,arms in tests:
        group = next((r for r in pairs if predicate(r)),None)
        if group is None:
            continue
        cases[label] = {}
        for arm in arms:
            row = group[arm]
            rich = play(spec,q,cfg['arms'][arm],row['seed'],tuple(row['pair']),True)
            assert all(rich[k]==v for k,v in row.items())
            cases[label][arm] = rich
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    parent = json.loads((ROOT/'results/v44/freeze.json').read_text())['config']
    spec,q = load_spec(parent),parent['q']
    parents = verify_parent(cfg['parent_freeze'])
    out = ROOT/('results/v50_smoke' if args.smoke else 'results/v50')
    out.mkdir()
    paths = [CONFIG,Path(__file__).resolve(),ROOT/'docs/response_cost_protocol_v50.md',
             *(ROOT/'mafia_lab'/f'{p}_v50.py' for p in ('response_cost','current_support')),
             *(ROOT/'tests'/f'test_{p}_v50.py' for p in ('response_cost','current_support'))]
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
    cases = {} if args.smoke else cases_for(spec,q,cfg,pairs)
    assert all(digest(ROOT/rel)==digest(out/'source'/rel)==h for rel,h in assets.items())
    save_gzip(out/'pairs.json.gz',pairs)
    save_gzip(out/'screen.json.gz',flow)
    save_gzip(out/'cases.json.gz',cases)
    save_json(out/'summary.json',summary)
    save_json(out/'manifest.json',dict(screened=len(flow),qualified=len(pairs),games=len(pairs)*len(cfg['arms']),
        sample_replays=0 if args.smoke else 3*len(cfg['arms']),compatibility_replays=0 if args.smoke else 12,
        case_replays=sum(map(len,cases.values())),elapsed=time.monotonic()-start,
        files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))
    print('qualified',len(pairs),'wins',{arm:r['wins'] for arm,r in summary['arms'].items()},flush=True)


if __name__=='__main__':
    main()
