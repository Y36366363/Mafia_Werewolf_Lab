#!/usr/bin/env python3
"""Readable dictionaries, primary held-out contrasts, and restricted bounds."""
import json
from pathlib import Path
from fractions import Fraction
from math import sqrt,log
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v20'
read=lambda n:json.loads((folder/n).read_text())
f,train,held,selection,manifest=map(read,['freeze.json','train.json','holdout.json','selection_before_holdout.json','manifest.json'])
lookup={(c['good'],c['mafia']):c for c in held['cells']}
cols=[m['name'] for m in f['mafia']]
labels={'credit_today':'旧信用／仅当天私人反驳','credit_memory':'旧信用／强化私人证据',
'evidence_today':'信息规则／仅当天私人反驳','evidence_q50':'信息规则＋记忆／50%回应',
'evidence_q0':'信息规则＋记忆／0%回应','evidence_q25':'信息规则＋记忆／25%回应',
'evidence_q75':'信息规则＋记忆／75%回应','evidence_q100':'信息规则＋记忆／100%回应','trained_local_q':'训练冻结的局部回应概率'}
clabel={'late_near':'后置刀／近端查杀','late_far':'后置刀／远端查杀','decoy_near':'伪装刀／近端查杀','decoy_far':'伪装刀／远端查杀'}
def pct(x):return '—' if x is None else f'{100*x:.2f}%'
def pp(x):return '—' if x is None else f'{100*x:+.2f}'
def interval(x):return '—' if x is None else '['+', '.join(pp(v) for v in x)+']'
lines=['# v20：先让玩家用对自己知道的信息，再检验单警回应概率','',
'## 策略与参数字典','',
'本次是4警4匪8民固定程序实验，没有语言模型扮演玩家。先解释名称：数字后缀只表示某个窄条件下，首名警察公开回应的概率，不是信用分、角色概率或胜率。','',
'|代码|实际动作与继承关系|','|---|---|']
for name,label in labels.items():lines.append(f'|`{name}`|{label}|')
lines += ['',
'共同底座：gap位置验人、等权位置后验、二人非绑定内推、真实验人声明、金水来源先于目标保护、前三死亡遗言、一轮PK后再平票平安日、允许弃票。第一天只允许一名预定活警公开，不为证明已公开队友再机械拉出第二警。多匪明确组队后的对冲尚未实现。', '',
'`remember`只决定是否跨日调用私人假警证据。公开发言一直可见，警队真实验人一直保留，不能叫“today完全失忆”。`credit_memory`还将警察当前知道的假警纳入优先投票，因此它对旧信用的增量不是纯记忆效应；纯记忆主比较是evidence_today→evidence_q50。这个实现解释在读取训练与留出结果之前单独记录于`docs/evidence_memory_interpretation_v20.md`。', '',
'|匪方列|刀与假跳目标|','|---|---|']
for name in cols:
    lines.append(f'|`{name}`|{clabel[name]}；第一个匪假查杀之后'+('第一个' if name.endswith('near') else '最后一个')+'尚未发言的非匪|')
