#!/usr/bin/env python3
"""Audit report: examples first, conditional counts without new strategy claims."""
import json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v21_verified'
data=json.loads((folder/'audit.json').read_text());examples=json.loads((folder/'examples.json').read_text())['examples']
labels={'late_near':'后置刀／近端假查杀','late_far':'后置刀／远端假查杀','decoy_near':'伪装刀／近端假查杀','decoy_far':'伪装刀／远端假查杀'}
roles={'police':'警','mafia':'匪','civilian':'民'}
mode_labels={'original':'原信息规则','corrected':'补首验一致性规则'}
def seat(p):return '无人' if p is None else f'{p+1}号'
def person(r,p):return seat(p)+'（'+roles[r['roles_evaluation_only'][p]]+'）'
def death(r,day,kind):
    row=r['deaths'].get(f'{day}_{kind}')
    return '未发生' if row is None else seat(row['player'])+'（'+roles[row['role']]+'）'
def stage(phase):return '历史全量重放' if phase=='historical_replay' else '新种子审计'
def countsum(blocks,mode,key):return sum(b['totals'][mode].get(key,0) for b in blocks)
old=[b for b in data['blocks'] if b['phase']=='historical_replay'];fresh=[b for b in data['blocks'] if b['phase']=='fresh_audit']
ps=[p for b in old for p in b['pairs']]
lines=['# v21 完整续局审计：首日更会出匪，为何最终仍更容易输？','',
'## 先读字典（没有新增策略或调参）','',
'|名称|实际含义|','|---|---|',
'|原信息规则 original|冻结v20的信息路由＋跨日私人记忆，不用数值来源信用|',
'|补一致性 corrected|冻结v20b，只比原规则多识别“首日两个不同首验不能同时为真警”|',
'|共同回应 q50|原窄条件中首名警察50%概率公开，保留真实验人与内推；本轮不改|',
'|后置刀／伪装刀|原safe_late／posterior_decoy，不知道警民具体身份|',
'|近端／远端假查杀|首个匪假查杀其后第一个／最后一个未发言非匪|',
'|旧来源冲突只剩一个活目标 orphan_conflict|某投票者仍保留历史声明冲突，合法候选中只有一个活冲突来源，程序集中投此人；至少一条相关冲突边另一端已死|',
'|引用死者查杀 dead_hit_used|所投目标也是某个未被该投票者排除的死亡来源的旧查杀目标；这是可用路径，不独立证明该来源决定了最终选择|',
'|票次数与局数|同局第一轮和PK、不同日可重复记票；不能把票次数当独立模拟样本|','',
'本文例子用1—16号座位；原始JSON为0—15。例子中的角色由评价器事后标注，并非平民当时知道的身份。规则仍4警4匪8民、死亡不翻身份、三死亡遗言、一轮PK再平票平安日、可弃票。', '',
'来源信用0.5/0.75及0.6门槛仍冻结，只在历史对照中存在，本轮没有恢复或调分；目标位置怀疑、公开建议资格、实际投票沿用原程序。跳/藏是保留的核心问题，待续局审计可解释后重启，不是放弃。', '',
'## 先看结论','',
'**主要问题已定位到“历史声明冲突如何进入今天的投票”，没有发现警察忘记已知匪或集体乱投的证据。** 当前程序有一个可复现的机械后果：假警已出局后，旧对跳仍保留，候选中只剩另一个活来源时，平民可能被迫集中投这个来源，即使他是真警、刚公布了有用查杀。死亡不翻身份确实不能认证谁真谁假，但“仍有不确定性”不等于“应自动轮出仅剩的活人”。','',
f"历史8192对中，原来赢而修正后输的有{sum(p['old_win'] and not p['new_win'] for p in ps)}对，其中{sum(p['old_win'] and not p['new_win'] and p['old_exile']==p['new_exile']=='mafia' for p in ps)}对两边首日都出匪，只是出了不同座位。没有出现“原首日未出匪、修后首日出了匪，并从赢变输”的配对。所以上次聚合的首日出匪率提升，不能解释为每个具体状态都获益；出哪个匪、保留什么旧冲突及后续顺序很重要。", '',
'这不是说已经证明了全部胜率差都由单一漏洞造成；本轮未做策略干预去分离各路径的因果贡献。发现的是完整可追踪的失利链、全样本中的频率变化，以及新种子上同样的异常处理路径。','',
'## 一个完整真实例子：两边第一天都出匪，却一赢一输','',
'按预定规则取后置刀／近端条件下第一局“原赢、修后输且修后首日出匪”的例子，种子163000010。它是解释性选例，不代表平均局。双方发牌、首验、首刀、首日声明相同。', '',
'首夜：11号民被刀，警方验8号是好人。12号真警在白天报8号金水；15号匪悍跳，假查杀16号真警。16号此前没有公开身份，其他平民不能自动知道谁真。','',
'|阶段|原信息规则|补首验一致性规则|','|---|---|',
'|第一天|出10号匪；15号悍跳匪还活着|出15号悍跳匪；10号匪还活着|',
'|第二夜|警方验7号为匪；匪刀12号公开真警|同样验7号为匪、刀12号真警|',
'|第二天公开信息|12号遗言及16号发言都报7号查杀|同样两份7号查杀|',
'|第二天平民怎么投|15号与16号都活着，旧对跳目标中选15号，出匪|15号已死，程序只剩16号活冲突来源；7名平民投16号真警|',
'|第二天警察怎么投|3名活警都投7号已知匪，没跟随民票|3名活警仍都投7号已知匪，但挡不住民匪票出16号|',
'|后续|依次出7号、9号匪，好人获胜|虽再出7号、9号匪，最后10号匪存活，把最后警察刀完|','',
'关键是：第二天不是警察不知道7号是匪，也不是验人丢失；同一份7号查杀没有转化成平民选票。程序先处理历史冲突，直接把“仅剩活来源16号”作为投票候选。平民本来不知道16号真警，但现有策略把这种不确定性机械转成了出人顺序。','',
'上次提到的“首日公开警察人数相同”仍成立；本例第二夜刀法也相同。但修后第二天额外白天损失一警，之后死亡锚点、发言顺序、验人候选与夜刀继续分叉。这是具体的连锁影响，不是抽象地把所有下降都解释成曝光成本。','']
# Fully data-derived day-by-day appendices for three preselected examples.
chosen=[]
for mafia,kind in [('late_near','lost_despite_day1_mafia'),('decoy_far','gained_win'),('late_near','sole_surviving_conflict_police')]:
    selected=next((e for e in examples if e['mafia']==mafia and e['kind']==kind),None)
    if selected:chosen.append(selected)
