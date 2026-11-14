"""Validate frozen results and derive process summaries and readable cases."""

from collections import Counter
import gzip
import json
from math import isclose

from scipy.stats import binomtest

from run_paired_source_routing_v40 import ROOT, digest, load_spec, play, save_json
from run_formal_source_conflict_v39 import play as play_v39


OUT = ROOT / 'results/v40'
for batch in (OUT, ROOT / 'results/v40_smoke'):
    manifest = json.loads((batch / 'manifest.json').read_text())
    frozen = json.loads((batch / 'freeze.json').read_text())
    for name, expected in manifest['files'].items():
        assert digest(batch / name) == expected
    for path, expected in frozen['assets'].items():
        assert digest(batch / 'source' / path) == digest(ROOT / path) == expected

freeze = json.loads((OUT / 'freeze.json').read_text())
config = freeze['config']
summary = json.loads((OUT / 'summary.json').read_text())
manifest = json.loads((OUT / 'manifest.json').read_text())
with gzip.open(OUT / 'pairs.json.gz') as stream:
    raw = json.load(stream)
with gzip.open(OUT / 'cases.json.gz') as stream:
    cases = json.load(stream)
with gzip.open(ROOT / 'results/v39/cases.json.gz') as stream:
    old_cases = json.load(stream)
spec = load_spec(config)
n = config['holdout']['n']
assert manifest['games'] == 4 * n

process = {}
for arm_a, arm_b in (
    ('source_exile', 'call_mapping'),
    ('merge_control', 'call_mapping'),
    ('merge_control', 'succession_report'),
):
    name = arm_a + '_to_' + arm_b
    pairs = list(zip(raw[arm_a], raw[arm_b], strict=True))
    assert len(pairs) == n
    for i, (a, b) in enumerate(pairs):
        assert a['seed'] == b['seed'] == config['holdout']['seed_start'] + i
        assert a['day1_hash'] == b['day1_hash']
        assert a['exiles'].get('1') == b['exiles'].get('1')
        if arm_b == 'call_mapping':
            assert a['day2_prefix'] == b['day2_prefix']
            assert a['pair_hash'] == b['pair_hash']
            assert a['counts'].get('day2_opportunities') == b['counts'].get('day2_opportunities')
        if arm_b == 'succession_report':
            first_a = next(iter(a['successions']), None)
            first_b = next(iter(b['successions']), None)
            assert first_a == first_b
    contrast = summary['comparisons'][name]
    wins = (sum(a['win'] < b['win'] for a, b in pairs),
            sum(a['win'] > b['win'] for a, b in pairs))
    assert wins == (contrast['gains'], contrast['losses'])
    for k, key in zip(wins, ('p_plus', 'p_minus')):
        precision = contrast['precision']
        ci = binomtest(k, n).proportion_ci(1 - 2 * precision['tail_alpha'], method='exact')
        assert isclose(ci.low, precision[key][0], abs_tol=1e-10)
        assert isclose(ci.high, precision[key][1], abs_tol=1e-10)
    same = [(a, b) for a, b in pairs if a['win'] == b['win'] and a['trace_hash'] != b['trace_hash']]
    process[name] = dict(
        same_terminal_changed_trace=len(same),
        same_terminal_changed_daily_exile_roles=sum(a['exiles'] != b['exiles'] for a, b in same),
        same_terminal_d2_transitions=dict(Counter(
            a['exiles'].get('2', 'none') + '_to_' + b['exiles'].get('2', 'none') for a, b in same)),
        first_succession=dict(Counter(str(next(iter(b['successions']), {}).get('day', 'none'))
                                      for a, b in pairs)))
    if arm_b == 'succession_report':
        affected = [(a, b) for a, b in pairs if a['successions']]
        process[name]['first_succession_games'] = len(affected)
        process[name]['wins_in_first_succession_games'] = [sum(a['win'] for a, b in affected),
                                                         sum(b['win'] for a, b in affected)]