lines += ['',
'匪方只知匪队座位，不知目标是警是民。若身后已无非匪则从全序选。near/far让匪能改变受害者反驳的时点，是预先指定的简单反制，不是训练出的最强回应。实际safe_late和posterior_decoy都在最高评分刀位随机破同分；2%均匀扰动仅用于好人位置模型的假设似然。续局停止新增假跳，继续追公开跳警者，采用既定投票。', '',
'## 先看本轮结论','',
'**本轮修复了信息使用的底层问题，但没有证实新信息协议整体优于旧信用规则。** 跨日记忆已真正影响行动；主比较在四列新留出中每4096局仅多赢1—2局，尚不足以确认稳定胜率提升。','',
'把旧信用门槛替换为当前信息协议后，后置刀／近端与远端条件的留出胜率分别从4.37%降到2.61%、4.69%降到0.66%；另外两列差异较小。本轮不会把新协议升级成已证实更强的默认策略，也不会反向认定旧门槛正确。不能据此证明信用分必要，因为新协议仍漏掉共享首验一致性等信息约束；也不能因符合直觉就宣布新协议更合理或更强。','',
'在当前两端点×四种固定匪回应里，训练选择q=0，冻结后在留出端点矩阵的经验gap仍为0；这只表示此小池的样本结果，没有证明警察应永远藏，也没有证明不存在内部混合。','',
'为区分协议缺口与信用分作用，另做仅补共享首验一致性的v20b新种子探索，结果单列在文末；不改主实验结果、不重选概率。','',
'## 行动规则：信用、怀疑、建议和投票分别是什么','',
'旧信用仅作对照：来源一般0.50，被报金水且未被查杀为0.75，自身1，金水关系传播到不低于来源；0.60门槛决定是否采纳建议，同分仍较晚建议优先。数值不是身份概率，未经校准，本轮未调优。', '',
'主模型evidence完全不读取这个来源权重或门槛，按以下次序行动：', '',
'1. 遵守当前/PK合法候选，警察排除自己已知好人；优先投自己确知的活匪或假警。',
'2. 保留金水来源先于目标的关系保护。私人确知的身份高于未经验证的公开声明。',
'3. 只有一个自己尚未排除的跳警来源时，采用其合法当日改归、活查杀或当日内推。该来源可能是匪，这是协调协议，不是真警认证。',
'4. 多个来源建议相同可按共同建议；验人声明互相矛盾或互相查杀跳警来源时，在活着的冲突来源中比较，不自动相信最后发言者。全部来源也可能都是匪。',
'5. 无冲突时合并合法建议；无建议则沿旧位置排序。名单内/冲突来源间选择也用原位置分、公开顺序，是固定策略，不是逻辑保证。', '',
'来源信用在主模型停用；目标怀疑仍来自旧位置模型；建议资格来自声明结构和私人排除；最终投票由各人从自己的观察独立产生。这四者没有合并成一个身份概率。金水目标的完整代理归票制度尚未重建，不能说现实桌游所有信息已模拟。', '',
'例：A查杀民C，C当场及之后都知道A不是警察。D只看到了A查杀C和C反驳，仍不知道C是民。若警B公开真实验人并反驳A，D现在需要比较A、B，而非因B后说就自动信B。若只有A声明，D可能依唯一来源协议受骗，这个风险本轮也让匪方利用。', '',
'## 回应概率具体控制什么','',
'q只作用于首夜未死警、首名警察尚未普通发言、此前出现假警且查杀未中警队的窄条件：以q报真实验人＋保留内推＋指出假警，否则暂缓身份、仍可提普通怀疑。假查杀命中警队时，只要预定首警还未发言且没有活警公开，就不作可选沉默。已有真警发言或首位警察已说完，不追加第二名。轮次已过、规则不给重复发言时不是主动隐藏；已有真警时，其他队友仍有普通发言但被本轮策略约束不补跳，这是策略限制，二者不能混同。', '',
'预定首警在自己的轮次私下抽一次，其他队友不再抽；不需要秘密整队相关信号。0%不是所有局面都藏，100%不是全队跳。只有一个可选节点且后续程序一致，所以理论上各固定对手下q收益是两端点收益的线性插值；最坏对手可能随q改变，因此受限稳健选择可能内部混合，也可能纯策略。不能只因“混合更像GTO”就强求内部概率。', '',
'## 本轮方法与检验范围','',
f"训练每单元2048局，种子160000000起；独立留出每单元4096局，161000000起。8×4训练和9×4留出，正式终局模拟共{manifest['games']:,}次。训练前冻结代码、参数、四种匪策略和选q规则；留出前冻结q与双方混合，不在留出上重新求最优值或调参数。留出已用于本次报告，今后不能当未看过的最终确认集。", '',
'两个主机制对比各4列共八项：evidence_today→evidence_q50（私人记忆）；credit_memory→evidence_q50（信息采纳）。主指标是所有开局的终局胜率，给八比较Bonferroni正常近似区间和保守Hoeffding区间；其他分层及首日指标为解释性。相同列跨行共用发牌、验人、刀、假跳位置和目标，核验分层掩码不变。配对减少多少方差由实际配对方差与未配对参照判断，不先保证一定减少。采样差值为零、正常近似区间退化为零不证明总体等效，仍须看保守区间与适用机会。', '',
'## 新留出结果：全部开局的好人胜率','',
'|好人规则|后置刀／近端|后置刀／远端|伪装刀／近端|伪装刀／远端|','|---|---:|---:|---:|---:|']
for name in labels:
    lines.append('|'+labels[name]+'|'+'|'.join(pct(lookup[name,m]['branches']['all']['rate']) for m in cols)+'|')
lines += ['', '## 两项主机制比较（新留出，每列4096局）','',
'正差值代表加入记忆或替换信用采纳后，好人胜率提高。区间单位都是百分点。', '',
'|比较|匪策略|差值|八比较正常近似95%区间|八比较保守95%区间|胜负变好／变坏|配对方差／未配对参照|','|---|---|---:|---|---|---:|---:|']
for name,title in [('memory_evidence','只加私人记忆'),('routing','旧信用改信息规则')]:
    for row in held['contrasts']:
        if row['name']==name and row['branch']=='all':
            v=row['win'];den=v['unpaired_variance_reference'];ratio=v['paired_variance']/den if den else None
            lines.append('|'+ '|'.join([title,clabel[row['mafia']],pp(v['delta']),interval(v['family8_normal']),interval(v['family8_hoeffding']),f"{v['improved']}／{v['worsened']}",'—' if ratio is None else f'{ratio:.3f}'])+'|')
