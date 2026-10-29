#!/usr/bin/env python3
"""Render frozen evaluation and diagnostics; does not modify or select policies."""
import json
from pathlib import Path
from math import log,sqrt
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
f=load('results/v24/freeze.json');tr=load('results/v24/train.json');ho=load('results/v24/holdout.json');sel=load('results/v24/selection_before_holdout.json');man=load('results/v24/manifest.json');audit=load('results/v24_integrity_audit.json');ex=load('results/v24_examples.json');precision=load('results/v24_paired_precision.json')
lookup={(c['good'],c['mafia']):c for c in ho['cells']}
bases=('late_near','late_far','decoy_near','decoy_far')
labels=dict(late_near='后置刀／近端假查杀',late_far='后置刀／远端假查杀',decoy_near='伪装刀／近端假查杀',decoy_far='伪装刀／远端假查杀')
P=lambda x:f'{x*100:.2f}%'
PP=lambda x:f'{x*100:+.2f}'
CI=lambda xs:'['+', '.join(PP(x) for x in xs)+']'
lines=[]
def add(s=''):lines.append(s)
add('# v24：接续反制是否触达原本可赢的路径？')
add('\n2026-10-29。规则、候选与种子在正式训练前冻结；本报告区分接续机会、局部行动损害和终局胜率。')
add('\n## 策略／参数字典（先读这部分）')
add('\n|名称|具体动作与继承关系|\n|---|---|')
for a,b in [
('repair_q0 / repair_q50 / repair_q100','两项续局修复、私人记忆、来源无数值信用的路由不变；仅在规定窄条件下，首位真警以0% / 50% / 100%概率回应假警。数字是行动概率，不是身份或信用。'),
('quiet','原固定匪续局，仍刀人、投票和发言，不特意重申旧假查杀。'),
('restate','原悍跳活着、旧目标活着：自己在普通发言扩展重申今天出旧目标。'),
('support','保留restate；原悍跳死后，首位活匪仅说“今天出旧目标”；普通占位不改，不自行跳警。'),
('claim','同support的触发、说话者、目标及accuse扩展；普通占位改成“我跳警”。不报新验人。'),
('late / decoy','safe_late位置刀 / posterior_decoy伪装刀；最高分合法刀中随机破同分。不是随机刀。'),
('near / far','首日首位匪在自己后续发言的非队友中，选最近 / 最远者假查杀；不知道这个人是警还是民。'),
('trained_local_q','仅由训练的两个端点×16匪列选出，留出前冻结。若等于现有行，只引用同一行，不重复计局。')]:add(f'|{a}|{b}|')
add('\n**q何时生效：** 首夜未死警、预定首警还没发言、已出现假警且查杀未中警队时，只有这一名警在自己的轮次抽一次。q0不是全游戏永远藏，q100不是全警队跳；被打中警队的必答分支不由q控制，也不机械拉第二警。')
add('\n**数值与权限：** q是人工定义的端点/对照概率，0至1，不积累、不更新；训练选出的有理数q也仅作用于这个单节点。信用分未重新启用。原位置后验的等权假设、2%似然扰动、gap验人和二人内推沿用：2%在好人假定的刀似然中，并未加到实际匪刀。位置怀疑排序、建议来源资格和最终投票是不同模块，不是统一身份概率。')
add('\n兼容字段source_credit=True仍保留，但实际routing=evidence不调用数值信用投票分支；history=False只关闭旧票型加分，remember=True仍保存跨日私人反证，公开消息也未删除。\n\n所有动作由固定程序及决策键随机数产生，不用LLM实时推理。规则仍为4警4匪8民、警互认并共享夜验、死亡不翻身份、前三死亡有遗言、可弃票、一轮PK后再平票则平安日。本池无平民假跳、真警乱报或自刀策略；这些是当前结论的前提与边界。')
add('\n## 本轮先回答三个问题')
add('\n1. **反制现在确实覆盖原本能赢的支路。** 固定q50的四组中，约89%—95%的原获胜局出现接续机会；接续跳警使总体好人胜率下降约3.2—8.6个百分点。四项同时95%的二项补充区间均排除零。')
add('2. **问题集中在当前来源与归票协议。** 队友只建议旧目标时，本次q50留出未见终局翻转；同目标、同归票信号加一句自己跳警后，结果明显改变。仍需具体动作区分平民接收与警方私人识破两条通路。')
add('3. **跳藏暂有端点证据，尚无通用最优比例。** 训练选该窄条件q0，留出该冻结池的最坏列也优于q50、q100；不是完整游戏最优隐藏，更不证明所有局面都应藏。')
add('\n## 为什么上轮会从“先出匪”变成“先出民”')
add('\n历史训练例169000044（下文座位从1开始）：14号匪第一天假查杀15号民。第二天不重申时，10号民、14号匪、1号民各4票进入PK；重申后，匪队四票从1号改到15号，PK变成10、14、15。')
add('\n关键是10号平民的一票：他原先投11号；PK时11不在候选里，自己也不能投自己。真警给的名单10、11对他没有合法候选。不重申时，他按位置回退投14号，匪以5票出局；重申时，程序发现14号今天还有“出15”的有效建议，就改投15号，民以5票出局。')
add('\n所以这里是**四张匪票改PK候选，再改变一张关键平民票**。没有新证据，也不是全场突然相信旧查杀。两局最终都输，二元终局指标掩盖了局部出人损失。本轮已重新完整重放并与v23两条归档哈希一致。')
add('\n## 本轮接续究竟增加什么')
add('\n例如A假查杀C后死亡，C仍活着。B是A的匪队友：support只说“今天出C”；claim先说“我是警察”，再给同一个建议。两者都使用accuse，匪队均能协调投C；claim额外改变B在当前路由中的来源资格，也让真警凭互认私下识破B。不是给B增加夜验，不是将A的谎言变成B的独立检查。')
add('\n接续只在当前发言序首名存活匪的普通轮次执行，一条普通声明加一条扩展；旧目标死后不换人，不追加PK发言，不刷新死者消息日期。依据只有自己的匪队、公开旧消息、死亡与发言序。未知警民标签仅用于事后评价。')
add('\n当前接收协议只将report/police声明者纳入来源；纯投票建议不自动获得来源资格。新的police+accuse未必产生基于report矛盾的冲突边。这是受测协议边界，不能把来源资格当认证真警。')
add('\n## 冻结方法与样本')
add(f"\n训练seed从{f['config']['train']['seed_start']}起，每格{f['config']['train']['n']}局；新留出从{f['config']['holdout']['seed_start']}起，每格{f['config']['holdout']['n']}局。正式实际模拟{man['games']:,}局。每阶段3好人行×16匪列；若另加训练实际q，明确计入新增行。")
add('\n四种反制固定q时首日轨迹逐局相同；restate、support、claim首次接续前轨迹逐局相同；控制世界shadow首次机会与处理世界实际执行有无逐局匹配。配对保留共同发牌与决策随机数，但后续路径可不同。')
add('\n主要比较是q50下claim−restate，四组一起控制；下面给配对差、校正正常近似区间与有界保守区间。正常近似属探索性，不将零样本方差当等效证明。其余比较及分支是解释性，未作同时保证。原赢局覆盖是控制世界描述，不从处理后挑子群当总体效应。')
add('\n## 新留出：固定q50的胜率与反制覆盖')
add('\n每格4096局。单位为好人最终胜率；差值是百分点，负号表示反制伤害好人。')
add('\n|匪组|原人重申restate|队友支持support|队友跳警claim|claim−restate|\n|---|---:|---:|---:|---:|')
for base in bases:
    a,b,c=[lookup['repair_q50',base+'_'+x] for x in ('restate','support','claim')]
    add(f"|{labels[base]}|{P(a['win']['rate'])}|{P(b['win']['rate'])}|{P(c['win']['rate'])}|{PP(c['win']['rate']-a['win']['rate'])}|")