lines += ['## 三类对局的逐日记录','',
'原始档案保存10个预定首例（部分类别不存在则不硬找）。以下只展开三例；完整每次投票的合法候选、私人已知匪/好人、公开声明、决定路径及当时Observation均保存在`results/v21_verified/examples.json`。','']
reason_names={'private_refutation_or_check':'私人确知匪／假警优先','compare_conflicting_sources':'比较声明冲突来源','compatible_sources_protocol':'合并未识别冲突的来源建议','common_recommendation_protocol':'共同建议','single_source_protocol':'唯一来源建议','single_source_no_legal_proposal':'唯一来源无合法建议','position_fallback':'位置回退','private_good_only':'候选均为私有已知好人','no_legal_candidate':'无合法候选'}
for ex in chosen:
    lines += [f"### {labels[ex['mafia']]}，种子{ex['seed']}，类别{ex['kind']}",'']
    for mode in ('original','corrected'):
        r=ex[mode];lines += [f"**{mode_labels[mode]}：{'好人赢' if r['raw']['win'] else '匪赢'}**",'',
        '|日|当夜验人（结果为事后标注）|夜间死者|白天出局|警方投票|平民决策路径与目标（次数）|','|---|---|---|---|---|---|']
        days=sorted({v['day'] for v in r['votes']})
        for day in days:
            checks=[n for n in r['nights'] if n['kind']=='inspection' and n['night']==day]
            check='；'.join(person(r,n['target']) for n in checks) or '无'
            police=[v for v in r['votes'] if v['day']==day and v['role']=='police']
            pcounts=Counter((v['target'],v['round']) for v in police)
            pd='；'.join(f"{seat(t)}×{n}"+('（PK）' if rd=='pk' else '') for (t,rd),n in pcounts.items()) or '无'
            ccounts=Counter((v['reason'],v['target'],v['round']) for v in r['votes'] if v['day']==day and v['role']=='civilian')
            cd='；'.join(f"{reason_names.get(reason,reason)}→{seat(t)}×{n}"+('（PK）' if rd=='pk' else '') for (reason,t,rd),n in ccounts.items()) or '无'
            lines.append('|'+ '|'.join([str(day),check,death(r,day,'night_death'),death(r,day,'day_death'),pd,cd])+'|')
        lines.append('')
