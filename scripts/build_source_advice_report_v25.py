#!/usr/bin/env python3
"""Explain the fixed ablation and limits, without selecting new policies."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
audit=load('results/v25_source_audit.json');tr=load('results/v25/train.json');ho=load('results/v25/holdout.json');f=load('results/v25/freeze.json');man=load('results/v25/manifest.json');check=load('results/v25_integrity_audit.json');aux=load('results/v25_aux_integrity_audit.json');ex=load('results/v25_examples.json')
L=[]
def add(s=''):L.append(s)
P=lambda v:f'{v*100:.2f}%'
PP=lambda v:f'{v*100:+.2f}'
CI=lambda a:'['+', '.join(PP(v) for v in a)+']'
bases=('late_near','late_far','decoy_near','decoy_far');labels=dict(late_near='后置刀／近端假查杀',late_far='后置刀／远端假查杀',decoy_near='伪装刀／近端假查杀',decoy_far='伪装刀／远端假查杀')
look={(c['good'],c['mafia']):c for c in ho['cells']}
add('# v25：反制是种子过拟合，还是在利用机械接收？')
add('\n2026-10-30。本轮先读旧留出做机制审计，再冻结一项消融及新训练／验收，不增加匪策略，不同时加信用或票型评分。')
add('\n## 策略／参数字典')
add('\n|名称|实际动作、继承与对照|\n|---|---|')
for a,b in [
('base_q0 / base_q50 / base_q100','v24两项修复、私人记忆和原路由不变；窄条件单警回应概率0% / 50% / 100%。base不是冻结信用对照。'),
('gate_q0 / gate_q50 / gate_q100','只在第二天起限制建议资格：仅说自己是警察、从未以本人来源提出report验人声明者，其建议不进入当日归票集合。'),
('restate','原首日假警与旧目标都活着时，原人再次建议出旧目标。'),
('claim','保留restate；原假警死亡且旧目标仍活时，首位活匪在正常发言自己跳警，并提议出旧目标；无新验人。'),
('late / decoy','继承safe_late后置位置刀 / posterior_decoy伪装刀。'),
('near / far','首位匪按公开后续发言序选最近／最远非队友作首日假查杀目标。'),
('q','局部行动概率，不是信用或身份概率，也不是全局跳警率。'),
('report','公开声称验人；没有裁判身份认证，匪也能伪造。'),
('police / accuse','公开跳警身份声明 / 今天想出某人的建议；accuse不自动等同于新查杀。')]:add(f'|{a}|{b}|')
add('\n**q生效条件：** 首夜没死警、预定首警尚未发言、已经出现假警且假查杀未中警队，只有该警在自己正常轮次抽一次。其余被打中警队的必答、后续警察发言规则不变，不再拉第二警。q从0至1，不累计、无信用衰减；本轮三档是人工比较网格，未训练、冻结或宣称新的最佳比例。')
add('\n**gate的具体例子：** A昨天查杀C后死亡，B今天只说“我也是警察，今天出C”。B的身份声明仍保存，也仍能形成冲突或被真警私下识破，但其建议暂不进入集合。B如果自己报了一条验人，即使是假的，也能通过资格。这里不是判断B真伪，只改变建议通道；没有数值权重、门槛拟合或身份概率。')
add('\n来源信用、目标怀疑、建议资格和实际投票分开：数值信用继续冻结；位置排序不变；gate仅改建议资格；私人已知匪优先、金水先后关系和投票破同分不变。source_credit=True为兼容字段，实际routing=evidence不用数值信用分支；history=False关闭旧票型加分，remember=True仍保留跨日私人证据。')
add('\n其余均继承：4警4匪8民、警方互认共享夜验、真实警察报真实实际验人、死亡不翻身份、前三死亡遗言、可弃票、一轮PK再平票平安日。位置等权似然、gap验人、二人内推、固定程序续局均不变。2%扰动只在好人位置似然假设中，实际匪刀未添加。规则虽允许自刀，本池无自刀策略；无平民假跳。所有玩家为固定程序，不使用LLM临场推理。')
main_rows=[r for r in ho['contrasts'] if r['primary']]
positive=sum(r['precision']['ci_simultaneous'][0]>0 for r in main_rows)
add('\n## 本轮先看结果')
add(f'\n四个固定匪条件中，{positive}/4项来源资格消融的同时95%区间支持好人胜率提高。这里只是同一对手池、同一规则中的机制证据，不是完整最优防守。下文同时列出不跳藏条件、负对照和未解决问题。')
add('\n## 先回答过拟合的质疑')
add('\n应区分三件事：**记住某批seed**、**针对固定对手协议的利用**、**对更完善好人策略仍稳健**。v24的新seed验证反制不是只在开发种子上好用；合法Observation审计未见直接读取未知警民标签。它仍明显针对现有来源与归票协议，尚未证明能利用合理、完善的好人最佳应对。双方都不是完整最佳应对，所以不能解释为真实游戏客观只剩这些胜率。')
add('\n旧两项逻辑修复和新漏洞可以同时存在：不再按死—活历史冲突强制轮出是合理动作修复；新活人声明改变当日建议又是另一机制。本轮继续不认证死亡、不恢复机械轮出，也不拿胜率降低作为撤销修复的理由。')
add('\n“有意针对对手”在固定模型里是合法反制；“这就是完整游戏的稳健最优应对”目前没有证据。若轻微改变接收规则就改变结果，则更说明反制对协议敏感；这仍不等于匪策略不合法或只拟合了seed。')
add('\n## 两项分别审计：先有证据，再决定做哪项消融')
add('\n固定重放v24旧留出前512seed×四组×restate/claim，共4096个不同单元轨迹。第一次发现口径后补充核查“两个目标是否都私知匪”，实际共两遍8192次旧轨迹运行；只算4096个不同旧轨迹，不算新确认样本。旧留出已使用开发，不能继续充当未看过验收。')
add('\n“打散”口径：原路由取兼容建议并集；有无本人验人声明的新来源；其他有验人声明的来源存在共同建议；在完全同一观察中，只挡无report建议的影子票改变。影子票是动作敏感性诊断，不是整局因果效应。此口径只计进入兼容建议并集的情况，未包括新来源触发活人冲突比较等其他来源敏感路径；86—285局不是全部受影响局。')
add('\n|匪组|模式|打散动作局／512|警察公开查杀与自身票不一致局／512|\n|---|---|---:|---:|')
for r in audit['rows']:
 c=r['counts'];add(f"|{labels[r['base']]}|{r['mode']}|{c['dilution_games']}|{c['police_report_vote_mismatch_games']}|")
add('\n公开查杀与投票不一致的全部被标记票，两目标都在该警私知匪集合中。这不是“明知匪却投好人”，但可能让平民跟A、警队投B。该标记仅限本人当天公开过合法活目标查杀；没说话者不被误计。它仍需单独试验，今天没有修。两类可同局出现，不能把计数相加当独立损失贡献。\n\n例：旧留出174000033（后置刀组），第二天10号真警公开查杀5号，却投3号；他的私人已知匪同时有3、5。公开信息让平民倾向5，警方位置破同分却倾向3，这是需要单独研究的协调差异，不是没记住5号是匪。')
add('\n选择来源资格消融的理由：四个claim组都有较多来源敏感动作，restate中该口径均0；先用一个明确开关隔离这个通道。不因胜率不好就同时修两个模块，也不按新结果继续调门槛。')
add('\n## 票型能不能抓匪？本轮先量化误判风险')
add('\n统计所有已完成普通首轮投票中，某个被公开提议的目标获得至少3票的组。3只是描述口径，不是部署的怀疑阈值。事后裁判角色仅用于评价，不能进入当时玩家推理；同局／跨日组重复且相关，不作为独立样本做显著性结论。')
add('\n|模式|集中票组|其中全是好人的票组|组内累计好人票／全部票|匪占多数票组|\n|---|---:|---:|---:|---:|')
for mode in ('restate','claim'):
 rows=[r for r in audit['rows'] if r['mode']==mode];co={k:sum(r['vote_cohorts'][k] for r in rows) for k in rows[0]['vote_cohorts']}
 add(f"|{mode}|{co['groups']}|{co['zero_mafia_groups']}|{co['good_voters']}／{co['voters']}|{co['mafia_majority_groups']}|")
add('\n初始只有4名匪，因此5张票的组至少有1名好人；不能把整组都判坏。仅凭总票数也不知道其中几张是匪。\n\n因此你的方向值得继续：跟随已被自己合法证据推翻的来源、连续多轮同一联盟冲票，可能是比孤立同票更好的信号。但“15号挂5票”不足以把5人都判匪：真警会抱团，普通民会被假警误导，匪也可跟真查杀做身份。你提出“可信好人共同投票不应让整个团队被同等怀疑”是合理方向；但即使是真好人也可能因信息不足投错。金水来源还可能是假警，所以需要记录来源关系，不能把每个集中票组作对称加分。')
add('\n下一步票型应按观察者的合法信息来定义：何时公开了改归、谁当时有反证、PK是否合法候选、哪些金水互相支持、是否存在可以解释的改票。只有完成的票可用；普通首投公布后可供PK/后续日参考，不能预读尚未发生的票。本轮旧路由虽然看得到公开票，尚未实现这种完整学习；没有直接加任意怀疑分。')
add('\n## 新消融的冻结方法')
add(f"\n6好人行×8原匪列，训练每格512局，seed176000000起；独立验收每格2048局，seed177000000起。正式新模拟{man['games']:,}局。训练只描述、核查，不选策略/q；中间保存不选择声明再读留出。相应源码、规则、参数、测试哈希在results/v25。")
add('\n同q的base/gate首日及第二天投票前完整前缀逐局相同；gate从第二天投票开始才可影响动作。主要比较固定q50、四个claim条件；同时95%CP组合界在正式训练前规定，每尾.05/16；保留校正正常近似和Hoeffding。二项数值反演依赖SciPy，不能与精确有理数均衡证书混淆。跨seed独立同分布是模拟统计假设，不要求各列独立。')
add('\n## 新留出结果：一项资格开关是否改变损害')
add('\n|匪组|base q50|gate q50|差（百分点）|四项同时95%二项组合区间|赢转输／输转赢|\n|---|---:|---:|---:|---|---:|')
for r in ho['contrasts']:
 if r['primary']:
  a,b=look['base_q50',r['mafia']],look['gate_q50',r['mafia']];w=r['win']
  add(f"|{labels[r['mafia'].removesuffix('_claim')]}|{P(a['win']['rate'])}|{P(b['win']['rate'])}|{PP(w['delta'])}|{CI(r['precision']['ci_simultaneous'])}|{w['worsened']}／{w['improved']}|")
add('\n原预定的其余区间：')
add('\n|匪组|四项校正正常近似95%区间|四项Hoeffding保守95%区间|\n|---|---|---|')
for r in ho['contrasts']:
 if r['primary']:add(f"|{labels[r['mafia'].removesuffix('_claim')]}|{CI(r['win']['family_normal'])}|{CI(r['win']['family_hoeffding'])}|")
add('\n|原人重申负对照|base q50|gate q50|逐局终局翻转数|\n|---|---:|---:|---:|')
for base in bases:
 a,b=look['base_q50',base+'_restate'],look['gate_q50',base+'_restate'];flips=sum(x!=y for x,y in zip(a['raw']['win'],b['raw']['win']))
 add(f"|{labels[base]}|{P(a['win']['rate'])}|{P(b['win']['rate'])}|{flips}|")
add('\n补充描述核查：三个q下，gate对claim与base对restate在本批留出逐局终局相同；这是已测反制效果被这个开关消除的证据，不是行动轨迹完全等价或所有未来反制无效。')
add('\n上述负对照不意味着不同政策完全等价；零翻转也不证明总体差精确为零。每格Wilson区间和全部配对统计在原始结果中。今天没有增加任何新的反制列；gate是否抗其他反制未验证。')
add('\n## 跳藏继续作为常用可变参数')
add('\n下表是固定八个对手条件中每个q的经验最差胜率；不据留出选新q，不声称求了均衡。')
add('\n|阶段|接收规则|q0|q50|q100|\n|---|---|---:|---:|---:|')
for phase,report in [('训练',tr),('新留出',ho)]:
 for pre in ('base','gate'):
  values=[min(c['win']['rate'] for c in report['cells'] if c['good']==pre+'_q'+q) for q in ('0','50','100')]
  add(f'|{phase}|{pre}|'+ '|'.join(P(v) for v in values)+'|')
add('\n即使一个端点较高，也只限当前单节点、固定接收规则与匪池。q50的直接模拟可与两端点估计的均值略不同，是有限样本抽样差；不是非线性最优或求解失败。零胜例不等于总体胜率为零。未来需要根据当时可见局面定义条件q，不能借赛后知道查杀中民就选择行动。')
add('\n窄条件端点比较（解释性，n远小于2048；实际中民角色只用于事后评价）：')
add('\n|接收规则|匪组／模式|条件n|q100−q0（百分点）|逐项正常近似95%区间|\n|---|---|---:|---:|---|')
for r in ho['contrasts']:
 if r['kind']=='response' and r['mafia'].endswith('_claim'):
  w=r['conditional'];add(f"|{r['good_family']}|{labels[r['mafia'].removesuffix('_claim')]}|{w['n']}|{PP(w['delta']) if w['delta'] is not None else '无样本'}|{CI(w['ci95_normal']) if w['ci95_normal'] else '无区间'}|")
add('\n## 具体例子与没解决的问题')
for row in ex['rows']:
 if row['status']!='replayed':continue
 first=row['first_vote_difference'];reason_text={'compare_conflicting_sources':'比较仍活着的冲突来源','common_recommendation_protocol':'跟随共同建议','compatible_sources_protocol':'在不同建议中按位置选择','single_source_protocol':'跟随唯一有建议的来源','position_fallback':'按位置回退','private_refutation_or_check':'投私人已知匪'};kind={'gain':'输变赢','loss':'赢变输','blocked_but_still_loss':'挡过建议但仍输'}[row['category']]
 text=f"\n- {labels[row['base']]}，seed {row['seed']}，{kind}："
 if first:
  a,b=first['base'],first['gate'];roles=row['runs']['base_q50']['roles_evaluation_only'];fmt=lambda p:'弃票' if p is None else str(p+1)+'号'+{'police':'警','mafia':'匪','civilian':'民'}[roles[p]]
  text+=f"第{a['day']}天{'首轮' if a['round']=='first' else 'PK'}，{a['player']+1}号从投{fmt(a['target'])}（{reason_text.get(a['reason'],a['reason'])}）变为投{fmt(b['target'])}（{reason_text.get(b['reason'],b['reason'])}）。"
 else:text+='本次对齐记录未找到同一日同轮同玩家的第一张差票。'
 add(text)
add('\n例如177000002的后置近端局：第二天14号死警的新遗言和15号活警都查杀9号；9号匪接续跳警，建议出1号民。原路由因新增来源产生分歧，部分平民反去比较活来源并投15号真警。消融后这条无本人验人声明的建议不打散共同目标，平民投9号匪。两侧发言在该时点相同，改变的是采纳规则。角色仅为赛后解释，玩家当时仍不知道真假。')
add('\n案例按留出前追加口径各类升序首例整理，复用留出解释而非新证据。完整角色评价标签、公开消息、私人已知集合、逐票路由在results/v25_examples.json；对照首差票前信息相同，分叉后不能把不同观察当纯动作差。')
add('\n**本轮没有宣称修好了所有问题。** gate会挡住某些真实但暂未报验人的警察建议；本池真警一般会报真实验人，因此未检验这种潜在代价。匪伪造一条report就可绕过，这是已通过手工测试的合法边界，不需再刷种子来证明。若结果恢复，证明的只是建议资格通道在当前池内重要，不能据此把gate选成最终最佳防守。')
add('\n警队公开目标与实际票一致性的消融、跨日票型学习、公开怀疑/好人声明、遗言制度、4v4团队对冲仍分开待办；信用分保持冻结，等来源与信息更新更可靠后独立比较。今天不增加历史机械轮出、不把死者当认证身份、不把模拟低胜率写成真人游戏天然比例。')
add('\n两项旧漏洞、忽略合法已知匪、投私人已知好人、非法票在本轮所有正式格子的审计标记均为0；这核对特定规则，不证明其余推理完整。')
add('\n## 实际验证与复现')
add(f"\n实际运行：`python scripts/audit_source_routing_v25.py`两遍，4096个不同旧轨迹全部匹配胜负；`python -m pytest tests -q`：299 passed；`python scripts/run_source_advice_v25.py`：{man['games']:,}次正式新模拟；`python scripts/verify_source_advice_v25.py`：{check['status']}，{check['cells_checked']}单元核查、{check['sampled_unwrapped_replays']}条抽样无包装器重放、{check['baseline_v24_compatible_replays']}条v24兼容、{check['independent_binomial_intervals']}个独立二项区间反演通过，非全部独立重跑。")
add(f"\n`python scripts/diagnose_source_advice_v25.py`：{ex['detailed_replays']}条详细案例与同数无包装器重放一致；`python scripts/verify_source_audit_v25.py`：{aux['status']}，核对旧审计口径与首例选择。包冻结源码、配置、逐局原量、训练／留出和不选择声明齐备。案例整理脚本与报告在正式冻结之后补充，有单独口径记录，不冒称全在训练前。统计依赖SciPy {f['scipy_version']}。")
add('\n本轮是固定策略机制消融与开发审计，不是新算法、完整游戏GTO或抗池外反制证明。历史经验均衡证书原样保留，本轮没有重新求矩阵或扩大策略池。下一步建议只在了解本次机制结果后，由用户决定先检验来源资格的绕过代价，还是独立修正警方公共归票；票型学习应先定义来源条件与误判对照，再加到策略中。')
(ROOT/'docs/source_advice_results_v25.md').write_text('\n'.join(L)+'\n');print('wrote docs/source_advice_results_v25.md')
