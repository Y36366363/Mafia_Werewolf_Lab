"""Replay every v44 coordination loss without changing any actual decision."""
from collections import Counter
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import platform
import shutil
import time

from run_corroborated_hit_v44 import ROOT, digest, load_spec, save_gzip, save_json
from mafia_lab.continuation_audit_v45 import ContinuationAuditAPI
from mafia_lab.continuation_forensics_v38 import daily_counts
from mafia_lab.engine import Role
from mafia_lab.police_execution_experiment_v26 import hash_events
from mafia_lab.simulation import continue_game, opening

CONFIG = ROOT / 'configs/continuation_audit_v45.json'


def verify_parent(path, checked=None):
    checked = {} if checked is None else checked
    if path in checked:
        return checked
    parent = ROOT / path
    archive = json.loads(parent.read_text())
    checked[path] = digest(parent)
    for rel, expected in archive['assets'].items():
        assert digest(ROOT / rel) == expected, rel
        saved = parent.parent / 'source' / rel
        if saved.exists():
            assert digest(saved) == expected, str(saved)
    refs = dict(archive.get('parents', {}))
    if 'parent_sha256' in archive:
        refs[archive['config']['parent_freeze']] = archive['parent_sha256']
    for rel, expected in refs.items():
        assert digest(ROOT / rel) == expected, rel
        verify_parent(rel, checked)
    return checked


def play(spec, q, setup, seed):
    rules, good, (_, mafia, cooperation, relay) = spec
    api = ContinuationAuditAPI(cooperation, relay, q, *setup)
    state = opening(rules, good, mafia, seed, api)
    result = continue_game(state, good, mafia, seed, trace=True, decision_api=api, public_ballots=True)
    # Referee identity is joined only after all real and shadow decisions finish.
    shadow = api.latest_report_shadow(3)
    roles = [r.value for r in state.roles]
    days = daily_counts(roles, api.nights, result.transcript, result.good_win)
    for day in days:
        day['reports'] = [e['payload'] for e in result.transcript
                          if e['day'] == day['day'] and e['event'] == 'message'
                          and e['payload']['kind'] == 'report']
        day['calls'] = [e['payload'] for e in result.transcript if e['day'] == day['day']
                        and e['payload'].get('kind') == 'accuse']
        first = [v for v in api.audit_votes if v['observation']['day'] == day['day']
                 and v['candidates'] is None]
        day['first_votes'] = [dict(player=v['observation']['player'], target=v['target'],
                                  role=v['observation']['role'], reason=v.get('info', {}).get('reason'))
                              for v in first]
        day['tally'] = dict(Counter(v['target'] for v in first if v['target'] is not None))
    return dict(seed=seed, win=result.good_win, trace=hash_events(result.transcript),
                roles_evaluation_only=roles, events=result.transcript, days=days,
                messages=api.audit_messages, votes=api.audit_votes,
                calls=api.call_events, copy_events=api.copy_events,
                successions=api.successions, common_events=api.common_events,
                shadow=shadow)


def main():
    cfg = json.loads(CONFIG.read_text())
    parent_cfg = json.loads((ROOT / cfg['parent_freeze']).read_text())['config']
    parents = verify_parent(cfg['parent_freeze'])
    archive = json.load(gzip.open(ROOT / cfg['parent_pairs'], 'rt'))
    a, b = cfg['primary_comparison']
    losses = [x['seed'] for x,y in zip(archive[a], archive[b], strict=True) if x['win'] and not y['win']]
    assert losses == cfg['seeds']
    paths = [CONFIG, Path(__file__).resolve(), ROOT/'mafia_lab/continuation_audit_v45.py',
             ROOT/'tests/test_continuation_audit_v45.py', ROOT/'docs/continuation_audit_protocol_v45.md']
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    out = ROOT/'results/v45'
    out.mkdir()
    for rel in hashes:
        dest = out/'source'/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/rel, dest)
    save_json(out/'freeze.json', dict(config=cfg, assets=hashes, parents=parents,
              parent_pairs_sha256=digest(ROOT/cfg['parent_pairs']), python=platform.python_version()))
    start = time.monotonic()
    spec = load_spec(parent_cfg)
    cases = {}
    for seed in cfg['seeds']:
        cases[str(seed)] = {}
        for arm in cfg['arms']:
            row = play(spec, parent_cfg['q'], parent_cfg['arms'][arm], seed)
            old = next(v for v in archive[arm] if v['seed'] == seed)
            assert row['trace'] == old['trace'] and row['win'] == old['win']
            cases[str(seed)][arm] = row
        assert cases[str(seed)]['copy_base']['trace'] == cases[str(seed)]['copy_shared']['trace']
        assert cases[str(seed)]['copy_coordinate']['trace'] == cases[str(seed)]['copy_both']['trace']
        print(seed, 'four full traces reproduced', flush=True)
    assert all(digest(ROOT/rel) == digest(out/'source'/rel) == expected for rel,expected in hashes.items())
    assert verify_parent(cfg['parent_freeze']) == parents
    save_gzip(out/'cases.json.gz', cases)
    save_json(out/'manifest.json', dict(games=24, historical_selected_cases=6,
              fresh_performance_games=0, policy_changes=False,
              elapsed=time.monotonic()-start,
              files={p.name:digest(p) for p in out.iterdir() if p.is_file()}))


if __name__ == '__main__':
    main()
