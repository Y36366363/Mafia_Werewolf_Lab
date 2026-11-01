#!/usr/bin/env python3
"""Derived presentation only; no policy or seed selection."""
import sys,json
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mafia_lab.restatement_experiment_v23 import save


def build():
    root=ROOT/'results/v27';cfg=json.loads((root/'freeze.json').read_text())['config']
    held=json.loads((root/'holdout.json').read_text());train=json.loads((root/'train.json').read_text())
    audit=json.loads((ROOT/'results/v27_integrity_audit.json').read_text())
    examples=json.loads((ROOT/'results/v27_examples.json').read_text())
    D={(c['good'],c['mafia']):c for c in held['cells']};T={(c['good'],c['mafia']):c for c in train['cells']}
    comparisons={(c['comparison'],c['mafia']):c for c in held['contrasts'] if c['primary']}
    names=sorted({c['mafia'] for c in held['cells']});pct=lambda x:f'{100*x:.2f}%'
    interval=lambda c:'['+', '.join(f'{100*x:+.3f}' for x in c['precision']['ci_simultaneous'])+']'
    lines=['# v27 完整方法与结果：金水接受委托与接力归票','',
      '日期：2026-11-01。先读结论，再查参数和数据。本报告仅是冻结策略评估，不是矩阵均衡、最佳回应或完整游戏GTO。','',
      '## 先看结论','']
    changes=sum(c['win']['improved']+c['win']['worsened'] for c in held['contrasts'])
    votes=sum(sum(c['raw']['relay_changed_ballots']) for c in held['cells'])
    lines += [f'本轮实现了“警察明确授权 → 金水在自己回合接受或拒绝 → 公众按来源接纳”的完整链条。验收全部预定比较累计胜负翻转记录为 **{changes}**；所有验收单元中接力改变实际投票的次数为 **{votes}**。这些记录跨比较共享局面，不能当成独立样本总量。', '',
      '**如果目标是提高当前好人胜率，本轮没有发现新增收益。** 若接力虽然频繁发生、却选出大家原本就会投的人，它只补充了表达，并没有新协调效果。这不能说明现实金水归票没有价值，更不能排除其他接力规则；说明当前受限选人模型下，需要先找出金水与原归票确实会产生分歧的合法信息条件。','',
      '本轮未增加信用权重、票型学习、名单外强制改归、假跳挡刀或更复杂匪反制。匪方不接续列全部保留，没有为显示增益而去掉低胜率条件。','',
      '## 1. 策略与参数字典（先于表格）','',
      '| 名称 | 实际含义 |','|---|---|',
      '| `base` | v26 aligned：验人和内推保留；有私有活匪时公开明确执行目标，并按合法私人事实投票。不委托。 |',
      '| `fixed` | base 加明确委托；金水沿用授权名单第一目标。若自己掌握名单内活匪，先投该匪；若已知活匪在名单外则拒绝接力。是重申/集中作用对照。 |',
      '| `local` | 相同委托；金水用自身信息和原有信息路由，在授权名单内重新选目标。不是拿警队信息替其选。 |',
      '| `q0 / q50 / q100` | 0% / 50% / 100%只作用于首日特定可选回应窗口；不是整局跳警概率。没有首夜死警、此前未有真警公开、假警已出现但未查杀警队、轮到首名活警时才可抽样。 |',
      '| `late` | 原 `safe_late` 冻结位置刀。 |',
      '| `decoy` | 原 `posterior_decoy` 冻结位置伪装刀。 |',
      '| `near / far` | 首名匪的早期假查杀，指向其后非匪最近 / 最远发言位。只排除匪同伴，不会偷看警民。 |',
      '| `restate` | 原假警活着重申，死后队友不接续。 |',
      '| `claim` | 原假警死后，存活队友可接续跳警并提旧目标；没有新验人。 |',
      '| `_team` | 匪方仍用原共同目标投票；本轮不启用票型小试验或倒钩扩展。 |',
      '| `delegate(B,[C,D])` | A公开委托B当天在C/D中定执行目标。每次1—3个候选是沿用模板上限，不是这次优化出的最佳名单长度；主模型仍用原二人内推。 |',
      '| `relay(C, source=A)` | B接受A委托，明确选C；接力替换A原建议，不新增一个独立来源。 |','',
      '例如 `local_q50 × decoy_far_restate_team`：好人用金水自主接力；首日窄分支50%回应；匪用位置伪装刀和远位假查杀，原人死后不接续，按旧队伍规则投票。','',
      '信用分和目标身份概率都没有新增。现有数值信用体系继续冻结为旧对照，不参与本轮采纳；q是行动随机概率，不是信用或身份概率。金水接力资格是公开授权关系，不是“身份信用=1”。','',
      '## 2. 游戏、流程与信息权限','',
      '4警4匪8民；匪胜条件为警察全灭，好人胜条件为匪全灭。死亡不翻身份；前三个死亡有遗言；公开顺序投票；最多一次PK发言/复投，再平票为平安日，可弃票。普通非匪首刀、无平民假跳/真警乱报的候选池假设继续保留；游戏允许自刀，但本轮匪候选不含自刀。','',
      '委托从第二天起：警察保留原report和shortlist。已知活匪的明确执行归票优先，不被委托覆盖；只有尚未形成这类硬归票的名单才交接。受托者必须仍有正常发言机会，是自己实际验过、并由自己此前或本回合公开报过金水的非警队成员。程序只使用警察的观察，不用裁判身份区分警民。','',
      '受托者在自己正常回合看截至此时的公开信息、自身身份和私人反证；看不到警队名单、未公开验人或未来发言。可以在授权范围选人或拒绝。原普通声明仍保留，额外加一条接力；没有额外轮次，但确实增加了声明内容，因此不是完全等表达预算的纯投票干预。','',
      '旁观者分别判断：来源是否被自己反证、是否同来源曾报该人金水、委托是否先于接力、是否当天有效。后续来源自己的新归票/名单/委托撤回旧委托。多来源委托时保守拒绝，不使用“后说的人天然优先”。接力不递归，不能自行出名单外。金水不自动获得警队视角或全场无条件指挥权。','',
      '逻辑例：A说“昨晚验5好，内推3/7，我此前验好的B请在3/7里接力”。B可选3/7，也可因私人反证拒绝；别人把有效接力当A建议的更新值，而非A和B两个独立证人。若A曾给某平民发假查杀，该平民能反证A，不能被B的金水地位强迫改信A。','',
      '私有活匪仍优先；私有好人、既有金水保护和PK合法性保留。目标不在PK候选中时重新在合法范围行动，不能继续投名单外对象。旧声明保留而不自动成为今日指令；死亡既不认证身份，也不触发剩余来源机械轮出。','',
      '金水假跳警挡刀暂不加入：这会破坏当前“警队外跳警者必是假来源”的受限假设，必须同步修改双方推理，不能只让金水免费获得此行动。','',
      '## 3. 冻结设计与样本','',
      f'- 9好人行×8匪列=72单元；开发每单元256局，种子182000000—182000255；独立验收每单元2048局，种子183000000—183002047。共{audit["formal_games"]:,}场正式仿真调用。',
      '- 不同策略共享相同seed、发牌和决策键随机流；总计2304个基础seed，不能把所有策略运行当作165888个独立发牌。各单元的2048个验收seed独立，跨策略为配对，比较族可相互相关。',
      '- 开发集不拟合参数、不选q；开发结果查看后未更改冻结策略/比较/种子。验收一次运行，不因结果追加种子。首日轨迹在全部预定配对中逐局相同。',
      '- q50三对比较×8匪条件=24项共同主要比较族。区间是翻转正/负两边际二项率的Clopper–Pearson区间，union bound覆盖整个24项族，名义同时95%；单侧尾部α=0.05/(4×24)。不是精确总体胜率/均衡证书。',
      '- q0/q100仅敏感性分析，不从这些结果宣布最佳混合。单元胜率的逐点Wilson区间也保留在原始JSON。成对差区间不把零样本方差错误写成总体严格相等。','',
      '## 4. 验收主要结果：q50','',
      '每格分母2048；区间单位为**百分点**。按固定匪列分别比较，不跨列择优。','',
      '| 匪条件 | base | fixed | local | local−base（同时95%区间，百分点） |','|---|---:|---:|---:|---|']
    for mn in names:
        a,b,c=[D[g+'_q50',mn]['win']['rate'] for g in ('base','fixed','local')];x=comparisons['base->local',mn]
        lines.append(f'| {mn} | {pct(a)} | {pct(b)} | {pct(c)} | {100*(c-a):+.3f} {interval(x)} |')
    lines += ['', '全部24项配对差与验收区间：','', '| 匪条件 | 比较 | 负转胜 | 胜转负 | 差值百分点 | 同时95%区间 |','|---|---|---:|---:|---:|---|']
    for mn in names:
        for pair in ('base->fixed','base->local','fixed->local'):
            x=comparisons[pair,mn];w=x['win']
            lines.append(f'| {mn} | {pair} | {w["improved"]} | {w["worsened"]} | {100*w["delta"]:+.3f} | {interval(x)} |')
    lines += ['', '## 5. 接力是否发生，以及是否改变行动','',
      '以下q50 local；“覆盖”是至少发生一次的局数；“接力出匪率”是所有接力目标里匪的比例，仅裁判事后统计，不是金水决策可见信息。跨日重复接力会重复计次，不能把接力条数当独立对局。','',
      '| 匪条件 | 委托局/2048 | 接力局/2048 | 接力条数 | 接力改变票数 | 接力出匪率 |','|---|---:|---:|---:|---:|---:|']
    for mn in names:
        r=D['local_q50',mn]['raw'];offers=sum(r['delegate_game']);accepted=sum(r['relay_game']);n=sum(r['relay_count'])
        lines.append(f'| {mn} | {offers} ({pct(offers/2048)}) | {accepted} ({pct(accepted/2048)}) | {n} | {sum(r["relay_changed_ballots"])} | {pct(sum(r["relay_mafia_target_count"])/n) if n else "—"} |')
    lines += ['',
      '接力发生不等于增加信息。警察候选名单、金水与旁观者现在仍使用继承的确定性信息路由/位置排序；金水没有额外的独立语言判断或新的后置线索模型。明确授权若只把相同目标再说一次，已有名单内集中规则可以产生相同实际票。因此当前负结果首先限制**这个协议＋接收/选人模型**，不能推断现实后置金水毫无价值。','',
      '分票计数仅描述各自实际存活轨迹：不同政策可改变轮次数，不能直接用其比例声称因果中介。原始结果保留 good_rounds / good_split_rounds；本轮没有用这些分数训练投票模型。','',
      '## 6. 跳藏敏感性与开发结果','',
      '下面每个数字为该行在预定8匪列中的**最低观测胜率**，不是对任意匪策略的下界。最小值选取本身有噪声；不据此求最佳q或受限均衡。','',
      '| 策略 | q0开发/验收 | q50开发/验收 | q100开发/验收 |','|---|---:|---:|---:|']
    for g in ('base','fixed','local'):
        parts=[]
        for q in ('0','50','100'):
            tr=min(T[g+'_q'+q,m]['win']['rate'] for m in names);ho=min(D[g+'_q'+q,m]['win']['rate'] for m in names)
            parts.append(pct(tr)+' / '+pct(ho))
        lines.append('| '+g+' | '+' | '.join(parts)+' |')
    lines += ['', '每个q×匪列的完整验收率：','', '| 匪条件 | q | base | fixed | local |','|---|---:|---:|---:|---:|']
    for mn in names:
        for q in ('0','50','100'):
            lines.append('| '+mn+' | '+q+' | '+' | '.join(pct(D[g+'_q'+q,mn]['win']['rate']) for g in ('base','fixed','local'))+' |')
    lines += ['', '## 7. 测试、重放与案例','',
      '- 实际运行 `python -m pytest tests -q`：315 passed，34.09秒；本轮新增8项，覆盖信息权限、授权撤销、私有反证、未知身份置换不变、PK和旧控制兼容等。最初测试构造把day1报告加在day2、错用了座位环起点及观察字段；均在正式冻结前修正。',
      f'- 实际运行 `python scripts/run_gold_relay_v27.py --workers 4`：{audit["formal_games"]:,}局；运行时间见 manifest.json。',
      f'- 实际运行 `python scripts/verify_gold_relay_v27.py`：{audit["cells_checked"]}单元结构及原始统计核对；{audit["direct_sample_replays"]}个抽样无审计器完整重放；{audit["v26_compatibility_replays"]}个v26控制兼容；{audit["independently_checked_intervals"]}个主要比较区间用独立binomtest接口核对；{audit["frozen_assets"]}项冻结资产哈希通过。不是重跑全部正式模拟。',
      '- 全单元未见非法票、忽略合法私人活匪、投私人好人、接力目标为警队成员或警察冒充本轮受托平民的审计异常。后三项零值还依赖本轮仅真实警队授权、名单排除己队的策略限制，不是任意假授权安全定理。',
      f'- 实际运行 `python scripts/diagnose_gold_relay_v27.py`：按冻结规则挑选首个收益/损失/改变票案例，得到{examples["audited_detail_runs"]}条详细轨迹与{examples["independent_direct_replays"]}次对应无审计器重放。没有满足条件的案例如实标null，不另挑有利故事。','',
      '上述验证使用当前冻结v27源码。历史其他版本测试数字不是本轮重新运行其全部实验。原始数据、配置、每个单元的逐局0/1结果及关键计数均保存；报告生成不更改决策源码。','',
      '## 8. 可以得出什么、不能得出什么','',
      '1. 已实现并验证一个信息合法、明确授权、仅当天单层名单内的金水接力协议；受托者地位不同于无委托普通平民，但不冒充警察、不凭全知裁判选人。',
      '2. 对当前冻结策略池，本轮未证明接力能增加胜率。若对应实际票零变化，应解释为行为上的重复，而不是样本少所以先宣称“可能显著提高”。统计仍留有限样本边界，不能由观察相同证明所有seed相同。',
      '3. 匪可以不接续；不能仅汇报claim列替代最差情形。匪尚不会伪造“假金水＋委托”、针对受托者夜刀或通过新的授权内容训练反制，现有结果不是抗任意反制保证。',
      '4. 这不是新算法、有限矩阵均衡或完整游戏GTO；没有新增均衡证书，也没有根据这次结果重新训练q。',
      '5. 有用的下一问题不是继续加信用数值，而是：有没有一个真实可达、双方信息合法的局面，使警察的名单还不足以确定归票，但后置金水从后续公开内容得到应当改归的新依据？先人工追踪这种分歧；再比较只重申与允许有证据改归，并补匪方伪造授权。','',
      '## 9. 保留待办与复现','',
      '优先建议（需用户决定）：先做少量受托者独有信息/后续公开变化案例审计，不扩大策略池或搜索有利种子。区分名单排序已经等价、接收规则吞掉差别、真正缺乏新增信息这三种解释。跳藏q0/50/100继续保留；不能因本轮接力无增益就遗忘跳藏。','',
      '分开待办：首日金水接力；有依据的名单外改归与PK联动；假金水授权反制；跨日投票来源及公开怀疑；遗言制度；信用分独立消融；金水假跳挡刀；多匪声明后的4v4对冲；白天报匪；LLM影子验证。','',
      '```sh',
      'python -m pytest tests -q',
      'python scripts/run_gold_relay_v27.py --output results/v27_reproduction --workers 4',
      'python scripts/verify_gold_relay_v27.py',
      'python scripts/diagnose_gold_relay_v27.py',
      'python scripts/build_gold_relay_report_v27.py',
      '```','',
      '运行脚本拒绝覆盖既有结果目录；验证/案例脚本默认核查原存档results/v27。完整历史源码在results/v27/source；未来主分支变动后应在冻结源码中复现，不能混用新版决策。新增的报告生成脚本属于派生分析，另用analysis_manifest记录；非原决策冻结的一部分。','',
      '材料：[冻结方案](gold_relay_protocol_v27.md)、[配置](../configs/gold_relay_v27.json)、[原始验收](../results/v27/holdout.json)、[资产清单](../results/v27/freeze.json)、[核验](../results/v27_integrity_audit.json)、[案例选择](../results/v27_examples.json)。']
    redundant=json.loads((ROOT/'results/v27_redundancy_audit.json').read_text())
    pos=lines.index('## 8. 可以得出什么、不能得出什么')
    extra=['### 查看结果后的只读冗余审计（不是预注册确认实验）','',
      '预定的胜负翻转/改票案例全部为空，所以没有强找正反故事。为解释零变化，查看结果后另外固定取每个匪列中第一个实际接力的q50 seed，不挑收益；共8个条件案例，仅3个不同seed。每例重放base/fixed/local三个版本，24条详细轨迹、24次无审计器重放，另8次记录受托者实际观察。这是同一批验收数据的描述性检查，没有新增验证样本。','',
      '八例中，删除新增delegate/relay声明后，其余完整公开行动轨迹逐条相同。受托者的队友表为空、私人验人为空；原本选谁与接力后选谁相同。与全验收所有接力改票计数为零相互吻合，但样例相同不能证明所有可能历史都等价。','',
      '下表座位转为桌游习惯的1起编号；原始JSON为0起编号。','',
      '| 匪条件 | seed | 日 | 委托人→金水 | 授权名单 | 原首选→接力选择 |','|---|---:|---:|---|---|---|']
    for case in redundant['cases']:
        if case['seed'] is None:continue
        v=case['first_relay_view'];pool='/'.join(str(p+1) for p in v['offered_candidates'])
        extra.append(f"| {case['mafia']} | {case['seed']} | {v['day']} | {v['source']+1}→{v['recipient']+1} | {pool} | {v['unmodified_target']+1}→{v['chosen']+1} |")
    extra += ['', '例如seed183000001、decoy_far_claim：第2日12号警察把13/15号交给5号金水选择；5号没有警队名单或私人验人，原来会选13号，接受委托后仍选13号。新增声明没有改变这局的任何实际行动，不能靠给它更高“信用分”就凭空获得新信息。见[只读审计](../results/v27_redundancy_audit.json)。','']
    lines[pos:pos]=extra
    report=ROOT/'docs/gold_relay_results_v27.md';report.write_text('\n'.join(lines)+'\n')
    files=[report,Path(__file__),ROOT/'results/v27_integrity_audit.json',ROOT/'results/v27_examples.json', ROOT/'results/v27_redundancy_audit.json',ROOT/'scripts/audit_gold_relay_redundancy_v27.py',ROOT/'results/v27_validation.json']
    save(ROOT/'results/v27_analysis_manifest.json',dict(files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files},
         note='Derived report and read-only analysis assets; policies unchanged after formal freeze.'))
    print(report)


if __name__=='__main__':build()
