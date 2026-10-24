#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'results/v19'
f=json.loads((folder/'freeze.json').read_text())
reports={b['name']:json.loads((folder/(b['name']+'.json')).read_text()) for b in f['config']['blocks']}
labels={'old_keep':'原信用＋平民自辩','guard_keep':'金水保护＋原流程','guard_answer':'金水保护＋及时回应','guard_selective':'只在查杀警队时回应','guard_bait':'选择性回应＋存活怀疑','answer_no_denial':'及时回应但无平民自辩'}
mlabels={'safe_late_forward':'后置刀／早跳','safe_late_last':'后置刀／末匪跳','posterior_decoy_forward':'伪装刀／早跳','posterior_decoy_last':'伪装刀／末匪跳'}
def pct(x):return '—' if x is None else f'{100*x:.2f}%'
def pp(x):return '—' if x is None else f'{100*x:+.2f}'
def ci(x):return '—' if x is None else '['+', '.join(pp(v) for v in x)+']'
lines=['# v19：保留验人和内推后，真警是否应回应假查杀？','',
'## 先读策略字典','',
'胜率表中的百分数指好人胜率，其他比例另有标注；胜率与出人率“差值”的单位为百分点。没有训练策略或求解均衡。行名不是信用等级，也不是概率。', '',
'|代码|白话含义与实际动作|','|---|---|']
for name,label in labels.items():lines.append(f'|`{name}`|{label}|')
lines += ['', '共同底座：4警4匪8民，位置验人、等权位置后验、二人内推、原信用门槛、关闭票史加分。`keep`保留原有警察报验和带队，只是不额外因假警起跳；`answer`增加首个有合法发言机会的真警回应，仍报真实验人并保留原内推，再指认假警；`selective`只在假查杀命中警队时回应。平民被查杀后只能用自己的身份反驳，旁观者没有角色认证。', '',
'|列名|具体策略|','|---|---|',
'|`safe_late_forward`|按匪座位挑后置优势刀；第一个匪查杀之后第一个尚未说话的非匪|',
'|`safe_late_last`|同后置刀；最后一个匪若已看见报验，查杀最后报验者|',
'|`posterior_decoy_forward`|选择削弱旧位置后验的伪装刀；同早跳|',
'|`posterior_decoy_last`|同伪装刀；同末匪跳|','',
'这些匪不知道警民具体分布；并非上帝视角挑警察查杀。实际刀法在最高评分刀位之间随机破同分；2%均匀扰动只存在于好人计算位置后验时的假设似然中，不是匪方实际刀法的2%随机偏离。后续所有列都停止新增假跳，继续用共同公开信息刀法与原投票策略，因此不是学习过的最强反制。', '',
'## 数值规则：哪些是铁约束，哪些仍是粗糙权重','',
'来源信用是行动权重，不是身份概率。平民看普通来源为0.50；被他人报金水且没有被另报查杀为0.75；自己为1。警察对队友为1，其他来源为0。建议权重至少0.60才进入正式选择；取最高，仍沿用旧规则同分较晚者优先，本轮未证明这个破同分合理。', '',
'金水保护有两层：A报B金水，把B的来源权重提升到至少A（重复传播至稳定，最高1）；公开候选池中若A、B均可出，先考虑A，环路不把全部候选清空。这是在不允许平民假跳、真警不乱发身份下实施的关系约束，不是用“均匀数世界”给单警贴坏人概率。私有查杀和当事人对假查杀的自辩另外处理。', '',
'来源权重只决定建议是否被采用；位置怀疑决定没有可采纳建议时的候选排序；内推是候选名单而非强制放逐；最后每人独立按固定程序投票。本轮关闭额外票史怀疑，不把这四者合并为一个“身份分”。', '',
'`guard_bait`在第二天起，将仍活着的第一天跳警者信用先限制为不超过0.50，然后再做金水传播，可能由支持关系重新提升。对真警假警相同。这是未经校准的探索性怀疑规则，不是“没死就是匪”的逻辑。', '',
'例：A假查杀民C，C知道A是假警，可以提名、投A；旁观D并不知道C确为民。真警B若接着回应，报的是自己实际首验，再声明A是假警，不伪造“验A为匪”。若首验是金水，还能保留原来的内推名单。', '',
'## 本次方法与证据边界','',
'预先冻结6行×4列，A、B两个互不重叠区块，每单元各4096局，总196608局。A种子156000000起，B种子157000000起。不用A挑策略再跑B；两批配置运行前一并冻结。相同列跨行共享发牌、首验、首刀与假跳时点和目标，程序检查所有分层掩码一致。进入续局后行动不同会自然导致轨迹不同。', '',
'主分层：首夜死者不是警察，并且假跳之后确实有活警尚未普通发言。再按假查杀实际命中民或警分层；角色标签仅供评价统计，不输入决策。首夜死警且有回应机会另列。“末匪跳”并不必然是全场末位；仍需逐局检查实际机会。没有假跳的局面不计入有假跳但无机会分支。', '',
'差值采用同种子配对。正态近似95%区间是探索性、未校正多重比较；另给保守有界变量Hoeffding区间。两批方向一致支持可重复性，但不是证明总体收敛、所有匪策略下成立或达到GTO；条件样本量远小于4096时尤其要谨慎。', '',
'## 主结果：首夜未死警，而且有回应机会','']
for block,report in reports.items():
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    lines += [f'### {block}（独立区块）','', '|好人动作|后置刀／早跳|后置刀／末匪跳|伪装刀／早跳|伪装刀／末匪跳|','|---|---:|---:|---:|---:|']
    for name in labels:
        vals=[pct(lookup[name,m]['branches']['eligible']['rate']) for m in mlabels]
        lines.append('|'+labels[name]+'|'+'|'.join(vals)+'|')
    lines += ['', '|匪策略|条件样本n|及时回应−原流程|探索性95%区间|保守95%区间|首日出匪差值|首日出警差值|','|---|---:|---:|---|---|---:|---:|']
    for row in report['contrasts']:
        if row['name']=='reply' and row['branch']=='eligible':
            w=row['win'];lines.append(f"|{mlabels[row['mafia']]}|{w['n']}|{pp(w['delta'])}|{ci(w['ci95_normal'])}|{ci(w.get('ci95_hoeffding'))}|{pp(row['day1_mafia_exile']['delta'])}|{pp(row['day1_police_exile']['delta'])}|")
    lines.append('')