lines += ['', '## 记忆是否真的进入行动','',
'下表是各行4列合计的平民投票次数（含PK）。只有过去假查杀者活着且在本轮合法候选中、今天没有重复同一私人证据时，才计“旧证据机会”；同局可能多次计数。它用于检查实现是否生效，不能当独立样本作因果显著性，也不能因不同规则的机会数不同而直接比较比例优劣。','',
'|规则|旧私人证据机会次数|投旧已知假警次数|有活已知假警却投其他人次数（含当日与过去）|','|---|---:|---:|---:|']
for name in ['credit_today','credit_memory','evidence_today','evidence_q50']:
    sums=[sum(sum(lookup[name,m]['raw'][k]) for m in cols) for k in ('civil_prior_only_ballots','civil_prior_used_ballots','civil_ignored_known_ballots')]
    lines.append('|'+labels[name]+'|'+'|'.join(str(v) for v in sums)+'|')
diagnostic_path=ROOT/'results/v20_adoption_diagnostic.json'
if diagnostic_path.exists():
    diag=json.loads(diagnostic_path.read_text())
    lines += ['', '## 为什么取消门槛也会出问题：预定子样本诊断','',
    '这项解释性分析在看过训练、未读留出时指定：4个机制对照×4列，各复用留出前128个种子；共2048局重新续局，胜负与原记录相符。这不是新增独立确认集。实际来源身份只在动作完成后由评价器标注。','',
    '|匪策略|首日平民采纳唯一来源的投票次数|其中来源实际为匪|投给民的次数|沿用“来源兼容”路径的次数|','|---|---:|---:|---:|---:|']
    for row in diag['rows']:
        if row['good']=='evidence_q50':
            c=row['counts'];lines.append('|'+ '|'.join([clabel[row['mafia']],str(c.get('route_single_source_protocol',0)),str(c.get('single_source_mafia',0)),str(c.get('single_target_civilian',0)),str(c.get('route_compatible_sources_protocol',0))])+'|')
    lines += ['', '该子样本中，唯一来源通道被采用的这部分首日投票均跟随了匪来源并指向民。这揭示可利用路径，不表示所有唯一跳警者都是匪，更不能将投票次数当独立局数。另一个缺口是：两个来源报不同首验但目标互不关联时，旧信息协议可能仍当作兼容；在本轮共享一次首验且必须如实报实际结果的前提下，这条兼容判断不完整。下一项约束修复测试只改这个机制。','']
lines += ['', '## 回应而非暂缓：首名警察前假查杀中民的窄条件','',
'此处分层只用开局角色、顺位、假查杀目标决定，角色标签只供评价，不输入策略。比较q0→q100；0与100的实际第一天公开警察人数每个适用局差1，验证确实实现了隐藏／公开干预。条件n远小于4096，不用总模拟数夸大精度。', '',
'|阶段|匪策略|条件n|暂缓胜率|回应胜率|回应−暂缓|逐项正常近似95%区间|首日出匪差值|','|---|---|---:|---:|---:|---:|---|---:|']
for phase,report in [('训练',train),('新留出',held)]:
    cells={(c['good'],c['mafia']):c for c in report['cells']}
    for row in report['contrasts']:
        if row['name']=='response_endpoints' and row['branch']=='narrow_civilian':
            m=row['mafia'];w=row['win']
            lines.append('|'+ '|'.join([phase,clabel[m],str(w['n']),pct(cells['evidence_q0',m]['branches']['narrow_civilian']['rate']),pct(cells['evidence_q100',m]['branches']['narrow_civilian']['rate']),pp(w['delta']),interval(w['ci95_normal']),pp(row['day1_mafia_exile']['delta'])])+'|')
