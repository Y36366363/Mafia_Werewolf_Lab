"""Audit instrumentation and explicit continuation failure demonstrations."""
import importlib.util
from pathlib import Path
from random import Random

SPEC=importlib.util.spec_from_file_location('continuation_audit_v21',Path('scripts/audit_continuations_v21.py'))
audit=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(audit)
from mafia_lab.engine import Rules,from_roles,resolve_night,resolve_votes,add_message,Message,observe


def case_after_false_source_exiled():
    rules=Rules(tie_rule='pk')
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,14)
    for m in [Message(0,'report',14,False,'day',1),Message(4,'report',8,True,'day',1)]:s=add_message(s,m)
    s=resolve_votes(s,{p:(4 if p!=4 else None) for p in s.alive})
    s=resolve_night(s,13,12)
    good=audit.original.GoodPolicyV20(name='test',leadership='nominate',position_model='posterior',source_credit=True)
    return s,good


def test_dead_source_can_leave_sole_live_true_source_as_conflict_target():
    s,g=case_after_false_source_exiled();obs=observe(s,9)
    api=audit.AuditAPI('corrected')
    target=api.vote(obs,g,Random(1))
    assert target==0
    row=api.votes[-1]
    assert row['orphan_conflict'] and row['dead_sources']==[4]
    assert row['live_conflicts']==[0]
    assert row['reason']=='compare_conflicting_sources'


def test_dead_false_hit_remains_an_unverified_recommendation():
    s,g=case_after_false_source_exiled();obs=observe(s,9)
    api=audit.AuditAPI('original');assert api.vote(obs,g,Random(1))==8
    assert api.votes[-1]['dead_hit_used']
    # By contrast the actual falsely accused civilian has private refutation;
    # its source is dead, so the actor cannot vote that dead player.
    assert 4 not in obs.alive
    assert 4 in audit.original.private_bad(observe(s,8),True)


def test_police_never_votes_private_known_good_or_ignores_live_known_bad():
    s,g=case_after_false_source_exiled()
    for mode in ('original','corrected'):
        api=audit.AuditAPI(mode)
        for p in (0,1,2,3):
            api.vote(observe(s,p),g,Random(1))
            assert not api.votes[-1]['votes_private_good']
            assert not api.votes[-1]['ignores_private_bad']


def test_wrapper_full_trace_matches_uninstrumented_archived_policy():
    import json
    f=json.loads(Path('results/v20b/freeze.json').read_text())
    rules,gs,ms=audit.build_spec(f['config']);g=next(p for p in gs if p.name=='evidence_q50')
    from hashlib import sha256
    for mode,api in [('original',audit.original),('corrected',audit.corrected)]:
        for m in ms:
            result=audit.replay(mode,rules,g,m,165000000)
            state=audit.opening(rules,g,m,165000000,api)
            outcome=audit.continue_game(state,g,m,165000000,trace=True,decision_api=api,public_ballots=True)
            assert result['trace_hash']==sha256(repr(outcome.transcript).encode()).hexdigest()
            assert result['raw']==audit.metrics(state,outcome)


def test_night_audit_excludes_mafia_actor_own_claim():
    s,g=case_after_false_source_exiled()
    s=add_message(s,Message(5,'report',8,True,'day',2))
    m=audit.original.MafiaPolicyV20(name='test_mafia',response='forward')
    api=audit.AuditAPI('corrected');api.choose_kill(observe(s,5),m,Random(1))
    assert api.nights[-1]['public_claimants']==[0]
    assert 5 not in api.nights[-1]['public_claimants']
