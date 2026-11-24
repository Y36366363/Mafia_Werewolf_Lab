from dataclasses import replace
from random import Random

from mafia_lab.adaptive_counter_v49 import AdaptiveCounterAPI
from mafia_lab.current_support_v50 import CurrentSupportMixin, current_alternative
from mafia_lab.engine import Message, PublicEvent
from mafia_lab.strategies_v30 import MafiaPolicyV30
from test_formal_source_conflict_v39 import sample


def prefix():
    messages = (
        Message(9, 'nominate', 2, day=1),
        Message(10, 'nominate', 2, day=2),
        Message(11, 'accuse', 2, day=2),
        Message(11, 'nominate', 3, day=2),
        Message(13, 'nominate', 2, day=2),
        Message(14, 'accuse', 0, day=2),
        Message(5, 'nominate', 2, day=2),
        Message(7, 'nominate', 2, day=2),  # Later nonteammate, not in the actual prefix.
        Message(8, 'nominate', 2, context='last_words', day=2),
        Message(4, 'report', 15, False, day=2),
    )
    votes = PublicEvent('vote', 1, ballots=((9, 3), (10, 3), (11, 3)))
    return replace(sample(4), teammates=(1, 5, 6), messages=messages, public_events=(votes,), last_anchor=8)


def test_current_support_uses_latest_ordinary_nomination_in_the_actor_prefix():
    obs = prefix()
    assert current_alternative(obs, (0, 4), 15) == dict(target=2, voters=[10, 13], rival=0, rival_voters=[14])
    # Withdraw the second current supporter. Yesterday's votes and teammate
    # or last-words statements cannot preserve eligibility.
    withdrawn = replace(obs, messages=tuple(m for m in obs.messages if m.speaker != 13))
    assert current_alternative(withdrawn, (0, 4), 15) is None
    assert current_alternative(obs, (0, 4), 2) is None
    assert current_alternative(replace(obs, pending_pk=(0, 2)), (0, 4), 15) is None
    protected = replace(obs, messages=obs.messages + (Message(12, 'report', 2, False, day=2),))
    assert current_alternative(protected, (0, 4), 15) is None


def test_redirect_preserves_the_report_and_publishes_the_call_the_team_follows():
    class API(CurrentSupportMixin, AdaptiveCounterAPI):
        pass

    api = API('ordinary', False, '1/2', True, 'neutral', False)
    api.pair = (0, 4)
    api.bluff_plan = dict(source=4, target=15, hit=False, call=0)
    obs = prefix()
    policy = MafiaPolicyV30(name='test', response='forward')
    rng = Random(2)
    assert api.after_speech(obs, policy, rng).target == 0
    assert api.live_alternative['voters'] == [10, 13]
    api.live_redirect = True
    call = api.after_speech(obs, policy, rng)
    assert call == Message(4, 'accuse', 2, day=2)
    assert api.message(obs, policy, rng) == Message(4, 'report', 15, False, day=2)
    assert api.bluff_plan == dict(source=4, target=15, hit=False, call=0)
    ballot = replace(obs, player=5, teammates=(1, 4, 6), messages=obs.messages + (call,))
    assert api.vote(ballot, policy, rng) == 2
