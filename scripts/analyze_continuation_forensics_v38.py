"""Post-outcome forensics; no policy changes or case-driven seed search."""
import sys,json,gzip,math
from pathlib import Path
from collections import Counter,defaultdict
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_continuation_forensics_v38 import read_gz,simulate,spec
from mafia_lab.hit_candidates_v37 import HitCandidatesAPI
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.restatement_experiment_v23 import save
from scipy.stats import binomtest


def aggregate(rows):
    out=Counter();reasons=Counter();speech_gaps=[];round_gaps=[]
    for row in rows:
        out['games']+=1;out['wins']+=row['win']
        for speech in row['speeches']:
            if speech['day']<2:continue
            out['police_speech_turns']+=1
            calls=[p['target'] for p in speech['parts'] if p['kind']=='accuse']
            if speech['known_bad']:
                out['speech_has_known_bad']+=1
                if speech['own_report']:
                    out['report_and_known_bad']+=1
                    if not any(t in speech['known_bad'] for t in calls):
                        out['report_known_bad_missing_call']+=1
                        speech_gaps.append(dict(seed=row['seed'],day=speech['day'],speaker=speech['speaker'],kind='missing_known_call'))
                    else:out['report_known_bad_correct_call']+=1
                else:out['known_bad_but_no_own_report']+=1
            if calls:
                out['formal_call_to_known_false_source']+=calls[-1] in speech['known_false_sources']
                out['formal_call_to_other_known_bad']+=calls[-1] in speech['known_bad'] and calls[-1] not in speech['known_false_sources']
            if calls and calls[-1]!=speech['target']:
                out['same_prefix_call_selector_disagreement']+=1
                speech_gaps.append(dict(seed=row['seed'],day=speech['day'],speaker=speech['speaker'],kind='same_prefix_disagreement'))
        for rd in row['rounds']:
            if rd['day']<2:continue
            out['rounds']+=1;out['police_ballots']+=len(rd['police'])
            out['rounds_with_private_bad']+=bool(rd['police_with_known_bad'])
            out['rounds_police_split_with_private_bad']+=rd['police_coordinated'] is False
            out['rounds_with_live_false_claimant']+=any(x['role_evaluation_only']=='mafia' for x in rd['alive_claimants'])
            for p in rd['police']:
                out['police_known_bad_ballots']+=bool(p['known_bad'])
                out['police_ignored_known_bad']+=bool(p['known_bad']) and p['target'] not in p['known_bad']
                out['police_votes_known_false']+=p['target'] in p['known_false_sources']
                call=p['team_call']
                if call and call['target'] in p['known_bad']:
                    out['police_legal_team_call_ballots']+=1
                    out['police_team_call_mismatch']+=p['target']!=call['target']
            for call in rd['calls']:
                out['truthful_police_call_episodes']+=1
                out['truthful_police_call_to_mafia']+=call['target_role_evaluation_only']=='mafia'
                out['civilian_call_opportunities']+=call['civilians']
                out['civilian_call_legal']+=call['eligible']
                out['civilian_call_admitted']+=call['proposal_contains']
                out['civilian_call_followed']+=call['followed']
                reasons.update(call['reasons'])
    return dict(counts=dict(out),call_nonfollow_reasons=dict(reasons),speech_flags=speech_gaps,round_flags=round_gaps)


def horizon(rows,d):
    values=[next((v for v in row['days'] if v['day']==d),row['days'][-1]) for row in rows]
    return dict(day=d,n=len(rows),end_totals={role:sum(v['end'][role] for v in values) for role in ('police','mafia','civilian')},
        ended_before=sum(row['days'][-1]['day']<d for row in rows),
        exact_day_no_speech=sum(v['day']==d and not v['day_played'] for v in values))


