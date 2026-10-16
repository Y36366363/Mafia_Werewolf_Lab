#!/usr/bin/env python3
"""Human-readable method and result tables; no policy selection."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(x) for x in row)+' |' for row in rows])


def pct(x):return f'{100*x:.2f}%'
def pp(x):return f'{100*x:+.2f}'
def interval(a):return f'[{100*a[0]:+.2f}, {100*a[1]:+.2f}]'


def main():
    folder=ROOT/'results/v11'
    data=json.loads((folder/'evaluation.json').read_text())
    analysis=json.loads((folder/'analysis.json').read_text())
    audit=json.loads((ROOT/'results/v11_integrity_audit.json').read_text())
    labels={'none':'新增评分关闭','vote':'只用于投票','kill':'只用于夜刀','both':'投票与夜刀'}
    names={'anchor':'集中目标','diverse':'分散目标'}
    contrast_names={'anchor_minus_diverse_none':'关闭时：集中减分散',
                    'interaction_both_minus_none':'交互：集中变化减分散变化'}
    for g in names:
        for c in ('vote','kill','both'):
            contrast_names[f'{g}_{c}_minus_none']=f'{names[g]}：{labels[c]}减关闭'
    rows=[]
    for c in data['cells']:
        m=c['means']
        rows.append([names[c['good']],labels[c['channel']],pct(m['win']),pct(m['day1_good_vote_concentration']),
                     pct(m['day1_exile_mafia']),pct(m['day1_exile_police']),pct(m['night2_kill_police'])])
    lines=['# v11：目标集中与分散的行动阶段消融','',
           '2026-10-16。方案在正式运行前以1778ecf提交冻结；主配置4警4匪8民。',
           '本轮只拆分已有评分的使用阶段，不增加均衡矩阵、不重新训练、不进行参数晋级。', '',
           '## 在做什么、用了什么方法','',
           '研究问题：同样的平民首发预算下，集中和分散目标的好人方案，会如何受到匪方新增集中支持者评分的影响？这项评分用于投票还是夜刀是否有区别？', '',
           '两个好人协议沿用v10的anchor与diverse，首日发言前8位中的平民按各自公开规则提名，警察只在公开目标与私人查杀一致时跟进。两者的完整参数只差目标映射；验人、投票、第二日起的规则相同。公共提名可由匪发起，并不认证身份。', '',
           '匪方原有combined推理和发言始终保留，只将已有concentration特征（权重固定2）分别关闭、用于投票、用于夜刀、用于两者。四种条件统一采用确定性夜刀破同分。因此关闭新增评分不等于匪方不使用公开信息。其余算法相同，但不同票型可以间接影响后续历史。', '',
           '正式种子91000000—91004095，共4096个全新种子，每个种子跑8个条件，共32768次终局执行。没有训练集或本轮策略选择，正式样本之前只用另一组小样本验证程序。这里是基于旧探索提出的固定消融新样本评价，不是未来整篇论文的最终盲测。', '',
           '逐种子核验8条件首夜状态完全相同、同一好人方案下4条件首日投票前记录相同、夜刀开关不影响首日指标、两好人方案的平民提名数量相同。实际独立单位是4096个种子，不能当成32768个互相独立开局。', '',
           '## 原始表现','',
           table(['好人协议','匪方新增评分','好人终局胜率','首日好人票集中度','首日放逐匪','首日放逐警','第二夜刀中警'],rows),'',
           '好人票集中度=首日存活好人投向同一非空目标的最大票数/存活好人人数，弃票仍计分母。第二夜在本配置全部开局中存在，刀中警察按所有开局作分母。除终局胜率外，这些指标均为描述性诊断，不是已证实的因果中介。','',
           '## 八项预先固定的终局比较','',
           '下表单位为百分点；正数代表好人胜率上升。每项按同种子配对。正态Bonferroni区间控制8项比较但只是渐近近似；Hoeffding为8项同时保守界。交互项每个样本取值范围宽度为4，其他项为2。','',
           table(['对照','变化pp','95%家族正态近似区间','95%家族Hoeffding区间'],
                 [[contrast_names[k],pp(v['delta']),interval(v['ci95_family_normal_approx']),
                   interval(v['ci95_family_hoeffding'])] for k,v in analysis['primary'].items()]),'',
           '预先关注尺度为3pp，但未宣称4096样本足以识别每种3pp效应。区间包含0不等于无效；未显著也不等于等效。辅助指标和其他跨单元比较不能沿用本表的8项家族界。','',
           '## 结果是什么意思','',
           '在关闭新增评分的共同基线上，集中目标胜率32.30%，分散目标14.53%，差17.77pp；8项同时Hoeffding区间为[12.47,23.08]pp。集中方案在这个指定对手下有明确优势，但这不是全候选最差收益，也不推翻旧实验中其他对手可能更擅长反制集中方案的结果。','',
           '新增集中支持者评分没有成为更强匪方回应：只加在夜刀上时，好人胜率在集中方案下增加4.17pp，在分散方案下增加6.32pp。后者的同时Hoeffding下界为+1.02pp；前者的正态家族近似区间排除0，但保守Hoeffding区间仍跨0，证据强度应分开描述。两通道一起用时也没有挽回匪方收益。','',
           '只加在投票上时，两方案的好人胜率变化分别为+0.24pp和+0.02pp。观察值很小；本轮未开展正式等效检验，不能宣布投票通道严格无效。','',
           '第二夜刀中警察的比例，集中方案从20.97%降到9.18%，分散方案从52.17%降到34.96%。这与新增夜刀评分误导目标选择的解释一致。由于该特征会额外追踪热门提名的支持者，可能追到参与掩护的平民；此解释尚未通过目标身份分解和分数归因逐一核实，不能写成已证明的中介机制。','',
           '集中方案的首日好人票集中度更高，首日放逐匪和放逐警的比例也都更高。因此公开集中既可能帮助有效放逐，也可能让错误放逐更一致；终局优势不能只用票集中度一个指标解释。','',
           '本轮收紧了研究主张：应研究公开协议与特定回应的相互作用，而不是预设公开集中一定被更强追踪击穿。此前w2只是同家族权重中的经验赢家，不能据此说它优于关闭评分的等条件基线。','',
           '建议下一步由用户决定：优先对已有配对开局中夜刀目标发生变化的记录，核查基础分、额外分与实际目标身份，并单独标出双方原本就选择相同目标的开局。这是解释性诊断，不能把按处理后目标变化筛选的子集当作新的无偏因果效应。本轮尚未执行该分析，不继续调权重或扩大策略池。','',
           '## 验证和证据边界','',
           f"170项全量回归测试通过。审计检查{audit['cells']}个单元、{audit['primary_contrasts']}项主要对照、所有单元逐种子原始指标和{audit['archived_assets_checked']}个归档文件，并从归档源码抽样重放{audit['archived_full_trace_replays']}局，逐项比对指标、首夜状态及完整轨迹哈希。全部通过。",'',
           '抽样重放不是全部32768局独立重跑，也不是第二个独立模拟器。策略只接受合法Observation，真身份用于赛后指标；新增信息不变性和行动阶段测试通过。','',
           '结果仅针对这两种好人策略、一个固定权重的评分家族、固定续局及公开顺序投票规则。总体优势不能直接归因于隐私泄露；评分并不输出校准的警察后验概率。本轮不含团队秘密混合执行，不生成均衡证书，不证明完整游戏GTO。','',
           '历史v10证书继续对应旧经验矩阵；其留出复用和机制解释的修正见[evidence_corrections_20261016.md](evidence_corrections_20261016.md)。','',
           '## 复现','',
           '- [冻结配置](../configs/mechanism_v11.json)、[协议](mechanism_protocol_v11.md)、[运行前冻结](../results/v11/freeze_before_evaluation.json)。',
           '- [原始指标与轨迹哈希](../results/v11/evaluation.json)、[对照分析](../results/v11/analysis.json)、[清单](../results/v11/manifest.json)、[审计](../results/v11_integrity_audit.json)。', '',
           '```sh',
           'PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q',
           'PYTHONDONTWRITEBYTECODE=1 python scripts/run_mechanism_v11.py --output results/v11_reproduction --workers 4',
           'PYTHONDONTWRITEBYTECODE=1 python scripts/verify_mechanism_v11.py results/v11 --replay --output results/v11_integrity_audit.json',
           'python scripts/build_mechanism_report_v11.py',
           '```', '',
           '冻结执行源码和配置位于results/v11/source；后续工作区版本变化时应使用归档运行入口与配置复现，不能自动把新源码运行当成旧版本复现。','']
    (ROOT/'docs/mechanism_results_v11.md').write_text('\n'.join(lines))
    print('docs/mechanism_results_v11.md')


if __name__=='__main__':main()