for arm, rows in raw.items():
    for index in (0, n // 2, n - 1):
        row = rows[index]
        again = play(spec, config['q'], row['seed'], arm)
        assert again['trace_hash'] == row['trace_hash']
        assert again['counts'] == row['counts']

role_names = {'police': '警', 'mafia': '匪', 'civilian': '民'}
notes = ['# v40 逐局解释', '',
         '以 1 起算座位。身份标注供赛后核查。开局、投票、发言和续局均可按冻结种子重放。', '']
for old, case in zip(old_cases, cases[:2], strict=True):
    seed = case['seed']
    assert seed == old['arms'][0]['seed']
    rules, good, plan = spec
    for enabled, archived in zip((False, True), old['arms'], strict=True):
        replay = play_v39(rules, good, plan, config['q'], seed, enabled)
        assert replay['trace_hash'] == archived['trace_hash']
    assert case['arms']['merge_control']['trace_hash'] == old['arms'][0]['trace_hash']
    assert case['arms']['source_exile']['trace_hash'] == old['arms'][1]['trace_hash']
    notes.extend([f'## {seed}', ''])
    source = case['arms']['source_exile']
    calls = {int(actor) + 1: target + 1 for ballot in source['ballots'] if ballot['day'] == 2 and ballot['pair']
             for actor, target in ballot['pair']['calls'].items()}
    notes.extend(['第二天两名公开来源的正式归票为 ' + '、'.join(f'{actor}号归{target}号' for actor, target in calls.items()) + '。', '',
                  '| 规则 | 第二天首轮总票 | 第二天放逐 | 四天内放逐身份 | 终局 |',
                  '|---|---|---|---|---|'])
    for arm, label in [('merge_control', '原合并'), ('source_exile', '按来源放逐'), ('call_mapping', '按归票目标映射')]:
        row = case['arms'][arm]
        ballots = next(e['payload'] for e in row['events'] if e['day'] == 2 and e['event'] == 'votes')
        tally = Counter('弃票' if p is None else f'{p+1}号' for p in ballots.values())
        exile = next((e['payload']['victim'] for e in row['events'] if e['day'] == 2 and e['event'] == 'day_death'), None)
        result = '无人' if exile is None else f"{exile+1}号{role_names[row['roles'][exile]]}"
        path = '、'.join(f"第{day}日{role_names[role]}" for day, role in row['exiles'].items() if int(day) <= 4)
        notes.append(f"| {label} | {'、'.join(f'{p} {v}票' for p,v in tally.most_common())} | {result} | {path} | {'胜' if row['win'] else '负'} |")
    notes.append('')
    if seed == 217000045:
        notes.append('12号当天报15号金水，并对警队私知的假警5号另行归票。5号沿用第一天的假查杀7号。旧候选是5、7号，发言顺序令13号选到5号。来源放逐把候选换成5、12号，12号在这一顺序中更靠前，六张平民票移去12号。映射组把这六票改给7号，12号避开了当天放逐。该支第三、四日各出一匪，仍有一匪活到第五夜，最后一警被刀。')
    else:
        notes.append('6号报16号金水并归假警7号。7号的旧假查杀指向10号，10号实际也是警察。原合并的四个日放逐是1警2匪1民，来源放逐是2警1匪1民，终局同负。映射组选10号，说明假查杀打到另一名警察时，可避免原警察当天出局，却未必保住警察总数。')
    notes.append('在两局各方案第二天的第一轮中，最高票均唯一，裁判直接放逐。PK 只在最高票平票时开始。')
    notes.append('')

labels = {'source_exile': '按来源放逐', 'call_mapping': '按归票目标映射',
          'merge_control': '原合并', 'succession_report': '接续报假验人'}
for case in cases[2:]:
    notes.extend([f"## 新样本 {case['seed']}", '',
        '| 规则 | 接续声明（发言者→目标） | 白天放逐 | 终局 |', '|---|---|---|---|'])
    for arm, row in case['arms'].items():
        events = '、'.join(f"第{s['day']}日{s['speaker']+1}→{s['target']+1}" for s in row['successions']) or '无'
        exiles = '、'.join(f"第{e['day']}日{e['payload']['victim']+1}号{role_names[row['roles'][e['payload']['victim']]]}"
                          for e in row['events'] if e['event'] == 'day_death')
        notes.append(f"| {labels[arm]} | {events} | {exiles} | {'胜' if row['win'] else '负'} |")
    if 'succession_report' in case['arms']:
        first = case['arms']['merge_control']['successions'][0]
        assert first == case['arms']['succession_report']['successions'][0]
        admissions = [sum(first['speaker'] in v['proposal_sources'] for v in row['ballots']
                          if v['day'] == first['day'] and v['round'] == 'first')
                      for row in case['arms'].values()]
        notes.append(f"两组第{first['day']}天由{first['speaker']+1}号匪在同一发言槽接续，正式归票都指向{first['target']+1}号。"
                     f"只跳警时有{admissions[0]}名平民接收该来源的建议。补报假验人后，这个数变成{admissions[1]}。"
                     "补报分支把当天的放逐从匪改成了民，少出的一匪最终活过最后一警。")
    notes.append('')

notes.append('逐条公开发言、平民当轮的选择、夜刀及存活人数在 cases.json.gz。')
(ROOT / 'docs/paired_source_routing_cases_v40.md').write_text('\n'.join(notes) + '\n')
save_json(ROOT / 'results/v40_validation.json', dict(snapshot_assets=len(freeze['assets']),
    holdout_games=manifest['games'], sampled_replays=12, v39_replays=4,
    interval_crosschecks=6, process=process))
print(json.dumps(process, ensure_ascii=False, indent=2))
