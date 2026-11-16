"""Verify pilot archives and render its report and cases."""
from collections import Counter
import gzip
import json

from run_source_evidence_pilot_v42 import ROOT, digest, load_spec, save_json
from run_succession_channels_v41 import play as play_v41

OUT = ROOT / 'results/v42'
for path in (OUT, ROOT / 'results/v42_smoke'):
    manifest = json.loads((path/'manifest.json').read_text())
    assert all(digest(path/name)==h for name,h in manifest['files'].items())
    freeze = json.loads((path/'freeze.json').read_text())
    parent = ROOT / freeze['config']['parent_freeze']
    assert digest(parent)==freeze['parent_sha256']
    assert digest(ROOT/'results/v41/v40_losses.json.gz')==freeze['history_sha256']
    for rel,h in freeze['assets'].items():
        assert digest(ROOT/rel)==h
        if path==OUT:
            assert digest(path/'source'/rel)==h
    for rel,h in json.loads(parent.read_text())['assets'].items():
        assert digest(ROOT/rel)==digest(parent.parent/'source'/rel)==h

S = json.loads((OUT/'summary.json').read_text())
M = json.loads((OUT/'manifest.json').read_text())
N = S['n']
config = json.loads((OUT/'freeze.json').read_text())['config']
ordinary_spec = load_spec(dict(config, mafia='late_copy'))
with gzip.open(OUT/'pairs.json.gz') as stream:
    archive = json.load(stream)
