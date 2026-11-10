"""Summarize audited trajectories and verify frozen/fresh evidence separately."""
import sys,json,gzip
from pathlib import Path
from hashlib import sha256
from collections import Counter
from unittest.mock import patch
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_continuation_audit_v36 import load_json_gz,simulate
from run_private_response_v35 import spec,simulate as baseline_simulate
from mafia_lab.restatement_experiment_v23 import save


def main():
    out=ROOT/'results/v36';f=json.loads((out/'freeze.json').read_text());cfg=f['config']
    for rel,h in f['assets'].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
        assert sha256((out/'source'/rel).read_bytes()).hexdigest()==h
    for rel,h in f['inputs'].items():assert sha256((ROOT/rel).read_bytes()).hexdigest()==h
    for rel,h in json.loads((out/'manifest.json').read_text())['files'].items():assert sha256((out/rel).read_bytes()).hexdigest()==h
    source=json.loads((ROOT/cfg['source_freeze']).read_text());old=load_json_gz(ROOT/cfg['source_holdout'])
    r,g,plans,bc=spec(source['config']);P={x[0]:x for x in plans};G={x['name']:x for x in source['config']['profiles']}
    oldD={(c['profile'],c['mafia']):c['rows'] for c in old['cells']}
    counts=dict(historical_complete_replays=0,fresh_games=0,fresh_baseline_replays=0,
                q50_q100_existing_hash_matches=0,q50_q100_true_hit_matches=0,interval_crosschecks=0,ballot_checks=0)
    summaries=[];case_keys=[];data_by_phase={}
    for phase in ('historical','fresh'):
        data=load_json_gz(out/(phase+'.json.gz'));data_by_phase[phase]=data
        for cell in data['cells']:
            gn,mn=cell['profile'],cell['mafia'];rows=cell['rows']
            if phase=='historical':
                expected=oldD[gn,mn];assert len(rows)==len(expected)==2048
                assert all(all(x[k]==y[k] for k in ('seed','win','trace_hash','opening_hash','day1_mafia_exile')) for x,y in zip(rows,expected))
                counts['historical_complete_replays']+=len(rows)
            else:
                assert [x['seed'] for x in rows]==list(range(cfg['fresh']['seed_start'],cfg['fresh']['seed_start']+cfg['fresh']['n']))
                counts['fresh_games']+=len(rows)
                for index in (0,len(rows)//2,len(rows)-1):
                    row=rows[index];plain=baseline_simulate(r,g,P[mn],G[gn],row['seed'])
                    assert plain['trace_hash']==row['trace_hash'];counts['fresh_baseline_replays']+=1
            counts['ballot_checks']+=sum(x['ballot_checks'] for x in rows)
            hit=[x for x in rows if x['true_day1_alive_hit']]
            if phase=='historical' and gn=='dead_q50':
                for x,y,z in zip(rows,oldD['dead_q50',mn],oldD['dead_q100',mn]):
                    if any(a['reported'] for a in y['response_audit']):
                        assert x['trace_hash']==y['trace_hash']==z['trace_hash']
                        counts['q50_q100_existing_hash_matches']+=1
                        counts['q50_q100_true_hit_matches']+=int(x['true_day1_alive_hit'])
            all_hits=[h for x in rows for h in x['hits'] if h['round']=='first']
            later_hits=[h for h in all_hits if h['day']>=2]
            histories=[z for x in rows for z in x['history']]
            alive_history=[z for z in histories if z['status']=='target_still_alive']
            assert all(z['history_retained'] for z in alive_history)
            duals=[z for x in rows for z in x['duals']]
            mismatch=[z for z in duals if z['disagreement']]
            auto=[z for x in rows for z in x['auto_reports']]
            current_gold=[z for z in auto if not z['verdict']]
            s=dict(phase=phase,profile=gn,mafia=mn,n=len(rows),wins=sum(x['win'] for x in rows),
                first_day_mafia_exiles=sum(x['day1_mafia_exile'] for x in rows),
                day1_true_alive_hit_games=len(hit),day1_hit_target_exiled=sum(x['day1_hit_exiled'] for x in hit),
                day1_all_civ_follow=sum(x['day1_hit_all_civ_follow'] for x in hit),
                day1_majority_civ_follow=sum(x['day1_hit_majority_follow'] for x in hit),
                day1_hit_terminal_wins=sum(x['win'] for x in hit),
                day1_hit_source_killed_night2=sum(x['source_killed_night2'] for x in hit),
                day1_hit_exile_then_loss=sum(x['day1_hit_exiled'] and not x['win'] for x in hit),
                day1_nonexecutable_hit_reports=sum(x['dead_target_day1_hit'] for x in rows),
                day1_vote_reasons=dict(sum((Counter(x['day1_reasons']) for x in rows),Counter())),
                day1_other_vote_roles=dict(sum((Counter(h['other_vote_roles']) for h in all_hits if h['day']==1),Counter())),
                later_hit_episodes=len(later_hits),later_eligible_civilian_ballots=sum(z['eligible'] for z in later_hits),
                later_follow_civilian_ballots=sum(z['follow'] for z in later_hits),
                later_target_exiled_episodes=sum(z['target_exiled'] for z in later_hits),
                old_hit_target_already_dead_rounds=sum(z['status']=='target_already_dead' for z in histories),
                old_hit_alive_rounds=len(alive_history),old_hit_history_missing=0,
                old_hit_no_source_current_instruction=sum(z['source_has_no_current_proposal'] for z in alive_history),
                repeated_old_true_hit_reports=sum(x['repeated_old_true_hits'] for x in rows),
                civil_dual_calls=len(duals),civil_dual_disagreements=len(mismatch),
                dual_disagreement_actual_matches_relay=sum(z['matches_relay'] for z in mismatch),
                dual_disagreement_games=sum(any(z['disagreement'] for z in x['duals']) for x in rows),
                day2plus_police_ordinary_reports=len(auto),day2plus_good_reports=len(current_gold),
                good_report_no_live_private_bad=sum(not z['live_private_bad'] for z in current_gold),
                good_report_no_mafia_claim=sum(z['no_current_mafia_claim'] for z in current_gold))
            summaries.append(s)
            # Only cases from existing batches; no new seed search.
            for label,predicate in [
                ('unfollowed_truth_hit',lambda x:x['true_day1_alive_hit'] and not x['day1_hit_majority_follow']),
                ('truth_hit_exile_then_loss',lambda x:x['true_day1_alive_hit'] and x['day1_hit_exiled'] and not x['win']),
                ('gold_dual_action',lambda x:any(z['disagreement'] for z in x['duals']))]:
                found=next((x for x in rows if predicate(x)),None)
                if found:case_keys.append((phase,gn,mn,found['seed'],label))
        if phase=='fresh':
            for c in data['contrasts']:
                for metric in ('win','day1_mafia_exile'):
                    v=c[metric];tail=v['precision']['tail_alpha']
                    for key,k in [('p_plus',v['gains']),('p_minus',v['losses'])]:
                        ci=binomtest(k,c['n']).proportion_ci(confidence_level=1-2*tail,method='exact')
                        assert abs(ci.low-v['precision'][key][0])<1e-9 and abs(ci.high-v['precision'][key][1])<1e-9
                        counts['interval_crosschecks']+=1
    selected=[('historical',gn,'self_copy_early',207000002,'predeclared_previous_case') for gn in cfg['profiles']]
    # Deterministic descriptive ordering, cap documents to eight complete cases.
    for key in [x for x in case_keys if x[0]=='fresh']+case_keys:
        if len(selected)>=cfg['case_limit']:break
        if key[:4] not in [x[:4] for x in selected]:selected.append(key)
    cases=[]
    for phase,gn,mn,seed,label in selected:
        detail=simulate(r,g,P[mn],G[gn],seed,True)
        expected=next(c for c in data_by_phase[phase]['cells'] if c['profile']==gn and c['mafia']==mn)
        row=next(x for x in expected['rows'] if x['seed']==seed);assert detail['trace_hash']==row['trace_hash']
        cases.append(dict(phase=phase,profile=gn,mafia=mn,label=label,**detail))
    # Credit flags are inherited; verify that the numerical-credit helpers are
    # not reached in two full evidence-routing sample replays.
    credit_checks=0
    for gn in cfg['profiles']:
        with patch('mafia_lab.strategies_v17._credit',side_effect=AssertionError('numeric credit unexpectedly used')),patch('mafia_lab.strategies_v19.source_credit',side_effect=AssertionError('numeric credit unexpectedly used')):
            row=baseline_simulate(r,g,P['self_copy_early'],G[gn],207000002)
            assert row['trace_hash']==next(x for x in oldD[gn,'self_copy_early'] if x['seed']==207000002)['trace_hash']
            credit_checks+=1
    save(ROOT/'results/v36_diagnostics.json',dict(**counts,summaries=summaries,cases=cases,
        case_replays=len(cases),numeric_credit_guard_replays=credit_checks,
        note='Episode counts and ballot counts correlated within games; descriptive only. Only fresh q0→q50 contrasts have new confirmation intervals.'))
    print(json.dumps(counts))

if __name__=='__main__':main()
