#!/usr/bin/env python3
"""Mechanism coverage, matched counter-response and reopened local q."""
import json
from pathlib import Path
from fractions import Fraction
from math import sqrt,log
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v23'
rd=lambda n:json.loads((folder/n).read_text())
f,train,hold,selection,manifest=map(rd,['freeze.json','train.json','holdout.json','selection_before_holdout.json','manifest.json'])
coverage=json.loads((ROOT/'results/v23_repair_coverage.json').read_text())
lookup={(c['good'],c['mafia']):c for c in hold['cells']}
bases={'late_near':'后置刀／近端假查杀','late_far':'后置刀／远端假查杀','decoy_near':'伪装刀／近端假查杀','decoy_far':'伪装刀／远端假查杀'}
def pct(v):return '—' if v is None else f'{100*v:.2f}%'
def pp(v):return '—' if v is None else f'{100*v:+.2f}'
def ci(v):return '—' if v is None else '['+', '.join(pp(x) for x in v)+']'
def rate(g,m):return lookup[g,m]['win']['rate']
lines=['# v23：修复是否真的覆盖旧问题？匪方重申后，还该怎样跳藏？','',
'## 策略／参数字典','',
'|名称|实际含义|','|---|---|',
'|legacy_q50|旧v20b续局，保留历史冲突轮出与旧查杀直接建议；局部回应概率50%|',
'|repair_q0、q25、q50、q75、q100|v22双修复冻结不变；局部回应概率分别0%、25%、50%、75%、100%|',
'|trained_local_q|只由训练端点矩阵选择并在留出前冻结的回应概率；可能是纯策略，也可能是内部混合|',
'|quiet|原固定匪续局，不特意重申原假查杀；仍然正常刀人、发言、投票|',
'|restate|原首日悍跳者仍活着且原目标活着时，在自己普通发言扩展位置再次提出“今天仍出这个人”|','',
'q后缀不是来源信用或身份概率。它只作用于首夜未死警、预定首警未发言、假警已发言且查杀未中警队的窄条件。只有该警私下抽一次，不需要整队秘密相关装置。0%不是全局永远藏，100%不是全队跳；已公开真警后不机械拉第二警。','',
'4个刀／目标组再各分quiet、restate，共8列：late_near、late_far、decoy_near、decoy_far分别表示后置刀/伪装刀×近端/远端假查杀。匪只知匪队，不知道警民；近远按公开座位发言顺序在非匪中选，实际刀在最高评分合法刀中随机破同分。2%扰动仍仅是好人位置似然假设。','',
'**重申的通俗例子：** A第一天跳警说C是匪。第二天A、C都还活着，A在正常轮次重说“今天我仍要出C”。代码用accuse表达建议，不伪造第二次验人，不换目标，不让队友接力，不额外加发言，也不在PK再重复。重复不是独立新证据；普通civilian发言占位不代表撤回原身份声明。','',
'全部玩家由固定程序决策，没有LLM实时判断；随机性仅在预定q、同分选择等规则中。共同固定4警4匪8民、警互认共享夜验、真实实际验人声明、死亡不翻身份、前三死亡遗言、可弃票、一轮PK再平票平安日。规则允许匪自刀，但本轮候选均为普通首刀，不测试自刀悍跳。gap验人、等权位置模型、二人内推和私人记忆不变。来源信用继续冻结不用，不新增数值评分。目标位置排序、建议资格与实际投票分开，尚未实现理想的全信息推理。','',
'## 先回答“旧例仍输，是否说明没修好？”','',
f"读取v22全部按匪列分组的{coverage['pairs']:,}个旧/双修复配对局面，修后本轮定义的两条目标路径残留为{coverage['aggregate'].get('target_mechanism_remains',0)}。旧路径消失但仍输的有{coverage['aggregate'].get('old_path_removed_loss',0):,}个；旧路径本来未出现且仍输的有{coverage['aggregate'].get('no_old_target_path_loss',0):,}个。说明应分别判断动作修复与终局成功，不能用一个仍输的例子否定修复。", '',
'这不表示剩下的失利只是少数特例：整体胜率仍低，其他策略缺口广泛存在；同时也不表示本轮定义之外的所有逻辑漏洞均已排除。不同匪列复用发牌种子，这些计数不是全部互相独立的新样本。旧路径出现也不表示每一票都实际有害。','',
'第三个旧例163000001修后仍输的链条：首日出12号匪；第二天出3号民；第三天出13号匪；第四天出8号匪。警察每次遇合法已知匪都投匪，第四天平民也跟对了；第五夜最后一警被刀，9号匪仍活着。这是固定续局下少了一轮找匪时间，不是旧的“剩一活来源必须轮出”仍在触发。进一步改验人、隐藏或归票可能有用，本轮不据这个例子直接调参。','',
'旧例与全覆盖统计只作事后解释，来源文件和哈希见results/v23_repair_coverage.json，不计入新种子证据。','',
'## 本轮先看结论','',
f"训练冻结的局部回应概率为{selection['q_exact']}，约{pct(float(Fraction(selection['q_exact'])))}。这表示当前有限对手池给出一个混合候选，不表示50%是稳定或完整游戏最优。",'',
'新留出中，q50修复相对旧续局的增益在四个刀/目标组和有无重申条件下均保留。重申的八个q50配对比较都没有观察到终局翻转；这描述本轮固定反制，不是已经抗全部反制。','',
'训练50%是内部混合候选，但留出端点收益没有确认它比纯隐藏更好；不在留出上改选q0。应把“局部混合已实现并重新评估”与“精确比例已确定”分开。','',
'## 本轮新实验的方法','',
f"训练：169000000起，每单元1024局；新留出：170000000起，每单元4096局。正式实际终局模拟{manifest['games']:,}局。6个好人策略×8匪列在训练前冻结；训练只选局部q，读取留出前保存选择，留出不重新调q。smoke171000000起，不计正式。", '',
'两项主要比较各自控制8比较：同q50的修复收益（8个匪列）；quiet→restate的影响（旧／修复两行×4组）。报告配对差及各组校正的正常近似与有界区间；两个分别控制的组不能合称16项整体95%。训练数据用于开发与选择，不当独立确认。', '',
'修复比较的q固定50%，同列第一天、第二夜和第二天投票前完整轨迹逐局匹配；反制quiet/restate只保证首夜及第一天相同，因为重申本来就要改变次日发言。跨q比较共享首夜及假查杀目标，但发言和后续局面可变化。反制执行机会受续局影响，不按执行后的子群筛出“因果收益”。','',
'## 新留出：修复遇到重申后表现怎样','',
'下表每个胜率基于4096局。箭头表示旧q50→修复q50，差值为百分点；第三列反制效应负数表示重申让好人更难赢。','',
'|匪条件|原续局：旧→修复|允许重申：旧→修复|重申对修复的影响|重申实际执行局数／4096|','|---|---|---|---:|---:|']
for b,label in bases.items():
    quiet=b+'_quiet';rest=b+'_restate';c=lookup['repair_q50',rest]
    lines.append('|'+ '|'.join([label,pct(rate('legacy_q50',quiet))+'→'+pct(rate('repair_q50',quiet)),pct(rate('legacy_q50',rest))+'→'+pct(rate('repair_q50',rest)),pp(rate('repair_q50',rest)-rate('repair_q50',quiet)),str(sum(c['raw']['repeat_game']))])+'|')