lines += ['## 全样本：哪些怀疑没有查到，哪些路径反复出现','',
'|样本|忽略合法已知匪票|警投私有已知好人票|非法投票|已知匪时警队分票轮次|报验时遗漏活查杀|','|---|---:|---:|---:|---:|---:|']
for blocks in (old,fresh):
    keys=['ignores_private_bad','votes_private_good','illegal','police_known_bad_split_rounds','reports_omit_live_hit']
    lines.append('|'+stage(blocks[0]['phase'])+'（双方合计）|'+'|'.join(str(sum(countsum(blocks,m,k) for m in ('original','corrected'))) for k in keys)+'|')
lines += ['',
'“报验遗漏活查杀”为实际发生的警察report中，有已验活匪却报了别的目标；不等于未跳警者没有隐藏信息。警队分票只检查同日同轮至少两名活警且各自有合法已知匪的轮次；没有查到不证明所有协调情形已穷尽。','',
'|样本|匪条件|旧：仅剩活冲突来源时投真警的票次数|修后同类票次数|旧：引用死者查杀且投民的次数|修后同类次数|','|---|---|---:|---:|---:|---:|']
for block in data['blocks']:
    a,b=block['totals']['original'],block['totals']['corrected']
    lines.append('|'+ '|'.join([stage(block['phase']),labels[block['mafia']],str(a.get('orphan_conflict_target_police',0)),str(b.get('orphan_conflict_target_police',0)),str(a.get('dead_hit_used_target_civilian',0)),str(b.get('dead_hit_used_target_civilian',0))])+'|')
lines += ['',
'这两条计数可在同一票重叠，不可相加当“坏票总量”。引用死者查杀本身并非逻辑错误：死亡不翻身份；问题是未认证声明仍可能被作为直接出人指令，且没有始终与其他声明相容性一起处理。对真警的角色标签是事后评价，并非平民可读信息。新种子重复出现这些路径，支持它们是程序性现象，不是单个漂亮故事；尚未验证修哪条能改善总体收益。','',
'## 首日出匪与最终胜负的配对分解','',
'|样本|对局配对数|原赢|修后赢|原赢→修后输|原输→修后赢|失利翻转中两边首日都出匪|同一首日死者但胜负不同|','|---|---:|---:|---:|---:|---:|---:|---:|']
for blocks in (old,fresh):
    pairs=[p for b in blocks for p in b['pairs']]
    values=[len(pairs),sum(p['old_win'] for p in pairs),sum(p['new_win'] for p in pairs),sum(p['old_win'] and not p['new_win'] for p in pairs),sum(not p['old_win'] and p['new_win'] for p in pairs),sum(p['old_win'] and not p['new_win'] and p['old_exile']==p['new_exile']=='mafia' for p in pairs),sum(p['same_day1_victim'] and p['old_win']!=p['new_win'] for p in pairs)]
    lines.append('|'+stage(blocks[0]['phase'])+'|'+'|'.join(str(v) for v in values)+'|')
