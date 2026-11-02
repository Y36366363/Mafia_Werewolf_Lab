#!/usr/bin/env python3
"""Read-only derived report; no strategy tuning or seed selection."""
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.restatement_experiment_v23 import save
from mafia_lab.dead_gold_experiment_v28 import MODES,PAIRS


def build():
    root=ROOT/'results/v28';f=json.loads((root/'freeze.json').read_text());cfg=f['config']
    phases={p:json.loads((root/(p+'.json')).read_text()) for p in ('train','holdout')}
    D={(c['good'],c['mafia']):c for c in phases['holdout']['cells']}
    T={(c['good'],c['mafia']):c for c in phases['train']['cells']}
    C={(c['comparison'],c['mafia'],c['branch']):c for c in phases['holdout']['contrasts'] if c['primary']}
    audit=json.loads((ROOT/'results/v28_evidence_audit.json').read_text())
    integrity=json.loads((ROOT/'results/v28_integrity_audit.json').read_text())
    examples=json.loads((ROOT/'results/v28_examples.json').read_text())
    validation=json.loads((ROOT/'results/v28_validation.json').read_text())
    names=sorted({c['mafia'] for c in phases['holdout']['cells']})
    pct=lambda p:'—' if p is None else f'{100*p:.2f}%'
    ci=lambda r:'['+', '.join(f'{v*100:+.2f}' for v in r['precision']['ci_simultaneous'])+']'
    net_equal={p:all(c['raw']['process_hash']==next(z for z in phases[p]['cells'] if z['good']=='reference_q'+c['good'].split('_q')[1] and z['mafia']==c['mafia'])['raw']['process_hash'] for c in phases[p]['cells'] if c['good'].startswith('evidence_')) for p in phases}
    sig=[]
    for key,c in C.items():
        if key[2]=='dead_clear' and 'precision' in c:
            lo,hi=c['precision']['ci_simultaneous']
            if lo>0 or hi<0:sig.append(dict(comparison=key[0],mafia=key[1],direction='positive' if lo>0 else 'negative'))
    lines=['# v28 完整方法与结果：首夜死警金水、后续信息与改归权限','',
      '2026-11-02。先给可读结论；策略字典在所有结果表前。信用分继续冻结，跳藏三档保留，金水假跳挡刀没有加入。','',
      '## 先看结论','',
      f'你的两个担心都得到单独检查。旧v27固定窗口2048对完整公开轨迹未见“胜负一样但过程不同”；但首夜死警验好人的432个条件局中，有60局金水听完后续发言后改变了自身目标。上一轮的零增量不能替代首日死警金水检验。','',
      f'新实验把“死警新增内推/委托”“金水最终归票”“有依据的改归规则”分开。新验收中，证据改归版与原参考版逐局行动过程是否完全相同：**{"是" if net_equal["holdout"] else "否"}**；开发批次相同检查：**{"是" if net_equal["train"] else "否"}**。过程指公开投票/出人/终局及警察夜验、匪刀，不包含两版本就不同的新增声明，也不等价于证明所有内部信息处理均正确。','',
      f'共同48项主要比较族中，死警分支24个比较里有{len(sig)}项区间排除0；方向和对照见下表。即使“list→evidence”提高胜率，也必须与原reference比较，不能把修复新内推带来的损失写成超过旧基线。','',
      '**具体发现：**死警新增的未决内推，可能与假警查杀重合，被旧“共同建议优先”规则错误集中到实际平民。名单内接力不能解开这个路径；有依据改归恢复了原参考动作。以decoy_far_claim为例，445个死警金水条件局中，reference→notice有278局过程不同，其中259局两边仍然都输；这正是只看终局会漏掉的局部伤害。观察胜局为29→10→29（reference→名单内接力→有依据改归），不是29→更多。上述胜率差的预设保守同时区间仍含0，故不宣称总体稳定效应。','',
      '金水接力继续保留，不因暂时没有超越基线而删除。其价值应来自更好的协调、合法的新信息或阻止错误控场，不能仅靠身份标签给它更高数值权重。','',
      '## 1. 策略与参数字典','',
      '| 名称 | 实际动作及对照关系 |','|---|---|',
      '| `reference` | 原v27 local：保留第二天起活警金水接力；首日死警只按旧规则报验人。是原始参考。 |',
      '| `notice` | 首夜死警验好人时，同一次遗言加二人内推和对该金水的明确委托；金水不新增最终归票。作为新增遗言信息/授权文本的组合对照。 |',
      '| `list` | 和notice相同遗言；普通发言完后，金水在最终槽用自身信息从原名单选人。自己已知匪全在名单外时可拒绝。 |',
      '| `evidence` | 和list相同归票时点/槽数；优先按新依据选人，可在名单内或名单外，否则保留名单内流程。 |',
      '| `q0 / q50 / q100` | 首日特定可选真警回应窗口0%/50%/100%；不是整局跳警率。首夜死警时此节点不出现，三档在该分支应一致。 |',
      '| `late / decoy` | 原safe_late位置刀 / posterior_decoy位置伪装刀；未改刀法或重新训练。 |',
      '| `near / far` | 首名匪早假查杀，选其后非己队中最近/最远发言位；匪不知道警民。 |',
      '| `restate / claim` | 原人活着重申，死后同伴不接续 / 原人死后同伴接续跳警提旧目标。两种都保留。 |',
      '| `_team` | 原队伍投票；无新倒钩或票型训练。 |',
      '| `dead_clear` | 评价分层：首死确实是警察且首验好人。玩家不会收到这个裁判标签。 |','',
      '例如 `evidence_q50 × decoy_far_restate_team`：使用有依据改归权限；原窄窗口50%回应；匪用位置伪装刀、远位假查杀、死后不接续。','',
      '没有新增信用分、怀疑权重或身份概率。q是行动概率；位置后验和旧排序继承冻结模型，没有用本轮结果校准。下面的“依据优先顺序”是离散策略设定，不是概率、加分或最优性证明。','',
      '## 2. 审计首先回答了什么','',
      '审计在新规则实现前固定取v27旧验收183000000—183000255，8匪列、base_q50/local_q50各跑一遍，共4096次完整运行。全部逐局胜负核对旧存档。删除新增delegate/relay内容后，2048对完整公开轨迹相同；未发现胜负抵消掩盖不同投票/出人链。这里只覆盖固定窗口，且旧验收已经查看，不能再当全新验证。','',
      '432个条件局中，金水被假查杀且发生在自身发言前的有28个；只在其发言后才被假查杀为0；自身回合目标与投票前目标改变的有60个；可见的来源自身硬矛盾为0。这些是跨策略条件记录，可共享同一基础seed，不是432个独立自然发牌。','',
      '例：旧seed183000002、late_near_restate，第1日死者3号验好11号。11号自己发言时倾向2号，听完后续发言后投票目标变为13号。11号原本可以改变私下的票，但不因此自动拥有一轮新的公开归票机会。该案例来自旧诊断，不作为新机制效果证据。','',
      '因此本轮list/evidence共同增加一个投票前最终归票槽。这个槽是明确的**研究协议资源**，不是声称标准桌游天然允许随时插话。两者之间比较有依据的改归规则包，既改变依据优先级又开放名单外对象；不能分离纯权限效果。本轮也没有单独识别最终槽与普通座位时点的差别。','',
      '## 3. 规则、信息与依据','',
      '4警4匪8民；警队互认、共同每夜一验；匪互认；警全灭匪胜、匪全灭好人胜。死亡不翻身份，前三死亡有遗言，公开顺序投票，可弃票，一轮PK复投再平则平安日。首夜被刀警拿到当夜验人。','',
      '死警的新增名单仅由自己的合法警队座位、首验和继承的位置后验排序产生，排除队友和金水；金水只拿到公开名单，不能拿到警队座位表或未公开验人。遗言report→shortlist→delegate必须同一时刻连续，之后不得补说。引擎只检查资格与模板，不认证来源身份。','',
      '金水最终决策只看当时自己的Observation。未被反证的委托及接力，被旁观者解释为原来源建议的更新；不增加一个独立警察来源，不把金水自动加入私人已知好人。对跳、其他来源以及私有硬事实仍由原路由处理。当天授权不跨日自动续指令。','',
      '名单外依据有三类：活来源自查自己是匪；同一来源对同一人报相反结果；首夜共享验人冲突。前两类在“真警如实报告、平民不假跳”的受限假设下直接反证来源，优先于第三类，同类用原排序。','',
      '**第三类必须条件化：**A遗言报B好，F报了不同的首夜验人；如果A是真警，F就不是真警。不能由此直接证明A真或F匪。金水可以据此提出对F的条件性改归，但其他玩家仍可怀疑A。校验只用relay发出前的消息，不用后续信息追认。','',
      '你的“真实金水至少由好人视角归票”成立于来源确真的条件。死亡不翻身份时，桌面玩家未必知道这个条件成立。本轮普通首刀池没有匪自刀，所以实际产生的遗言委托都是真警发出；这是候选池限制，不是程序鉴真。若额外把零自刀当作全场共同知道的事实，还能构造完全信任死者警察声明的基线；本轮没有穷尽这种池内推理，固定接收规则不能当理性最优。人工假遗言/假金水例中，普通平民可能接受，警队可凭己队信息拒绝，显示该机制尚不能抵御所有假授权。','',
      '金水假跳警挡刀暂不加入，因为它会改变“警队外跳警者是匪”的当前私人反证假设，双方推理都需重审。','',
      '## 4. 新实验设计与统计','',
      '方法范围更正：验收文件生成/读取前的代码审计发现，冻结方案“只比较权限”措辞过窄。evidence即使发现的对象在名单内，也会先用新增依据优先级。已另存[范围澄清](dead_gold_scope_clarification_v28.md)和未读取验收的检查点，未更改策略、seed、对照或统计。故本轮仅称“改归规则包”，不能把差值单独归因于名单外权限。','',
      f'正式{integrity["formal_games"]:,}次运行：12好人行×8匪列=96单元，开发每单元128局（185000000—185000127），全新验收每单元2048局（186000000—186002047）。跨策略共享2176个基础seed，不是208896次独立发牌。另有192局调试，187000000起，未进入正式结果。','',
      '策略、参数、比较与种子全部在开发/验收前冻结；开发批次只检查，不选择候选、q或阈值。开发与验收分离，未因结果搜索更多seed。首夜状态在全部配对中一致；新干预分支以外过程不变；死警分支三个q逐局过程相等。','',
      '主要比较为reference→notice、notice→list、list→evidence，q50下8匪列×3对照×总体/死警分支两范围，共48项族。翻转正/负两个边际二项率用Clopper–Pearson，union bound给名义同时95%区间，尾部α=0.05/(4×48)。这是有限样本策略收益的区间，不是均衡或收益矩阵无误差证书。','',
      '死警分支是首夜、干预前定义的固定条件，不按最终输赢选择。它样本量小于每格2048，下面明确分母。q0/q100用于总体敏感性；条件分支不重复当独立证据。','',
      '除胜负，保存首日出匪/出警/平安日/PK、接力与改票计数，以及包含所有投票/出人/终局与私有夜验/匪刀的过程哈希。不同政策实际续局轮次数可能不同，累计次数只作描述，不混成统一因果中介率。','',
      '## 5. 首夜死警验好人：验收主表（q50）','',
      '| 匪条件 | 分支局数 | reference | notice | list | evidence | evidence−reference百分点 |','|---|---:|---:|---:|---:|---:|---:|']
    for mn in names:
        vals=[D[m+'_q50',mn]['branch_win'] for m in MODES]
        lines.append('| '+mn+' | '+str(vals[0]['n'])+' | '+' | '.join(pct(v['rate']) for v in vals)+f' | {100*(vals[-1]["rate"]-vals[0]["rate"]):+.2f} |')
    lines += ['', '相邻对照及过程结果：区间单位为百分点；“同终局异过程”指同一配对seed两边都赢或都输，但投票/出人/夜行动不同。','',
      '| 匪条件 | 比较 | 胜率差 | 同时95%区间 | 负转胜/胜转负 | 异过程局数（其中同终局） |','|---|---|---:|---|---|---|']
    for mn in names:
        for a,b in PAIRS:
            c=C[a+'->'+b,mn,'dead_clear'];w=c['win']
            lines.append(f'| {mn} | {a}→{b} | {w["delta"]*100:+.2f} | {ci(c)} | {w["improved"]}/{w["worsened"]} | {c["process_different"]} ({c["same_terminal_different_process"]}) |')
    lines += ['',
      'evidence相对reference的净效应不是另加一组挑选比较。若需要保守总体区间，可将同一匪条件三个相邻差值区间相加（它们已在同一同时覆盖族内），得到合法但较宽的净效应区间；不能拿list→evidence的显著结果代替净改善。原始JSON保留总体和分支全部主区间。','',
      '## 6. 授权、采纳与名单外改归','',
      '以下q50，每格为局数或实际投票次数。这些新遗言接力仅发生于dead_clear分支；相同局的多名玩家采纳会重复计票，不是额外样本。'
      ,'“evidence改变票数”指：同一个已经包含新遗言名单的Observation里，启用/关闭死者接力解释时，投票建议是否改变。这是局部影子对照，不是相对reference从头运行的票差。因此可能局部改票很多，而最终完整行动重新回到reference。'
      ,'原始day1_shortlist沿用旧定义，只统计普通发言扩展中的名单；本轮遗言名单另由grant_game统计，不能把旧字段零值误读为没有新增内推。','',
      '| 匪条件 | 遗言授权局 | list接力局 | evidence接力局 | evidence名单外局 | evidence改变票数 |','|---|---:|---:|---:|---:|---:|']
    for mn in names:
        a,b=D['list_q50',mn]['raw'],D['evidence_q50',mn]['raw']
        lines.append(f'| {mn} | {sum(a["grant_game"])} | {sum(a["gold_call_game"])} | {sum(b["gold_call_game"])} | {sum(b["outside_call_game"])} | {sum(b["changed_ballots"])} |')
    lines += ['', '## 7. 总体表现及跳藏敏感性','',
      '保留不接续列，不只报告claim。以下为q50全2048局，不混成死警分支条件胜率。','',
      '| 匪条件 | reference | notice | list | evidence |','|---|---:|---:|---:|---:|']
    for mn in names:lines.append('| '+mn+' | '+' | '.join(pct(D[g+'_q50',mn]['win']['rate']) for g in MODES)+' |')
    lines += ['', '每个q的最低观测总体胜率（预定8匪列内；不是任意策略下的理论下界，不据此选最佳q）：','',
      '| 版本 | q0 | q50 | q100 |','|---|---:|---:|---:|']
    for mode in MODES:lines.append('| '+mode+' | '+' | '.join(pct(min(D[mode+'_q'+q,m]['win']['rate'] for m in names)) for q in ('0','50','100'))+' |')
    lines += ['', '开发批次对应死警分支率（每格仅约数十局，用于流程检查，不能代替验收）：','',
      '| 匪条件 | 分支局数 | reference | notice | list | evidence |','|---|---:|---:|---:|---:|---:|']
    for mn in names:
        vals=[T[m+'_q50',mn]['branch_win'] for m in MODES]
        lines.append('| '+mn+' | '+str(vals[0]['n'])+' | '+' | '.join(pct(v['rate']) for v in vals)+' |')
    lines += ['', '## 8. 完整案例及解释边界','',
      f'按冻结规则选择每种刀×接续×三个相邻比较的首个负转胜、胜转负、同终局异过程案例；不存在则null。得到{examples["detail_runs"]}个去重条件轨迹，另{examples["direct_replays"]}次无包装器重放，均对齐原始逐局记录。这些是已测数据的解释，不是新验证集。','',
      '查看完整案例时，应分开：原遗言内容改变了谁的候选；最终接力是否真正改变票；改归依据是否在当时可见；同胜负背后的白天出人及夜间行动是否改变。不能以“都输了”否认局部伤害，也不能以“改归后赢了”跳过原参考版本。','',
      '## 9. 验证、限制与下一步','',
      f'- 实际 `python -m pytest tests -q`：{validation["tests"]["passed"]} passed，{validation["tests"]["elapsed_seconds"]}秒；新增11项，覆盖连续遗言权限、前缀信息、条件冲突/硬反证区分、假来源、未知角色置换、PK合法性、旧控制兼容和q节点。',
      f'- 实际 `python scripts/run_dead_gold_v28.py --workers 4`：{integrity["formal_games"]:,}次正式运行；过程和配置冻结；运行时间见manifest。',
      f'- 实际 `python scripts/verify_dead_gold_v28.py`：{integrity["cells_checked"]}单元全结构/统计核查、{integrity["direct_sample_replays"]}次首中末抽样无包装器重放、{integrity["v27_compatibility_replays"]}次v27参考兼容、{integrity["independently_checked_intervals"]}个区间用独立binomtest接口复核、{integrity["frozen_assets"]}冻结资产哈希。不是全部正式运行重做。',
      '- 全部正式记录未见非法票、忽略合法私有活匪、投私有已知好人；这些检查不能保证所有公共推理优先级最优或完整。',
      '- 冻结前试运行暴露旧引擎把遗言限定为一条模板，导致内推/委托组件被拒绝；新增同一连续遗言字段校验，仍禁止第二次发言、迟到补说。修复了实验函数局部变量遮蔽opening调用，均在正式冻结前。',
      '- 候选匪不会自刀/假金水授权，也不专门针对金水改夜刀；所有列首日都早悍跳，“不接续”只指原人死后的续局，不等于首日不跳。首日沉默/非跳警式控场尚未覆盖；共享首验和如实报告假设仍有限制。不能声称金水身份被认证、该协议抗任意反制或真人胜率如此。',
      '- 没有求新矩阵均衡、没有选最优q、更不是完整GTO。警察临场语言、公开怀疑和跨日票型仍简化；无校准信用分，也未接入LLM。','',
      '下一步建议先把“内推只是备选”与“正式归票/查杀”分层，再复查有分歧的来源建议是如何合并的：如果一个真来源的未决名单与假来源的查杀碰巧重合，旧“共同建议优先”是否压过了它们叙述上的冲突？这是公共信息采纳策略的问题，不等于程序偷看身份。先用本轮具体案例解释，再决定是否单独消融；不在本轮顺手改接收优先级后重用同一验收。','',
      '保留金水接力及跳藏变量；后续分开处理来源相容性、首日匪沉默对照、假遗言授权/自刀、可持续跨日委托、正常座位接力与最终槽时点、PK联动、信用分独立比较、票型/公开怀疑、遗言制度以及假跳挡刀。','',
      '```sh','python -m pytest tests -q','python scripts/audit_gold_evidence_v28.py',
      'python scripts/run_dead_gold_v28.py --output results/v28_reproduction --workers 4',
      'python scripts/verify_dead_gold_v28.py','python scripts/diagnose_dead_gold_v28.py','python scripts/build_dead_gold_report_v28.py','```','',
      '未来使用冻结决策重跑：','', '```sh','cd results/v28/source','python scripts/run_dead_gold_v28.py --output ../../v28_reproduction --workers 4','```','',
      '旧审计脚本拒绝覆盖；其来源指纹为v27（正式新实现前），不应拿当前主分支重算旧审计而声称同一版本。新实验保存完整source快照；未来复现应使用冻结源码。验证/案例脚本默认核查results/v28，报告生成是另存哈希的派生分析。','',
      '材料：[冻结方案](dead_gold_protocol_v28.md)、[审计范围](gold_evidence_audit_scope_v28.md)、[旧过程审计](../results/v28_evidence_audit.json)、[配置](../configs/dead_gold_v28.json)、[原始验收](../results/v28/holdout.json)、[完整案例](../results/v28_examples.json)、[核验](../results/v28_integrity_audit.json)。']
    explanations=json.loads((ROOT/'results/v28_case_explanations.json').read_text())
    pos=lines.index('## 9. 验证、限制与下一步')
    extra=['### 预选案例中的实际接收路径','']
    role={'police':'警','mafia':'匪','civilian':'民'}
    for story in explanations['stories']:
        extra += [f"**{story['kind']}：seed{story['seed']}，{story['mafia']}。**",'',
          f"{story['source']}号死警验好{story['gold']}号，新增内推{'/'.join(map(str,story['shortlist']))}；{story['fake']}号悍跳查杀{story['false_hit']}号。假查杀目标恰好在内推里。notice中{'/'.join(map(str,story['common_recommendation_receivers']))}号平民的记录理由变为共同建议优先，和reference的目标不同。",'',
          '| 版本 | 首日放逐 | 金水最终归票 | 后续白天出人（座位+实际身份） | 终局 |','|---|---|---|---|---|']
        for mode in MODES:
            v=story['variants'][mode];first='平安日' if v['first_day_exile'] is None else str(v['first_day_exile'])+role[v['first_day_exile_role']]
            call='无' if v['gold_call'] is None else str(v['gold_call']['target'])+('（名单外）' if v['gold_call']['outside'] else '（名单内）')
            chain=' → '.join(str(z['day'])+'日'+str(z['seat'])+role[z['role']] for z in v['day_exiles'][:6])
            extra.append('| '+mode+' | '+first+' | '+call+' | '+chain+' | '+('好人胜' if v['win'] else '好人负')+' |')
        extra += ['', '这显示的是接收策略的优先级：系统把来源建议的交集作为集中目标；新增内推可能与假查杀形成共同目标，从而改变放逐。来源叙述冲突并未在此路径中优先处理。evidence重新指向冲突来源，可恢复原参考轨迹。它不是私有信息权限违规的证明，也不表示“建议重合一概应忽略”；其他匪策略和假遗言仍需独立比较。','']
    extra += ['完整记录含票型与每夜夜验/刀：[案例解释数据](../results/v28_case_explanations.json)。该解释只读取预先选定的案例，没有新跑模拟；案例选择和结果不能代替总体区间。','']
    lines[pos:pos]=extra
    report=ROOT/'docs/dead_gold_results_v28.md';report.write_text('\n'.join(lines)+'\n')
    files=[report,Path(__file__),ROOT/'results/v28_integrity_audit.json',ROOT/'results/v28_examples.json',ROOT/'results/v28_validation.json',ROOT/'docs/dead_gold_scope_clarification_v28.md',ROOT/'results/v28_scope_clarification_checkpoint.json',ROOT/'scripts/explain_dead_gold_cases_v28.py',ROOT/'results/v28_case_explanations.json']
    save(ROOT/'results/v28_analysis_manifest.json',dict(files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files},
         significant_branch_comparisons=sig,net_process_equal=net_equal,
         note='Derived presentation only, frozen decision package unchanged.'))
    print(report)


if __name__=='__main__':build()