lines += ['## 直接回应“查杀到平民时，警察先藏还是回应？”','',
'下表只看首夜未死警、有回应机会、假查杀实际命中平民。选择性回应在这些局面不额外起跳，因此与及时回应形成比较。不能解读为其他好人已经确定目标是平民。','',
'|区块|匪策略|n|选择性回应胜率|及时回应胜率|及时回应−选择性回应|探索性95%区间|保守95%区间|','|---|---|---:|---:|---:|---:|---|---|']
for block,report in reports.items():
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    for row in report['contrasts']:
        if row['name']=='selective' and row['branch']=='civilian_target':
            # stored delta is selective - answer; reverse for intuitive wording
            w=row['win'];normal=w['ci95_normal'];h=w.get('ci95_hoeffding')
            lines.append('|'+ '|'.join([block,mlabels[row['mafia']],str(w['n']),pct(lookup['guard_selective',row['mafia']]['branches']['civilian_target']['rate']),pct(lookup['guard_answer',row['mafia']]['branches']['civilian_target']['rate']),pp(-w['delta']) if w['delta'] is not None else '—',ci([-normal[1],-normal[0]]) if normal else '—',ci([-h[1],-h[0]]) if h else '—'])+'|')
lines += ['', '## 首夜死警对照与机会覆盖','',
'|区块|匪策略|死警且可回应n|原流程胜率|及时回应胜率|差值|假跳覆盖率|有假跳但无机会局数|','|---|---|---:|---:|---:|---:|---:|---:|']
for block,report in reports.items():
    lookup={(c['good'],c['mafia']):c for c in report['cells']}
    for m in mlabels:
        a,b=lookup['guard_keep',m],lookup['guard_answer',m];x,y=a['branches']['dead_police'],b['branches']['dead_police']
        delta=y['rate']-x['rate'] if x['n'] else None
        lines.append('|'+ '|'.join([block,mlabels[m],str(x['n']),pct(x['rate']),pct(y['rate']),pp(delta),pct(a['means']['false_claim']),str(sum(a['raw']['no_opportunity']))])+'|')