lines += ['', '### 修复收益的区间（8项一组，单位：百分点）','',
'|匪列|修复−旧规则|校正正常近似95%区间|校正保守95%区间|从输变赢／从赢变输|','|---|---:|---|---|---:|']
for r in hold['contrasts']:
    if r['name']=='repair' and r['branch']=='all':
        w=r['win'];lines.append('|'+ '|'.join([r['mafia'],pp(w['delta']),ci(w['family_normal']),ci(w['family_hoeffding']),f"{w['improved']}／{w['worsened']}"])+'|')
lines += ['', '### 重申影响的区间（另一个8项组）','',
'|好人规则|匪组|restate−quiet|校正正常近似95%区间|校正保守95%区间|','|---|---|---:|---|---|']
for r in hold['contrasts']:
    if r['name']=='counter':
        w=r['win'];lines.append('|'+ '|'.join([r['good'],bases[r['base']],pp(w['delta']),ci(w['family_normal']),ci(w['family_hoeffding'])])+'|')
diag_path=ROOT/'results/v23_restatement_diagnostic.json'
if diag_path.exists():
    diag=json.loads(diag_path.read_text())
    lines += ['', '### 为什么终局零差异仍不足以叫抗反制','',
    '这项检查在看过训练、读取留出前补充安排；复用所有训练q50实际执行重申的局，不是新独立证据。比较同seed的正常投票、PK、死亡行动链，区别只多一句话与实际行动变化。','',
    '|匪组|训练执行重申局数|投票／出局链改变|行动链未变|','|---|---:|---:|---:|']
    for row in diag['rows']:
        lines.append('|'+ '|'.join([bases[row['base']],str(row['executed_games']),str(row['action_chain_changed']),str(row['action_chain_unchanged'])])+'|')
    lines += ['', '第一个预定行动变化例（169000044，训练旧种子）：14号匪第一天假查杀15号民；无重申时第二天出14号匪、第三天出15号民；重申后第二天改出15号民、第三天才出14号匪。反制确实干扰了出人顺序，两边却都输，所以二元终局指标看不出这一局部损失。案例为种子升序首例，不按胜负挑选，完整信息在results/v23_restatement_diagnostic.json。','',
    '|新留出匪组（修复q50）|执行重申局数|这些配对中quiet原本赢的局数|这些配对中restate赢的局数|全部4096局的胜负翻转数|','|---|---:|---:|---:|---:|']
    for base,label in bases.items():
        a,b=lookup['repair_q50',base+'_quiet'],lookup['repair_q50',base+'_restate']
        mask=b['raw']['repeat_game']
        vals=[sum(mask),sum(w and k for w,k in zip(a['raw']['win'],mask)),sum(w and k for w,k in zip(b['raw']['win'],mask)),sum(x!=y for x,y in zip(a['raw']['win'],b['raw']['win']))]
        lines.append('|'+label+'|'+'|'.join(str(v) for v in vals)+'|')
    lines += ['', '执行局是处理后条件，这里只用于解释覆盖，不能当作一个单独随机试验。从旧例仍输不能断定修复失败；同样，从已输支路上的反制不改终局，也不能断定新规则抗所有反制。','']
