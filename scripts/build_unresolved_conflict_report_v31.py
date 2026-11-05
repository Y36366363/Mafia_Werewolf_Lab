"""Human-readable report from frozen raw evaluation, never modifies decisions."""
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]

def pp(v):return f'{v*100:+.2f}'
def run():
 data=json.loads((ROOT/'results/v31/holdout.json').read_text());D={(c['good'],c['mafia']):c for c in data['cells']};check=json.loads((ROOT/'results/v31_integrity_audit.json').read_text());diag=json.loads((ROOT/'results/v31_examples.json').read_text());man=json.loads((ROOT/'results/v31/manifest.json').read_text())
 G=['legacy','neutral','aligned'];M=['late_old','late_copy','late_quiet','decoy_old','decoy_copy','decoy_quiet','false_notice','false_grant']
 def rate(g,m,branch=False,key='win'):
  a=D[g,m]['raw'];mask=a['dead_clear'] if branch else [1]*len(a['win']);n=sum(mask);w=sum(v for v,k in zip(a[key],mask) if k)
  return f'{w}/{n} ({100*w/n:.2f}%)' if n else '—'
 def interval(c,key='win'):
  lo,hi=c[key+'_precision']['ci_simultaneous'];return f'{pp(c[key]["delta"])} [{pp(lo)}, {pp(hi)}]'
 s='''# v31：不认证死者的首日冲突处理与公开意图一致性

2026-11-05。本轮先修订研究问题再冻结评估，不追求把胜率调高。主配置4警4匪8民；结果是固定候选策略评估，没有新均衡或完整游戏GTO结论。

## 1. 策略和参数字典

先区分：来源的可信程度、目标的怀疑程度、委托归票权限、实际投票是不同对象。本轮没有新增数值信用、身份概率或加减分规则；信用与复杂票型继续冻结。`v31`是版本；q=50表示既有可选回应节点以50%跳警，不是信用50%。q0/50/100仍可配置，主矩阵固定50；真死警开局没有该可选节点。

| 好人行 | 实际规则 | 对照边界 |
|---|---|---|
| legacy | v30 evidence_guard：原有见证优先金水改归，首日接收器以有效遗言授权触发 | 旧API精确兼容参考 |
| neutral | 首日无论有无授权，都区分名单/明确建议并检查来源相容；只有两端都活的冲突才可直接比较；死/活冲突保留未决，按建议并集/位置排序选目标 | 移除授权开关和存活端直接指令；不保证猜对谁真 |
| aligned | 同neutral；获遗言授权的平民在既有末尾槽用投票接收器选目标并公开；首日已有公开验人的警察在普通发言内用同选择器明确已知匪归票，警队仅在自己已知是匪且合法时跟随 | 同时统一选择器及使用完整合法候选范围，是实现组合，不称纯单因素 |

neutral/ aligned公开授权都允许在场非自己的目标；neutral旧见证选择器通常只用名单或见证对象。自己的relay不用于给自己循环证明，旁观者只把它当原来源建议替代，不增加一个独立警察。后续新信息或PK候选变了仍可改票，不通过强制听错话追求表面零差。day2+续局保持旧规则。

| 匪列名 | 具体动作 |
|---|---|
| late_old / decoy_old | safe_late / posterior_decoy首刀；首个匪远位假查杀，原人可重申、死后队友可接续，团队票 |
| late_copy / decoy_copy | 到自己普通发言时若已见首死金水，复制该公开金水并明确归最远合法非队友；排除金水，匪不知该非队友警/民；无可复制结果则回old |
| late_quiet / decoy_quiet | 首日匪全部过，不悍跳；之后按既有续局 |
| false_notice / false_grant | 首夜固定首个匪自刀，遗言报公开顺序首个非队友金水，给两名非队友内推；前者无授权、后者有授权，其余匪首日过 |

copy/quiet可能没有旧接续所需的首日假查杀记录，故这些是整套策略对照，不把全部收益归给一个首日字段。false两列同发牌/首验/首死，专测授权；自刀成本比较则必须对普通刀的**全部发牌**，不能只取真死警分支。自刀后的授权伤好人，不代表付出一匪的自刀优于普通刀。**继承位置模型的限制：**当前seat_scores仍按普通非队友刀的似然排除首死者，并在未知座位枚举原配置匪数；它未联合建模“死者可能为自刀匪”的角色后验。故自刀对照只评价冻结代理在模型错配下的实际行为，不能称为双方对自刀充分贝叶斯回应后的收益。此轮只修来源动作规则，不把全信息集/位置后验称为已修完整。运行后核对继承代码的范围补注：false列任一首日有遗言的匪（包括当天又被放逐者）也会报假金水/名单，false_grant还追加授权；主要offer仍只取首夜死者，其他声明仍进入公共历史。它不是仅一条假遗言的纯刀法消融，未修改v30代码。

规则：448、警队互认共同验一人、被刀仍得当夜验人、匪知自己队友但不知警/民；杀光警察匪胜、杀光匪好人胜；不翻身份，前三死遗言；可弃票，一次PK复投仍平票平安日；公开顺序不可撤回投票。金水末尾槽与遗言多字段是研究资源。没有平民假跳/真警乱报的候选，警队私人辨伪依赖此前提。两人名单、q1/2、先验与2%似然平滑均继承，未经本轮调优；2%是模型防零而非真实匪刀新增随机性。

## 2. 偏置为什么发生，与你指出的跳警矛盾如何对应

旧路径有两层：首先首日的冲突表保留死/活两端，但可投目标只剩活端；随后v29/v30把“有有效遗言授权”作为启用新接收器的条件。于是同一遗言只多一个delegate字段，就能从名单交集改成优先投存活冲突源。这没有明文写死者真，但行动效果相当于偏向死者。死亡不翻身份时，此推论不合法。

修复后，授权只决定谁可以更新建议，不决定谁是假警。未决冲突不凭一端已死而指定另一端；**这不意味着活来源免死**，也不意味着名单一定比来源可信。若活来源被独立查杀、被自己的言论反证或另有合法建议，仍可投他。

首夜真死警时，当前既定警队策略通常不再额外暴露活警，但已有“首位活警看到假查杀命中警队则防御报告”的强制分支；匪仍可以选择跳出来争夺解释权。首夜自刀时，警队知道死者不在自己队伍，真实发言者可能会回应。平民不知道自己处于哪个评价分支。故“死者报金水后又有人跳”值得怀疑，但不是不需要分析的定理。

**你的质询还指出一个真实局限：**当前闭眼玩家没有根据“真警在这种时点本应少跳”的策略生成概率，建立完整来源贝叶斯后验。相容检查只是排矛盾，不能推得某个来源的概率；本轮不增加一个未经校准的扣分来代替这项推理，也不声称已经合理理解警队为何补跳。警队验人信息保持在警察自己的观察里，评价侧的真/假标签不传入接收器。

## 3. 方法、冻结与不确定性

24单元=3行×8列。开发每格64局（194000000起）；新验收每格2048局（195000000–195002047）；正式共50,688局，逐局运行。烟测196000000起2局/格，共48局另计。正式共享2112个基础seed，不是50688份独立牌。开发后没有选行、改规则、改q、选种子或训练回应。旧192000016/192000073仅作机制重放，不算新确认。

37个预设对照、两项共同主要指标（终局好人胜/首日放逐匪），共74项家族95%同时区间：16个接收器比较、12个old→copy/quiet比较、3个假授权比较、6个普通quiet→自刀授权全发牌比较。采用配对正负翻转率Clopper–Pearson界+union bound。数字均是有限样本收益估计，精确计算区间或矩阵算术不消除抽样误差；未显著不证明等价。

前两类普通刀主要条件固定为首死真警且首验非匪，仅评价者知道；false列及自刀成本用全部发牌。一般比较同首夜状态；自刀成本只能匹配发牌Nature，因为首夜行动正是被改变对象。所有重要比较预先指定，74项数字全部存holdout.json。下面区间单位为百分点。

## 4. 新验收：先看同口径结果

### 4.1 全部发牌的终局好人胜率（每格2048局）

这张表回答整套策略表现与自刀资源成本。不可与下一张条件胜率混用。

| 匪列 | legacy | neutral | aligned |
|---|---:|---:|---:|
'''
 for m in M:s+='| '+m+' | '+' | '.join(rate(g,m) for g in G)+' |\n'
 s+='''
### 4.2 仅首夜真死警且首验好人的终局胜率

| 匪列 | legacy | neutral | aligned |
|---|---:|---:|---:|
'''
 for m in M[:6]:s+='| '+m+' | '+' | '.join(rate(g,m,True) for g in G)+' |\n'
 s+='''
### 4.3 两个修复步骤，终局差及家族95%区间

正值有利好人，负值也必须保留，不能为保留旧真死警增益恢复来源偏置。

| 匪列 | legacy→neutral | neutral→aligned |
|---|---:|---:|
'''
 for m in M:
  row=[]
  for a,b in [('legacy','neutral'),('neutral','aligned')]:
   c=next(c for c in data['contrasts'] if c['kind']=='receiver' and c['control']==[a,m] and c['treatment']==[b,m]);row.append(interval(c))
  s+='| '+m+' | '+' | '.join(row)+' |\n'
 s+='''
### 4.4 授权本身与自刀是否划算

false_notice→false_grant检验同一次自刀多授权；quiet→false_grant检验整套正常首刀与自刀，两边首日其余匪均不悍跳。不是“单独刀法成本”的纯消融，也不能对所有可能自刀战术作支配判断。

| 好人行 | 匪方变化（全部发牌） | 好人终局变化[同时区间] |
|---|---|---:|
'''
 for c in data['contrasts']:
  if c['kind'] in ('false_authority','selfkill_cost'):s+=f'| {c["control"][0]} | {c["control"][1]}→{c["treatment"][1]} | {interval(c)} |\n'
 s+='''
**核心判断：**

- 旧规则给死者隐性优势，修复在两个方向都有后果。真死警旧假查杀条件：late从88/489胜降到neutral27/489，decoy从29/421降到0/421，两项下降有同时区间支持。假自刀授权则从154/2048升到317/2048，同时区间支持好人改善。不能只报告后一项。
- 旧“多授权”在同自刀下使192胜变154胜（净-38）；修复后neutral为323→317，aligned为323→322。aligned差-0.05个百分点、74项同时区间[-0.74,+0.64]；不再有原先的显著损害，但未证明总体严格相等。新规则的授权删除不变性只指**没有真实relay时**，不是说授权永远不能经合法接力改变行动。
- 统一意图在late_old条件使27→49胜，有35局转赢、13局转输，净多22；增量+4.50个百分点，同时区间[-2.65,+11.46]，尚不足以确认稳定终局收益。decoy_old仍0胜，不能写成一致性修复解决了鉴真。
- 你的自刀质询在固定方案下得到支持：aligned自刀授权好人322/2048=15.72%，普通late_quiet83/2048=4.05%，decoy_quiet52/2048=2.54%；对应匪胜84.28%、95.95%、97.46%。相对这两个普通quiet计划，自刀对匪明显更差，两项家族区间支持。不能外推所有自刀劣势，也不能从自刀差推出旁观者应100%信死者；它相对其他非quiet计划可能有不同收益。

### 4.5 冻结回应能否在新接收器上回调（aligned条件分支）

| 匪方变化 | 首日出匪差[同时区间] | 终局差[同时区间] |
|---|---:|---:|
'''
 for c in data['contrasts']:
  if c['kind']=='opponent' and c['control'][0]=='aligned':s+=f'| {c["control"][1]}→{c["treatment"][1]} | {interval(c,"day1_mafia_exile")} | {interval(c)} |\n'
 s+='''
**回应效果会随好人规则改变：**旧接收器下copy显著伤害decoy的真死警分支；新aligned下old/copy都0/421胜，因此这批没有进一步终局下降的空间，不能叫“已成功防住copy”。late中old49胜、copy64胜，方向甚至相反，但差的同时区间跨0，不能反过来宣布copy稳定有利好人。quiet在late仍使49→9胜，降8.18个百分点，区间[-14.23,-1.78]。所以不能把“更会反制”简单等同匪胜率单调上升；反馈是接收规则与具体候选的关系，而非无限叠加优势。

**如何判断“过拟合”：**这些匪策略是在本轮之前已提出、未在本轮开发/验收拟合的结构性回应，独立seed可以查抽样偶然性；不能因此证明它对所有好人策略稳健，也不能证明它是最佳回应。刻意针对公开接收规则本就是对手应有能力；应区分“利用有限策略弱点”和“针对验收seed选战术”。本轮只支持前者的固定池评价，不直接计算完整exploitability。

预先固定的前/后1024种子方向核查（条件分支，百分点；仅描述，不追加显著性检验）：

| 好人行 | 刀／回应 | 前半 | 后半 |
|---|---|---:|---:|
'''
 for g in G:
  for knife in ('late','decoy'):
   for mode in ('copy','quiet'):
    bb=[b for b in diag['blocks'] if b['good']==g and b['knife']==knife and b['mode']==mode]
    s+=f'| {g} | {knife}/{mode} | {pp(bb[0]["delta"])} (n={bb[0]["n"]}) | {pp(bb[1]["delta"])} (n={bb[1]["n"]}) |\n'
 s+='''
## 5. 小比例混合的解释边界

下表只做aligned行的**全发牌经验收益**线性加权：匪队开局共同抽old或替代整套计划。未重新模拟，未选择最优比例，不是各匪独立抽动作，也不是局部信息集的纳什混合；没有共同选择实现条件时不能声称可分散执行。玩家也不会随这个混合比例更新来源信任；因此这里无法估计“少量自刀维持死者不确定性”的均衡价值，固定端点劣势不能排除该价值。它展示无需100%采用替代策略，固定好人策略也可能承受相应期望变化；不能据此推断好人自适应后的均衡值。

| 刀／替代计划 | 0%替代 | 25% | 50% | 75% | 100% |
|---|---:|---:|---:|---:|---:|
'''
 for knife in ('late','decoy'):
  for mode in ('copy','quiet'):
   vals=[v for v in diag['mixtures'] if v['knife']==knife and v['mode']==mode]
   s+=f'| {knife}/{mode} | '+' | '.join(f'{100*v["good_win"]:.2f}%' for v in vals)+' |\n'
 s+='''
50%不是目标，也没有理由预设最终能“回收到基本平衡”。警察灭队胜负条件、位置刀、表达预算和固定续局均可造成偏斜。需要先让信息处理合法，再研究有限候选之间的回应与局部混合；不能把逻辑错误抵消成一个好看的50%。

## 6. 公开意图、实际票与信息权限审计

下表对各行8列全部验收记录汇总，跨列共享seed，不作为独立样本数。接力只统计首日新增末尾槽；归票不一致第一轮含所有天，PK另列。不是身份概率。

| 行 | 首日金水relay数 | 金水自己第一轮归票不一致 | PK归票不一致（含候选限制） | 警察自己第一轮归票不一致 | 既定警队归票可执行却未执行 |
|---|---:|---:|---:|---:|---:|
'''
 for g in G:
  vals=[]
  for k in ['relay_count','relay_own_first_mismatch_ballots']:
   vals.append(sum(sum(D[g,m]['raw'][k]) for m in M))
  vals.append(sum(sum(D[g,m]['raw']['relay_own_mismatch_ballots'])-sum(D[g,m]['raw']['relay_own_first_mismatch_ballots']) for m in M))
  for k in ['police_own_first_mismatch_ballots','team_call_mismatch_ballots']:vals.append(sum(sum(D[g,m]['raw'][k]) for m in M))
  s+='| '+g+' | '+' | '.join(map(str,vals))+' |\n'
 s+='''
首死真警验好人条件下的活警额外报告次数（评价侧计数，不能传给玩家）：

| 行 | late_old | decoy_old | copy/quiet其余四列合计 |
|---|---:|---:|---:|
'''
 for g in G:
  vals=[sum(a for a,k in zip(D[g,m]['raw']['day1_live_police_reports'],D[g,m]['raw']['dead_clear']) if k) for m in ['late_old','decoy_old']];s+='| '+g+' | '+' | '.join(map(str,vals))+' | 0 |\n'
 s+='''
这47/74次是旧假查杀打到警队后的防御分支，三行同轨触发，本轮未新增警察暴露；它们不是三份独立证据。人工无威胁例中活警保持隐藏。现有防御规则是否最优仍未验证，不能以“被打到警队”就宣称必跳。

以上零/非零只能核查指定条件与模块，不是完整理性证明。尤其相容假警并没有被自动识别；当前来源模型仍不计算“为什么这个人会在此时跳”的完整策略似然。旁观者既不共享警队名单，也不应被程序静默认证死者。

**审计字段勘误：**冻结的`orphan_directive_ballots`实现漏限day1，可能把day2+正常活/活比较也计入，不能用它宣称首日问题仍存在或已消失。原始结果不改写，策略不变；派生审计在逐个首日Observation上直接检查条件，并核对没有实际relay时删授权字段是否改变决定。该检查只验证抽样/人工信息集，不冒充穷举所有信息集。

## 7. 完整案例与验证材料

案例按每列、每个预设接收器比较最早gain/loss/同终局路径变，以及最早归票不一致选择；不是挑最好案例。旧例仅解释机制，新的总体结论来自整批验收及区间。详细轨迹、角色评价字段、每夜验人/刀人、当时合法目标、私人已知匪/好人、来源边与实际票见`results/v31_examples.json`；阅读版见[案例解释](unresolved_conflict_cases_v31.md)。

'''
 s+=f'- 正式：`python scripts/run_unresolved_conflict_v31.py --workers 4`，{man["games"]:,}局、{man["elapsed_seconds"]:.2f}秒。\n'
 s+='- `python -m pytest tests/test_unresolved_conflict_v31.py -q`：12通过、5.49秒；`python -m pytest tests -q`：359通过、35.06秒，均本轮实际运行。\n'
 s+=f'- 烟测`python scripts/smoke_unresolved_conflict_v31.py`：48局、24单元、37对照契约通过。\n- `python scripts/verify_unresolved_conflict_v31.py`：48个单元结构/统计核查，{check["direct_sample_replays"]}条无审计包装器直接完整重放、{check["v30_compatibility_replays"]}次旧API兼容、{check["independently_checked_intervals"]}个区间由binomtest接口交叉核验、{check["frozen_assets"]}份冻结资产哈希检查。**不是所有正式对局独立重跑**。\n'
 s+=f'- `python scripts/diagnose_unresolved_conflict_v31.py`：{diag["detail_runs"]}个新资料细节案例与同数直接重放；另48局审计重放逐首日信息集检查，完成{diag["grant_prefix_checks"]}次无relay授权删除不变性核验；同一审计核查已死警队后活警报告必须已有警队被假查杀威胁（抽样触发{diag["defensive_report_checks"]}次）；旧例{diag["historical_runs"]}条重放，其中legacy的4条另以旧API复核。派生检查不增加独立验收样本。\n'
 s+='''- 冻结source/参数/协议在`results/v31/`；train.json、holdout.json含全部逐局数组及74项同时区间，manifest记正式文件哈希。分析脚本、报告、验证清单另记派生哈希，不冒充运行前冻结。冻结source只含本轮测试，完整历史测试来自最终Git版本。

## 8. 后续决策边界

本轮不根据结果重调规则。若新接收器取消了旧真死警优势，应先承认旧比较有方向性偏置；不能认证死者来回收数字。若统一归票仍挡不住copy/quiet，下一步应解释哪些公共信息足以让平民区别回应时点、哪些需要更完整策略生成模型，而非先加信用权重。

跳藏q与局部混合保留，信用继续冻结；金水假跳挡刀、跨日委托、跨日票型、公开怀疑、遗言制度与白天报匪分别待办。假跳挡刀会改变警队“非队友跳警必假”的私人推理前提，必须另作信息权限审计。
'''
 (ROOT/'docs/unresolved_conflict_results_v31.md').write_text(s)
 files=list(ROOT.glob('scripts/*v31.py'))+[ROOT/'docs/unresolved_conflict_results_v31.md',ROOT/'docs/unresolved_conflict_cases_v31.md',ROOT/'results/v31_examples.json',ROOT/'results/v31_integrity_audit.json',ROOT/'results/v31_smoke.json',ROOT/'results/v31_validation.json',ROOT/'README.zh.md']
 (ROOT/'results/v31_analysis_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files if p.exists()},note='Derived analysis after fixed evaluation, no policy change.'),indent=2)+'\n')
 print('report generated')
if __name__=='__main__':run()
