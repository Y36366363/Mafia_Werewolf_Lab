"""Write the v39 reports from verified paired outcomes and stored replays."""

from collections import Counter
import gzip
import json
from pathlib import Path

from run_formal_source_conflict_v39 import ROOT, digest, save_json


OUT = ROOT / 'results/v39'
SUMMARY = json.loads((OUT / 'summary.json').read_text())
MANIFEST = json.loads((OUT / 'manifest.json').read_text())
FREEZE = json.loads((OUT / 'freeze.json').read_text())
for batch_name in ('v39_first_pass', 'v39_first_pass_smoke', 'v39_smoke'):
    batch = ROOT / 'results' / batch_name
    manifest = json.loads((batch / 'manifest.json').read_text())
    freeze = json.loads((batch / 'freeze.json').read_text())
    for filename, expected in manifest['files'].items():
        assert digest(batch / filename) == expected
    for path, expected in freeze['assets'].items():
        assert digest(batch / 'source' / path) == expected
for filename, expected in MANIFEST['files'].items():
    assert digest(OUT / filename) == expected
for path, expected in FREEZE['assets'].items():
    assert digest(OUT / 'source' / path) == expected
    assert digest(ROOT / path) == expected

n = SUMMARY['n']
old, new = [Counter(row) for row in SUMMARY['totals']]
old_win, new_win = SUMMARY['wins']
win_low, win_high = SUMMARY['win_interval']['ci_simultaneous']
follow_low, follow_high = SUMMARY['day2_follow_interval']
pct = lambda x: f'{100*x:.2f}%'
signed = lambda x: f'{100*x:+.2f}'
rate = lambda c, k: c[k + '_follows'] / c[k + '_opportunities']
rows = []
for label, key in [('第二日首轮', 'day2'), ('第二日首轮触发对立的机会', 'day2_edge'), ('全续局含PK', 'all')]:
    if not old[key + '_opportunities'] or not new[key + '_opportunities']:
        rows.append(f"| {label} | {old[key+'_follows']:,}/{old[key+'_opportunities']:,} | "
                    f"{new[key+'_follows']:,}/{new[key+'_opportunities']:,} | — |")
        continue
    rows.append(f"| {label} | {old[key+'_follows']:,}/{old[key+'_opportunities']:,}（{pct(rate(old,key))}） | "
                f"{new[key+'_follows']:,}/{new[key+'_opportunities']:,}（{pct(rate(new,key))}） | "
                f"{signed(rate(new,key)-rate(old,key))} |")