zero_path=ROOT/'results/v23_zero_counter_bound.json'
if zero_path.exists():
    zero=json.loads(zero_path.read_text())
    if all(r['win_flips']==0 for r in zero['rows']):
        bound=max(r['absolute_population_win_effect_bound'] for r in zero['rows'])
        lines += ['', f'补充精度说明（训练后、读取留出前指定）：8个固定配对各4096局均无终局翻转。独立seed模拟假设下，以|E[D]|≤P(D≠0)和零次翻转的二项概率界，八项同时95%的总体终局胜率差绝对值上界约{100*bound:.3f}个百分点。该界只对这8个固定比较，不能约束其他反制或条件行动损失；不把正常近似零区间当精确等效证明。公式与适用条件见results/v23_zero_counter_bound.json。','']
lines += ['',
'只在原说话者、原目标仍活着时执行重申，很多局根本没有机会。因此总体影响小不能证明重申在所有信息集无效，更不能证明匪方无其他更强回应。反制引起的损失也不能自动叫旧漏洞复发：新的活人当前声明冲突，与死—活历史强制轮出是不同机制。','',
'## 修复的目标路径有没有重新出现','',
'|好人策略（留出八列合计）|孤立死—活冲突票|旧死者无当日重申的指令票|忽略合法已知匪票|投私有好人票|非法票|','|---|---:|---:|---:|---:|---:|']
for g in ('legacy_q50','repair_q50','repair_q0','repair_q100'):
    cs=[c for c in hold['cells'] if c['good']==g]
    vals=[sum(sum(c['raw'][k+'_ballots']) for c in cs) for k in ('orphan','stale','ignored_known','voted_good','illegal')]
    lines.append('|'+g+'|'+'|'.join(str(v) for v in vals)+'|')