lines += ['', '## 机制消融（不是新增最优策略的证明）','',
'|区块|匪策略|主条件n|金水保护−旧机制|加入平民自辩−无自辩|加入存活怀疑−不加|回应后公开警察数增量|','|---|---|---:|---:|---:|---:|---:|']
for block,report in reports.items():
    rows={(r['name'],r['mafia'],r['branch']):r for r in report['contrasts']}
    for m in mlabels:
        key=lambda name:rows[name,m,'eligible']
        lines.append('|'+ '|'.join([block,mlabels[m],str(key('reply')['win']['n']),pp(key('clear_guard')['win']['delta']),pp(key('civilian_denial')['win']['delta']),pp(key('survival')['win']['delta']),("—" if key('reply')['police_claims']['delta'] is None else f"{key('reply')['police_claims']['delta']:+.3f}")])+'|')
lines += ['', '原始文件保留所有局面的胜负、分层、首日出人、PK、内推和公开警察数，以及所有预定配对对比；本报告聚焦上述问题，不按漂亮的子分支挑策略。', '',
'## 无效干预必须单列','', '存活降权对照在本轮组合中没有形成有效干预：第一天的跳警来源没有获得额外金水支持，原信用本来就为0.50，再封顶0.50不会改变建议资格。当前数据中的零差异不能说明存活信息无用，也不能否定沉默钓鱼。需要先设计确实可触发、不会自动判假的跨日规则再研究。','', '## 仍未解决的限制','',
'1. 固定信用0.50/0.75和0.60门槛不是学到的身份概率；未对跳的单警仍不自动获得高权威。首验金水支持、警察队友信用、PK候选限制都会影响回应能否转化为选票。',
'2. 本轮保留原来同分较晚建议优先，尚未专门验证其后置匪风险；跨日存活怀疑只是粗规则，没有建模匪方自刀或故意留真警。',
'3. 匪不根据本轮结果学习，只有两种刀、两种固定假跳；真警回应、隐藏均不是完整策略空间。仅限首日干预和既定续局。被假查杀平民的显式优先反驳只读取当日声明，尚未加入跨日保存“已知假警”的私人记忆，因此不能把本轮选择性隐藏当作完整钓鱼执法策略的检验。',
'4. 不允许平民假跳或警察乱发身份，才能使用当前金水逻辑；金水关系不意味着来源已经真警认证，也不证明某个放逐次序全局最优。',
'5. 本轮保持三死亡遗言、自刀候选不加入。透明票型的可信度、跨日投票联盟、公开怀疑声明、遗言制度差异、白天报匪仍待分开研究。', '',
'## 复现与核验','',
'正式运行：`python scripts/run_reply_v19.py`；测试：`python -m pytest tests -q`；档案核验：`python scripts/verify_reply_v19.py`。冻结配置在`configs/reply_v19.json`，协议在`docs/reply_protocol_v19.md`，源码快照和逐局评价量在`results/v19/`。两个新独立评价块不是用于选择策略的训练／留出流程，也不宣称最终从未查看的论文确认集。', '',
'核验的全局数、哈希和抽样重放数量见`results/v19_integrity_audit.json`；抽样重放不等于所有196608局独立重跑。一次默认根目录pytest因同时收集源码快照中同名测试文件而发生收集冲突；改用明确的`tests`目录后通过，未因此修改或重新挑实验。', '']
timing_path=ROOT/'results/v19_timing_diagnostic.json'
if timing_path.exists():
    timing=json.loads(timing_path.read_text())
    lines += ['', '## 补充解释：第一名真警回应，还是额外暴露队友？','',
    '这项分层是在查看A后、读取B前补充的解释性分析，不是原冻结主比较。按假警发言前首个真警是否已经有普通发言，使用开局角色和顺序确定分层；不按回应后的输赢或暴露数量挑样本。只复算开局，不增加或选择策略。','',
    '|区块|匪策略|假跳前真警已发言|n|回应−原流程胜率差|公开警察人数差|探索性95%区间|','|---|---|---|---:|---:|---:|---|']
    for r in timing['rows']:
        if r['branch']=='eligible':
            exposure=r['police_claims']['delta']
            lines.append('|'+ '|'.join([r['phase'],mlabels[r['mafia']],'是' if r['police_already_spoke'] else '否',str(r['n']),pp(r['win']['delta']),'—' if exposure is None else f'{exposure:+.3f}',ci(r['win']['ci95_normal'])])+'|')
    lines += ['', '如果原定首个真警本来就将在假警之后报验，回应并不一定增加新的公开身份；如果真警已经说完，再叫下一位回应才会多暴露一个人。二者不能混称为“跳与不跳”。','']
(ROOT/'docs/reply_results_v19.md').write_text('\n'.join(lines))
print('report written')