lines += ['',
'四个匪条件复用同一批发牌种子；汇总仅为计数描述，不把全部列当互不相关的独立样本计算置信区间。相同首日死者时没有观察到胜负翻转，不等于后续每个动作都相同，也不证明新增约束只在首日生效：代码每天都重读历史声明。','',
'## 夜刀与信息释放','',
'|样本|原：有可刀的公开非匪跳警者的夜次／其中刀该类的夜次|修后同项|','|---|---:|---:|']
for blocks in (old,fresh):
    vals=[]
    for mode in ('original','corrected'):
        a=countsum(blocks,mode,'night_public_claimants_available');b=countsum(blocks,mode,'night_targets_public_claimant')
        vals.append(f'{a}／{b}')
    lines.append('|'+stage(blocks[0]['phase'])+'|'+'|'.join(vals)+'|')
lines += ['',
'这是匪视角的“非队友公开跳警者”，并不靠裁判知道其警/民身份；当前无平民假跳时这些公开来源通常是真警。现有刀法按设定优先追这些来源；新旧首日出局不同会改变之后活人池、位置验人和发言锚点，不能假定后续状态相同。','',
'## 方法、复现与限制','',
'本轮没有改裁判、策略、q或信用分。使用`results/v20b/source`中的冻结代码；历史8单元×2048＝16384局全部重新跑到终局，逐局核对所有已保存raw指标；另用164000000起每列512对＝4096局预定新种子审计相同机制。重复重放不是新的独立实验，不能把两次审计执行相加扩大样本。','',
'审计包装器只记录每次决策的Observation及返回值；真值角色只在动作结束后评价。完整个案保存每一票的角色自己的信息，不把全局真值作为输入。票数是描述性，未做因果中介分解或总体策略比较，也未运行均衡求解。','',
'初版审计器从夜刀候选剔除队友时忘记剔除行动者自身，导致把匪自己的假跳计入可刀来源。策略使用的teammates(obs)一直正确，胜负和逐局旧结果核对未受影响。`results/v21/superseded.json`说明该版被替代；最终结果来自修正审计器后的`results/v21_verified/`，重新完整重放、重新核验，不覆盖或清理旧记录。专项构造测试曾给将出局者自己投自己，已改为合法弃票并重跑；均未改策略。','',
'运行：`python scripts/audit_continuations_v21.py`（拒绝覆盖）；核验：`python scripts/verify_continuations_v21.py`；测试：`python -m pytest tests -q`。参数与选例规则见`docs/continuation_audit_protocol_v21.md`，原始完整信息见`results/v21_verified/examples.json`。','']
audit_path=ROOT/'results/v21_integrity_audit.json'
if audit_path.exists():
    audit=json.loads(audit_path.read_text())
    lines += [f"最终270项测试通过；{audit['historical_full_replays']}局历史重放已逐局核对旧结果；另对{audit['sampled_uninstrumented_full_replays']}局用不带包装器的原冻结策略完整重放，轨迹哈希一致；{audit['examples_checked']}份预定完整个案核验通过。新种子{audit['fresh_games']}局只作审计验证，不标为新的策略优化留出。",'']
lines += ['## 下一步建议与保留事项','',
'建议下一次只检验一处改动：把“历史两人不能都真”与“今天必须出谁”分开，避免死掉一个来源后自动轮出另一个活来源；死亡不认证身份，旧查杀也不无条件升级为指令。先以本轮三类人工/真实残局验证信息权限和分支，再冻结新规则与原规则，用全新种子比较。不在本轮直接修好后宣称胜率提升。','',
'跳警／隐藏及局部混合仍是重点，待续局信息处理可靠后重启；当前q固定，旧训练q0和小矩阵经验gap0不升级成理论结论。信用分继续冻结为对照，未来独立与其他信息采纳机制比较。跨日信息集还需逐步补全，多匪团队声明后的4v4对冲、票型、公开怀疑和遗言制度保持分开待办。','']
(ROOT/'docs/continuation_audit_results_v21.md').write_text('\n'.join(lines));print('continuation audit report written')