def analyze_pair(a,b):
    for x,y in zip(a,b):
        assert x['seed']==y['seed'] and x['prefix_hash']==y['prefix_hash'] and x['opening_hash']==y['opening_hash']
    changed=[(x,y) for x,y in zip(a,b) if x['trace_hash']!=y['trace_hash']]
    both=[(x,y) for x,y in changed if x['day1_mafia_exile'] and y['day1_mafia_exile']]
    lost=[(x,y) for x,y in both if x['win'] and not y['win']]
    saved=[(x,y) for x,y in zip(a,b) if x['day1_police_exile'] and not y['day1_police_exile'] and not y['day1_mafia_exile'] and y['day1_victim'] is not None]
    reg={}
    for name,pairs in [('both_changed',both),('both_lost',lost),('police_to_civilian',saved)]:
        aa=[x for x,y in pairs];bb=[y for x,y in pairs]
        data=dict(n=len(pairs),original=aggregate(aa),retain_hits=aggregate(bb),seeds=[x['seed'] for x in aa])
        if pairs:
            data['horizons']={key:[horizon(rr,d) for d in range(1,6)] for key,rr in [('original',aa),('retain_hits',bb)]}
            counts=Counter();firstdiv=Counter();preserved_day2=0;no_bad3=0
            for x,y in pairs:
                ro=x['rounds'][0];rn=y['rounds'][0]
                claim_a={p['player'] for p in ro['alive_claimants'] if p['role_evaluation_only']=='mafia'}
                claim_b={p['player'] for p in rn['alive_claimants'] if p['role_evaluation_only']=='mafia'}
                counts['old_exiled_public_mafia_claimant']+=x['day1_victim'] in claim_a
                counts['new_exiled_public_mafia_claimant']+=y['day1_victim'] in claim_b
                for xx,key in [(x,'original'),(y,'retain_hits')]:
                    round2=next((r for r in xx['rounds'] if r['day']==2 and r['round']=='first'),None)
                    if round2:
                        counts[key+'_day2_live_false_claim']+=any(p['role_evaluation_only']=='mafia' for p in round2['alive_claimants'])
                r3a=next((r for r in x['rounds'] if r['day']==3 and r['round']=='first'),None)
                r3b=next((r for r in y['rounds'] if r['day']==3 and r['round']=='first'),None)
                no_bad3+=bool(r3a and r3b and r3a['police_with_known_bad'] and not r3b['police_with_known_bad'])
                for d in range(1,17):
                    dx=next((v for v in x['days'] if v['day']==d),x['days'][-1])['end']
                    dy=next((v for v in y['days'] if v['day']==d),y['days'][-1])['end']
                    if dx!=dy:firstdiv[str(d)]+=1;break
            data['path_counts']=dict(counts,old_known_bad_new_none_day3=no_bad3)
            data['first_daily_count_divergence']=dict(firstdiv)
            data['terminal_flips']=dict(gains=sum(x['win']<y['win'] for x,y in pairs),losses=sum(x['win']>y['win'] for x,y in pairs))
        reg[name]=data
    return reg


