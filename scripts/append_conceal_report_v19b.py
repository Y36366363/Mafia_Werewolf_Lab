#!/usr/bin/env python3
"""Append the clearly separated, post-v19 exploratory follow-up."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v19b';p=ROOT/'docs/reply_results_v19.md'
lines=['','## v19b补充：这次确实比较暂缓首个跳警','',
'这是查看v19两批结果后新增的探索问题，使用另外两批新种子C/D；不是原实验的留出检验。策略和C/D在读结果前同时冻结：每单元4096局，两行×两种早跳刀法×两区块，共32768局。', '',
'`conceal`：此前没有真警公开、假警查杀未中警队时，首名真警暂不报验或跳警，仍能表达普通怀疑、保留私人验人并据此投票。`answer`：立即报真实验人、内推并指出假警。其余同v19。警察只看队友位置，不看未知目标真实身份。比较的是完整的这组行动差别，不能单独归因于某一条发言。', '',
'主条件还要求首夜未死警、确有回应机会、假查杀实际命中民。目标民身份只供评价统计。此条件下实际公开警察人数差必须为1，否则干预没有成功。','',
'|新种子区块|匪刀法|主条件n|暂缓跳警胜率|立即回应胜率|回应−暂缓差值（百分点）|探索性95%区间|保守95%区间|首日出匪差值|公开警察人数差|','|---|---|---:|---:|---:|---:|---|---|---:|---:|']
def pcent(x):return '—' if x is None else f'{100*x:.2f}%'
def pp(x):return '—' if x is None else f'{100*x:+.2f}'
def ci(x):return '—' if x is None else '['+', '.join(pp(v) for v in x)+']'
for block in ('evaluation_C','replication_D'):
    r=json.loads((folder/(block+'.json')).read_text())
    for row in r['contrasts']:
        if row['branch']=='narrow_civilian':
            w=row['win'];lines.append('|'+ '|'.join([block,'后置刀' if row['mafia'].startswith('safe') else '伪装刀',str(row['n']),pcent(row['conceal']['rate']),pcent(row['answer']['rate']),pp(w['delta']),ci(w['ci95_normal']),ci(w.get('ci95_hoeffding')),pp(row['day1_mafia_exile']['delta']),str(row['police_claims']['delta'])])+'|')
lines += ['', '**如何理解：** 后置刀下，暂缓跳警的整局胜率在C/D都更高；伪装刀下，立即回应的首日出匪率增加约54.11／50.36个百分点，误出警率减少约43.21／39.09个百分点，但整局胜率只增加2.32／1.27个百分点，第二批的探索性区间仍跨零。首日组织收益与后续曝光成本不能互相替代。', '', '这不是说警察可以直接“见后置刀就藏、见伪装刀就跳”：实际对局不知道匪方使用哪条策略，本表是研究者分组评价。未来只能根据当时可见历史作判断，或在未知刀法混合下评估稳健性。','', '窄条件只覆盖每单元4096局中的一部分；此处少数胜负变化不能因为总执行数较大而叫作已经收敛。没有加入真正的跨日私人“此人已知假警”记忆、诱导发言回应或匪方留警反制，所以即使暂缓跳警占优，也只支持本规则中的短期隐藏，不等于已验证完整钓鱼执法。', '',
'复现：`python scripts/run_conceal_v19b.py`；核验：`python scripts/verify_conceal_v19b.py`；冻结源码、展开配置、逐局评价量在`results/v19b/`。与主实验合计229376次正式终局模拟，不含测试和抽样重放。', '']
p.write_text(p.read_text()+'\n'.join(lines));print('conceal supplement appended')
