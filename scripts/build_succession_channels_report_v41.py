"""Render the v41 mechanism report and readable examples from verified archives."""

from collections import Counter
import gzip
import json

from run_succession_channels_v41 import ROOT, digest, save_json


OUT = ROOT / 'results/v41'
SUMMARY = json.loads((OUT / 'summary.json').read_text())
MANIFEST = json.loads((OUT / 'manifest.json').read_text())
VALID = json.loads((ROOT / 'results/v41_validation.json').read_text())
N = SUMMARY['n']
LABELS = {'bare': '只跳警', 'report_neither': '补报，两项关闭',
          'report_gate': '补报，只开门槛', 'report_conflict': '补报，只开冲突',
          'report_both': '补报，两项开启'}
ROLES = {'police': '警', 'civilian': '民', 'mafia': '匪', 'none': '无人出局'}


def percent(k, n=N):
    return f'{100*k/n:.2f}%'


def read_cases(name):
    with gzip.open(OUT / name) as stream:
        return json.load(stream)


def seat(player):
    return '弃票' if player is None else f'{int(player)+1}号'


def report():
    lines = ['# v41 接续假验人机制消融与 17 场败局审计', '',
             '2026-11-15。主配置为 4 警 4 匪 8 民。', '',
             '## 策略与指标字典', '',
             '| 名称 | 行动与含义 |', '|---|---|',
             '| 只跳警 | 原悍跳者死、旧查杀对象仍活着时，首名有资格的活匪在自己的普通发言说“我是警察”，照旧正式归旧查杀对象。 |',
             '| 补报，两项关闭 | 用同一发言槽改说“验旧查杀对象是匪”，正式归票仍指同一人。实验报告在平民投票的建议门槛和冲突图中都不生效，其他用途照常。 |',
             '| 补报，只开门槛 | 把这份报告计入“该来源曾报过验人”。其建议还须通过原有的本人反证、金水保护和本轮目标合法性。 |',
             '| 补报，只开冲突 | 这份报告可以产生与其他报告或来源的冲突。该来源仍需有其他报告才能凭报告资格提供建议。 |',
             '| 补报，两项开启 | v40 的完整补报策略。建议门槛和来源冲突均使用这份报告。 |',
             '| 冲突边 | 两份声明在现有规则下不能同时成立，例如一方报某人是匪，另一方报同一人是好人。接收器也把报告里被查杀的跳警者与报告者视为对立。公开边只记录不相容。 |',
             '| 原合并／来源放逐／归票映射 | v40 的三个好人策略。分别从现行建议池取目标、从两名公开对立来源取目标、先选来源再投另一方明确归的人。续局同分按发言顺序。 |',
             '| 跟真警归票 | 平民投了某真警当天最后一次直接正式归票的人，而且该目标合法。真实身份只作赛后核查。机会和票在同局相关。 |',
             '| q=1/2 | v35 局部回应条件中的一次 50% 抽样，范围 0 到 1。四组补报方案及只跳警沿用相同 q，数值信用仍冻结。 |',
             '| late_copy | 固定普通后位刀。符合条件时可复制死者金水，原悍跳者离场后才触发本次续局实验。 |', '',
             '## 怎么拆开两条路径', '',
             '五组共用发牌与随机种子。所有补报组向全场公开同一类假查杀，匪方原来的归票目标与发言预算保持。每次满足接续条件都会替换，同一局可能跨日报；这不是每局只干预一次。两开关只作用于平民实际投票。实验标记定位的是本实验替换的报告，无法直接用于桌游里识别谁在说谎。原来已经存在的边、其他报告给出的资格、被诬陷者的私人反证和警方行为照旧。两项都关闭时仍可观察这份报告通过其他渠道产生的变化。', '',
             '现有接收器若只剩一个合资格建议来源，先用其建议。在多来源时先看共同建议，然后比较合法的活冲突端点，最后才从相容建议的并集选。画出新边和实际切换投票分支是两个步骤。', '',
             f'正式种子 221000000–221002047，共 {N:,} 组、{5*N:,} 局。四个独立冒烟种子共 20 局。五组首日完整轨迹一致，首日各出匪 {SUMMARY["day1_mafia"]:,} 局。共有 {SUMMARY["triggered"]:,} 组到达相同的首次接续日序、发言者和目标。完全未接续的组逐局保持完整轨迹相同。', '',
             '## 新留出结果', '',
             '| 策略 | 第二日出匪／警／民／无人 | 第二日首轮跟真警归票 | 全续局跟真警归票 | 终局好人胜 |',
             '|---|---:|---:|---:|---:|']
    for arm, row in SUMMARY['arms'].items():
        counts = row['counts']
        exiles = '/'.join(str(row['day2_exiles'].get(role, 0)) for role in ('mafia', 'police', 'civilian', 'none'))
        d2 = f"{counts['day2_follow']:,}/{counts['day2_opportunities']:,}（{percent(counts['day2_follow'], counts['day2_opportunities'])}）"
        all_days = f"{counts['follow']:,}/{counts['opportunities']:,}（{percent(counts['follow'], counts['opportunities'])}）"
        lines.append(f"| {LABELS[arm]} | {exiles} | {d2} | {all_days} | {row['wins']:,}/{N:,}（{percent(row['wins'])}） |")
    lines += ['', '跟票率是过程描述，发言和存活变化可能改变其机会分母。下面的终局区间用两方向成对翻转的二项 Clopper–Pearson 区间及联合界，五项预定终局差同时覆盖 95%，每个边际的单侧尾概率为 0.0025。', '',
              '| 比较 | 由负转胜／由胜转负 | 胜率差及 95% 同时区间，百分点 |', '|---|---:|---:|']
    for key, result in SUMMARY['contrasts'].items():
        a, b = key.split('_to_')
        low, high = result['precision']['ci_simultaneous']
        delta = 100*(result['gains']-result['losses'])/N
        lines.append(f"| {LABELS[a]} → {LABELS[b]} | {result['gains']}/{result['losses']} | {delta:+.2f} [{100*low:+.2f}, {100*high:+.2f}] |")
    traces = VALID['trace_changes']
    lines += ['', f"只开启冲突图的组与两项都关闭的组，完整轨迹不同 {traces['report_neither_to_report_conflict']} 对。"
              f"门槛开启之后再开启冲突图，有 {traces['report_gate_to_report_both']} 对续局轨迹不同，胜负逐局相同。"
              '因此在本次固定对手及接收器下，约 10 个百分点的终局损失由建议准入再现。'
              '冲突路径可能影响过程，尤其在门槛也开放时。', '',
              '相对两项都关闭，单开门槛第二日少出 173 匪，多出 65 警和 108 民。'
              '相对只跳警，补报但两项关闭仍少了 161 次第二日首轮跟真警归票，且终局有一胜一负抵消。报告还有其他可见用途。']
    s = SUMMARY['shadows']
    lines += ['', '## 相同发言下，平民怎样改票', '',
              f"在全开分支的首次接续日首轮，对同一份观察重算四种规则，共 {s['votes']:,} 张平民票。此处每张票面对相同公开发言和裁判投票限制，真实阵营只用于统计改投方向。", '',
              '| 打开的用途 | 新增接续者建议资格 | 新增活冲突边的票 | 目标改变 | 匪改投警 | 匪改投民 |',
              '|---|---:|---:|---:|---:|---:|']
    for key, label in [('report_neither_to_report_gate','双关 → 只开门槛'),
                       ('report_neither_to_report_conflict','双关 → 只开冲突'),
                       ('report_gate_to_report_both','开门槛后再开冲突')]:
        lines.append('| ' + label + ' | ' + ' | '.join(f'{s.get(key+":"+k,0):,}' for k in (
            'admission', 'added_edge', 'changed', 'role:mafia_to_police', 'role:mafia_to_civilian')) + ' |')
    lines += ['', '门槛使原本只有一个建议或多个建议都指向同一匪的局面多出一份相反归票。'
              '改变目标的票有 1,011 张进入相容建议并集或留在该分支，347 张进入已有活来源的冲突比较分支。'
              '后者是建议变多后改变了路由优先级，和报告直接新增冲突边是两件事。'
              '只打开冲突图时，170 张票的可见活边增加，但在这批首次接续的同观察检查中没有改票。']
    w = {arm: row['wins'] for arm,row in SUMMARY['arms'].items()}
    interaction = 100*(w['report_both'] - w['report_gate'] - w['report_conflict'] + w['report_neither'])/N
    lines += ['', f'四种补报策略的终局双差为 {interaction:+.2f} 个百分点，作描述。两条路径可有交互，以上数字对应具体的开关顺序与固定的匪方接续动作。', '',
              '## v40 的 17 场为什么输', '']
    for arm, counts in VALID['comparisons'].items():
        police = counts.get('day2_exile_mafia_to_police',0)
        civil = counts.get('day2_exile_mafia_to_civilian',0)
        lines.append(f"- {('来源放逐' if arm=='source_exile' else '归票映射')}的 {sum(v for k,v in counts.items() if k.startswith('first_change_day_'))} 对均在第二日投票首次分岔。第二日从出匪改成出警 {police} 场、出民 {civil} 场。第一次变票有 {counts.get('voter_civilian',0)} 张平民票，警、匪的第一次分岔票分别为 {counts.get('voter_police',0)}、{counts.get('voter_mafia',0)}。第二日日末相对原合并合计少 {abs(counts.get('day2_survival_delta_police',0))} 警、剩余匪多 {counts['day2_survival_delta_mafia']} 人。")
    lines += ['', '这 17 对由终局事后选出，用来核查机制。归票映射能把部分出警改成出民，但第一步仍用发言顺序选择来源，足以把成组的平民票从原本能出的匪移走。两条规则最终少赢的局可以相同，实际出局者和人数轨迹可以不同。精确 A→C 放逐干预留给独立实验。', '',
              '第三夜，来源放逐的 17 场都刀到平民，归票映射的 17 场都刀到警察。归票映射第三天仍全部出匪，第四天有 13 场出匪。'
              '但这批到终局合计剩 21 名匪，来源放逐合计剩 38 名匪。'
              '这说明挡推对续局有可见区别，即使两组最后胜负相同。'
              '这些合计是已翻转局的机制描述，用来定位分岔，不能代表所有对局。', '',
              '## 复现', '',
              '执行了 `python scripts/run_succession_channels_v41.py --smoke`、`python scripts/run_succession_channels_v41.py`、`python scripts/audit_succession_channels_v41.py` 与 `python scripts/build_succession_channels_report_v41.py`。专项 2 项、全库 440 项测试通过。', '',
              f"正式运行 {MANIFEST['elapsed']:.1f} 秒。核验 {VALID['assets']} 项冻结资产、原始结果哈希、10 项区间边际、15 次新批抽样重放、6 次旧接口抽样兼容重放以及 51 次历史详细重放。完整重放只覆盖上述范围。冻结配置、原始逐局记录和详细案例在 `results/v41/`。", '',
              '[查看案例](succession_channels_cases_v41.md)']
    return '\n'.join(lines).rstrip() + '\n'