follow_table = '\n'.join(rows)
conclusion = (
    '终局区间覆盖零，本批尚无法确定终局方向。'
    if win_low <= 0 <= win_high else
    ('终局区间全为负，本批支持这项改动降低好人胜率。' if win_high < 0 else
     '终局区间全为正，本批支持这项改动提高好人胜率。')
)
report = f"""# v39 活来源正式对立与续局归票

2026-11-13。两组都从 v37 的保留查杀候选版本开始，干预在第二日起的平民实际投票生效。

## 策略和指标字典

| 名称 | 实际含义 |
|---|---|
| `merge_control` 原合并规则 | 使用 v37 `retain_hits` 的完整行为。续局继承现有验人资格门槛及共同或相容建议合并。 |
| `formal_conflict` 正式对立规则 | 原本要合并时，若当天最后一条普通正式归票把一个已跳警的活来源指向另一个已跳警的活来源，且两者都具备建议资格，记录新冲突。票在保护后的合法冲突端点中按原位置排序。无合法端点时使用保护后的合法池。 |
| `late_copy` | v38 的固定普通后位刀条件。若存在相应死者金水可复制，否则沿用原假查杀。接续匪仍只跳警，验人资格门槛因此仍会影响续局。 |
| q=1/2 | v35 私人条件下首位有资格警察局部抽一次 50% 是否回应。它是冻结参数，范围 0–1。 |
| 正式归票与内推 | `accuse` 是明确想出的目标。普通提名和名单只表达候选，接力只更新建议。后二者均不增加本轮冲突边。 |
| 活来源与建议资格 | 两人均活着，有先前跳警或验人声明，当事人尚未反证，并且现有报验人门槛与目标资格允许其建议参与当前合并。历史身份不由裁判公开。 |
| 位置排序 | 原有基于位置的决策顺序，沿用既有金水保护、PK合法性和私知匪优先。位置顺序、建议资格、实际票和身份概率各自独立。本轮没有新增数值权重或信用。 |
| 跟票 | 真警当天最后一条普通正式归票与某名有资格投该目标的平民实际票一致。真警身份是事后标注。该指标度量目标一致，可能包含平民独立判断一致。 |
| 冲突触发 | 现有接收器本要合并，但可见的正式归票出现至少一条明确的活来源对立，包括旧图已经记过的边。按平民票统计，一局可以多次触发。 |

## 用户提出的同概率替换

设 A 真警、B 悍跳，B 假查杀 C 平民。如果实验先用共同随机数抽取原先的放逐分支，抽到出 A 的概率为 a，再在新策略中把这个分支的目标映射为 C，同时原本出 B 的分支仍出 B，则新策略出 C 的概率严格等于 a。比如用同一个 U∈[0,1)；U<a 时分别出 A/C，其余出 B。这个等式要求把分支固定在最终放逐层，或证明投票、PK、弃票、改归和匪票响应都保留相同映射。只保留个人信任分数或投票前抽样权重，不足以保证最终 a 相同。

在这个严格对照下，首日日末，出 A 的分支每次都多留一警、少留一民，匪人数相同；出 B 的分支两支相同。每局平均多留 a 名警察。A 若随后被刀，收益仍要结合下一夜刀位与遗言看。本轮两组首日规则一致，给出的是续局接收器的证据。同概率首日替换留作独立的放逐层反事实。

即使警匪各自使用同一套程序，座位、声明历史、平民可见信息和夜刀时点也能区分个体。因此已知 E、F 都是匪时，先出谁仍取决于票能否协调和该来源此后能否影响建议。把目标换成影响力更大的匪应另设对照。

## 实验方法

以 {n:,} 个新种子逐对复用发牌和随机机制，完整模拟 {2*n:,} 局。主配置4警4匪8民。程序核对完整首日、首日放逐和第二日首轮投票前公开前缀逐对一致。四个独立冒烟种子另跑八局。构造测试覆盖了正式对立、普通内推、时序、来源存活、PK和私知限制。正式种子和规则先冻结。第一批的实现只拦截旧图未收录的边，遗漏了已有边仍走共同建议的情形。修订补上这个分支，以独立种子验收。两个批次均保留冻结资产与原始记录。

主要终局差值用配对胜负翻转的二项边际 Clopper–Pearson 区间联合构造95%覆盖，边际单侧尾概率0.0125。第二日首轮跟票率的区间用配对种子为重抽样单位，重抽4,000次，统计每次总跟票差除以共同机会数，取2.5%和97.5%经验分位。二者各自报告，未构成跨指标同时区间。全续局机会随存活和发言变化，比例差是描述性过程结果。

## 新留出结果

| 指标 | 原合并 | 正式对立 | 差值（百分点） |
|---|---:|---:|---:|
| 首日出匪 | {SUMMARY['day1_mafia']:,}/{n:,} | {SUMMARY['day1_mafia']:,}/{n:,} | 0（每局首日一致） |
| 终局好人胜 | {old_win:,}/{n:,}（{pct(old_win/n)}） | {new_win:,}/{n:,}（{pct(new_win/n)}） | {signed((new_win-old_win)/n)} [{signed(win_low)}, {signed(win_high)}] |

{SUMMARY['gains']} 对由负转胜，{SUMMARY['losses']} 对由胜转负。{conclusion} 对修订批17对转负局另外进行了34次完整重放，均匹配原轨迹哈希。17对的第二天放逐全部从匪改为警。这是按终局变化选出的机制切片。

| 真警归票跟随 | 原合并 | 正式对立 | 差值（百分点） |
|---|---:|---:|---:|
{follow_table}

第二日首轮总体跟票差的95%重抽样区间为 [{signed(follow_low)}, {signed(follow_high)}] 个百分点。触发子集共用相同前缀和相同机会，表中的子集比例只作描述。全续局原合并组有 {SUMMARY['edge_games'][0]} 局出现符合检查条件的正式对立，正式对立组有 {SUMMARY['edge_games'][1]} 局触发，{new['changed_ballots']} 张票相对同一观察下的旧规则改变。两组完整轨迹有 {SUMMARY['changed_games']} 对不同。

初版独立留出 215000000–215004095 得到 582→561 胜，第二日首轮跟票 22,300→21,635 次。初版与修订批分别报告，原因是两批执行的冲突条件有上述差别。初版用来核查实现与比较方向。

## 对上一轮未跟票的解释

v38 的 563 次未跟中，53 次属于可见的正式来源对立遗漏。另有平民根据自己被假查杀的事实投了另一名匪，也有真警的归票指向尚未跳警的已知匪，或者后置悍跳在归票后才出现。此次修改针对第一种，后几种仍需要不同的信息或发言时点处理。两个来源互斥只告诉平民不能兼信，沿用旧排序时仍可能选中真警。

用旧例 211000044 检查了这个区别。第三日 2 号归 10 号，10 号归 5 号。原合并在部分平民视角投 5 号，新增边后这部分票转投 2 号。旧例的两支最终都输。它说明形式上的归票冲突可以修正，正确选出假警还需要另行验证。固定匪策略只覆盖现有接续声明，接续编验人的同预算对照留待独立留出。该实验估计的是把冲突送入既有排序后的整体效果。单独识别冲突与如何决定出哪一名来源，需要分别评价。

## 核验与复现

- `python -m pytest tests/test_formal_source_conflict_v39.py -q`，5 项通过。
- `python -m pytest tests -q`，434 项通过。随后独立补跑引擎验过发言格式的PK回归测试，1 项通过。
- `python scripts/run_formal_source_conflict_v39.py --smoke`。
- `python scripts/run_formal_source_conflict_v39.py`。
- `python scripts/build_formal_source_conflict_report_v39.py`。

冻结初版见 `results/v39_first_pass/`，修订版见 `results/v39/`，相应冒烟目录均随附。修订正式运行耗时约 {MANIFEST['elapsed']:.1f} 秒。抽取新批首、中、末共 {MANIFEST['baseline_replays']} 局用原 v37 接口完整重放，轨迹哈希匹配。案例 {MANIFEST['case_replays']} 局详细重放也匹配。正式冻结 {len(FREEZE['assets'])} 个资产，验证工作源码、快照及原始结果哈希。个体投票合法性和私知约束在运行时检查。快照按原字节保留两处既有文件尾空行。推断范围限于该固定规则和对手。
"""
report_path = ROOT / 'docs/formal_source_conflict_results_v39.md'
report_path.write_text(report)

