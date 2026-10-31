#!/usr/bin/env python3
"""Readable report for frozen execution calls and a separately scoped history pilot."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
f=load('results/v26/freeze.json');tr=load('results/v26/train.json');ho=load('results/v26/holdout.json');man=load('results/v26/manifest.json');audit=load('results/v26_integrity_audit.json');aux=load('results/v26_aux_integrity_audit.json');ex=load('results/v26_examples.json')
D={(c['good'],c['mafia']):c for c in ho['cells']};bases=('late_near','late_far','decoy_near','decoy_far')
labels=dict(late_near='后置刀／近端假查杀',late_far='后置刀／远端假查杀',decoy_near='伪装刀／近端假查杀',decoy_far='伪装刀／远端假查杀')
def label(m):
 b=next(b for b in bases if m.startswith(b));return labels[b]+'／'+('接续跳警' if '_claim_' in m else '原人重申')+'／'+('保结果倒钩' if m.endswith('_bus') else '原匪票')
P=lambda x:f'{x*100:.2f}%';PP=lambda x:f'{x*100:+.2f}';CI=lambda a:'['+', '.join(PP(x) for x in a)+']'
L=[]
def add(s=''):L.append(s)
add('# v26：验人信息与执行归票分开；来源条件票型先作小试验')
add('\n2026-10-31。先验证警方执行归票，再单独比较票型；不把二者揉成一个增益。本轮未调用LLM API，也未按训练或留出数字选新策略/q。')
add('\n## 策略／参数字典')
add('\n|名称|实际动作与继承|\n|---|---|')
for a,b in [('legacy_q0/q50/q100','v25的gate资格规则、双修复与私人记忆；局部回应概率0%/50%/100%。'),('aligned_q0/q50/q100','第二天起，已有验人发言的警察保留report和内推，补明确“今天出X”；警队若X合法且仍私知匪就跟首个队友执行目标。'),('history_q50','在aligned_q50上加来源条件票型计数，只在原候选池里打破未解决的多选。'),('team','原固定匪队投票，通常不会投自己的队友。'),('bus','仅小试验：最后发言的活匪在实时票差保证队友已必然被放逐时，可以跟票该队友；不改变当日放逐，不保证后续零成本。'),('late/decoy','safe_late后置位置刀／posterior_decoy位置伪装刀；不使用未知警民标签。'),('near/far','首日首位匪按其后公共发言序选最近／最远非队友假查杀。'),('restate/claim','原首日假警自己重申／原假警死后由队友自己跳警并建议同一旧目标。'),('q','单警在规定窄条件下的局部抽样概率，不是来源信用、目标身份概率或全局跳警率。')]:add(f'|{a}|{b}|')
add('\n**共同规则：** 主配置4警4匪8民、警互认共享验人、真警只报实际验人、死亡不翻身份、前三死亡有遗言、可弃票、一轮PK再平票平安日。普通投票是继承的公开顺序投票，各票不可撤回；全轮完成后才进入新的票型计数。不是同时投票。规则允许自刀，但本池无自刀；无平民假跳。gap验人、等权位置似然、二人内推不变，2%仅在好人位置似然假设，未加到实际匪刀。')
add('\n**q窗口：** 首夜未死警、预定首警仍有自己的发言机会、假警已发言且假查杀没中警队时，才由这一个警察抽样；首日被打中警队的既定必答及后续策略不变。执行归票从第二天才开始，不借机制比较改首日q。')
add('\n来源信用继续冻结。source_credit=True是兼容字段，routing=evidence没有调用数值信用；remember=True保留跨日私人证据，history=False仅停用旧票型加分模块，和本轮独立vote_history开关不同。')
add('\n## 本轮结果先看这三件事')
main=[r for r in ho['contrasts'] if r['primary']];pilot=[r for r in ho['contrasts'] if r['kind']=='history']
add(f"\n- 明确执行归票：八个预定q50比较中，{sum(r['precision']['ci_simultaneous'][0]>0 for r in main)}项同时95%区间全在零上，{sum(r['precision']['ci_simultaneous'][1]<0 for r in main)}项全在零下，其余未分辨方向。不能只因动作更一致就宣称终局改善。")
add(f"- 票型小试验：四项中，{sum(r['precision']['ci_simultaneous'][0]>0 for r in pilot)}项区间支持提高、{sum(r['precision']['ci_simultaneous'][1]<0 for r in pilot)}项支持降低；是否覆盖到可决策局面另表报告，不由胜率零差直接推无用。")
add('- 死亡仍不认证身份。公开报验人与今天执行目标可以不同；当前验人不是唯一已知匪时，报5、明确归3、实际投3是合理的一致行动。')
add('\n主要提升集中在固定的接续跳警条件，而原人重申条件增量很小。对手可以选择不接续，不能把19%—27%的条件胜率写成总体稳健胜率；q50八个原条件的经验最差列仍约5.76%。本轮未测试匪不悍跳或重新选择发言时点的最强回应。')
add('\n## 执行归票具体改了什么')
add('\n警察视角包含队友与共享验人，平民没有这些秘密。旧规则可能报“5是匪”，警队却按所有私知匪排序去投3，平民只读到5的验人。现在同一个原有发言者保留真实report和shortlist，再明确说“今天出3”。公开建议路由优先读这个当日accuse；警方也跟首个真实队友的合法私知匪执行目标。不是让平民知道警队名单。原内推仍是怀疑名单；明确出人可指向名单外、警队已有私人反证的目标，不再把“名单里选谁”与“今天必须出谁”混成一件事。')
add('\n没有额外发言轮次或新增警察跳出，但确实增加一条声明内容，所以这是**公开协调协议干预**，不能说成完全同语义预算、纯改投票的一致性修复。匪也能使用同一合法accuse模板；固定反制仍可重申、接续、冲票，本轮未学习最强回应。公布执行目标与警队跟随是在同一协议中一起改变，尚未做二者独立贡献的分解，不能把全部增量归因于某一行投票条件。')
add('\n调用只在原警察自己的普通发言位置，前后位由既有座位/死者决定，没有强行把警察移动到前置位；因此本轮不能声称已检验“前置位一定最佳”。金水接力归票未加入，需独立规定委托与可疑来源，不把单方金水当裁判认证。')
add('\n## 新种子与配对方法')
add(f"\n主比较6行×8旧匪条件48格；票型小试验增加6格，54实际单元，非完整7×10矩阵。训练179000000起每格512局，新验收180000000起每格2048局，共{man['games']:,}次正式模拟。没有按训练选择q/策略；全部预定小试验也照常运行，不以主实验数字决定是否加入。")
add('\n同q的legacy/aligned第一天和第二天普通发言前前缀逐局相同；aligned/history直到第二天第一次投票前逐局相同。后续不同死亡会改变验人、发言与刀，不强行保持不可能相同的续局。')
add('\n八个alignment q50是一个同时95%比较族；四个history是另一族。分别给CP正负翻转概率组合区间、正常近似、Hoeffding；两族不能合称12项整体95%。CP在正式训练前规定，需每比较跨seed iid模拟假设，列间共享seed不需独立；不是收益无误差或有理数均衡证书。')
add('\n## 主实验：明确归票与终局收益')
add('\n|匪条件|legacy q50|aligned q50|差（百分点）|八项同时95%二项组合区间|赢转输／输转赢|\n|---|---:|---:|---:|---|---:|')
for r in main:
 a,b=D['legacy_q50',r['mafia']],D['aligned_q50',r['mafia']];w=r['win']
 add(f"|{label(r['mafia'])}|{P(a['win']['rate'])}|{P(b['win']['rate'])}|{PP(w['delta'])}|{CI(r['precision']['ci_simultaneous'])}|{w['worsened']}／{w['improved']}|")
add('\n原预定区间同时保留：')
add('\n|匪条件|校正正常近似95%区间|Hoeffding保守95%区间|\n|---|---|---|')
for r in main:add(f"|{label(r['mafia'])}|{CI(r['win']['family_normal'])}|{CI(r['win']['family_hoeffding'])}|")
add('\n## 一致性指标：不能继续只用“报谁是否投谁”')
add('\n下表合计q50主实验八个条件的动作次数；同局可重复，不当独立样本。')
add('\n|指标|legacy|aligned|含义|\n|---|---:|---:|---|')
for flag,title,meaning in [('report_vote_mismatch_ballots','验人报告目标与票不同','可能合法：明确归另一个已知匪后，不应再叫失误'),('call_mismatch_ballots','合法且私知匪的执行目标与警方票不同','开启执行协议后应为0；PK候选外不强迫跟票'),('police_split_rounds','有私知匪的警队内部投票分散轮次','与平民是否跟到同一目标是两回事'),('call_count','显式执行声明次数','主实验的新公开信息内容')]:
 vals=[sum(sum(c['raw'][flag]) for c in ho['cells'] if c['good']==pre+'_q50' and c['mafia'].endswith('_team')) for pre in ('legacy','aligned')]
 add(f'|{title}|{vals[0]}|{vals[1]}|{meaning}|')
add('\nlegacy的call违背为0是因为没有新协议，不能解读成原来已正确表达执行意图；两侧警队内部原本都不分票。主要变化是把私有证据变成公开可执行的建议，而非把警方从分散票变抱团。')
add('\n## 来源条件票型：到底如何加减')
add('\n这不是重新启用信用。对已完成投票，依据观察者当时的合法信息，每名投票者每天最多一个计数：')
add('\n|行为|计数|解释|\n|---|---:|---|\n|投私人已知匪|−1|降低对该投票者的怀疑排序；倒钩也可获得它|\n|否则投私人已知好人|+1|可能跟错票，不能直接判匪|\n|否则跟已被自己合法反证的来源，且无未反证声明源也推同目标|+1|来源条件关联，仍非身份铁证|\n|其他/弃票|0|不因弃票或改口本身惩罚|')
add('\n+1/−1是人工等权的“日证据计数”，无校准，不是概率。累计在[-完成天数,+完成天数]，同日PK最新完整结果覆盖首轮，避免一日重复计分；目前不把后来验人回填成历史时点已知。旧日死亡也不提供阵营标签。公开金水保持来源关系，没有直接变私人确证。')
add('\n仅当原路由给出至少两个未解决候选时，先按怀疑计数较高者投；同分沿用旧位置排序。不得越过金水保护、私人已知匪或唯一明确建议。前置/后置改变归票及PK新增信息不会因为“声明与票不同”自动受罚。部分平民没有可用确证，计数覆盖低是应报告的结果。观察者知道某源是假，不代表其他投票者当时也知道，所以+1仍可能误伤合理跟票。当前只处理轮次、历史前缀和候选合法性，尚未完整建模每个投票者的替代选择或改归理由，不能称完整票型推理。')
add('\n## 小试验：票型收益及匪方倒钩')
add('\n|条件|aligned q50|history q50|差（百分点）|四项同时95%二项组合区间|进入多选且有证据局／2048|实际改票局／2048|bus执行次数|\n|---|---:|---:|---:|---|---:|---:|---:|')
for r in pilot:
 a,b=D['aligned_q50',r['mafia']],D['history_q50',r['mafia']]
 add(f"|{label(r['mafia'])}|{P(a['win']['rate'])}|{P(b['win']['rate'])}|{PP(r['win']['delta'])}|{CI(r['precision']['ci_simultaneous'])}|{sum(b['raw']['history_available_game'])}|{sum(b['raw']['history_changed_game'])}|{sum(b['raw']['bus_count'])}|")
add('\n保结果倒钩只在“当前目标票数>其他最高票+全部尚未投票人数”时触发，最后活匪可投非自己的队友；无论自己和后续怎么投，队友本来就会出局。它说明投已知匪可以被伪装，不表示主动卖队友从无收益。这里只在两组预定条件运行，不能称全反制池。')
add('\n本批伪装刀条件的票型增量约1.27个百分点（同时区间+0.41至+2.11），值得继续；后置刀约0.29个百分点（−0.21至+0.80），尚未分辨。两种投票模式的相同终局统计不是四份互相独立复现，同一seed配对相关。')
add('\n事后追加、复用已选案例180000002可看到具体伪装：13号平民私下知道首日查杀自己的1号是假警，首日12号匪曾投自己，因此在内推10/12中由10号民改投12号匪。保结果倒钩模式下，12号已跟票必出的1号，其日计数从+1变−1，13号不再通过该计数优先投12，回到10号。两侧最后仍输，说明终局零差也能掩盖局部信号被洗掉。该追加例保存在results/v26_bus_signal_example.json，不作新确认数据。')
add('\n计数启发式若没有稳定终局证据，不晋升默认策略。零差要结合改票覆盖及bus是否触发，不把“少数改票而未改变结果”写成所有票型推理都无用。更强分票、主动卖队友、诱饵与来源条件更新仍待单独设计。')
add('\n## 跳藏继续作为常用参数')
add('\n下表只在主实验八个原条件中取经验最差列，不据留出挑比例，也不新求均衡。')
add('\n|阶段|规则|q0|q50|q100|\n|---|---|---:|---:|---:|')
for phase,report in [('训练',tr),('新验收',ho)]:
 for pre in ('legacy','aligned'):
  values=[min(c['win']['rate'] for c in report['cells'] if c['good']==pre+'_q'+q and c['mafia'].endswith('_team')) for q in ('0','50','100')]
  add(f'|{phase}|{pre}|'+ '|'.join(P(v) for v in values)+'|')
add('\nq0不是永远藏，q100不是全警队跳；本轮没有训练最佳比例。条件化与局部混合仍保留，后续须根据当时可见局面定义。q50直接抽样可与端点估计均值有有限样本差，不能把微小差当非线性收益或求解失败。')
add('\n## 具体对局与修复边界')
reason={'common_recommendation_protocol':'共同建议','compare_conflicting_sources':'比较活冲突来源','compatible_sources_protocol':'建议并集位置选择','private_refutation_or_check':'私人已知匪排序','private_bad_team_execution_call':'跟合法私知匪的队友执行目标','single_source_protocol':'单来源建议','position_fallback':'位置回退'}
for row in ex['rows']:
 if row['status']!='replayed':continue
 kind_text={'alignment_gain':'明确归票后输变赢','alignment_loss':'明确归票后赢变输','called_still_loss':'有明确归票仍输','history_first_change':'票型首次改票'}[row['kind']]
 add(f"\n- {label(row['mafia'])}，{kind_text}，seed {row['seed']}：")
 for gn,run in row['runs'].items():
  chain=[]
  for e in run['transcript']:
   if e['event']=='day_death':
    p=e['payload']['victim'];rr=run['roles_evaluation_only'][p];chain.append(f"第{e['day']}天出{p+1}号"+{'police':'警','mafia':'匪','civilian':'民'}[rr])
  add('  - '+gn+'：'+'；'.join(chain)+'；'+('好人赢' if run['raw']['win'] else '好人输')+'。')
add('\n明确归票首收益例180000003（后置远端）：第四天8号真警报15号金水，保留5/6二人内推；9号匪早在第二天就已接续跳警，警队凭互认一直知道其为假警，却未验过9。旧规则当天错出5号民；新规则8号补“今天出9”，平民跟出最后一匪，当天获胜。这不是新增验人，而是将早已有的私人来源反证用于公开执行。')
add('\n这依赖当前池排除了平民假跳：真警认出队外假警才能进一步视其为匪；如果以后加入平民掩护假跳，这条推理及票型计数都必须调整。当前匪接续暴露的代价被协调协议回收，因此原本有害反制可转为帮好人找匪；尚未说明对手仍会选择这种已不利的反制。')
add('\n例子按预先追加口径取种子最小者，未匹配的类别不虚构。首差票、当时已知匪、明确执行目标、票型日计数及含终止夜的透明夜行动均保存在results/v26_examples.json；角色标签仅用于赛后评价，不进入策略。例子复用验收是解释，不增加独立样本。')
add('\n对旧174000033开发例的legacy/aligned重放单独保存，不算新确认；旧例中第二天10号警仍报5号真查杀，但明确归3号；三名活警都投3号，最终放逐由旧5号匪变为3号匪。验人信息与执行目标不同可以保留，真正要消除的是未表达的执行意图和未跟随合法执行目标。')
add('\n## 什么时候接入LLM API')
add('\n目前还不用把LLM放入主模拟。此次问题可用可复查的结构化规则定位；LLM不会自动解决来源、时间或权限错误，也不能把其解释当真实身份或均衡证据。本轮没有API请求或外部调用费用。')
add('\n更合适的切入点是：明警/金水的建议权限、执行目标、跨日信息和票型前缀已经稳定可重放；接下来真正需要研究的是语言歧义、临时改归理由、诱导或说服。不必等完整GTO；只要核心信息权限和对应任务的动作接口可复查，就可先设计小批冻结案例的“影子解释/动作建议”，不改变正式策略，并让用户先判断几例再比较模型建议。')
add('\n影子输入只给该玩家Observation：自己的身份/合法队友与验人、截至发言时的公开历史；删除赛后roles_evaluation_only、未来票和未来验人。输出限制为合法声明/提名/投票并附引用来源。记录模型/提示词版本、随机设置、成本、失败与权限违规，再用新留出比较。若切入自然语言，双方需相同信息与动作/发言资源，分开比较语言解析质量和整局胜率；不要把更长发言、额外思考或裁判真相混作策略收益。')
add('\nLLM可以辅助检验人类可理解性、解析自然语言、提出候选策略；裁判、信息投影、收益统计和精确证书继续由程序检查。开始这些有费用的API实验前，需另定预算和模型，不在今天自动接入。')
add('\n## 验证、复现与下一步')
add(f"\n实际运行：`python -m pytest tests -q`：307 passed；`python scripts/run_police_execution_v26.py`：{man['games']:,}局正式新模拟；`python scripts/verify_police_execution_v26.py`：{audit['status']}，{audit['cells_checked']}个实际单元核查、{audit['sampled_unwrapped_replays']}条抽样无包装器轨迹、{audit['legacy_v25_compatible_replays']}条v25兼容、{audit['independent_binomial_intervals']}个独立二项反演；不是全部模拟独立重跑。")
add(f"\n`python scripts/diagnose_police_execution_v26.py`：{ex['detailed_replays']}条详细/无包装器/透明夜行动重放各自一致；`python scripts/verify_police_execution_aux_v26.py`：{aux['status']}。训练/验收配置、冻结源码、逐局量、不选择声明和统计完整。案例/报告在冻结后追加，口径先于查看验收保存；不是所有整理脚本都预注册。SciPy {f['scipy_version']}用于二项区间。")
add('\n补充实际运行：`python scripts/diagnose_bus_signal_v26.py`，复用预定首票型案例对应的另一投票模式，2条详细与2条无包装器重放匹配原raw。它是查看结果后追加的局部解释，未改策略、不增加独立胜率样本。')
add('\n两项旧漏洞、忽略合法已知匪、投私人好人、非法票与合法执行目标违背分别核查；零标记只验证指定规则。没有新经验矩阵均衡，也没有完整游戏GTO或真人胜率结论。数值信用继续冻结。')
add('\n后续由本轮机制证据决定：优先解释明确归票的收益/代价及保留失败例；金水在合法发言位置接力归票应单独规定来源资格和反制。票型若低覆盖或未显示稳定收益，继续作为小试验，先补真实可用证据/反制，不能用更多任意分数替代推理；跳藏与局部条件混合继续保留。')
(ROOT/'docs/police_execution_results_v26.md').write_text('\n'.join(L)+'\n');print('wrote docs/police_execution_results_v26.md')
