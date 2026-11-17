from dataclasses import replace

from mafia_lab.engine import Death, Message
from mafia_lab.succession_copy_v43 import SuccessionCopyAPI, copyable_report
from test_formal_source_conflict_v39 import sample


def test_copy_reads_only_current_night_words_and_checks_target():
    obs = replace(sample(4), deaths=(Death(8, 2, 'night', 1),))
    report = Message(8, 'report', 9, True, 'last_words', 2)
    assert copyable_report(replace(obs, messages=(report,))) == (9, True)
    assert copyable_report(replace(obs, messages=(replace(report, day=1),))) is None
    assert copyable_report(replace(obs, messages=(replace(report, target=4),))) is None
    assert copyable_report(replace(obs, messages=(replace(report, speaker=0),))) is None


def test_same_slot_copy_preserves_legacy_execution_target():
    from random import Random
    from mafia_lab.unresolved_conflict_experiment_v31 import build_spec
    from pathlib import Path
    import json

    _, _, plans = build_spec(json.loads(Path('configs/unresolved_conflict_v31.json').read_text()))
    mafia = next(p for p in plans if p.name == 'late_copy')
    obs = sample(5)
    obs = replace(obs, alive=tuple(p for p in obs.alive if p != 4),
                  deaths=(Death(8, 2, 'night', 1),),
                  messages=(Message(4, 'report', 11, True, 'day', 1),
                            Message(8, 'report', 9, False, 'last_words', 2)))
    api = SuccessionCopyAPI('ordinary', False, '1/2', copy=True)
    report = api.message(obs, mafia, Random(0))
    assert report == Message(5, 'report', 9, False, 'day', 2)
    public = replace(obs, messages=(*obs.messages, report))
    assert api.after_speech(public, mafia, Random(0)) == Message(5, 'accuse', 11, context='day', day=2)