def main():
    root=ROOT/'results/v38';f=json.loads((root/'freeze.json').read_text());cfg=f['config']
    for rel,h in f['assets'].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
        assert sha256((root/'source'/rel).read_bytes()).hexdigest()==h
    for rel,h in f['inputs'].items():assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
    manifest=json.loads((root/'manifest.json').read_text())
    for rel,h in manifest['files'].items():assert sha256((root/rel).read_bytes()).hexdigest()==h
    r,g,plans,_=spec(f['source_config']['base_config']);plan=next(p for p in plans if p[0]==cfg['mafia'])
    result={};checks=Counter();samples=[]
    inherited_root=(ROOT/cfg['source_freeze']).parent/'source'
    for rel,h in f['source_config']['assets'].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
        assert sha256((inherited_root/rel).read_bytes()).hexdigest()==h
        checks['inherited_v37_source_hashes']+=1
    for phase in ('historical','fresh'):
        d=read_gz(root/(phase+'.json.gz'));D={c['receiver']:c['rows'] for c in d['cells']}
        a,b=D['original'],D['retain_hits'];checks['pairs']+=len(a)
        result[phase]=dict(contrasts=d['contrasts'],all={key:aggregate(rows) for key,rows in D.items()},slices=analyze_pair(a,b))
        checks['ballots']+=sum(v['vote_checks'] for c in d['cells'] for v in c['rows'])
        for key,rows in D.items():
            for idx in (0,len(rows)//2,len(rows)-1):
                old=rows[idx];_,m,coop,fake=plan;api=HitCandidatesAPI(coop,fake,'1/2',key=='retain_hits')
                s=opening(r,g,m,old['seed'],api);o=continue_game(s,g,m,old['seed'],trace=True,decision_api=api,public_ballots=True)
                assert hash_events(o.transcript)==old['trace_hash'];checks['original_api_full_replays']+=1
        if phase=='historical':
            assert result[phase]['slices']['both_lost']['n']==91
            assert result[phase]['slices']['both_changed']['n']==398
            assert result[phase]['slices']['police_to_civilian']['n']==14
        else:
            for metric,v in d['contrasts'].items():
                for k,key in ((v['gains'],'p_plus'),(v['losses'],'p_minus')):
                    ci=binomtest(k,len(a)).proportion_ci(confidence_level=1-2*v['precision']['tail_alpha'],method='exact')
                    assert math.isclose(ci.low,v['precision'][key][0],abs_tol=1e-10)
                    assert math.isclose(ci.high,v['precision'][key][1],abs_tol=1e-10)
                    checks['interval_marginals']+=1
    # Observation-level receiver audit of every selected losing continuation.
    # These replays do not change frozen policies and are descriptive only.
    receiver_audits={}
    for phase in ('historical','fresh'):
        batch=read_gz(root/(phase+'.json.gz')); lookup={c['receiver']:{v['seed']:v for v in c['rows']} for c in batch['cells']}
        seeds=result[phase]['slices']['both_lost']['seeds']; records=[];totals=Counter();old_gate=Counter();new_gate=Counter()
        for seed in seeds:
            game=simulate(r,g,plan,seed,True,True)
            assert game['trace_hash']==lookup['retain_hits'][seed]['trace_hash']
            checks['selected_loss_full_replays']+=1
            oldgame=simulate(r,g,plan,seed,False,True)
            assert oldgame['trace_hash']==lookup['original'][seed]['trace_hash']
            checks['selected_loss_full_replays']+=1
            for gg,gate in ((oldgame,old_gate),(game,new_gate)):
                rr=gg['roles_evaluation_only']
                for v in gg['votes']:
                    if v['day']<2 or v['role']!='civilian':continue
                    gate['civilian_ballots']+=1
                    admitted=[s for s in v['proposal_sources'] if rr[s]=='mafia']
                    blocked=[s for s in v['blocked_advice_sources'] if rr[s]=='mafia']
                    gate['with_admitted_mafia_source']+=bool(admitted)
                    gate['with_bare_mafia_source_blocked']+=bool(blocked)
            counts=Counter();events=[]
            for rd in game['rounds']:
                if rd['day']<2:continue
                civs=[v for v in game['votes'] if v['day']==rd['day'] and v['round']==rd['round'] and v['role']=='civilian']
                for call in rd['calls']:
                    source,target=call['source'],call['target']
                    for v in civs:
                        counts['call_ballots']+=1
                        if v['target']==target:continue
                        counts['nonfollow']+=1
                        both_sources=source in v['sources'] and target in v['sources']
                        edge=sorted((source,target))
                        missing=both_sources and edge not in [sorted(e) for e in v['active_edges']]
                        key='missing_live_formal_call_conflict' if missing else 'other_nonfollow'
                        counts[key]+=1
                        counts['reason_'+v['reason']]+=1
                        if missing and v['reason']=='compatible_sources_protocol':counts['compatible_missing_conflict']+=1
                        if any(game['roles_evaluation_only'][s]=='mafia' for s in v['proposal_sources']):counts['nonfollow_with_admitted_mafia_source']+=1
                        events.append(dict(day=rd['day'],round=rd['round'],player=v['player'],
                            call_source=source,call_target=target,actual_vote=v['target'],reason=v['reason'],
                            sources=v['sources'],proposals=v['proposals'],active_edges=v['active_edges'],
                            known_bad=v['known_bad'],missing_call_conflict=missing))
                if rd['round']=='first' and rd['police_with_known_bad'] and not rd['calls']:
                    counts['known_bad_without_public_police_call_rounds']+=1
                    speeches=[v for v in game['speeches'] if v['day']==rd['day'] and v['own_report']]
                    if speeches and all(not v['known_bad'] for v in speeches):
                        counts['report_before_known_bad_no_call_rounds']+=1
            totals.update(counts);records.append(dict(seed=seed,counts=dict(counts),events=events))
        receiver_audits[phase]=dict(totals=dict(totals),records=records)
        result[phase]['selected_loss_receiver_audit']=dict(totals)
        result[phase]['selected_loss_advice_gate']=dict(original=dict(old_gate),retain_hits=dict(new_gate))
    (root/'loss_receiver_audit.json.gz').write_bytes(gzip.compress(json.dumps(receiver_audits,separators=(',',':')).encode(),mtime=0))
    # Posthoc explanatory cases, selected only within already generated batches.
    hist=read_gz(root/'historical.json.gz');D={c['receiver']:c['rows'] for c in hist['cells']}
    a,b=D['original'],D['retain_hits'];lost=result['historical']['slices']['both_lost']['seeds']
    protected=result['historical']['slices']['police_to_civilian']['seeds']
    missing_seed=next(rec['seed'] for rec in receiver_audits['historical']['records'] if any(e['missing_call_conflict'] for e in rec['events']))
    selected=[('both_mafia_loss',lost[0]),('both_mafia_loss',lost[len(lost)//2]),('missing_formal_conflict',missing_seed),('police_to_civilian',protected[0])]
    cases=[]
    for kind,seed in selected:
        c=dict(kind=kind,seed=seed)
        for key,retain in [('original',False),('retain_hits',True)]:
            c[key]=simulate(r,g,plan,seed,retain,True)
            assert c[key]['trace_hash']==next(v['trace_hash'] for v in D[key] if v['seed']==seed)
            checks['case_full_replays']+=1
        cases.append(c)
    (root/'cases.json.gz').write_bytes(gzip.compress(json.dumps(cases,separators=(',',':')).encode(),mtime=0))
    save(ROOT/'results/v38_diagnostics.json',result)
    save(ROOT/'results/v38_validation.json',dict(checks=checks,source_hashes=len(f['assets']),
        historical_full_matches=4096,source_inputs_and_raw_hashes=True,cases=[dict(kind=c['kind'],seed=c['seed']) for c in cases]))
    print(json.dumps(dict(checks=checks,historical=result['historical']['slices']['both_lost'],fresh=result['fresh']['contrasts']),indent=2))

if __name__=='__main__':main()