add('\n|匪组|主比较差|四项校正正常近似95%区间|四项保守95%区间|原赢→输／原输→赢|\n|---|---:|---|---|---:|')
for c in ho['contrasts']:
    if c['primary']:
        v=c['win'];add(f"|{labels[c['base']]}|{PP(v['delta'])}|{CI(v['family_normal'])}|{CI(v['family_hoeffding'])}|{v['worsened']}／{v['improved']}|")
add('\n训练后、留出文件生成及读取前，另冻结了配对精度补充：分别对赢转输/输转赢概率作二项Clopper–Pearson反演，再以16尾并集界得到四项差同时95%区间。不是最初协议的一部分，不改策略或选择。它利用低翻转率的信息，也不要求不同匪列独立；依赖跨seed独立同分布的模拟假设。分析使用SciPy 1.16.3，独立binomtest反演核对通过，数值分位数不属于有理数均衡证书。')
add('\n|匪组|同时95%精确二项边界组合区间（百分点）|\n|---|---|')
for z in precision['rows']:add(f"|{labels[z['base']]}|{CI(z['simultaneous_ci'])}|")
add('\n|匪组|restate原赢局|原赢局中有接续机会|claim实际执行局（全部）|有机会且接续后仍赢|\n|---|---:|---:|---:|---:|')
for c in ho['coverage']:
    if c['good']=='repair_q50' and c['mode']=='claim':
        add(f"|{labels[c['base']]}|{c['baseline_wins']}|{c['baseline_wins_with_opportunity']}|{c['treatment_executed']}|{c['baseline_win_treatment_exec']-c['baseline_wins_lost']}|")
