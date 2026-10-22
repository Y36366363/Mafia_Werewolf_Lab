#!/usr/bin/env python3
"""Build the human-readable report from frozen v17 artifacts, without selecting policies."""
import json
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def pct(x): return f'{100*float(x):.2f}%'
def pp(x): return f'{100*x:+.2f}'
def build():
    folder=ROOT/'results/v17'
    read=lambda name:json.loads((folder/name).read_text())
    train,hold,cal,manifest=map(read,['train.json','holdout.json','calibration.json','manifest.json'])
    audit=json.loads((ROOT/'results/v17_integrity_audit.json').read_text())
    out=['# v17 内推时序、来源信用与跨日票史：完整方法与结果报告','',
         '日期：2026-10-22。主配置4警4匪8民。固定候选策略评估与有限经验矩阵证书，不是完整游戏GTO。','',
         '## 方法与研究问题','',
         '优先检验内推语义修复：警察在自己发言时给出怀疑范围，后置位公开金水或声明警察者可在自己的时点提出名单内外改归。普通玩家可以公开怀疑，但没有自动获得归票权。投票时每名玩家根据自己可见信息决定是否采纳，不添加全场结束后的秘密警队指令。前置金水不会事后补发言。','',
         'legacy1/legacy2保留v16全员发言后名单内选择流程，但使用本轮相同匪方策略，因此是内部机制对照，不能视为v16数值复现。timed1/2/3是新流程的一/二/三人名单；credit2增加来源信用；history2在credit2上增加跨日票史评分。legacy到timed同时改变时点、可改归范围及公开多数规则，是流程组合效应，不能归因于时点一个因素。','',
         '来源信用是冻结启发式：普通版本声明信用0.6；信用版本被他人公开报金水且未被查杀者0.75，否则0.5；采纳门槛0.6。平民无权读取真实警队。警察可以私下识别队友；自己的声明不成为自己的新证据。公开金水是可伪造声明，不是裁判认证。无可信改归则按名单和私人排序收束；私人查杀优先。','',
         '票史评分在第二天起才生效：此前声明目标与实际投票不符（包括有目标后弃票）最多增加0.10怀疑；与当前已怀疑玩家至少两轮共同投票最多增加0.05。只读公开历史和本人合法验人，没有死亡翻牌。这是有上限的描述性规则，不是校准的身份概率；跟随后续可信改归也可能造成声明与投票不符，属于本轮局限。','',
         '四个匪方列为late/首夜后验伪装 × 安静/后置位悍跳。悍跳者在看到外队警察声明后可查杀该声明者并提出名单外改归，匪队同步集中投票。没有开放伪造警察内推名单、任意真假金水链或完整语言说服，所以反制能力仍有限。','',
         '全部好人固定equal位置模型及inspect_gap；位置模型只用于第一天，后续不误用首夜模型。2% tremble仍只平滑假设似然，实际匪方没有新增2%随机失误。PK最高票平票时仅一轮，复投仍平则平安日。遗言固定前三死者。','',
         '## 冻结样本与评价边界','',
         f"正式对局总数：{manifest['games']:,}。主矩阵7×4，训练1024局/格（seed145000000起），留出4096局/格（146000000起），随机刀校准1024局/行（147000000起）。共享发牌seed支持配对比较；三段互不重叠。训练求解后冻结混合，再读取留出；校准不参与策略选择。",'',
         '不同匪方列可能选择不同首刀，故条件分支只在同一匪方列内配对。下述区间为探索性95%配对Wald近似，未作全部对比多重校正；原始文件同时保留保守Hoeffding区间。不能将区间跨零解释为等价或无效，也不能将经验矩阵精确证书解释为收益无误差。','',
         '## 留出总体终局胜率','',
         '| 好人策略 | '+' | '.join(hold['matrix']['mafia'])+' |',
         '|---|'+'---:|'*len(hold['matrix']['mafia'])]
    for name,row in zip(hold['matrix']['good'],hold['matrix']['rates_exact']):
        out.append('| '+name+' | '+' | '.join(pct(Fraction(x)) for x in row)+' |')
    out+=['','## 首夜未死警且首验金水：机制指标','',
          '这里的“首轮最高票目标命中”是实际首轮投票的唯一最高票者为匪比例；平票计0。它不是最后一条改归建议。名单外建议发生率与实际名单外放逐率分开报告，避免把提出建议误当成功改归。','',
          '| 行 | 匪方 | 分支n | 终局胜率 | 首轮最高票命中 | 名单外放逐 | 名单外建议 |',
          '|---|---|---:|---:|---:|---:|---:|']
    for c in hold['cells']:
        b=c['branches']['eligible_clear'];mask=c['raw']['eligible_clear'];n=b['n']
        avg=lambda key:sum(x for x,k in zip(c['raw'][key],mask) if k)/n if n else 0
        out.append(f"| {c['good']} | {c['mafia']} | {n} | {pct(b['win']['rate'])} | {pct(b['final_target_mafia_rate'])} | {pct(avg('outside_exile'))} | {pct(avg('outside_reroute'))} |")
    out+=['','## 预声明配对对比','',
          '变化均为后者减前者，以百分点表示；主表使用首夜未死警分支。查杀与金水子分支完整结果保留在原始留出文件。','',
          '| 对比 | 匪方 | n | 终局差pp | 95%近似区间pp | 改善/恶化局数 |',
          '|---|---|---:|---:|---:|---:|']
    for x in hold['predeclared_paired_contrasts']:
        if x['branch']!='leader_eligible':continue
        s=x['win'];a,b=s['ci95_normal']
        out.append(f"| {x['name']} | {x['mafia']} | {s['n']} | {pp(s['delta'])} | [{pp(a)}, {pp(b)}] | {s['improved']}/{s['worsened']} |")
    out+=['','## 校准：随机刀＋后置悍跳','',
          '| 好人行 | n | 总体胜率 |','|---|---:|---:|']
    for c in cal['cells']:out.append(f"| {c['good']} | {c['n']} | {pct(c['win_summary']['rate'])} |")
    out+=['','## 有限经验矩阵证书','']
    for name,sol in [('训练',train['restricted_empirical_equilibrium']),('留出事后诊断',hold['restricted_empirical_equilibrium'])]:
        out += [f"{name}：value={sol['value_exact']}（{pct(sol['value'])}），代数gap={sol['gap_exact']}。",
                f"好人混合：`{sol['good_mixture']}`。匪方混合：`{sol['mafia_mixture']}`。",'']
    f=hold['frozen_train_mixture_on_holdout']
    out += [f"冻结训练混合在留出上：lower={f['lower_exact']}（{pct(f['lower'])}），upper={f['upper_exact']}（{pct(f['upper'])}），gap={100*f['gap']:.4f}个百分点。最坏匪方列={f['worst_mafia']}，最佳好人行={f['best_good']}。",'',
           '证书给出一组可行均衡混合，未证明其唯一；不同混合得到同一值不代表求解失败，也不能把这些比例解释为真实玩家的客观出招频率。上述混合是在双方预先约定各自完整团队协议的元策略层面求解；不代表每个平民独立随机化就能实现同样的整队抽样，也不证明无需秘密团队相关装置即可实现任意元混合。尚未搜索候选池外最佳回应。','',
           '## 验证与复现','',
           '执行：`python -m pytest -q`；`python scripts/run_timed_nomination_v17.py --workers 4`；`python scripts/verify_timed_nomination_v17.py results/v17 --replay --output results/v17_integrity_audit.json`。',
           f"完整性审计：{audit['cells_checked']}个单元、{audit['archived_assets_checked']}项冻结资产、{audit['sampled_full_replays']}次抽样完整轨迹重放，状态{audit['status']}。这不是全部模拟独立重跑或独立引擎验证。",'',
           '原始数组、协议、配置、训练冻结选择、经验矩阵和源码位于`results/v17/`；测试还检查名单在本人发言时产生、后置金水可名单外改归、隐藏警察无公开特权、平民不能识别真实警队、未知身份置换不改变可见行动、票史在首日不产生效应。','',
           '## 待办清单','',
           '1. 对来源信用与票史评分做校准和针对性反制，区分合法跟随改归与投票背离。',
           '2. 在更完整策略池内研究跨日冲票、弃票与投票联盟，避免把警察抱团等同匪徒抱团。',
           '3. 加入可独立消融的公开“认为谁是好人”声明、真假金水与诱饵；当前只实现公开怀疑和有限悍跳。',
           '4. 固定策略后独立比较前三死者、前四死者及全员遗言。',
           '5. 白天报匪机制继续暂缓。','']
    out[4:4] = [
        '## 本轮核心结果与应如何理解','',
        '1. 内推流程已经实际开放：一人/二人/三人怀疑范围在警察本人发言时公布，后置金水和声明警察者可以提出名单外改归；实际名单外放逐可被观测。流程修复本身不保证更高胜率。安静late列，legacy1到timed1总体从2.15%到2.64%；伪装安静列则从1.86%降到1.42%。',
        '2. 在没有来源信用的版本中，后置悍跳能机械劫持改归。五种无信用策略在两种counter列各4096局样本均未获胜；不能把样本零胜写成总体胜率等于零。单格零胜的单侧95%二项上界约0.073%。',
        '3. 来源信用是防御性增量。timed2到credit2，late_counter总体从0/4096升到138/4096=3.37%，decoy_counter从0/4096升到44/4096=1.07%。在首夜未死警分支，配对差分别+3.42个百分点（近似95%区间[+2.73,+4.11]）和+1.60（[+1.13,+2.07]）。它并未修复安静伪装刀导致的弱金水误归。',
        '4. 票史规则可以大幅利用固定安静匪票型：late_quiet从credit2的3.37%到history2的40.21%，decoy_quiet从1.07%到5.35%；但counter列分别降到1.12%和0.10%。因此票史模块有强策略依赖，不能替代信用防御，也不是接近完整GTO的证据。',
        '5. 一人/二人名单尚不能普遍排序。timed2相对timed1，在首夜未死警的late_quiet分支只改善3局、恶化0局（+0.11个百分点，近似区间跨零），decoy_quiet改善1局、恶化8局（-0.25个百分点）。三人相对二人在四列中仅有1局终局胜负变化。这个低覆盖差异不足以永久淘汰三人名单。后续主测试可压缩到一人、二人，三人留少量挑战对照；本轮没有credit1/credit3，不能推断加入信用后也相同。','',
    ]
    out += [
        '## 额外机制核查与限制','',
        '本轮完整测试224项通过。额外只读检查16,384组成对开局，credit2与history2的首日名单、放逐身份、PK、名单外建议和名单外放逐全部一致，符合票史第二天才生效的设计。另保存4局完整解释轨迹，材料在results/v17_mechanism_diagnostics.json；这是事后诊断，不是新的独立验证集。',
        '例子使用零起始座位seed146000009。在安静late下，第一天两版都验出并放逐7号匪，匪方四票集中0号。第二天credit2名单为14、15，公开金水6号误归警察13号并导致放逐；history2名单为14、3，金水改归14号匪，随后继续出3、5号匪。轨迹说明固定共同票和声明背离提供了可利用指纹，也说明公开金水并不拥有警队私有信息，可能误归真警。真实角色只用于离线解释，从未传给平民策略。',
        '该例不能单独证明全部40.21%收益由某一票史组件造成；当前两项评分同时启用，未做独立组件消融。悍跳会改变可见声明、怀疑锚点及后续行动路径，因此counter列的失败也不能只归因一个评分组件。',
        '正式流程组合会在后续白天继续执行，不是只替换第一天动作、固定其余全部续局。因此首夜分支的终局差包括后续流程影响。第一天位置评分之后，信用版后续未验未知位基准分全为0，0.05的票史增量便可打破大批同分；这会放大相对一个简单续局基线的收益。',
        '有公开金水支持的归票采用更高权重，只是当前启发式。对手尚未加入给队友假金水、伪造完整内推或刻意一致投票等针对性回应；信用有效不代表真实身份被确认。先加强这些反制和后续基线，再判断是否扩展更多名单或提高模型复杂度。',
        '本轮主池沿用上一轮有支持的late与伪装刀；middle/late混合权重优化并未在本轮完成。遗言制度和白天报匪也未同时变更。','',
    ]
    (ROOT/'docs/timed_nomination_results_v17.md').write_text('\n'.join(out))
if __name__=='__main__':build()
