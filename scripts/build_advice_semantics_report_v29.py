#!/usr/bin/env python3
"""Read-only factorial report; no policy selection or new simulations."""
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.advice_semantics_experiment_v29 import PROFILES,PAIRS
from mafia_lab.restatement_experiment_v23 import save


def build():
    phases={p:json.loads((ROOT/'results/v29'/(p+'.json')).read_text()) for p in ('train','holdout')}
    D={(c['good'],c['mafia']):c for c in phases['holdout']['cells']}
    T={(c['good'],c['mafia']):c for c in phases['train']['cells']}
    C={(c['comparison'],c['mafia']):c for c in phases['holdout']['contrasts'] if c['primary']}
    names=sorted({c['mafia'] for c in phases['holdout']['cells']})
    audit=json.loads((ROOT/'results/v29_integrity_audit.json').read_text())
    val=json.loads((ROOT/'results/v29_validation.json').read_text())
    cases=json.loads((ROOT/'results/v29_examples.json').read_text())
    pct=lambda v:'—' if v is None else f'{100*v:.2f}%'
    interval=lambda c,k:'['+', '.join(f'{100*v:+.2f}' for v in c[k+'_precision']['ci_simultaneous'])+']'
    branch_mean=lambda g,m,k:sum(v for v,z in zip(D[g,m]['raw'][k],D[g,m]['raw']['dead_clear']) if z)/sum(D[g,m]['raw']['dead_clear'])
    equivalent={g:all(D['anchor',m]['raw']['process_hash']==D[g,m]['raw']['process_hash'] for m in names) for g in ('typed','guard','both')}
    significant={k:[dict(comparison=c['comparison'],mafia=c['mafia'],direction='positive' if c[k+'_precision']['ci_simultaneous'][0]>0 else 'negative') for c in C.values() if c[k+'_precision']['ci_simultaneous'][0]>0 or c[k+'_precision']['ci_simultaneous'][1]<0] for k in ('win','day1_mafia_exile')}
    lines=['# v29 完整方法与结果：内推备选、正式建议与来源冲突','',
      '2026-11-03。本轮只做已定问题的接收器消融；不训练信用分、不扩匪池、不优化跳藏、不求新均衡。','',
      '## 先看结论','',
      '相同信息并不保证相同判断：原先零增量只限于那几套接力规则在那些样本中的行为重复，不能推导“没有新增信息就不会有改进”。这次改变已有信息的合并，已经改变行动和部分终局。','',
      '本轮把“分清声明类型”和“检查共同建议来源是否相容”做成两个独立开关。同一局四个消融版本在首次投票前看到完全相同的公开内容，因此不是靠增加警察信息或发言次数制造差异。','',
      f'在新验收批次中，typed/guard/both是否分别恢复原anchor的完整行动轨迹：**{'两个单开及双开均与原参考同轨' if all(equivalent.values()) else str(equivalent)}**。这里比较的是公开投票、放逐、终局和私有夜验/匪刀，不包括本来就不同的遗言内容；有限样本相同不是所有历史的等价定理。','',
      f'80项共同主要比较族中，终局胜率有{len(significant["win"])}项区间排除0；首日出匪率有{len(significant["day1_mafia_exile"])}项区间排除0。首日出匪是可解释的局部过程指标，不能写成当时局面胜率已经提高；终局不显著也不能证明没有作用。','',
      '这2项终局结果来自同一匪列的plain→typed和plain→guard；16项首日结果是8列各两个替代修正。两种单开走的是相同样本轨迹；restate/claim只在后续分叉，同一刀法×目标的首日样本也重复，8列对应4种首日情境。不能将这些记录说成多组独立复现或16次独立实验。','',
      '核心解释：仅有“我怀疑C/D”和另一来源“我查杀C”，不应直接包装成两份明确归票；即使两人都明确要出C，也仍要看两人的验人叙述能否同时为真。两个开关若覆盖同一错误，收益不能再加一次。','',
      '一个清楚的预定条件是decoy_far_claim：502局首夜死警验金水，旧接收器首日出匪153局，单开修正后467局（30.48%→93.03%）；终局13胜→52胜（2.59%→10.36%，差+7.77个百分点，同时95%区间[+2.40,+12.95]）。但本批anchor本来就有52胜，所以是修复损失，没有超过原参考。','',
      '## 1. 参数与策略字典','',
      '| 行名 | 内推/委托 | 类型开关 | 冲突开关 | 实际含义 |','|---|---|---|---|---|',
      '| `anchor` | 无新增 | 关 | 关 | v28 reference，死警只按原规则报验人，作为净效果参考。 |',
      '| `plain` | 有 | 关 | 关 | v28 notice，旧接收器会把备选名单和查杀的交集当优先共同目标。 |',
      '| `typed` | 和plain相同 | 开 | 关 | 含备选名单的重合先不当明确共同归票，先比较已有来源冲突；无冲突时仍可用软重合。 |',
      '| `guard` | 和plain相同 | 关 | 开 | 来源报告不相容时，不让建议交集抢先于冲突比较。 |',
      '| `both` | 和plain相同 | 开 | 开 | 两个开关同时启用，检验覆盖重叠/互补。 |','',
      '| 名称 | 含义、来源与限制 |','|---|---|',
      '| `typed_advice / conflict_guard` | 两个布尔协议开关，不是概率、信用分或身份置信度，没有加分/累积/阈值。 |',
      '| `shortlist` | 内推备选池，不保证成员是匪，也不承诺今天一定从中出。 |',
      '| `claimed_hit` | “我验X是匪”的公开声明；仅在来源真且如实报告的条件下为事实，不自动进入旁观者私人已知匪。 |',
      '| `execution` | “今天出X”的正式执行建议/有效受托接力。意图明确，但不保证X身份；同一来源归票优先于较早的查杀目标。 |',
      '| `q0/q50/q100` | 原窄首日窗口的可选回应概率0/50/100%，仍可配置；主实验q50。处理分支首夜死警，q节点不出现，单元测试核对三档过程一致，没有重新测三档总体最优。 |',
      '| `late / decoy` | 原safe_late位置刀 / posterior_decoy位置伪装刀。 |',
      '| `near / far` | 首名匪早悍跳，给其后非队友最近/最远发言位发假查杀。 |',
      '| `restate / claim` | 原假警活着重申、死后同伴不接续 / 原人死后同伴接续跳警。首日均早悍跳，没有首日沉默列。 |',
      '| `_team` | 原匪队投票，未针对新规则重新训练。 |','',
      '例如typed×decoy_far_restate_team：区分声明类型、不检查共同建议的来源相容性；匪用位置伪装刀、远位假查杀、死后不接续。','',
      '## 2. 实际规则：区分什么，保留什么','',
      '冲突开关关不等于完全不考虑冲突：旧接收器在没有优先共同建议时也有来源冲突比较。typed把含软名单的重合移到这个已有步骤之后；guard则给所有共同目标额外加相容性门。因此两个开关可在同一路径上重复覆盖，但不是完全相同的代码条件。','',
      '来源自己的当前合法执行建议优先于自己的查杀声明，查杀优先于尚未归票的备选名单。这个次序沿用原模型，本轮只改变跨来源合并。执行建议从来不等同于验人结果。两者在共识门都算单一明确目标，但本轮没有重新优化归票与查杀彼此的优先顺序。','',
      'typed开：只要共同目标中有来源仅给了备选名单，就暂不让交集抢先；先用原来源冲突比较。若没有可比较冲突，名单重合仍可作为备选破同分，理由标为soft_overlap_fallback，不升级成身份事实。','',
      'guard开：共同目标的来源间有公开不相容边，就阻止该交集抢先及再次作为软重合返回；保留所有来源和建议，继续原冲突/并集备选流程，不把任何一人认证成真警或匪。','',
      '人工区分例：A只内推C/D，F查杀C，typed或guard都可能阻止旧共同目标。若A的金水已合法接力出C，A就有明确执行建议；typed允许将两个明确目标视为共同建议，但guard仍会检查A/F的报告是否相容。这种人工合法声明用于权限与方法校验，不是主池里新增了一个策略列。','',
      '兼容的明确建议仍可共同归票；没有冲突的软名单仍可供参考。相容不是认证：假来源可以复制公开金水、避免报告矛盾后再建议错误目标，本轮匪池未执行这种反制。私人合法已知匪、私人好人保护、金水保护、PK候选合法性都先于合并规则，声明强硬程度不改变这些事实。','',
      '## 3. 处理范围与信息控制','',
      '4警4匪8民，警互认共同每夜一验；匪互认；警全灭匪胜、匪全灭好人胜；死亡不翻身份，前三个死亡有遗言，公开顺序投票，可弃票，一轮PK再平为平安日。','',
      '只在第1日、玩家自身视角存在有效首死金水委托时应用新规则；触发使用公开报告和自己能否反证来源，不输入裁判身份标签。第二日起完全沿用v28；处理分支外也保持原行动。这里延用的“比较存活冲突来源”是行动策略，不是因为另一来源死亡便证明他是假警，不恢复次日起机械轮出。','',
      '四个消融版本拥有相同真实验人、相同内推/委托、相同全部首次投票前发言；不新增最后归票槽。anchor没有新内推/委托，比较它只回答净效果参考问题。','',
      '本轮固定dead_gold=notice以免稍后接力把软名单升级成正式目标、掩盖两个开关的差异。金水机制保留：原v27第二天起活警接力不动；v28首日金水接力/有依据改归代码不删，人工测试包含合法relay的类型。重新把它接回主实验是下一阶段，而非本轮已测结论。','',
      '信用和票型权重冻结，没有新信用分、额外验人信息、LLM或阵营秘密相关装置。警察私有记忆和角色知晓权限不变。','',
      '## 4. 冻结实验与统计','',
      f'5行×8列=40单元。开发188000000—188000127，每格128；新验收189000000—189002047，每格2048。共{audit["formal_games"]:,}次实际模拟，2176个基础seed跨版本配对；不是87040次独立发牌。另调试190000000起80次，不进入正式结果。','',
      '每个匪列内按同seed实际跑五个接收器，仅复用确定性似然缓存，不复制“预计等价”的整局。无审计器与旧版本兼容重放检查这种执行顺序。开发不筛候选/q/阈值，验收一次冻结，不追加seed或对手。旧186000016仅作已查看的开发单元案例，不作新确认。','',
      '预定五对：plain→typed、plain→guard、typed→both、guard→both、anchor→both；主要范围是干预前首死警且首验好的固定分支。每对×8列×终局胜与首日出匪两个共同主要指标=80项同时比较；配对正/负翻转率的Clopper–Pearson区间加union bound，名义同时95%，尾部α=.05/(4×80)。总体表现另作描述，不把它当另一组独立确认。','',
      '同seed配对不保证对每个指标都降低误差；本轮直接对配对翻转构造区间，不凭直觉宣称降噪。矩阵或概率计算精确不等于模拟收益无误差。','',
      '## 5. 新验收：终局与首日分别看','',
      '以下均为首夜死警验金水的条件分支；分母列清楚，不能把这些率当整体448胜率。','',
      '| 匪条件 | 分支局数 | anchor | plain | typed | guard | both |','|---|---:|---:|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+str(D['plain',mn]['branch_win']['n'])+' | '+' | '.join(pct(D[g,mn]['branch_win']['rate']) for g in PROFILES)+' |')
    lines += ['', '相同条件下首日出匪率：','', '| 匪条件 | anchor | plain | typed | guard | both |','|---|---:|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+' | '.join(pct(branch_mean(g,mn,'day1_mafia_exile')) for g in PROFILES)+' |')
    lines += ['', '五对主要比较：差值/区间单位都是百分点，两个指标共同做80项同时覆盖。','',
      '| 匪条件 | 比较 | 终局差及区间 | 首日出匪差及区间 | 同终局但异过程局数 |','|---|---|---|---:|']
    for mn in names:
        for a,b in PAIRS:
            c=C[a+'->'+b,mn]
            lines.append(f'| {mn} | {a}→{b} | {100*c["win"]["delta"]:+.2f} {interval(c,"win")} | {100*c["day1_mafia_exile"]["delta"]:+.2f} {interval(c,"day1_mafia_exile")} | {c["same_terminal_different_process"]} |')
    lines += ['', '## 6. 覆盖重叠与过程指标','',
      '交互=both−guard−typed+plain。区间由guard→both区间减plain→typed区间得到，沿用原80项同时覆盖，不另挑显著指标。负交互可能仅表示两个单开阻止同一错误，不能解读成双开伤害。','',
      '| 匪条件 | 终局交互百分点及保守区间 | 首日出匪交互百分点及保守区间 |','|---|---|---|']
    interactions=[]
    for mn in names:
        row=dict(mafia=mn);parts=[]
        for k in ('win','day1_mafia_exile'):
            a=C['plain->typed',mn];b=C['guard->both',mn]
            lo=b[k+'_precision']['ci_simultaneous'][0]-a[k+'_precision']['ci_simultaneous'][1]
            hi=b[k+'_precision']['ci_simultaneous'][1]-a[k+'_precision']['ci_simultaneous'][0]
            point=b[k]['delta']-a[k]['delta'];row[k]=dict(delta=point,derived_ci=[lo,hi])
            parts.append(f'{100*point:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}]')
        lines.append('| '+mn+' | '+' | '.join(parts)+' |');interactions.append(row)
    lines += ['', '次日结束前累计出匪数/警察存活数是资源指标，不是局面胜率；实际存活轨迹和信息随政策变化，不从这两个数直接推断优势。','',
      '| 匪条件 | plain累计出匪 | both累计出匪 | plain警存活 | both警存活 |','|---|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+' | '.join(f'{branch_mean(g,mn,k):.3f}' for k in ('mafia_eliminated_by_day2','police_alive_after_day2') for g in ('plain','both'))+' |')
    lines += ['', '资源方向也不总一致：例如late_far_claim，次日累计出匪均值1.410→1.505，而警存活2.570→2.560。它们是描述性差异，不是额外显著性检验；不能只取有利指标就宣称局面价值更高。','',
      '某次两边都输，不能证明两条中间路径的条件胜率相同；中间多出一匪也不能单独证明条件胜率提高。若将来要估计局面价值，需另冻结共同续局策略、信息权限和随机续局方法。本轮没有做该价值估计。','',
      '## 7. 全体448对局与开发检查','',
      '总体每格2048，包含不受新规则干预的分支；不接续列全部保留。跨日期参考率也会因新seed变化；本轮原参考在decoy_far_claim条件为10.36%，上轮6.52%，不能将跨批差值当模型改进，归因必须看本轮配对。','',
      '| 匪条件 | anchor | plain | typed | guard | both |','|---|---:|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+' | '.join(pct(D[g,mn]['win']['rate']) for g in PROFILES)+' |')
    lines += ['', '开发批次条件胜率（每格分支仅数十局，仅流程检查；参数未按此选择）：','',
      '| 匪条件 | 分支局数 | anchor | plain | typed | guard | both |','|---|---:|---:|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+str(T['plain',mn]['branch_win']['n'])+' | '+' | '.join(pct(T[g,mn]['branch_win']['rate']) for g in PROFILES)+' |')
    lines += ['', '## 8. 具体接收路径与案例','',
      f'冻结规则挑每对×刀法×是否接续的首个负转胜、胜转负、同终局异过程，缺失则null。得到{cases["detail_runs"]}个条件轨迹，另{cases["direct_replays"]}次无包装器重放；不是新验证样本。','']
    EX={(c['good'],c['mafia'],c['seed']):c for c in cases['cases']}
    for kind in ('gain','same_terminal_different_process'):
        selection=sorted([c for c in cases['selected'] if c['comparison']=='plain->typed' and c['kind']==kind and c['seed'] is not None],key=lambda c:(c['seed'],c['mafia']))
        if not selection:continue
        item=selection[0];mn,seed=item['mafia'],item['seed'];plain=EX['plain',mn,seed]
        pool=next(m['targets'] for m in plain['extensions'] if m['kind']=='shortlist')
        lines += [f'**{kind}：seed{seed}，{mn}。**','',
          f'{plain["raw"]["first_dead"]+1}号死者报{plain["raw"]["first_check"]+1}号金水，内推'+ '/'.join(str(p+1) for p in pool)+f'；{plain["raw"]["fake_speaker"]+1}号悍跳查杀{plain["raw"]["fake_target"]+1}号。下面座位1起编号，身份是裁判事后说明，玩家未看到翻牌。','',
          '| 版本 | 首日放逐 | 终局 | 首次公开合并改变（若有） |','|---|---|---|---|']
        for g in PROFILES:
            row=EX[g,mn,seed];victim=next((e['payload']['victim'] for e in row['transcript'] if e['day']==1 and e['event']=='day_death'),None)
            exile='平安日' if victim is None else str(victim+1)+'号'+{'police':'警','mafia':'匪','civilian':'民'}[row['roles_evaluation_only'][victim]]
            change=next((v for v in row['votes'] if v['changed']),None)
            why='无' if change is None else str(change['player']+1)+'号：'+change['reason']
            lines.append('| '+g+' | '+exile+' | '+('好人胜' if row['raw']['win'] else '好人负')+' | '+why+' |')
        lines += ['', '列表与查杀的交集不再自动抢先于来源冲突；没有给玩家增加验人或认证金水。完整票型、逐票类型/冲突字段与每夜夜验/刀保留在案例JSON。','']
    lines += ['## 9. 验证、解释边界与下一步','',
      f'- 实际 `python -m pytest tests -q`：{val["tests"]["passed"]} passed，{val["tests"]["elapsed_seconds"]}秒，新增12项；涵盖语义/相容性独立场景、兼容建议、私人事实/PK、未来消息、未知身份置换、旧案例、独立执行与q节点。',
      f'- 实际 `python scripts/run_advice_semantics_v29.py --workers 4`：{audit["formal_games"]:,}次实际运行；冻结完整决策包、配置与本轮测试。',
      f'- 实际 `python scripts/verify_advice_semantics_v29.py`：{audit["cells_checked"]}单元结构/统计核对；{audit["direct_sample_replays"]}次首中末抽样完整重放；{audit["v28_compatibility_replays"]}次anchor/plain与v28兼容；{audit["independently_checked_intervals"]}个区间用独立binomtest复核；{audit["frozen_assets"]}冻结资产哈希。不是全部87040次独立重跑。',
      '- 全记录验证4个消融版首次投票前公开轨迹相同、干预外分支行动相同；非法票/忽略合法私有活匪/投私人好人/未计划金水最终槽均为0。',
      '- 主池没有冲突来源都给正式目标的丰富场景，故两个机制在这个池中相同，不证明它们理论上等价；区别在人工合法信息集里验证，不能将其冒充新的大局实证。',
      '- 相容性判断依赖共同首验、真实警察如实报告、平民不假跳的受限假设；允许警队假报队友金水或加入自刀/假授权后需重审。来源可被怀疑，不由死亡或建议类型认证。',
      '- 所有匪列首日早悍跳；不含首日沉默、针对内推重新选假查杀、伪造金水授权或针对新接收器重新训练。当前是固定候选策略评估，不能宣称抗任意反制、人体玩家效果或完整GTO。',
      '- 本轮没有用LLM，没有新增均衡证书。q三档保留但新主样本仅q50，不声称重新优化了跳藏。','',
      '下一步建议先把金水接力接回同一套接收器，检查它是否把软名单又升级成冲突来源的正式共同建议，并审计公开归票与实际票是否一致；同步设计匪复制死者金水后发错误正式归票、假遗言授权/首日不悍跳的小对照。在这些基础上再讨论信用和更复杂票型，不在同一验收批次继续调规则追数字。金水假跳挡刀、跨日委托、公开怀疑、遗言制度继续分开待办。','',
      '```sh','python -m pytest tests -q','python scripts/run_advice_semantics_v29.py --output results/v29_reproduction --workers 4','python scripts/verify_advice_semantics_v29.py','python scripts/diagnose_advice_semantics_v29.py','python scripts/build_advice_semantics_report_v29.py','```','',
      '未来主分支变动后使用冻结源码：','', '```sh','cd results/v29/source','python scripts/run_advice_semantics_v29.py --output ../../v29_reproduction --workers 4','```','',
      '报告生成脚本为只读派生分析，另存哈希；不属于正式决策冻结包。验证/案例默认读取原results/v29。完整旧测试套件保存在本阶段Git提交；冻结source包含完整决策包和本轮新增测试，不等于所有历史测试目录。','',
      '材料：[冻结方案](advice_semantics_protocol_v29.md)、[配置](../configs/advice_semantics_v29.json)、[原始验收](../results/v29/holdout.json)、[冻结资产](../results/v29/freeze.json)、[核验](../results/v29_integrity_audit.json)、[完整案例](../results/v29_examples.json)。']
    report=ROOT/'docs/advice_semantics_results_v29.md';report.write_text('\n'.join(lines)+'\n')
    files=[report,Path(__file__),ROOT/'results/v29_integrity_audit.json',ROOT/'results/v29_validation.json',ROOT/'results/v29_examples.json']
    save(ROOT/'results/v29_analysis_manifest.json',dict(files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files},
        empirical_process_equal_to_anchor=equivalent,significant=significant,interactions=interactions,
        note='Read-only derived analysis; frozen policies and seeds unchanged.'))
    print(report)


if __name__=='__main__':build()
