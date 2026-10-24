#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'docs/reply_results_v19.md';s=p.read_text()
a=json.loads((ROOT/'results/v19/evaluation_A.json').read_text());b=json.loads((ROOT/'results/v19/replication_B.json').read_text())
def delta(report,name,mafia,metric='win',branch='eligible'):
    r=next(r for r in report['contrasts'] if r['name']==name and r['mafia']==mafia and r['branch']==branch)
    return f"{100*r[metric]['delta']:+.2f}"
summary=['## 先看结论：解决了什么，尚不能回答什么','',
'1. **完成公平一些的回应比较。** 本次不再用v18的均匀声明世界计数给单警定罪；保留旧信用，加入金水关系保护、真实验人、原有内推、合法发言机会和平民自己的反驳。不能用这些绝对胜率直接与v18比较，它们是不同策略条件。',
'2. **早假查杀后“总要回应”仍没有稳定胜率收益。** 后置刀下A/B差值分别为'+delta(a,'reply','safe_late_forward')+'／'+delta(b,'reply','safe_late_forward')+'个百分点；伪装刀下为'+delta(a,'reply','posterior_decoy_forward')+'／'+delta(b,'reply','posterior_decoy_forward')+'。方向翻转，不足以确定必回或必藏。',
'3. **已有真警公开后，再暴露一名队友，需要单独权衡。** 伪装刀／末匪跳分支，额外回应A/B胜率差为'+delta(a,'reply','posterior_decoy_last')+'／'+delta(b,'reply','posterior_decoy_last')+'个百分点，每局多公开一名真警。正常近似区间为负，但保守区间仍跨零；这是固定续局中的负向证据，不能当全策略定理。后置刀／末匪跳没有后续真警发言机会，不能伪造一个回应结论。',
'4. **“被错查杀的平民知道假警是谁”确实可影响首日。** 在伪装刀／早跳主条件中，加入该平民的反驳提名和优先投票后，首日出匪率A/B增加'+delta(a,'civilian_denial','posterior_decoy_forward','day1_mafia_exile')+'／'+delta(b,'civilian_denial','posterior_decoy_forward','day1_mafia_exile')+'个百分点；整局胜率只增加'+delta(a,'civilian_denial','posterior_decoy_forward')+'／'+delta(b,'civilian_denial','posterior_decoy_forward')+'个百分点。不能把局部选票优势等同于已经赢局。',
'5. **没有验证完整沉默钓鱼。** 原keep仍让首名真警报验；因此另用全新C/D种子补测真正暂缓首个跳警，结果在文末v19b。存活信用封顶对照本轮没有有效触发，不能据其零差异否定存活推理。', '',
'**真正隐藏的补充结果：** 当假查杀中民、无真警先公开且确能回应时，后置刀下暂缓跳警在两批均更好；伪装刀下回应明显改善首日出人，但整局胜率增量仍不确定。详见文末独立新种子C/D表，不能据此定出必跳或必藏的统一规则。','', '**模型限制直接影响解释：** 原信用给未获金水支持的真警来源0.50，低于0.60建议采纳门槛；真警出来反驳，不意味着旁观平民会听从。于是观察到的无收益可能来自信息没有转化为合理投票，不能直接归结为对跳战术不好。', '',
'**建议下一步先做：** 保存跨日的私人“我知道此人是假警”证据，区分无人回应与无机会回应，给有无对跳和存活信息建立可触发的更新，再验证原来的信用门槛是否阻断了真实信息。完成这些基础核查后再决定是否增加策略；跨日联盟、公开怀疑、遗言制度和白天报匪继续分开保留。','']
s=s.replace('## 本次方法与证据边界','\n'.join(summary)+'\n## 本次方法与证据边界')
audit=json.loads((ROOT/'results/v19_integrity_audit.json').read_text());auditb=json.loads((ROOT/'results/v19b_integrity_audit.json').read_text())
s += '\n## 本轮完成的核验\n\n最终 `python -m pytest tests -q`：247项通过。主实验48个单元的算术、分层和冻结文件哈希通过；归档源码抽样完整重放144局。补充实验8个单元通过，抽样完整重放24局。共168局抽样重放，不是229376局全部重跑。补充测试开发时的测试辅助函数被pytest识别成初始化钩子，已更名修正并重跑全部测试；没有改动冻结策略或因结果更换seed。\n'
p.write_text(s);print('readable conclusions added')
