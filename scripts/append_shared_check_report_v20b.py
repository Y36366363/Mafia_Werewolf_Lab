#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'results/v20b';path=ROOT/'docs/evidence_memory_results_v20.md'
r=json.loads((folder/'probe.json').read_text());audit=json.loads((ROOT/'results/v20b_integrity_audit.json').read_text())
lookup={(c['mode'],c['mafia']):c for c in r['cells']}
labels={'late_near':'后置刀／近端查杀','late_far':'后置刀／远端查杀','decoy_near':'伪装刀／近端查杀','decoy_far':'伪装刀／远端查杀'}
def pct(v):return f'{100*v:.2f}%'
def pp(v):return f'{100*v:+.2f}'
def ci(v):return '['+', '.join(pp(x) for x in v)+']'
lines=['','## v20b：仅补首验一致性的新种子探索','',
'该补充在v20训练后已发现缺口、读取v20留出后冻结并运行，不能写成原预注册结果。新种子163000000起，每单元2048局；原信息协议与修正协议两行×四列，共16384局。只在q=50%时比较，不重新选q，不改信用，不挑seed。本块没有独立复现。', '',
'新增规则：本轮真警仅报实际共享的首验，因此首日两个来源如果报告目标或结果不同，不能同时是真警；进入冲突来源比较。这不直接证明哪一人是真的。如果以后允许真警给队友发掩护金水，这条约束不能原样沿用。人工构造案例已检验不同首验触发冲突、相同首验不误触发、不同日期不误套首验约束。', '',
'|匪策略|修复前整局胜率|修复后整局胜率|整局差值（百分点）|逐项正常近似95%区间|保守95%区间|首日出匪率：前→后|出匪率差值（百分点）|','|---|---:|---:|---:|---|---|---|---:|']
for row in r['contrasts']:
    m=row['mafia'];a,b=lookup['original',m],lookup['corrected',m];w=row['win']
    assert a['raw']['police_claims']==b['raw']['police_claims']
    lines.append('|'+ '|'.join([labels[m],pct(row['original']['rate']),pct(row['corrected']['rate']),pp(w['delta']),ci(w['ci95_normal']),ci(w['ci95_hoeffding']),pct(a['means']['day1_mafia_exile'])+'→'+pct(b['means']['day1_mafia_exile']),pp(row['day1_mafia_exile']['delta'])])+'|')
lines += ['',
'**这说明什么：** 增补确定的一致性约束，能明显改变首日投票并提高首日出匪率，但目前“在冲突来源中按位置选人＋既定续局”没有普遍把这个收益转为整局胜利。两边第一天公开警察人数逐局完全相同，因此这里不能再用“多暴露了一名警察”解释胜率差；也没有足够证据归因于某个具体后续机制。', '',
'信息更多不要求玩家强制执行某种新投票规则，玩家原本可以忽略新增信息。本轮比较的是强制采用不同处理规则的固定策略，负结果不能证明信息本身有害、逻辑约束错误或旧信用是必要的。当前冲突排序、共同验人后的后续报验/投票、不同出局角色导致的续局变化需要先审计。', '',
'**建议下一阶段先做续局审计：** 冻结同样的首夜和发言，记录首日选票→夜刀→次日合法候选与投票的完整链条；检查好人是否避开私有已知好人、是否能协调投同一个已知匪、是否把失去来源的旧声明当成无条件权威。用小型人工残局校验这些动作，再决定要不要加入跨日票型或复杂信用。不是立刻扩大矩阵或寻找更好数字。', '',
f"补充核验：{audit['cells_checked']}个单元算术与冻结哈希通过，归档源码抽样完整重放{audit['sampled_full_replays']}局一致。专项测试开发时有一项第二天发言的构造遗漏推进裁判日期，已在当前测试修正并全部重跑；冻结策略与模拟结果未改。冻结快照保留当时测试文件，复现模拟和归档核验使用冻结策略代码，当前测试入口为项目根目录的tests。", '',
'复现与审计：`python scripts/shared_check_v20b.py`（拒绝覆盖已有结果）、`python scripts/shared_check_v20b.py --verify`。源码、配置、原始逐局结果在`results/v20b/`。', '',
'## 本轮阶段结算','',
'正式主实验212992局＋约束修复探索16384局＝229376局；另有2048局复用留出种子的解释性诊断，不是新增独立证据。当前265项测试全部通过；主实验和补充合计228局归档源码抽样完整重放一致，并未将229376局全量独立重跑。', '']
text=path.read_text()+'\n'.join(lines)
text=text.replace('为区分协议缺口与信用分作用，另做仅补共享首验一致性的v20b新种子探索，结果单列在文末；不改主实验结果、不重选概率。',
'为区分协议缺口与信用分作用，另做仅补共享首验一致性的v20b新种子探索：首日出匪率四列都增加17—50个百分点，但整局胜率不普遍改善；首日公开警察数逐局相同。它提示应先审计投票和固定续局衔接，不能单用曝光成本解释。结果单列文末，不改主实验、不重选概率。')
path.write_text(text);print('shared-check supplement appended')
