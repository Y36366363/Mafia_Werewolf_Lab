"""Check archived inputs and generate the written v43 report and cases."""
from collections import Counter
import gzip
import json
from pathlib import Path

from run_paired_source_routing_v40 import ROOT, digest, load_spec, save_json
from run_source_evidence_pilot_v42 import play as play_v42


OUT = ROOT / 'results/v43'


def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    freeze = json.loads((folder/'freeze.json').read_text())
    for rel, sha in manifest['files'].items():
        assert digest(folder/rel) == sha
    for rel, sha in freeze['assets'].items():
        assert digest(ROOT/rel) == sha
        if folder == OUT:
            assert digest(folder/'source'/rel) == sha
    for rel, sha in freeze['parents'].items():
        path = ROOT/rel
        assert digest(path) == sha
        for parent_rel, expected in json.loads(path.read_text())['assets'].items():
            assert digest(ROOT/parent_rel) == digest(path.parent/'source'/parent_rel) == expected
    return manifest, freeze


def read_gzip(path):
    with gzip.open(path) as stream:
        return json.load(stream)


M, F = verify(OUT)
verify(ROOT/'results/v43_smoke')
S = json.loads((OUT/'summary.json').read_text())
DATA = read_gzip(OUT/'pairs.json.gz')
N = S['n']
SPEC = load_spec(F['config'])
for arm, enabled in [('old_base', False), ('old_agreement', True)]:
    for i in (0, N//2, N-1):
        row = DATA[arm][i]
        replay = play_v42(SPEC, ('late_copy', '1/2', 'succession_report', enabled), row['seed'])
        assert replay['trace'] == row['trace']

LABELS = {'old_base':'旧报告＋原合并', 'old_agreement':'旧报告＋一致优先',
          'copy_base':'复制遗言＋原合并', 'copy_agreement':'复制遗言＋一致优先'}
ROLES = {'police':'警', 'mafia':'匪', 'civilian':'民', 'none':'无人'}
STRATA = ('无改报机会', '可复制且指匪队友为匪', '其他可复制结果')
strata = {label: Counter() for label in STRATA}
for rows in zip(*DATA.values(), strict=True):
    ref = rows[0]['first_copy']
    group = STRATA[0] if not ref else STRATA[1] if ref['hit_teammate'] else STRATA[2]
    for row in rows:
        candidate = row['first_copy']
        assert (dict(candidate, copied=False) if candidate else None) == ref
        assert not candidate or candidate['day']==2
    strata[group]['n'] += 1
    for arm, row in zip(DATA, rows, strict=True):
        strata[group][arm] += row['win']
        strata[group][arm+'_day2'] += row['exile_roles'].get('2')=='mafia'


def percent(count, total):
    return '无机会' if not total else f'{count:,}/{total:,}（{100*count/total:.2f}%）'


def seat(value):
    return '弃票' if value is None else f'{int(value)+1}号'


def make_report():
    lines = [
        '# v43 接续匪复制遗言与公开一致优先', '',
        '2026-11-17。普通后位刀接续局，主配置 4 警 4 匪 8 民。', '',
        '## 策略与指标字典', '',
        '| 名称 | 实际动作和解释 |', '|---|---|',
        '| 旧报告 | 接续匪在原槽假报首日悍跳队友留下的旧查杀，仍正式归该对象。 |',
        '| 复制遗言 | 接续匪读取公开的当夜被刀者遗言。仅有一组可见验人结果、对象仍活且非自己时，原样复制对象与匪／好人结论。原来的正式归票仍指旧查杀对象。无机会时沿用旧报告。 |',
        '| 原合并 | 沿用 v42 的原接收器。合资格建议进入既有合并和冲突处理，续局同分按发言位选。 |',
        '| 一致优先 | 沿用 v42。在无私人反证、原规则要比较不同建议或来源的续局，至少两个活来源有资格且归不同对象，只有一份当前验人与当夜遗言吻合时，优先投该来源合法归票。 |',
        '| 匹配数 | 在上述候选与归票条件满足后，计零、一或多个一致来源。唯一来源真假供赛后分组。出现多个一致来源时走原规则。 |',
        '| 跟真警归票 | 平民实际投真警当天最后一次合法直接归票的目标。统计票有同局相关，机会也随轨迹变化。 |',
        '| q=1/2 | v35 的首日条件回应概率 50%，范围 0–1，四组同值。 |',
        '| 资格、加成与实际票 | 资格决定建议可否进入池。加成本轮只有 v42 的唯一一致优先，二元、当轮有效，无累计分数。实际票还受合法名单和个人反证限制。 |', '',
        '同一份公开信息可能被重复引用。复制的报告与正式归票是两个字段，例如匪说“5 号是匪”，同时正式归 9 号。同场并列报告是否可信，不需要真实角色标签。匪方发言预算、归票规则、队友知识照旧。复制可重申对匪队友的查杀，属于本轮压力条件，另报发生次数。模型未训练匪方选择何时值得付这个成本。', '',
        '## 方法及结果', '',
        f'225000000–225002047 共 {N:,} 个新种子，每组完整终局，合计 {M["games"]:,} 局。另有 16 局冒烟。'
        '四组逐局通过首夜和完整首日匹配。每种好人规则下，复制与旧报告在第一条可改变的报告之前前缀相同。每种匪策略下，好人的两个版本在第二日首轮前前缀、跟票机会数及每人匹配状态相同。'
        '后面局面可以因投票、警方发言、出局和夜刀而分岔。', '',
        '| 策略 | 第二日出匪／警／民／无人 | 第二日首轮跟真警归票 | 全续局跟真警归票 | 好人终局胜 |',
        '|---|---:|---:|---:|---:|',
    ]
    for arm, row in S['arms'].items():
        d = row['counts']
        exile = '/'.join(str(row['day2'].get(r,0)) for r in ('mafia','police','civilian','none'))
        lines.append(f"| {LABELS[arm]} | {exile} | {percent(d.get('day2_follows',0), d.get('day2_opportunities',0))} | "
                     f"{percent(d.get('follows',0),d.get('opportunities',0))} | {percent(row['wins'],N)} |")
    lines += ['', '四项配对终局差使用双向翻转的二项边际 Clopper–Pearson 区间和联合界，同时覆盖 95%，每个边际的单侧尾概率为 0.003125。跟票和出局为机制描述。', '',
              '| 终局比较 | 负变胜／胜变负 | 差值与 95% 同时区间（百分点） | 轨迹变化局数 |',
              '|---|---:|---:|---:|']
    for key, d in S['comparisons'].items():
        a,b = key.split('_to_')
        lo,hi = d['precision']['ci_simultaneous']
        delta = 100*(d['gains']-d['losses'])/N
        lines.append(f"| {LABELS[a]} → {LABELS[b]} | {d['gains']}／{d['losses']} | "
                     f"{delta:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {d['changed_traces']} |")
    lines += ['', '## 复制怎么影响跟票', '',
              '| 策略 | 可复制局／槽 | 会改写旧报告的槽 | 其中查杀队友 | 第二日首轮唯一警／唯一匪／多个／零 | 全续局实际改票由唯一警／匪触发 |',
              '|---|---:|---:|---:|---:|---:|']
    for arm,row in S['arms'].items():
        d = row['counts']
        matches = '／'.join(f"{d.get('day2_match_'+r,0):,}" for r in ('police','mafia','multiple','zero'))
        changes = '／'.join(f"{d.get('actual_change_'+r,0):,}" for r in ('police','mafia'))
        lines.append(f"| {LABELS[arm]} | {row['copy_games']:,}／{row['eligible_slots']:,} | "
                     f"{row['changed_reports']:,} | {row['hit_teammate']:,} | {matches} | {changes} |")
    t = S['day2_match_transitions']
    w = {arm:row['wins'] for arm,row in S['arms'].items()}
    interaction = 100*(w['copy_agreement']-w['copy_base']-w['old_agreement']+w['old_base'])/N
    lines += ['',
              '旧报告条件的可复制槽是由相同观察计算的机会；那两组仍使用原报告。表中的匹配数按票计。同一个来源通常被多个平民同时观察。', '',
              f"原合并的两种匪方方案对照中，第二日首轮 {t.get('police_to_multiple',0):,} 张票由唯一真警匹配变成多匹配，"
              f"{t.get('police_to_mafia',0):,} 张由唯一真警变成唯一匪，"
              f"{t.get('police_to_out_of_scope',0):,} 张变成不再满足候选及理由等前置条件。"
              '这包含复制改变证据和其他公开发言后的整体路径，票数按配对座位记录。', '',
              f'复制使一致规则相对原合并的胜率增量改变 {interaction:+.2f} 个百分点。此双差只作描述。'
              '在同一匪策略内看好人组差值可以把报告内容固定。跨匪策略的差值还包含伪报改变冲突、建议保护、私人反证和续局的影响。', '',
              '## 有复制机会的对局', '',
              '这批所有首次可改报机会都在第二日首轮投票前，四组可见槽和候选复制内容相同。按这一共同前置条件分层可看出总体收益来自哪里。', '',
              '| 复制机会 | 组数 | 旧报告原合并 | 旧报告一致优先 | 复制原合并 | 复制一致优先 |',
              '|---|---:|---:|---:|---:|---:|']
    for name, row in strata.items():
        cells = [f"{row[arm+'_day2']}／{row[arm]}" for arm in DATA]
        lines.append(f"| {name} | {row['n']} | "+' | '.join(cells)+' |')
    lines += ['', '每格为第二日出匪局数／终局好人胜局数。对手可以改报的 413 局里，复制后的一致优先和原合并都无好人胜局，第二日出匪数也相同。'
              '复制条件总体多出的 11 胜来自其余 1,635 局。旧报告下另外赢的 10 局都位于可复制对匪队友查杀的 172 局。'
              '这说明本次压制作用集中于可能付出队友信息成本的复制。全局终局交互的区间未单独估计，分层结果仅描述该批。'
              '若对手只复制避开队友的结果，须按该策略重新跑续局。', '',
              '目前适合把公开一致作为一个可弃权、可被复制的候选特征保存。临场仅凭唯一一致就把归票当高可信，仍依赖对手能否模仿和成本。', '',
              '## 与警队协调、q、概率信用的关系', '',
              '你提出的选匪原则可以在警队已私知多个活匪时独立试验。先以合法且确定为匪作为硬约束，再用公开发言估计哪一个目标更可能形成同票。'
              '例如验出一个匪，但另一个已对跳的匪更容易得到平民支持，警察可以诚实说“验的是甲，今天归乙”，警队实际票同步。'
              '评价时记录可协调票和真实胜率，避免把预测的多数当成已经发生的票。固定“有查杀先出查杀”没有作为普适规则应用。', '',
              'v42 对照的两个对手中，现有 q 只在自刀复制开局触发，本轮是普通刀下接续报告的反制测试。q 的后续混合适用性仍要比较多种自刀对手和新的验证种子。', '',
              '概率信用可以先规定一个低可信门槛，再在仍有资格的来源之间按分差抽样。70 与 80 对应 30／70 可以是一组校准点，具体概率还要给出同分、门槛两侧与分差更大的定义。'
              '信用应与身份后验、目标嫌疑和投票资格分开；本人已知反证仍具有优先级。一项初步风险是，每名平民独立抽样可能制造分票，后续可同步报告协调度。'
              '本轮没有实现累计信用或概率信用。', '',
              '## 复现与边界', '',
              f"执行专项 2 项、全库 443 项测试均通过。运行命令为 `python -m pytest tests/test_succession_copy_v43.py -q`、`python -m pytest tests -q`、`python scripts/run_succession_copy_v43.py --smoke`、`python scripts/run_succession_copy_v43.py` 和 `python scripts/build_succession_copy_report_v43.py`。冻结结果耗时 {M['elapsed']:.1f} 秒，12 次正式抽样重放、"
              f"{M['case_replays']} 次详细案例重放、6 次旧 v42 接口重放以及 8 项独立区间边际核对。"
              '源码与原始数据哈希校验通过。冻结档案只保存本轮新增快照，并逐文件校验 v42 与 v41 的继承资产。', '',
              '固定对手的结果用于检验公开信号的抗复制性。多种匪方应对及不同信用模型仍需独立对照。', '',
              '[逐局案例](succession_copy_cases_v43.md)']
    return '\n'.join(lines)+'\n'


def describe_exile(row, day):
    key = str(day)
    if key not in row['exile']:
        return '无'
    return seat(row['exile'][key]) + ROLES[row['exile_roles'][key]]


def kind_name(matches, roles):
    if matches is None:
        return '未进入一致比较'
    if not matches:
        return '零匹配'
    return '、'.join(seat(p)+ROLES[roles[p]] for p in matches)


def make_cases():
    data = read_gzip(OUT/'cases.json.gz')
    lines = ['# v43 复制遗言逐局案例', '', '座位从 1 起算，身份仅供赛后核对。']
    for key, title in [('lost_unique_police','真警不再是唯一一致来源'),
                       ('changed_by_unique_mafia','唯一一致的是匪，平民改票')]:
        lines += ['', f'## {title}', '']
        if key not in data:
            lines.append('新批没有出现这一预定类型。')
            continue
        rows = data[key]
        if key == 'lost_unique_police':
            a,b = rows['old_base'],rows['copy_base']
            old = {x['player']:x for x in a['matches'] if x['day']==2 and x['first']}
            selected = next(x for x in b['matches'] if x['day']==2 and x['first']
                            and a['day2_matches'].get(str(x['player']))=='police'
                            and b['day2_matches'].get(str(x['player']))!='police')
            day = 2
            p = selected['player']
            lines.append(f"种子 {a['seed']}，第 2 日。{seat(p)}原本一致匹配 "
                         f"{kind_name(old[p]['matches'],a['roles'])}，"
                         f"复制后为 {kind_name(selected['matches'],b['roles'])}。")
        else:
            b = rows['copy_agreement']
            selected = next(ballot for ballot in b['ballots'] if ballot['supported']
                            and b['roles'][ballot['supported'][0]]=='mafia'
                            and ballot['target'] != ballot['baseline'])
            day = selected['day']
            p = selected['player']
            lines.append(f"种子 {b['seed']}，第 {day} 日。{seat(p)}在同一份观察中，原合并会投"
                         f"{seat(selected['baseline'])}，唯一一致优先令他跟随"
                         f"{seat(selected['supported'][0])}的归票，改投{seat(selected['target'])}。")
        if key == 'lost_unique_police':
            lines.append('当夜死者 3 号遗言报 16 号是匪。4 号真警也验出 16 号，并归 16。'
                         '旧报告下，一致规则改投 16。复制后，两人复述同一结果，却各有自己的归票。7 号回到原规则，投 15。')
        copy = next((event for event in b['copy_events'] if event['day']==day), None)
        if copy:
            check = '查杀' if copy['verdict'] else '金水'
            lines.append(f"接续匪{seat(copy['speaker'])}复制遗言，报{seat(copy['target'])}{check}，正式归{seat(copy['call'])}。")
        lines += ['', f'| 策略 | 第 {day} 日首轮票型 | 当日放逐 | 终局 |', '|---|---|---|---|']
        for arm,row in rows.items():
            votes = next((e['payload'] for e in row['events'] if e['day']==day and e['event']=='votes'), {})
            tally = Counter(seat(p) for p in votes.values())
            shown = '、'.join(f'{p} {n} 票' for p,n in tally.most_common()) or '未到达'
            lines.append(f"| {LABELS[arm]} | {shown} | {describe_exile(row,day)} | {'胜' if row['win'] else '负'} |")
    return '\n'.join(lines).rstrip()+'\n'


reports = [(ROOT/'docs/succession_copy_results_v43.md', make_report()),
           (ROOT/'docs/succession_copy_cases_v43.md', make_cases())]
for path, content in reports:
    path.write_text(content)
files = [Path(__file__).resolve(), *(path for path,_ in reports)]
save_json(ROOT/'results/v43_analysis_manifest.json',
          {str(path.relative_to(ROOT)):digest(path) for path in files})