lines += ['', '票次数同局可重复、与局数不同。零计数验证特定动作规则，不证明完整推理或全局最优；信息源未被认证，当前建议仍可能撒谎。','',
'## 跳藏与局部混合已重启','',
'先看固定网格在训练与留出的经验最差列收益。最差列会随q改变；这些点不是同一已知匪先验下的期望，不根据留出挑新q。','',
'|阶段|局部回应概率|quiet四列中最差胜率|restate四列中最差胜率|全部八列中最差胜率|','|---|---:|---:|---:|---:|']
for phase,report in [('训练',train),('新留出',hold)]:
    l={(c['good'],c['mafia']):c for c in report['cells']}
    for name,q in [('repair_q0',0),('repair_q25',25),('repair_q50',50),('repair_q75',75),('repair_q100',100)]:
        quiet=[c['win']['rate'] for (g,m),c in l.items() if g==name and m.endswith('quiet')]
        rest=[c['win']['rate'] for (g,m),c in l.items() if g==name and m.endswith('restate')]
        lines.append('|'+ '|'.join([phase,str(q)+'%',pct(min(quiet)),pct(min(rest)),pct(min(quiet+rest))])+'|')
cert=selection['certificate'];q=Fraction(selection['q_exact'])
lines += ['',
f"训练仅对q0/q100两端点×8固定匪列求受限经验均衡，值{cert['value_exact']}≈{pct(cert['value'])}，经验gap={cert['gap_exact']}。冻结局部回应q={selection['q_exact']}≈{pct(float(q))}。这使用已有矩阵方法，不是新求解算法；是否内部混合由矩阵决定，不预设混合一定更好。",'']
if selection['alias_of']:
    lines += [f"冻结q等于预定网格策略{selection['alias_of']}，直接引用该策略在全新留出的评估，未重复模拟、未把别名算独立证据。",'']
else:
    lines += ['冻结q不是网格值，因此额外用8×4096局直接模拟其局部抽样实现，仍使用新留出且不重新选择。','']
sensitivity_path=ROOT/'results/v23_q_sensitivity.json'
if sensitivity_path.exists():
    sens=json.loads(sensitivity_path.read_text())
    lines += [f"训练后另外做了500次配对seed bootstrap灵敏度诊断：{sens['optimal_set_includes_zero']}次最优集合包含q0，{sens['optimal_set_includes_one']}次包含q100，{sens['uniquely_interior']}次得到唯一内部解；端点计数可重叠，因为多解区间可能包含两端。它保留同seed跨列相关性、多解最优区间，未修改冻结q；这是探索性灵敏度，不是校准置信区间。当前50%比例仍对有限样本敏感。",'']
