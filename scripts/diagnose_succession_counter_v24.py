#!/usr/bin/env python3
"""Replay prespecified first-seed v24 examples without selecting new policies.

Run after the frozen experiment has produced its holdout and manifest. Detailed
roles are evaluation-only labels; the strategy receives only Observation.
"""
import json
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'results/v24'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def vote_summary(payload):
    counts = Counter(payload.values())
    return [dict(target=target, display_seat=None if target is None else target + 1, votes=count)
            for target, count in sorted(counts.items(), key=lambda item: (-item[1], -1 if item[0] is None else item[0]))]


def action_summary(result):
    """Keep machine seats zero-based and attach clearly marked human seats."""
    days = {}
    for event in result['transcript']:
        day = days.setdefault(event['day'], dict(day=event['day'], night_deaths=[], day_deaths=[], ballots=[]))
        if event['event'] in {'night_death', 'day_death'}:
            victim = event['payload']['victim']
            key = 'night_deaths' if event['event'] == 'night_death' else 'day_deaths'
            day[key].append(dict(player=victim, display_seat=victim + 1,
                                 role_evaluation_only=result['roles_evaluation_only'][victim]))
        if event['event'] in {'votes', 'pk_votes'}:
            day['ballots'].append(dict(round='pk' if event['event'] == 'pk_votes' else 'first',
                                       totals=vote_summary(event['payload'])))
    # The historical runner omits its final night_death event if that night
    # ends the game. Preserve its trace and expose the complete action log.
    for action in result.get('night_actions_evaluation_only', []):
        day = days.setdefault(action['day'], dict(day=action['day'], night_deaths=[], day_deaths=[], ballots=[]))
        day.setdefault('night_actions_evaluation_only', []).append(action)
    return dict(win=result['raw']['win'], days=[days[k] for k in sorted(days)],
                complete_night_actions_evaluation_only=result.get('night_actions_evaluation_only', []),
                succession_events=result.get('successions', []),
                original_repetitions=result.get('repeats', []))