add('\n上表“机会”是restate控制路径中首次可接续的描述；只要第一次机会相同，就能检查是否确实触达原赢局。后续执行次数可能受策略改变，不能混作同一个固定条件。没有额外保证能找到所有有害回应。')
zeros=[c for c in ho['contrasts'] if c['primary'] and c['win']['improved']+c['win']['worsened']==0]
if zeros:
    bound=1-(.05/4)**(1/4096)
    add(f'\n事前指定的零翻转补充界：主比较中{len(zeros)}项没有终局翻转；每项总体终局差绝对值界为{P(bound)}（四项族95%，按独立seed模拟假设）。只用于这些零计数项；不限制未测试回应或局部行动伤害。')
add('\n### 处理前的第二天分支（解释性）')
add('\n此分支在第二天普通发言前定义：原悍跳已死且旧目标仍活。四模式此时尚未接续，角色标签不输入策略。不能把4096总样本当分支样本。')
add('\n|匪组|分支n|claim−restate终局差|逐项正常近似95%区间|\n|---|---:|---:|---|')
for c in ho['contrasts']:
    if c['primary']:
        v=c['day2_branch'];add(f"|{labels[c['base']]}|{v['n']}|{PP(v['delta']) if v['delta'] is not None else '无样本'}|{CI(v['ci95_normal']) if v['ci95_normal'] else '无区间'}|")
add('\n## 跳藏：重新评估而不预设必须混合')
add(f"\n训练端点2×16经验矩阵的值为{tr['certificate']['value_exact']}≈{P(tr['certificate']['value'])}，精确经验gap={tr['certificate']['gap_exact']}。训练选q={sel['q_exact']}≈{P(float(Fraction(sel['q_exact'])))}，在读取留出前冻结。")
add('\n|阶段|回应概率|16固定匪列中经验最差胜率|\n|---|---:|---:|')
for phase,report in [('训练',tr),('新留出',ho)]:
    for gn,q in [('repair_q0','0%'),('repair_q50','50%'),('repair_q100','100%')]:
        rate=min(c['win']['rate'] for c in report['cells'] if c['good']==gn)
        add(f'|{phase}|{q}|{P(rate)}|')
add('\n留出表中的0.00%表示4096局没有胜例，不表示总体胜率严格为零。未根据留出改选比例。')
b=ho['frozen_bounds'];eps=sqrt(log(2*32/.05)/(2*4096))
add(f"\n冻结训练双方混合在留出端点矩阵：lower={b['lower_exact']}≈{P(b['lower'])}，upper={b['upper_exact']}≈{P(b['upper'])}，gap={b['gap_exact']}≈{b['gap']*100:.3f}个百分点。32端点单元的同时95% Hoeffding半径约{eps*100:.2f}个百分点；固定双方在总体受限收益上的gap保守界[0, {(b['gap']+2*eps)*100:.2f}]个百分点，不能把经验小gap当总体无误差。")
add('\n训练混合证书只用于这个冻结池。局部q由唯一预定警察私下抽样实现，不需全队秘密相关装置；匪列混合仅是矩阵对手分布，整队执行需赛前一致选择列。相同最优值可以对应多个混合，端点占优也不推出完整游戏永远隐藏或永远跳。q50直接抽样收益与两个端点收益的均值可有有限样本差别。此轮未新增条件q学习，亦未据留出重选。')
add('\n## 预定具体对局对照')
add('\n**首损留出例174000017（后置刀／远端）：** 8号匪假查杀4号民后第一天被出。2号匪接续跳警，仍建议出4号。第二天真警报3号匪，三模式仍都出3；第三天真警报5号匪，restate/support平民跟5，claim却把2号的旧目标4加入建议并集。12号平民等人按冻结位置排序改投4，民4得8票、匪5得3票。第四天虽出2号匪，第五夜最后警15被刀，匪5尚存，原赢变输。')
add('\n这个留出例中，警方报验人与实际投票相符；直接观察到的是新来源打散共同建议，而非警方自行分票。真警已经知道2号假警，但没有马上出掉它，因此接续的暴露成本没有立刻兑现。新的police模板没有新report，在这局未建立双活验人冲突边；不能扩成所有接续都无冲突。')
add('\n**保留原赢例174000377（后置刀／近端）：** 接续匪7正好是当前活警12公布的真查杀，于是出现双活冲突，仍出7；后来旧目标6又被当前真警验成金水，清白保护关系阻止旧提案主导，最终仍出完四匪。说明同一反制有可挡住的分支，不能把接续说成必胜。')
add('\n这两个例子的首警都已在原假警之前发言，没有触发q控制的可选回应节点；它们解释续局机制，不能用来证明跳藏比例。训练另有“警队统一投一个已知匪、却公开报另一个已知匪”的协调例，值得独立核查，但不是上述留出首损例的原因。')