lines += ['训练中这个内部混合相对最佳纯端点的最坏列收益只多1/1024，约0.10个百分点，远不能仅凭这一点确定精确比例。训练证书的收益来自端点矩阵的混合；直接以该概率抽样的模拟是另一份有限样本估计。比如本次训练端点混合值61/1024，而实际q50在两个最差列各60/1024，差一局并非求解失败。列收益相同也可能对应多组等价匪混合；求解器选quiet列不证明重申永远劣于quiet。','']
lines += ['|匪列|冻结局部q的留出胜率|','|---|---:|']
for m,w in hold['local_q_evaluation']['rates'].items():lines.append('|'+m+'|'+pct(w['rate'])+'|')
b=hold['frozen_bounds'];epsilon=sqrt(log(640)/(2*f['config']['holdout']['n']))
interval_gap=[max(0,b['gap']-2*epsilon),min(1,b['gap']+2*epsilon)]
lines += ['',
f"冻结训练双方混合在留出端点矩阵：lower={pct(b['lower'])}，upper={pct(b['upper'])}，gap={100*b['gap']:.2f}个百分点。对16个端点单元同时用95% Hoeffding界（独立模拟假设），单元半径约{100*epsilon:.2f}个百分点，固定双方的总体受限gap保守区间{ci(interval_gap)}个百分点。上下界不等于总体置信区间，精确矩阵不消除收益估计误差。", '',
'这是2×8冻结池的经验分析，不更新或替换历史7×13池，不表示池外不可利用；留出不重新解最优值。好人q可由唯一预定行动者局部实现；匪方列混合在本轮仅是矩阵对手分布及证书，若要实际执行还需赛前整队共选策略或共享信号，本轮没有实现分散匪徒自行抽样的等价协议。各纯匪列是预先一致配置的团队策略，不能把这个两队矩阵称为所有个体策略的纳什均衡。局部一次抽样对应端点混合是因为该策略只在单节点改变行为、后续规则一致，不需要秘密阵营相关装置。PRNG使用浮点概率，精确有理数证书只对模拟端点矩阵。','',
'### 窄条件下回应−隐藏（解释性）','',
'仅首夜未死警、假查杀实际中民、首警尚未普通发言且有机会的局面；角色标签仅评价，不输入策略。每行条件n通常远少于4096，不能把单元总n当分支样本。','',
'|匪列|条件n|q100−q0胜率差|逐项正常近似95%区间|','|---|---:|---:|---|']
for r in hold['contrasts']:
    if r['name']=='response' and r['branch']=='narrow_civilian':
        w=r['win'];lines.append('|'+ '|'.join([r['mafia'],str(w['n']),pp(w['delta']),ci(w['ci95_normal'])])+'|')
lines += ['',
'若q边界占优，仅限这个单节点、固定信息模型和8个匪回应；不能推出警察所有情况都藏/都跳。多个混合对应同值是正常现象，格点模拟的微小非线性可来自采样噪声，不当作求解失败。','',
'## 局限与后续决策','',
'- 目标漏洞在所测轨迹消失，不代表所有别的逻辑问题已修；最终仍输也不自动代表修复失效。后续应区分信息不足、归票启发式、曝光节奏和对手回应。',
'- 重申只是固定的一个反制，原目标死后不换人、不交棒，不含假金水、新查杀、队友接力或学习最强回应。若这一项无法推翻收益，也不能宣布已抗全部反制。',
'- 来源信用继续冻结，不永久删除；尚无校准信念、完整票型学习或理想的信息整合。跨日信息集、多匪4v4对冲、公开怀疑、遗言制度分开保留。',
'- 新留出已查看，后续不能反复优化后继续称未看过的最终验收；新实验须另冻参数与种子。','',
'## 复现与核验','',
'运行：`python scripts/run_restatement_response_v23.py --output results/v23_reproduction`；测试：`python -m pytest tests -q`；核验：`python scripts/verify_restatement_response_v23.py`。冻结参数、脚本、源码、原始逐局量和训练证书、留出前选择文件在results/v23；复现冻结版本应从results/v23/source启动，指定新目录。','']
audit=ROOT/'results/v23_integrity_audit.json'
if audit.exists():
    a=json.loads(audit.read_text());lines += [f"本轮286项测试通过，{a['cells_checked']}个实际单元的算术、信息前缀和机制不变量核查通过，{a['sampled_full_traces']}个抽样完整轨迹无包装器复现一致；不是全部{a['actual_games']:,}局独立重跑。",'']
lines += ['## 下一步建议','', '优先让下一项反制覆盖原本有望获胜的支路，而不是仅给已陷入劣势的存活悍跳者重复同一句话。例如可先讨论原悍跳者出局后队友承接旧说法的合法方式、来源归属和发言预算；转述不能被当成独立新验人。不要直接把当前零终局差异称为已经抗反制。','', '局部q的研究继续保留；当前50%不固化为默认最优，也不按这次留出改成0%。下一轮先明确要区分的信息集或反制，再冻结新的训练/验收种子。信用分仍冻结作对照，待信息更新与来源处理更可靠后独立比较。','']
(ROOT/'docs/restatement_response_results_v23.md').write_text('\n'.join(lines));print('restatement and response report written')
