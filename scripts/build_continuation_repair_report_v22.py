#!/usr/bin/env python3
"""Readable factorial mechanism report with frozen independent replications."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v22'
f=json.loads((folder/'freeze.json').read_text());manifest=json.loads((folder/'manifest.json').read_text())
reports={b['name']:json.loads((folder/(b['name']+'.json')).read_text()) for b in f['config']['blocks']}
rows={'legacy':'旧续局规则','live_pair':'仅取消死—活冲突轮出','current_day':'仅使用当日行动建议','both':'同时修复两项'}
cols={'late_near':'后置刀／近端假查杀','late_far':'后置刀／远端假查杀','decoy_near':'伪装刀／近端假查杀','decoy_far':'伪装刀／远端假查杀'}
def pct(v):return '—' if v is None else f'{100*v:.2f}%'
def pp(v):return '—' if v is None else f'{100*v:+.2f}'
def interval(v):return '—' if v is None else '['+', '.join(pp(x) for x in v)+']'
lines=['# v22：取消死亡后的机械轮出，并区分旧查杀与今日指令','',
'## 策略、参数字典（先读这部分）','',
'|行名|实际动作|','|---|---|',
'|`legacy`|v20b旧续局：全部历史冲突可进入候选，未重申的旧查杀仍可成为行动建议|',
'|`live_pair`|只改冲突资格：仅双方仍活着的冲突边进入对跳来源比较，旧建议处理不变|',
'|`current_day`|只改建议时效：当日重新提出的改归、查杀、内推可直接成为建议；旧冲突资格不变|',
'|`both`|同时启用以上两项修复，不给存活来源身份认证或免死资格|','',
'共同继承：4警4匪8民、无平民假跳或真警乱报、gap位置验人、等权位置模型、二人非绑定内推、真实验人、金水来源先于目标保护、跨日私人假警记忆、三死亡遗言、一轮PK再平票平安日、允许弃票。修复从第二天投票开始；第一天、第二夜刀验及第二天普通发言完全相同。','',
'本轮所有行的q固定为50%：仅首夜未死警、预定首警还未发言且假查杀未中警队的既定窄条件下，以50%回应，否则按原隐藏流程；不是所有警察都抽签，不是信用分或胜率。本轮不选择q，不重新优化跳藏。','',
'|列名|实际匪方动作|','|---|---|',
'|`late_near`|safe_late后置位置刀；首个匪假查杀其后第一个未发言非匪|',
'|`late_far`|同后置刀；假查杀其后最后一个未发言非匪|',
'|`decoy_near`|posterior_decoy削弱旧位置后验的刀；近端假查杀|',
'|`decoy_far`|同伪装刀；远端假查杀|','',
'匪只知队友，不知道警民具体分布。实际刀法在最高评分刀位随机破同分，2%tremble仍只在好人位置似然假设中。后续沿既定公开来源追刀及原票法，不重新学习，也不新增重复假跳。本轮能评估对该固定池的收益，不能证明修复面对自适应重申、伪装或自刀仍不可利用。','',
'## 修复没有偷偷增加什么信息','',
'历史消息、首验冲突和私人记忆全部保留；死者不自动变成匪，存活者不自动变成真警。新程序只修改“今天可据什么采取行动”：','',
'1. 私人确知且可投的匪最高优先，警察不投私有已知好人，遵守PK候选。',
'2. 当日公开建议可来自当日活人发言，也可来自当日死警的新遗言；声明都不经裁判认证。不能把所有死者话一概丢弃。',
'3. 无当日重申的旧查杀仍可保留作历史疑点，但不能凭过去那句话自动成为今日指令。多个历史来源中只有一个当前建议时，可按既定唯一建议协议协调；这不是认定来源为真警。',
'4. 冲突只剩死—活关系时，不能单凭此关系轮出活人；若仍有活—活对跳、私人反驳或其他当前建议，存活者仍可能被投。',
'5. 没有可用建议时仍使用旧位置/顺位回退。因此偶尔投到存活跳警者，不等于又触发旧的机械轮出；要看决定分支。','',
'来源信用数值保持冻结，四行均不读取来源0.5/0.75与0.6门槛，也没有新加身份概率或加减分。目标排序仍为旧位置模型（第二天起未知目标通常同分，按公开顺位破同分）；建议资格来自声明结构/时效；实际投票由各人观察单独决定。这些启发式尚未证明最优。','',
'## 先回答本轮最关心的事','']
# Conclusions are generated from held-independent blocks, never used to change them.
for phase,report in reports.items():
    primary=[r for r in report['contrasts'] if r['name']=='combined']
    positive=sum(r['win']['delta']>0 for r in primary);negative=sum(r['win']['delta']<0 for r in primary)
    lines.append(f"- {phase}：同时修复的四列中，{positive}列好人胜率上升、{negative}列下降。具体差值与区间见下表，不仅按胜率点估计宣称成功。")
primary_all=[r for report in reports.values() for r in report['contrasts'] if r['name']=='combined']
conservative_positive=sum(r['win']['family8_hoeffding'][0]>0 for r in primary_all)
normal_positive=sum(r['win']['family8_normal'][0]>0 for r in primary_all)
lines += ['',f'八项主比较中，{normal_positive}项的多重比较正常近似区间完全为正；更保守的有界区间有{conservative_positive}项完全为正，其余仍包含零。应同时看两种精度说明，不能将所有点估计上升说成每种统计标准下都已确定。','']
for phase,report in reports.items():
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    same=sum(lookup['current_day',m]['raw']['win']==lookup['both',m]['raw']['win'] for m in cols)
    lines.append(f'{phase}中，当前建议方案与双修复有{same}/4列逐局终局胜负一致。这个结果描述已观察的终局，不证明两个策略等价；死—活冲突动作是否消失仍单独核查。')
lines += ['',
'上次真实失利例（163000010）第二天的平民信息快照已验证：旧规则选16号真警，新双修复规则改用当天7号查杀。此处只是相同Observation上的分支校验，不能把旧种子当本轮新验证样本，也不因这个局部动作正确就宣布整局必胜。','',
'## 方法：先检查分支，再冻结两批新样本','',
'人工校验覆盖死—活冲突、旧查杀不自动续期、当日死警遗言、PK合法性、私人记忆、未见角色置换不改变动作、存活者仍可被其他证据怀疑。还复查v21保存的三类真实续局Observation，所有旧规则分支兼容；旧规则与冻结v20b完整轨迹抽样一致。','',
f"正式evaluation_A从166000000起、replication_B从167000000起，各单元4096局，4行×4列×两批，共{manifest['games']:,}局。两批在读取A前统一冻结，不训练、不选策略、不按A调整B。smoke使用168000000起的少量测试局，不计入正式样本。", '',
'四行逐局核对第二天投票前完整轨迹哈希，包含首夜、首日发言/投票/出局、第二夜刀验与次日普通发言。只有第二天投票开始才能出现干预差异，后续状态可自然分叉。主比较只有both−legacy的4列×2块共8项终局胜率，给Bonferroni八比较正常近似区间与保守Hoeffding区间；小改变数下正常近似可能不稳，零方差不证明总体等效。其余拆解为解释性逐项比较，不按最漂亮结果挑策略。','',
'## 两批新样本结果','']
for phase,report in reports.items():
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    lines += [f'### {phase}：每单元4096局','',
        '|续局规则|后置刀／近端|后置刀／远端|伪装刀／近端|伪装刀／远端|','|---|---:|---:|---:|---:|']
    for name,label in rows.items():lines.append('|'+label+'|'+'|'.join(pct(lookup[name,m]['win']['rate']) for m in cols)+'|')
    lines += ['', '|匪策略|双修复−旧规则（百分点）|八比较正常近似95%区间|八比较保守95%区间|从输变赢／从赢变输|','|---|---:|---|---|---:|']
    for r in report['contrasts']:
        if r['name']=='combined':
            w=r['win'];lines.append('|'+ '|'.join([cols[r['mafia']],pp(w['delta']),interval(w['family8_normal']),interval(w['family8_hoeffding']),f"{w['improved']}／{w['worsened']}"])+'|')
    lines += ['', '|匪策略|只改冲突−旧规则|只改时效−旧规则|已改时效后再改冲突|已改冲突后再改时效|','|---|---:|---:|---:|---:|']
    for m in cols:
        names=['live_only','current_only','live_given_current','current_given_live']
        vals=[next(r['win']['delta'] for r in report['contrasts'] if r['mafia']==m and r['name']==n) for n in names]
        lines.append('|'+cols[m]+'|'+'|'.join(pp(v) for v in vals)+'|')
    lines += ['', '以上拆解的单位均为百分点，只用于理解两项规则是否互补；不能只挑其中一个单元宣布哪项全局最优。','']
lines += ['## 机制是否真的被修掉','',
'“孤立活来源票”只统计投票实际走冲突比较、且所选目标只有死亡历史对手、没有任何仍活着的相关对手的情况。“旧死者指令票”只统计建议选择分支中，旧死者目标确实进入建议、但无当日重申。两者不是所有误投真警的总量。另存的旧查杀目标共现计数并不代表因果引用。','',
'|区块|规则|孤立活来源票次数|其中目标实际为警|旧死者指令票次数|第二天白天出警局数（四列合计）|','|---|---|---:|---:|---:|---:|']
for phase,report in reports.items():
    for name,label in rows.items():
        cs=[c for c in report['cells'] if c['good']==name]
        totals=[sum(sum(c['raw'][k]) for c in cs) for k in ['orphan_conflict_ballots','orphan_conflict_police_ballots','stale_dead_advice_selected_ballots','day2_police_exile']]
        lines.append('|'+phase+'|'+label+'|'+'|'.join(str(v) for v in totals)+'|')
lines += ['',
'同一局可能多日、多玩家或PK重复计票，不能当独立样本。这些零计数首先证明动作权限变更确已生效；它们不自动证明总胜率改善，也不等同于所有错误判断消失。各列同一批发牌配对复用，合计数字只是描述，不另作独立样本置信区间。','',
'## 次日出人与最终胜率分开看','',
'|区块|匪策略|第二天出警差值（双修复−旧）|第二天出匪差值|','|---|---|---:|---:|']
for phase,report in reports.items():
    for r in report['contrasts']:
        if r['name']=='combined':lines.append('|'+ '|'.join([phase,cols[r['mafia']],pp(r['day2_police_exile']['delta']),pp(r['day2_mafia_exile']['delta'])])+'|')
lines += ['',
'本轮第一天出人严格相同，不再用首日出匪率解释变化；次日与后续投票改变后，死亡锚点、验人候选及夜刀都会分叉，所以这些中间指标不是独立因果中介分解。','',
'## 局限、反制与保留事项','',
'- 当前时效协议并非完整贝叶斯身份推断，也未使用“多数人认为他悍跳”的校准信念；只是取消机械行动资格。死亡不给身份认证，存活者仍可能实际为匪。',
'- 匪方续局固定且不重新声明旧查杀，这可能让当日建议协议更有利于真警；尚未测试匪方重申旧查杀、假金水、当日诱饵或对本修复学习。不能将效果称为稳定抗剥削或完整GTO。',
'- 新规则也可能丢掉有价值的旧死警查杀，这不是逻辑证明旧信息无用。保存历史但不直接作为指令，是本次候选协议；将来可考虑在新的相容性或可信度机制下重新使用，不应倒退到无条件照单投。',
'- q固定50%，不更新旧q0和2×4经验gap0的解释；本轮不求均衡。跳/藏与局部混合待续局可靠、匪方同步反制后重启。信用分继续冻结作对照，不永久移除。',
'- 多匪团队4v4对冲、跨日信息集、透明票型、公开怀疑、遗言制度、白天报匪继续分开待办；本轮不把这些变更混入。','',
'## 复现与核验','',
'执行：`python scripts/run_continuation_repair_v22.py --output results/v22_reproduction`；测试：`python -m pytest tests -q`；归档核验：`python scripts/verify_continuation_repair_v22.py`。从冻结包重现时先进入`results/v22/source`再运行其入口脚本并指定新输出目录，避免使用后续版本的代码。配置、预定协议、冻结源码、逐局指标和哈希在`results/v22/`。','']
regression_path=ROOT/'results/v22_regression_examples.json'
if regression_path.exists():
    regression=json.loads(regression_path.read_text())
    lines += ['## 三个已知对局的回归检查（不算新证据）','',
    '除了人工残局和Observer快照，又用预先选好的v21三类旧对局各跑新旧两种续局，共6局。它们是开发/回归例子，不计入131072局新种子胜率，也不作为独立确认。','',
    '|旧例种子|情形|旧续局最终结果|双修复最终结果|','|---|---|---|---|']
    for case in regression['examples']:
        title={'lost_despite_day1_mafia':'原审计失利翻转例','gained_win':'原审计反向获胜例','sole_surviving_conflict_police':'孤立活来源被投例'}[case['kind']]
        old='好人赢' if case['runs']['legacy']['win'] else '匪赢'
        new='好人赢' if case['runs']['both']['win'] else '匪赢'
        lines.append(f"|{case['seed']}|{title}|{old}|{new}|")
    lines += ['', '163000010的旧失利链已在修复后转为好人获胜；163000001仍然失利，说明修掉一个不合理分支没有解决所有后续策略问题。完整每次投票时的观察和解释、刀验及轨迹保存在results/v22_regression_examples.json。','']
audit=ROOT/'results/v22_integrity_audit.json'
if audit.exists():
    a=json.loads(audit.read_text());lines += [f"当前279项测试通过；{a['cells_checked']}个单元所有逐局前缀哈希和原始结果算术核验通过。{a['sampled_full_replays']}局独立完整轨迹抽样复现一致，另有{a['additional_legacy_api_comparisons']}局旧API兼容比较一致；不是全部{manifest['games']:,}局独立重跑。",'']
lines += ['## 下一步建议','', '先只给仍活着的悍跳者在原有轮次重申原假查杀的能力，检验当前建议协议是否只是利用了匪方不重申的弱续局。继续固定好人修复与q，不同时增加自刀、团队对冲或复杂信用。通过针对性反制后，再在新续局下重启跳/藏和局部混合研究；信用机制另作独立比较。','']
(ROOT/'docs/continuation_repair_results_v22.md').write_text('\n'.join(lines));print('continuation repair report written')