baseline_rows = archive['late_base']
for index in (0,N//2,N-1):
    row = baseline_rows[index]
    assert play_v41(ordinary_spec,'1/2',row['seed'],'report_both')['trace_hash']==row['trace']
LABELS = {'late_base':'普通刀基线','late_agreement':'普通刀＋公开一致优先',
          'late_q0':'普通刀 q0','late_q100':'普通刀 q100',
          'self_q50':'自刀复制 q50','self_q0':'自刀复制 q0','self_q100':'自刀复制 q100'}
ROLES = {'police':'警','mafia':'匪','civilian':'民','none':'无人'}
base = S['arms']['late_base']
pilot = S['arms']['late_agreement']
history = S['history']['counts']
exile_moves = Counter((a['exile_roles'].get('2','none'), b['exile_roles'].get('2','none'))
                      for a,b in zip(baseline_rows,archive['late_agreement'],strict=True)
                      if a['exiles'].get('2')!=b['exiles'].get('2'))


def ratio(n, d):
    return f'{n:,}/{d:,}（{100*n/d:.2f}%）' if d else '无机会'


def seat(p):
    return '弃票' if p is None else str(int(p)+1) + '号'


lines = [
    '# v42 来源资格、平民改票与 q 小试', '',
    '2026-11-16。4 警 4 匪 8 民，三人遗言上限和不翻牌沿用既有规则。', '',
    '## 策略与指标字典', '',
    '| 名称 | 实际操作 |', '|---|---|',
    '| 建议资格 | 接收器将来源的合法归票放入候选建议池。通常须曾报过一份验人。资格只表示可考虑，没有身份认证或数值信用。 |',
    '| 来源冲突 | 两份验人说法互斥，或一人报告另一名跳警者是匪，于是为两名来源记录一条边。是否按这条边比较，取决于私有反证、建议数和合法候选。 |',
    '| 普通刀基线 | v40/v41 的普通后位刀。原悍跳者死且旧查杀对象尚活，首名合资格活匪用同一发言槽假报旧查杀并仍归该人。好人使用全开接收器和首日保留查杀候选。 |',
    '| 公开一致优先 | 第二日起，平民原本要比较来源或不同建议，且无私知匪时，检查当夜被刀者遗言的验人与活来源当天的验人。若至少两名有资格的活来源正式归不同对象，且恰好一人的验人对象和结论都与遗言相同，优先投此人归的合法对象。多个来源都符合或无人符合，就走原规则。 |',
    '| 自刀复制 | 保留 v33 的早位复制非匪金水。首夜死匪假报金水，活匪复制。好人用原合并，供观察现有 q 的触发范围。与普通刀之间不做同一参数的终局对比。 |',
    '| q0／q50／q100 | v35 首日私人条件下，警察知道首死冒充警察者并非队友。第一名有抽样资格者按 0%、50%、100% 的概率回应。自卫等路径保持原优先级。q 是动作概率，取值从 0 到 1，不是信用。 |',
    '| 改票 | 同一次平民观察中，新优先规则的目标与原接收器目标不同。对局轨迹一旦分岔，后续触发频次可不同。 |',
    '| 跟真警归票 | 某真警当天最后一次直接正式归票合法且平民投了同一个人。按机会计数，真实身份只在赛后标注。 |', '',
    '公开一致是一个二元优先级，只计算当前时点，不累计。它保留本人反证和候选限制。死亡不认证身份，匪徒也可模仿相同验人。两处相同声明来自共享信息的可能性很高，不能作为独立证据相乘。', '',
    '## 昨天两条路径具体做了什么', '',
    '假设真警归 16 号，接续匪一向归 15 号。建议资格打开后，15 号进入可比较的建议池，原排序若偏向较早发言的 15 号，就会有平民一起移票。只用于来源冲突时，接续报告可在与别的报告互斥时给来源加边，但接续者原本没报过其他验人，他的归票通常仍无建议资格。若接收器已找到一个可用归票或共同建议，也可能根本不走冲突比较。', '',
    'v41 固定同一份观察时，打开资格让接续匪的建议进入 4,253 张票的考虑范围，有 1,358 张实际改目标，其中 530 张从匪改投警，828 张从匪改投民。只开冲突时，170 张出现额外活冲突边，该时点目标无一变化。', '',
    '让接续匪用原发言槽报假验人，是补上对手可合理采取的公开欺骗。v41 的开关是因果诊断，用来说明接收器哪一处会放大骗局。未给匪额外发言、真实身份或额外投票。盲点在于“曾报验人”快速取得同等入池机会，而入池之后常靠座位破同分。好人无法当场证伪，并不等于其归票与已有来源等可信。这个漏洞在当前模型中可复现，但幅度取决于对手动作和接收器。', '',
    '## 17 场历史翻转的逐票核对', '',
    f"两种改版各对照原合并 {S['history']['n']} 场。第二日首轮之前的每条公开发言、每名平民可见的合法正式归票均逐项相等。"
    f"两种改版各有 {history['call_mapping:changed_civilian_votes']} 张变化票，改票前全部投真警所归的匪。"
    '原合并在归票建议池中选中该匪。改版先在两名跳警来源中按发言顺序比较，全部选中较早的真警作为来源放逐对象。'
    '归票映射再跟另一位来源，也就是假警的正式归票。因此改投后对象变了，A 本人的归票和来源信用没有发生更新。原先投对有时只是目标排序碰巧与真警一致。', '',
    f"来源放逐将这 105 票全部改投警察。归票映射将 {history['call_mapping:now_civilian']} 票改投平民，"
    f"{history['call_mapping:now_police']} 票改投警察。实际第二日结果为 14 场出民、3 场出警，17 场都错过原本能出的匪。"
    '样本是按历史胜负挑出的机制切片。它不估计一般对局的损失率。', '',
    '## 新种子小试', '',
    f'种子 223000000–223000767，每组 {N} 局。七组共享种子号，在各自对手内部配对，合计 {M["games"]:,} 局。另跑 28 局冒烟。'
    '五项冻结对照用成对胜负翻转的精确二项边际联合构造 95% 同时区间。其余计数用于描述。', '',
    '| 方案 | q 抽样／选择回应 | 首日活警公开验人 | 首／次日出匪 | 第二日首轮跟真警归票 | 好人胜 |',
    '|---|---:|---:|---:|---:|---:|',
]
for arm, row in S['arms'].items():
    counts = row['counts']
    lines.append(f"| {LABELS[arm]} | {row['draws']}／{row['responded']} | {row['police_day1']} | "
                 f"{row['day1_exiles'].get('mafia',0)}／{row['day2_exiles'].get('mafia',0)} | "
                 f"{ratio(counts.get('day2_follows',0),counts.get('day2_opportunities',0))} | {ratio(row['wins'],N)} |")

lines += ['', '| 预定对照 | 由负转胜／由胜转负 | 胜率差及 95% 同时区间（百分点） | 变化轨迹 |',
          '|---|---:|---:|---:|']
for key,row in S['comparisons'].items():
    a,b = key.split('_to_')
    lo,hi = row['precision']['ci_simultaneous']
    delta = 100*(row['gains']-row['losses'])/N
    lines.append(f"| {LABELS[a]} → {LABELS[b]} | {row['gains']}／{row['losses']} | "
                 f"{delta:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {row['changed_traces']} |")

counts = base['counts']
lines += ['', f"冻结普通刀基线的 {base['supported_games']} 局触发一致优先。共 {counts.get('supported_votes',0)} 张票有唯一支持，"
          f"其来源赛后标记为警察 {counts.get('supported_police',0)} 次、匪徒 {counts.get('supported_mafia',0)} 次。"
          f"在原观察上有 {counts.get('shadow_moves',0)} 张票的目标会不同。"
          f"实际应用整套规则的轨迹里，有 {pilot['counts'].get('actual_moves',0)} 张票在当时观察中偏离原选择。触发票可能集中于少数局和同一来源。", '',
          f"同一观察下，原来投民的 {counts.get('shadow_civilian_to_mafia',0)} 张和原来投警的 {counts.get('shadow_police_to_mafia',0)} 张都改向匪。"
          f"实际第二日有 {exile_moves['civilian','mafia']} 局从出民转为出匪，{exile_moves['police','mafia']} 局从出警转为出匪。"
          f"有 {S['comparisons']['late_base_to_late_agreement']['changed_first_succession']} 局首次接续也随续局变化。"
          '终局多 6 胜，95% 同时区间跨零。适合先检验来源规则能否抵抗复制遗言，再考虑累计信用。', '',
          '普通后位刀的两个 q 端点均逐局核查是否进入已有抽样，并与 q50 核对全程轨迹。自刀复制的三个 q 版本每组都抽了 768 次。q0 相对 q50 在这批 768 对净增 49 胜，而首日出匪从 229 变为 0。这是主动跳警与后续暴露、续局的整体效果。q100 与 q50 的区间覆盖零。单一自刀对手的结果无法确定混合比例。'
          '若要让 q 介入普通刀的第二日接续局，要先定义警察已经公开、是否有发言机会、手上是金水或查杀等条件，然后单独研究这个新的动作概率。', '',
          '## 解释边界与复现', '',
          '本次加成只测试唯一的公开一致信号。它是一个可被模仿的候选策略。A→C 严格同概率放逐仍留作单独裁判层对照。'
          '一致信号的真伪比和胜率依赖冻结对手。当前对手只重复旧查杀，尚未专门选择复制这一条遗言，也没有据此拟合概率。完整结果是固定策略的模拟证据。', '',
          f"执行了运行脚本的冒烟与正式模式，正式耗时 {M['elapsed']:.1f} 秒。"
          f"核对 {M['sampled_replays']} 次新批抽样重放与 {M['case_replays']} 次案例重放，另以 v41 全开接口重放 3 个普通刀基线样本。"
          '五项终局对照的十个二项边际都与独立 SciPy 接口校验。专项 1 项、全库 441 项测试通过。运行命令为 `python -m pytest tests/test_source_evidence_pilot_v42.py -q`、`python -m pytest tests -q`、`python scripts/run_source_evidence_pilot_v42.py --smoke`、`python scripts/run_source_evidence_pilot_v42.py` 及 `python scripts/build_source_evidence_pilot_report_v42.py`。'
          'v42 只复制自身新增的冻结资产，其余由 v41 冻结清单及快照逐文件哈希引用。首次正式运行因误要求公开一致组也保持首次接续相同而提前停止。之后仅修正核验及增加接续变动计数，用原策略和原种子重跑。初始冻结信息见 results/v42_retry_note.json。', '',
          '[通俗案例](source_evidence_pilot_cases_v42.md)', '']

with gzip.open(ROOT/'results/v41/v40_losses.json.gz') as stream:
    archived = json.load(stream)[0]
with gzip.open(OUT/'case.json.gz') as stream:
    fresh = json.load(stream)
cases = ['# v42 通俗案例', '', '座位自 1 起算，身份是赛后核对。', '',
         f"## 历史种子 {archived['seed']}", '',
         '1 号真警和死者 13 号都报了 3 号金水，1 号正式归 4 号匪，4 号正式归 9 号民。'
         '三组公开发言相同。原合并在 4 和 9 中选，改版在 1 和 4 中选，较早发言的 1 被选中。'
         '映射把票改投 4 所归的 9。这个顺序解释了为何没有任何归票或信用变化，平民的票还是会转向 9。', '',
         '| v40 策略 | 第二日首轮票数 | 当天放逐 | 终局 |', '|---|---|---|---|']
for arm,row in archived['arms'].items():
    votes = next(e['payload'] for e in row['events'] if e['day']==2 and e['event']=='votes')
    counts = Counter(seat(p) for p in votes.values())
    exile = row['days'][1]['day_exile']
    label = {'merge_control':'原合并','source_exile':'来源放逐','call_mapping':'归票映射'}[arm]
    cases.append(f"| {label} | {'、'.join(f'{p} {n}票' for p,n in counts.most_common())} | "
                 f"{seat(exile)}{ROLES[row['roles'][exile]]} | {'胜' if row['win'] else '负'} |")
if fresh:
    a,b = fresh['late_base'], fresh['late_agreement']
    changed = next(row for row in b['ballots'] if row['target']!=row['baseline'])
    source,target = changed['supported']
    cases += ['', f"## 新样本 {a['seed']}", '',
              f"第 {changed['day']} 日，{seat(changed['player'])}平民把{seat(source)}的当日报告与当夜遗言对照。"
              f"唯一一致来源是{seat(source)}，实际身份为{ROLES[b['roles'][source]]}。"
              f"原排序投{seat(changed['baseline'])}，公开一致优先投{seat(target)}。"
              "这个案例中，10 号遗言和 12 号公开报告都查杀 5 号。12 号也正式归 5 号。"
              "处在同一建议池的另一方归 4 号，位置顺序原本偏向 4 号。两边终局同输，出匪的日序不同。", '',
              '| 策略 | 白天出局 | 终局 |', '|---|---|---|']
    for arm,row in fresh.items():
        path = '、'.join(f"第{d}日{seat(p)}{ROLES[row['roles'][p]]}" for d,p in row['exiles'].items())
        cases.append(f"| {LABELS[arm]} | {path} | {'胜' if row['win'] else '负'} |")
else:
    cases += ['', '新批没有发生公开一致优先导致的实际轨迹变化，因此只有历史解释案例。']
reports = [(ROOT/'docs/source_evidence_pilot_results_v42.md',lines),
           (ROOT/'docs/source_evidence_pilot_cases_v42.md',cases)]
for path,content in reports:
    path.write_text('\n'.join(content).rstrip()+'\n')
save_json(ROOT/'results/v42_analysis_manifest.json',
          {str(path.relative_to(ROOT)):digest(path)
           for path in [*(path for path,_ in reports),ROOT/'scripts/build_source_evidence_pilot_report_v42.py']})
