import json
from dataclasses import replace
from pathlib import Path
from random import Random
import pytest
from mafia_lab import strategies_v27 as d
from mafia_lab import strategies_v26 as previous
from mafia_lab.engine import Message,Role,add_message,from_roles,observe,resolve_night
from mafia_lab.gold_relay_experiment_v27 import build_spec,simulate
from mafia_lab.simulation import opening,continue_game
from mafia_lab.police_execution_experiment_v26 import hash_events
C=json.loads(Path('configs/gold_relay_v27.json').read_text())


def case():
    rules,gs,ms=build_spec(C)
    s=resolve_night(from_roles(['police']*4+['mafia']*4+['civilian']*8,rules),15,8)
    s=add_message(s,Message(0,'report',8,False,'day',1))
    s=resolve_night(s,14,9)
    s=add_message(s,Message(0,'report',9,False,'day',2))
    return s,{g.name:g for g in gs},ms


def authorized(s,recipient=8,pool=(4,5)):
    return add_message(s,Message(0,'delegate',recipient,context='day',day=2,targets=pool))


def test_real_offer_preserves_report_list_and_excludes_team_and_already_spoken_gold():
    s,gs,_=case();g=gs['local_q50'];o=observe(s,0)
    parts=d.after_speech(o,g,Random(1))
    old=previous.after_speech(o,g,Random(1));oldparts=old if isinstance(old,tuple) else (old,)
    assert parts[:-1]==oldparts and parts[-1].kind=='delegate'
    assert parts[-1].target==8 and parts[-1].targets==oldparts[-1].targets
    # Anchor3 moves cleared8 before speaker0, and cleared9 before0: no future gold.
    before=replace(o,last_anchor=3)
    assert d.delegation_offer(before,g,oldparts) is None
    # Direct private-mafia call has priority and cannot be replaced by relay.
    hit=replace(o,investigations=o.investigations+(replace(o.investigations[-1],target=4,is_mafia=True),))
    assert not any(m.kind=='delegate' for m in d.after_speech(hit,g,Random(1)))


def test_acceptance_needs_prior_clear_and_current_report_and_single_source_and_order():
    s,gs,_=case();g=gs['local_q50'];s=authorized(s)
    relay=d.relay_decision(observe(s,8),g)
    assert relay.kind=='relay' and relay.target in (4,5)
    no_clear=replace(s,messages=tuple(m for m in s.messages if not(m.kind=='report' and m.target==8)))
    assert d.relay_decision(observe(no_clear,8),g) is None
    before=replace(observe(s,8),last_anchor=3)
    assert d.relay_decision(before,g) is None
    other=add_message(s,Message(1,'report',8,False,'day',2))
    other=add_message(other,Message(1,'delegate',8,context='day',day=2,targets=(4,5)))
    assert d.relay_decision(observe(other,8),g) is None


def test_private_refutation_rejects_false_source_and_outside_hit_rejects_offer():
    s,gs,_=case();g=gs['local_q50'];s=authorized(s)
    # Named source contradicts the recipient's known self identity.
    bad=replace(s,messages=(Message(0,'report',8,True,'day',1),)+s.messages)
    assert d.relay_decision(observe(bad,8),g) is None
    # False source6 is a private known mafia outside the authorized list4/5.
    conflict=replace(s,messages=(Message(6,'report',8,True,'day',1),)+s.messages)
    assert d.relay_decision(observe(conflict,8),g) is None


def test_local_choice_uses_recipient_information_without_secret_team_or_checks():
    s,gs,_=case();s=authorized(s,8,(4,5))
    s=replace(s,messages=(Message(5,'report',8,True,'day',1),)+s.messages)
    for name in ('fixed_q50','local_q50'):
        assert d.relay_decision(observe(s,8),gs[name]).target==5
    obs=observe(s,8)
    assert not obs.investigations and obs.teammates==()
    roles=list(s.roles);roles[1],roles[10]=roles[10],roles[1]
    swapped=observe(replace(s,roles=tuple(roles)),8)
    assert obs==swapped
    assert d.relay_decision(obs,gs['local_q50'])==d.relay_decision(swapped,gs['local_q50'])


def test_relay_replaces_one_source_not_authenticates_gold_and_can_be_revoked():
    s,gs,_=case();g=gs['local_q50'];s=authorized(s)
    s=add_message(s,Message(8,'relay',5,context='day',day=2,targets=(0,)))
    info=d.explain(observe(s,10),g)
    assert info['target']==5 and info['relay_admitted']==1
    assert 8 not in info['sources'] and 8 not in info['known_good']
    assert d.explain(observe(s,10),g,[4])['target']==4
    revoked=add_message(s,Message(0,'accuse',4,context='day',day=2))
    info=d.explain(observe(revoked,10),g)
    assert info['relay_admitted']==0 and info['target']==4
    # A relay outside its source's list is not authorized.
    fake=replace(s,messages=s.messages[:-1]+(Message(8,'relay',6,context='day',day=2,targets=(0,)),))
    assert d.explain(observe(fake,10),g)['relay_admitted']==0


def test_private_facts_override_delegated_target_and_day_does_not_renew_authority():
    s,gs,_=case();g=gs['local_q50'];s=authorized(s)
    s=add_message(s,Message(8,'relay',5,context='day',day=2,targets=(0,)))
    o=observe(s,1)
    hit=replace(o,investigations=o.investigations+(replace(o.investigations[-1],target=4,is_mafia=True),))
    assert d.explain(hit,g)['target']==4
    assert d.explain(replace(observe(s,10),day=3),g)['relay_admitted']==0
    # No actual role authentication is smuggled in by delegation templates.
    bad=replace(observe(s,10),messages=(Message(0,'report',10,True,'day',1),)+s.messages)
    assert d.explain(bad,g)['relay_admitted']==0


def test_engine_templates_allow_bluff_but_validate_scope():
    s,_,_=case()
    with pytest.raises(ValueError):add_message(s,Message(0,'delegate',8,context='day',day=2))
    with pytest.raises(ValueError):add_message(s,Message(0,'delegate',8,context='day',day=2,targets=(8,)))
    with pytest.raises(ValueError):add_message(s,Message(8,'relay',5,context='day',day=2))
    # The engine does not check truth or permission: a mafia may utter the same template.
    add_message(s,Message(4,'delegate',8,context='day',day=2,targets=(9,10)))


def test_no_relay_control_matches_v26_and_audited_runs_match_direct_api():
    r,gs,ms=build_spec(C)
    for g in gs:
        seed=184000000;m=ms[0];s=opening(r,g,m,seed,d)
        o=continue_game(s,g,m,seed,trace=True,decision_api=d,public_ballots=True)
        assert hash_events(o.transcript)==simulate(r,g,m,seed)['trace_hash']
        if g.relay_mode=='none':
            old=continue_game(s,g,m,seed,trace=True,decision_api=previous,public_ballots=True)
            assert old.transcript==o.transcript
