from dataclasses import replace

from mafia_lab.engine import Death, Message
from mafia_lab.source_evidence_pilot_v42 import agreement_choice
from test_formal_source_conflict_v39 import sample


def test_public_agreement_breaks_tie_without_authentication():
    obs = sample()
    obs = replace(obs, deaths=(Death(8, 2, 'night', 1),),
                  messages=(*obs.messages, Message(8, 'report', 9, False, 'last_words', 2)))
    info = dict(known_bad=[], reason='compatible_sources_protocol', proposal_sources=[0, 4],
                proposals={'0': [4], '4': [11]})
    assert agreement_choice(obs, info) == (0, 4)
    copied = replace(obs, messages=(*obs.messages, Message(4, 'report', 9, False, 'day', 2)))
    assert agreement_choice(copied, info) is None
    assert agreement_choice(obs, dict(info, known_bad=[4])) is None
    assert agreement_choice(obs, dict(info, proposals={'0': [], '4': [11]})) is None