for row in ex['selected']:
    if row['status']!='replayed':continue
    category={'baseline_win_to_loss':'原赢→输','baseline_loss_to_win':'原输→赢','executed_and_baseline_win_retained':'执行接续仍保留原赢'}[row['category']]
    add(f"\n- {labels[row['base']]}，{category}，seed {row['seed']}：")
    for mode in ('restate','support','claim'):
        summ=row['summaries'][mode]
        chain='；'.join(f"第{day['day']}天出"+','.join(str(p['display_seat'])+'号'+('匪' if p['role_evaluation_only']=='mafia' else '警' if p['role_evaluation_only']=='police' else '民') for p in day['day_deaths']) for day in summ['days'] if day['day_deaths'])
        add(f"  - {mode}：{chain}；终局{'好人赢' if summ['win'] else '好人输'}。")
add('\n选例按每类种子升序首例，未找到的类别不虚构。完整逐票来源、私人已知集合、发言、PK和死亡链保存在results/v24_examples.json；这些是重用留出局的解释，不计新独立证据。相同结局或不同结局都要结合中间动作，不能只用胜率猜原因。')
add('\n## 机制核验及结论边界')
add('\n|本轮全部留出轨迹|孤立历史冲突强制票|无当日声明的旧死者指令票|忽略合法已知匪票|投私人已知好人票|非法票|\n|---|---:|---:|---:|---:|---:|')
flags=['orphan','stale','ignored_known','voted_good','illegal']
add('|所有行列|'+ '|'.join(str(sum(sum(c['raw'][f+'_ballots']) for c in ho['cells'])) for f in flags)+'|')
add('\n若接续后胜率下降，不能直接叫两项旧漏洞复发：新活人当日跳警/建议与“死一方自动轮出另一方”是不同机制。此轮没有重新评估旧规则行，因此不把v23的4—8个百分点增益直接外推成对本轮新池仍成立的增益。旧修复有效与新协议仍有可被利用处可以同时成立。')
add('\n若support与claim不同，除了平民接收资格外，真警也可私下识破新claim；后续路径因此变化。该差异是完整机制净效应，不能不看轨迹便声称纯粹由信用/信息量导致。数值信用仍冻结，未引入新权重。')
add('\n## 复现、检查与下一步决策')
add(f"\n实际运行：`python -m pytest tests -q`：293 passed；`python scripts/run_succession_counter_v24.py`：{man['games']:,}局；`python scripts/verify_succession_counter_v24.py`：{audit['status']}，{audit['cells_checked']}单元全部算术/哈希/前缀/机制核查，{audit['sampled_full_traces']}条抽样无包装器完整重放一致，非全部独立重跑；`python scripts/diagnose_succession_counter_v24.py`：{ex['detailed_replays']}条详细案例及同数无包装器重放，另30条透明夜行动审计遍覆盖终止夜且轨迹一致；历史两条哈希匹配。")
add('\n补充实际运行：`python scripts/paired_precision_v24.py`四项完成；`python scripts/verify_succession_aux_v24.py`通过，独立二项反演8区间、核对12个预定案例槽位及旧两哈希。分析依赖SciPy 1.16.3；这是归档结果再核查，不新增独立胜率证据。')
add('\n正式冻结源码与配置在results/v24/source、freeze.json；原始逐局量、训练证书、留出前选择、留出结果和清单齐备。报告生成与案例脚本属于按协议的结果整理；根目录核查脚本补充了跨q首夜不变量及节点外无影响检查，冻结版本仍保留。均未反向修改冻结策略。完全复现应从冻结source加载，指定新输出目录，勿覆盖原结果。')
add('\n本轮已发现足够覆盖及明确净损害，建议下一步单独审计“新来源能否直接打散共同建议”及“警队公开目标与实际票是否一致”，再决定做哪一项消融。死亡仍不认证身份，不恢复机械轮出。不得为追求更好数字继续扩池或搜索种子。跳藏条件与局部混合继续保留，信用系统待信息来源处理更可靠后独立比较。')
(ROOT/'docs/succession_counter_results_v24.md').write_text('\n'.join(lines)+'\n')
print('wrote docs/succession_counter_results_v24.md')