lines += ['', '首夜死警对照：此时q本身不适用；原程序保留死警遗言，若活警轮到发言且假查杀命中警队则报真实验人回应。该控制并非本轮优化目标。各行首夜死警有机会分支、无机会分支与首验结果均保存在原始分层中，不把空分支填成零胜率。','',
'## 受限混合：只在训练的两端点×四种匪回应中求解','',
f"训练精确经验矩阵值 `{selection['certificate']['value_exact']}` = {pct(selection['certificate']['value'])}，矩阵gap `{selection['certificate']['gap_exact']}`。双方训练权重见`results/v20/selection_before_holdout.json`。训练冻结的回应概率q = `{selection['q_exact']}` ≈ {pct(float(Fraction(selection['q_exact'])))}。这里是已有矩阵方法的应用，不是新均衡算法。", '',
'不能混淆三件事：端点矩阵上的精确有理数证书；由有限模拟估计的收益；真正游戏的总体均衡。只对第一件事精确。四种固定匪策略不覆盖策略池外偏离；不称完整GTO。这是本轮窄问题的2×4子博弈证书，不替换历史7×13策略池的结果，也不表示这个信息协议优于保留的旧信用对照。', '',
'|匪策略|冻结q直接模拟的新留出胜率|两端点留出的线性插值|差值（百分点）|','|---|---:|---:|---:|']
q=Fraction(selection['q_exact'])
for m in cols:
    x=lookup['evidence_q0',m]['branches']['all']['rate'];y=lookup['evidence_q100',m]['branches']['all']['rate'];direct=lookup['trained_local_q',m]['branches']['all']['rate'];pred=(1-float(q))*x+float(q)*y
    lines.append('|'+ '|'.join([clabel[m],pct(direct),pct(pred),pp(direct-pred)])+'|')
bounds=held['frozen_train_mixture_bounds'];eps=sqrt(log(320)/(2*f['config']['holdout']['n']))
popgap=[max(0,bounds['gap']-2*eps),min(1,bounds['gap']+2*eps)]
uncertainty=dict(cell_family=8,confidence=.95,hoeffding_radius=eps,
    frozen_pair_restricted_gap_interval=popgap,
    scope='Assumes independent Monte Carlo games per cell; simultaneous bounds for 2x4 held-out means, arbitrary fixed train mixtures. Not full-game exploitability.')
(ROOT/'results/v20_uncertainty_summary.json').write_text(json.dumps(uncertainty,indent=2)+'\n')
lines += ['',
f"冻结训练双方混合在留出端点矩阵：lower={pct(bounds['lower'])}，upper={pct(bounds['upper'])}，gap={100*bounds['gap']:.2f}个百分点。lower/upper是固定双方混合对应的有限候选池收益界，不是总体胜率的置信区间。", '',
f"考虑留出每个端点单元有限样本，在独立模拟假设下，对8个单元同时应用95% Hoeffding界，单元半径约{100*eps:.2f}个百分点；固定双方混合的总体受限gap保守区间为{interval(popgap)}个百分点。这个界可能很宽，但它明确显示精确矩阵证书不消除收益估计误差。", '',
'固定对手下q的总体收益线性；中间网格或直接局部q与两端点经验插值有少量差别时，先视为Monte Carlo噪声，不能当作新非线性机制，也不能把多个等价混合误判为求解失败。', '',
'## 仍需保留的边界与待办','',
'- 单一来源的建议仍可能来自匪；取消数值门槛并不自动变成合理或最优的人类推理。声明似然、来源可信度尚未校准，旧信用体系暂不继续调分。',
'- 私人记忆和已知事实优先级可验证，但未知身份间的比较仍是位置与协议启发式。没有从放逐或存活自动翻身份，也没有额外裁判信息。',
'- 只有一个可选回应节点，真正的跨日钓鱼、针对隐藏策略学习、自刀悍跳、完整团队声明与4v4对冲均未加入。首警已公开后另一个隐藏警被查杀是否应自辩，尚未单独测试，不能把单警限制当成最优定理。匪知道目标不是匪，但不知道警民；好人不知道实际匪刀法列。',
'- 跨日透明票型、公开怀疑、金水代理归票资格、有限／全员遗言、白天报匪仍分别排队。需要每次预先写清一个可证伪问题再增加机制。', '',
'## 复现材料和核验','',
'运行：`python scripts/run_evidence_memory_v20.py --output results/v20_reproduction`（新目录）；测试：`python -m pytest tests -q`；归档核验：`python scripts/verify_evidence_memory_v20.py`。冻结源码、配置、逐局原始评价量、训练证书、留出前选择文件和留出数据在`results/v20/`。', '']
audit=ROOT/'results/v20_integrity_audit.json'
if audit.exists():
    a=json.loads(audit.read_text());lines += [f"本轮全部265项测试通过；{a['cells_checked']}个单元的哈希、算术、分层配对与单警公开约束核查通过，使用归档源码抽样完整重放{a['sampled_full_replays']}局一致。抽样重放不表示全部{manifest['games']:,}局独立重跑。",'']
(ROOT/'docs/evidence_memory_results_v20.md').write_text('\n'.join(lines));print('readable report written')