def case_report():
    lines = ['# v41 通俗案例', '', '座位从 1 开始。身份仅供赛后核查。']
    detail = read_cases('v40_losses.json.gz')[0]
    lines += ['', f"## 历史翻转 {detail['seed']}", '',
              '| 策略 | 第二天首轮票 | 日放逐 | 终局 |', '|---|---|---|---|']
    for arm, row in detail['arms'].items():
        votes = next(e['payload'] for e in row['events'] if e['event']=='votes' and e['day']==2)
        tally = Counter(seat(x) for x in votes.values())
        path = '、'.join(f"第{day}日{ROLES[role]}" for day,role in row['exiles'].items())
        label = {'merge_control':'原合并','source_exile':'来源放逐','call_mapping':'归票映射'}[arm]
        lines.append(f"| {label} | {'、'.join(f'{p} {v}票' for p,v in tally.most_common())} | {path} | {'胜' if row['win'] else '负'} |")
    old = detail['arms']['merge_control']
    mapped = detail['arms']['call_mapping']
    row = next(b for b in mapped['ballots'] if b['day']==2 and b['pair'] and b['target'] != b['original'])
    pair = row['pair']
    lines += ['', f"{seat(row['player'])}平民看到的两份归票是 " + '、'.join(f'{seat(p)}归{seat(q)}' for p,q in pair['calls'].items())
              + f"。原合并投{seat(row['original'])}。来源放逐选{seat(pair['source_exile'])}，归票映射则投另一方归的{seat(row['target'])}。"
              + f"两组第二日放逐的身份分别见表。第三夜及以后随新的存活和发言状态推进。", '']
    for case in read_cases('cases.json.gz'):
        full = case['arms']['report_both']
        first = full['first_succession']
        lines += [f"## 新批种子 {case['seed']}", '',
                  f"第 {first['day']} 日，{seat(first['speaker'])}匪接续已出局队友的旧查杀，继续归{seat(first['target'])}。"
                  '只跳警组只声明身份，其他四组在同一个位置加上了验人内容。', '',
                  '| 策略 | 日放逐身份 | 终局 |', '|---|---|---|']
        for arm, data in case['arms'].items():
            path = '、'.join(f"第{d}日{ROLES[r]}" for d,r in data['exiles'].items())
            lines.append(f"| {LABELS[arm]} | {path} | {'胜' if data['win'] else '负'} |")
        voted = next((row for row in full['ballots'] if 'shadow' in row and
                      len({v['target'] for v in row['shadow'].values()}) > 1), None)
        if voted:
            votes = '、'.join(f"{LABELS[arm]}投{seat(v['target'])}" for arm,v in voted['shadow'].items())
            sources = voted['shadow']
            before = sources['report_neither']
            after = sources['report_gate']
            lines += ['', f"关闭门槛时，{seat(voted['player'])}能采纳 " + '、'.join(map(seat,before['sources']))
                      + ' 的建议。开放门槛后，可采纳来源为 ' + '、'.join(map(seat,after['sources']))
                      + f"。新归票加入后，位置排序把票从{seat(before['target'])}移到{seat(after['target'])}。"]
            lines += ['', f"固定首次接续当天的公开发言，{seat(voted['player'])}在四种设置下的票为 {votes}。"
                      '这是一张相同观察下的四次重算。']
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


reports = [ROOT/'docs/succession_channels_results_v41.md', ROOT/'docs/succession_channels_cases_v41.md']
for path, content in zip(reports, (report(), case_report()), strict=True):
    path.write_text(content)
related = [*reports, ROOT/'scripts/audit_succession_channels_v41.py',
           ROOT/'scripts/build_succession_channels_report_v41.py',
           ROOT/'results/v41_validation.json', OUT/'v40_losses.json.gz']
save_json(ROOT/'results/v41_analysis_manifest.json',
          {str(path.relative_to(ROOT)): digest(path) for path in related})
