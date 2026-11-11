"""Independent replay checks and descriptive diagnostics for frozen v37 output."""
import sys,json,gzip,math
from pathlib import Path
from hashlib import sha256
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_hit_candidates_v37 import simulate, spec
from mafia_lab.private_response_v35 import PrivateResponseAPI
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save
from scipy.stats import binomtest


def main():
    out=ROOT/'results/v37';f=json.loads((out/'freeze.json').read_text());cfg=f['config']
    d=json.loads(gzip.decompress((out/'holdout.json.gz').read_bytes()))
    for rel,h in f['assets'].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
        assert sha256((out/'source'/rel).read_bytes()).hexdigest()==h
    manifest=json.loads((out/'manifest.json').read_text())
    for rel,h in manifest['files'].items():assert sha256((out/rel).read_bytes()).hexdigest()==h
    r,g,plans,_=spec(f['base_config']);P={p[0]:p for p in plans}
    D={(c['mafia'],c['receiver']):c['rows'] for c in d['cells']}
    replays=controls=intervals=0;diagnostics=[]
    for c in d['cells']:
        rows=c['rows'];mn=c['mafia'];retain=c['receiver']=='retain_hits'
        for index in (0,len(rows)//2,len(rows)-1):
            old=rows[index];new=simulate(r,g,P[mn],old['seed'],retain)
            assert old==new;replays+=1
            if not retain:
                _,m,coop,fake=P[mn];api=PrivateResponseAPI(coop,'original',fake,'1/2')
                s=opening(r,g,m,old['seed'],api)
                o=continue_game(s,g,m,old['seed'],trace=True,decision_api=api,public_ballots=True)
                assert hash_events(o.transcript)==old['trace_hash'];controls+=1
        subset=[v for v in rows if v['public_police_hit']]
        diagnostics.append(dict(mafia=mn,receiver=c['receiver'],n=len(rows),
            counts={k:sum(v[k] for v in rows) for k in ('win','day1_mafia_exile','day1_police_exile','scope_game','pool_expanded_game','true_hit_available','wrong_hit_available','true_hit_votes','wrong_hit_votes','first_changed','pk_changed','vote_checks','day2_scopes')},
            truthful_police_hit=dict(games=len(subset),civilian_votes=sum(v['civilian_follow_police_hit'] for v in subset),
                target_exiled=sum(v['police_hit_exiled'] for v in subset),wins=sum(v['win'] for v in subset))))
    pairs=0
    for mn in cfg['mafia']:
        a,b=D[mn,'original'],D[mn,'retain_hits']
        for x,y in zip(a,b):
            assert x['opening_hash']==y['opening_hash'] and x['prefix_hash']==y['prefix_hash']
            assert x['response_audit']==y['response_audit']
            assert x['true_hit_available']==y['true_hit_available']
            assert x['wrong_hit_available']==y['wrong_hit_available']
            assert not x['day2_scopes'] and not y['day2_scopes']
            pairs+=1
    for c in d['contrasts']:
        for metric in ('win','day1_mafia_exile'):
            m=c[metric];p=m['precision'];tail=p['tail_alpha']
            for k,key in ((m['gains'],'p_plus'),(m['losses'],'p_minus')):
                ci=binomtest(k,c['n']).proportion_ci(confidence_level=1-2*tail,method='exact')
                assert math.isclose(ci.low,p[key][0],abs_tol=1e-10)
                assert math.isclose(ci.high,p[key][1],abs_tol=1e-10)
                intervals+=1
    transitions=[]
    for mn in cfg['mafia']:
        a,b=D[mn,'original'],D[mn,'retain_hits']; counts={}
        def exile_role(v):
            return 'mafia' if v['day1_mafia_exile'] else 'police' if v['day1_police_exile'] else 'civilian' if v['day1_victim'] is not None else 'none'
        for x,y in zip(a,b):
            if x['trace_hash']==y['trace_hash']:continue
            key=(exile_role(x),exile_role(y)); c=counts.setdefault(key,dict(games=0,gains=0,losses=0))
            c['games']+=1;c['gains']+=int(x['win']<y['win']);c['losses']+=int(x['win']>y['win'])
        transitions.append(dict(mafia=mn,rows=[dict(original=k[0],retain_hits=k[1],**v) for k,v in sorted(counts.items())]))
    cases=[]
    for mn in ('self_copy_early','late_copy'):
        a,b=D[mn,'original'],D[mn,'retain_hits']
        for kind in ('gain','loss'):
            match=next(((x,y) for x,y in zip(a,b) if (x['win']<y['win'] if kind=='gain' else x['win']>y['win'])),None)
            if match is None:continue
            cases.append(dict(mafia=mn,kind=kind,seed=match[0]['seed'],
                original=simulate(r,g,P[mn],match[0]['seed'],False,True),
                retain_hits=simulate(r,g,P[mn],match[0]['seed'],True,True)))
            assert cases[-1]['original']['trace_hash']==match[0]['trace_hash']
            assert cases[-1]['retain_hits']['trace_hash']==match[1]['trace_hash']
    (out/'cases.json.gz').write_bytes(gzip.compress(json.dumps(cases,separators=(',',':')).encode(),mtime=0))
    from unittest.mock import patch
    import mafia_lab.strategies_v17 as credit17
    import mafia_lab.strategies_v19 as credit19
    for case in (cases[0],cases[-1]):
        with patch.object(credit17,'_credit',side_effect=AssertionError('numeric credit called')), patch.object(credit19,'source_credit',side_effect=AssertionError('numeric credit called')):
            checked=simulate(r,g,P[case['mafia']],case['seed'],True)
        assert checked['trace_hash']==case['retain_hits']['trace_hash']
    save(ROOT/'results/v37_diagnostics.json',dict(cells=diagnostics,contrasts=d['contrasts'],transitions=transitions))
    save(ROOT/'results/v37_validation.json',dict(source_hashes=len(f['assets']),paired_opening_and_prefix_checks=pairs,
        sampled_full_replays=replays,original_v35_full_replays=controls,case_full_replays=len(cases)*2,numeric_credit_blocked_replays=2,
        interval_marginal_crosschecks=intervals,ballot_assertions=sum(v['vote_checks'] for c in d['cells'] for v in c['rows']),
        source_hashes_verified=True,raw_hashes_verified=True,cases=[dict(mafia=c['mafia'],kind=c['kind'],seed=c['seed']) for c in cases]))
    print(json.dumps(dict(contrasts=d['contrasts'],diagnostics=diagnostics),indent=2))

if __name__=='__main__':main()