cases = json.loads(gzip.decompress((OUT / 'cases.json.gz').read_bytes()))
case_lines = ['# v39 逐局案例', '',
              '座位以1开始。真实身份仅供赛后核查。按冻结方案从改变轨迹且胜负改善、恶化、持平三类各取最早种子。', '']
role_names = {'police': '警', 'mafia': '匪', 'civilian': '民'}
for case in cases:
    a, b = case['arms']
    category = {1: '由负转胜', -1: '由胜转负', 0: '终局持平'}[case['delta']]
    roles = a['roles_evaluation_only']
    case_lines.extend([f"## 种子 {a['seed']} · {category}", ''])
    matching = {(v['day'], v['round'], v['player']): v for v in a['edge_ballots']}
    first = next(v for v in b['edge_ballots']
                 if v['target'] != v['original_target']
                 and (v['day'], v['round'], v['player']) in matching)
    old_ballot = matching[(first['day'], first['round'], first['player'])]
    seat = lambda p: '弃票' if p is None else f'{p+1}号{role_names[roles[p]]}'
    edges = '、'.join(f'{seat(x)}与{seat(y)}' for x, y in first['formal_edges'])
    proposals = '、'.join(f'{int(k)+1}号建议出' + '或'.join(seat(p) for p in values)
                         for k, values in first['proposals'].items() if values)
    case_lines.append(f"第{first['day']}日{'首轮' if first['round']=='first' else 'PK'}，"
                      f"{first['player']+1}号平民看到的合资格建议包括{proposals}。"
                      f"正式归票产生{edges}的对立。旧规则投{seat(old_ballot['target'])}，"
                      f"新规则投{seat(first['target'])}。")
    case_lines.extend(['', '| 策略 | 各日放逐 | 好人结果 |', '|---|---|---|'])
    for name, row in [('原合并', a), ('正式对立', b)]:
        exiles = '、'.join(f"第{e['day']}日出{seat(e['payload']['victim'])}"
                         for e in row['events'] if e['event'] == 'day_death')
        case_lines.append(f"| {name} | {exiles or '无'} | {'胜' if row['win'] else '负'} |")
    case_lines.append('')
case_lines.append('案例原始文件保留公开事件、触发时的平民票、建议及正式对立关系，供核查个体信息与行动。')
case_path = ROOT / 'docs/formal_source_conflict_cases_v39.md'
case_path.write_text('\n'.join(case_lines) + '\n')
assets = [report_path, case_path, Path(__file__).resolve(),
          ROOT / "tests/test_formal_source_conflict_pk_v39.py"]
save_json(ROOT / 'results/v39_analysis_manifest.json',
          {str(path.relative_to(ROOT)): digest(path) for path in assets})