def main():
    freeze = load(FOLDER / 'freeze.json')
    manifest = load(FOLDER / 'manifest.json')
    for relative, expected in freeze['assets'].items():
        assert digest(FOLDER / relative) == expected, relative
    for relative, expected in manifest['files'].items():
        assert digest(FOLDER / relative) == expected, relative
    # Import the archived implementation rather than the possibly evolving checkout.
    sys.path.insert(0, str(FOLDER / 'source'))
    from mafia_lab.succession_experiment_v24 import BASES, MODES, build_spec, simulate
    from mafia_lab import strategies_v24 as api
    from mafia_lab.simulation import continue_game, opening

    rules, good, mafia = build_spec(freeze['config'])
    selected_good = next(g for g in good if g.name == 'repair_q50')
    mafia_map = {m.name: m for m in mafia}
    holdout = load(FOLDER / 'holdout.json')
    lookup = {(c['good'], c['mafia']): c for c in holdout['cells']}
    replay_count = unwrapped_count = night_audited_count = 0

    class NightAuditAPI:
        """Transparent observation-only proxy; never receives referee roles."""
        def __init__(self):
            self.actions = []

        def __getattr__(self, name):
            return getattr(api, name)

        def choose_inspection(self, obs, policy, rng):
            target = api.choose_inspection(obs, policy, rng)
            self.actions.append(dict(day=obs.day + 1, action='inspection',
                                     actor=obs.player, target=target))
            return target

        def choose_kill(self, obs, policy, rng):
            target = api.choose_kill(obs, policy, rng)
            self.actions.append(dict(day=obs.day + 1, action='kill',
                                     actor=obs.player, target=target))
            return target

    def replay(base, mode, seed, archived_cell=None, index=None):
        nonlocal replay_count, unwrapped_count, night_audited_count
        opponent = mafia_map[base + '_' + mode]
        result = simulate(rules, selected_good, opponent, seed, details=True)
        replay_count += 1
        if archived_cell is not None:
            assert index is not None and archived_cell['seed_start'] + index == seed
            for key, values in archived_cell['raw'].items():
                assert result['raw'][key] == values[index], (base, mode, seed, key)
            for sample in archived_cell['samples']:
                if sample['index'] == index:
                    assert result['trace_hash'] == sample['trace_hash']
        # An independent, uninstrumented traversal checks the detailed audit's hash.
        initial = opening(rules, selected_good, opponent, seed, api)
        outcome = continue_game(initial, selected_good, opponent, seed,
                                trace=True, decision_api=api, public_ballots=True)
        assert result['trace_hash'] == sha256(repr(tuple(outcome.transcript)).encode()).hexdigest()
        unwrapped_count += 1
        # A third traversal records only the two night choices, including the
        # first opening night and a potentially terminal last night. Calls and
        # RNG objects pass through unchanged; annotation happens afterwards.
        night_api = NightAuditAPI()
        audited_initial = opening(rules, selected_good, opponent, seed, night_api)
        audited_outcome = continue_game(audited_initial, selected_good, opponent, seed,
                                       trace=True, decision_api=night_api, public_ballots=True)
        assert result['trace_hash'] == sha256(repr(tuple(audited_outcome.transcript)).encode()).hexdigest()
        assert audited_outcome == outcome
        assert len(night_api.actions) == 2 * outcome.nights
        for day in range(1, outcome.nights + 1):
            assert [action['action'] for action in night_api.actions if action['day'] == day] == ['inspection', 'kill']
        traced_night_deaths = {(event['day'], event['payload']['victim'])
                               for event in result['transcript'] if event['event'] == 'night_death'}
        result['night_actions_evaluation_only'] = [dict(
            action,
            actor_display_seat=action['actor'] + 1,
            target_display_seat=action['target'] + 1,
            actor_role_evaluation_only=result['roles_evaluation_only'][action['actor']],
            target_role_evaluation_only=result['roles_evaluation_only'][action['target']],
            night_death_present_in_transcript=(action['day'], action['target']) in traced_night_deaths
                if action['action'] == 'kill' else None,
        ) for action in night_api.actions]
        night_audited_count += 1
        return result

    rows = []
    for base in BASES:
        control = lookup[selected_good.name, base + '_restate']
        treatment = lookup[selected_good.name, base + '_claim']
        assert control['n'] == treatment['n']
        assert control['seed_start'] == treatment['seed_start']
        x, y = control['raw']['win'], treatment['raw']['win']
        execution = treatment['raw']['succession_game']
        predicates = {
            'baseline_win_to_loss': lambda i: x[i] == 1 and y[i] == 0,
            'baseline_loss_to_win': lambda i: x[i] == 0 and y[i] == 1,
            'executed_and_baseline_win_retained': lambda i: bool(execution[i]) and x[i] == y[i] == 1,
        }
        for category, predicate in predicates.items():
            index = next((i for i in range(control['n']) if predicate(i)), None)
            if index is None:
                rows.append(dict(base=base, category=category, seed=None, status='no_matching_case'))
                continue
            seed = control['seed_start'] + index
            runs = {mode: replay(base, mode, seed, lookup[selected_good.name, base + '_' + mode], index)
                    for mode in MODES}
            rows.append(dict(base=base, category=category, seed=seed, index=index, status='replayed',
                             summaries={mode: action_summary(run) for mode, run in runs.items()},
                             runs=runs))

    historical = dict(seed=169000044, base='late_near')
    historical_runs = {mode: replay('late_near', mode, historical['seed']) for mode in ('quiet', 'restate')}
    old_path = ROOT / 'results/v23_restatement_diagnostic.json'
    old_checks = []
    if old_path.exists():
        old = load(old_path)
        for row in old['rows']:
            if row['base'] != 'late_near':
                continue
            for example in row['examples'].values():
                if example['seed'] != historical['seed']:
                    continue
                for mode, run in historical_runs.items():
                    assert run['trace_hash'] == example[mode]['trace_hash']
                    assert run['raw']['win'] == example[mode]['raw']['win']
                    old_checks.append(dict(mode=mode, trace_hash=run['trace_hash'], status='matches_v23'))
    assert len(old_checks) == 2, 'The archived v23 reference example must remain available.'
    historical.update(runs=historical_runs,
                      summaries={mode: action_summary(run) for mode, run in historical_runs.items()},
                      archived_v23_checks=old_checks)
    result = dict(
        scope='Prespecified first seed in each holdout outcome category for q50; descriptive diagnostics only. Reuses held seeds, is not new independent confirmation and does not select policies.',
        selection_rule='For each base, seed-ascending first restate->claim win-to-loss, loss-to-win, and executed succession with original win retained. Replay all four modes at that same seed.',
        seats='All machine player/target fields are zero-based; display_seat fields alone are one-based.',
        script_sha256=digest(Path(__file__)),
        input_sha256={'v24_freeze': digest(FOLDER / 'freeze.json'),
                      'v24_holdout': digest(FOLDER / 'holdout.json'),
                      'v23_reference': digest(old_path)},
        source_assets_checked=len(freeze['assets']),
        detailed_replays=replay_count, independently_unwrapped_replays=unwrapped_count,
        night_audited_replays=night_audited_count,
        night_audit_scope='Separate transparent proxy logs only original Observation-based night choices from opening onward. Its complete trace and Outcome match both detailed and truly unwrapped traversals; referee role labels are attached only after all actions.',
        selected=rows, historical_restatement=historical,
    )
    destination = ROOT / 'results/v24_examples.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='pass', selected_cases=sum(row['status']=='replayed' for row in rows),
                          detailed_replays=replay_count, independently_unwrapped_replays=unwrapped_count,
                          night_audited_replays=night_audited_count,
                          historical_hashes_match=len(old_checks), output=str(destination))))


if __name__ == '__main__':
    main()
