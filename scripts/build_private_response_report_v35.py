"""Explain a private-condition probability experiment without GTO claims."""
import json
from pathlib import Path
from analyze_private_response_v35 import read_phase
ROOT=Path(__file__).resolve().parents[1]
NAMES={'late_old':'普通后置刀＋远位假查杀','late_copy':'普通后置刀＋复制金水','late_quiet':'普通后置刀＋首日静默',
'self_quiet':'自刀＋活匪静默','self_copy_early':'自刀＋活匪复制非匪金水','self_copy_team_pass':'两匪保第三匪，B不接力','self_copy_team_relay':'两匪保第三匪，B假接力'}


def main():
 out=ROOT/'results/v35';f=json.loads((out/'freeze.json').read_text());cfg=f['config'];data=read_phase(out,'holdout');a=json.loads((ROOT/'results/v35_diagnostics.json').read_text());manifest=json.loads((out/'manifest.json').read_text())
 S={(x['profile'],x['mafia']):x for x in a['summaries'] if x['phase']=='holdout'};profiles=[x['name'] for x in cfg['profiles']]
 lines=['# v35：明知死者不在警队时的跳藏概率（2026-11-09）','',
 '这轮只调整警察私下确认首死跳警者不是队友时的行动概率。真死警分支仍用原克制规则，平民接收不到警队身份标签。完整模拟至终局，跳藏权衡持续保留；打平衡只保留一条窄对照，不作为主要研究线扩展。','',
 '## 1. 策略／参数字典与q50解释','',
 '- **旧q50（legacy）**：原代理只在某些“首位警察已听到活假警、死者不是队友、假查杀没涉及警队”等局面才抽50%回应；没有活假警时还可能主动报验。首位警察选择隐藏后，后面警察受旧限制影响，未必还有一次回应选择。因此不能把旧q50理解为“所有情况下警方五五开”。',
 '- **新dead_q0 / dead_q50 / dead_q100**：仅首日，首死者遗言跳警／报验人，警察凭自己的警队名单知道死者不是队友。第一名有普通轮机会、尚无活警代表的警察，分别以0%／50%／100%概率报告真实验人，不要求活匪再跳一次。死者的假声明本身就是回应依据。这个概率不是信用分、不是身份概率，也不是计算出的最优混合。',
 '- **一次抽样如何执行**：该警察用自己原有的该日发言随机流抽u∈[0,1)，u<q时回应。后面警察知道哪些已发言者是队友，看到其普通轮已发生就不会重复抽样。没有额外秘密相关信号。例如q50下u=0.3会回应，u=0.8会隐藏；不会让四警各抽一次使总体回应率升到93.75%。',
 '- **私人防御优先**：本人此前被外部来源查杀时仍可真实回应；已有活警队友公开则不新增第二警。因而q0不保证整日零回应，q50实际公开率也未必正好50%。概率作用对象是一次非强制的初始决定。隐藏时仍保留私人验人、已知匪和正常实际投票，并非放弃私人信息。',
 '- **分支之外**：首死者是警队队友、没有跳警声明、第二日起、PK发言，全部继承v34 self；新q不改变它们。真警真实报告、平民不假跳仍是当前逻辑前提。',
 '- **legacy**：v34 self警方、original平民接收、原q50，为兼容控制。**dead_q50_balance**：新q50警方不变，仅把平民换成v34 first_live：首日优先处理第一活报告者，保留私人反证、金水保护、PK限制，次日起恢复original。只作小型对照，不学习打平衡概率。',
 '- **original接收器**：沿用v31 aligned，保留真假金水已有接力和正常来源处理；不加额外数值信用。**conditional_gold**保留历史实现但暂不继续投入实验：v34无终局增量，优先级并非已被证明无用或永久淘汰。',
 '- 匪方案继承v34，包括假金水能接力／能不接力。普通刀固定safe_late；未加伪装刀或新反制训练。七列数量不是匪方混合频率；不得把条件自刀列胜率与现实总体好人胜率混为一谈。','',
 '| 匪方案代码 | 行动说明 |','|---|---|']
 for name,meaning in NAMES.items():lines.append(f'| {name} | {meaning} |')
 lines+=['','## 2. 方法与冻结','',
 f'5好人方案×7匪计划=35单元，每单元训练诊断128、全新留出2048；共 **{manifest["games"]:,}局完整终局模拟**，耗时{manifest["elapsed_seconds"]:.1f}秒。发牌种子2,176个跨条件配对，不是76,160个独立发牌。训练206000000起、验收207000000起、smoke208000000起，另70局smoke。',
 '所有q、分支、接收器、刀法及种子在训练前冻结；训练不拟合规则，不择优q，不据验收再换种子。原始数据从初次运行即gzip无损保存。新模型尚未让平民按警方q重新学习信任，也没有让匪重训最佳回应。',
 '预设比较每匪条件legacy→dead_q50、dead_q0→dead_q50、dead_q50→dead_q100、dead_q50→dead_q50_balance，共28比较；终局好人胜率和首日出匪共56项同时95%区间，配对翻转Clopper–Pearson加联合界。覆盖、次夜死亡及半批次方向只描述，不追加确认性比较。本批结果一旦公开，就成为已查看的研究证据；下一版若据此选择策略需再用新的独立留出。',
 '所有普通刀局新私人分支均不触发，前三个新q的完整轨迹与legacy逐局相同。这包括真死警局，也包括首死平民局；因此本轮没有通过改变真死警行为获得增量。平衡对照会改变该分支的平民票，应另看。','',
 '## 3. 完整终局好人胜率','',
 '| 匪条件 | legacy旧规则 | 新q0 | 新q50 | 新q100 | 新q50＋首日平衡 |','|---|---:|---:|---:|---:|---:|']
 for mn in NAMES:
  vals=[f'{S[p,mn]["wins"]}/2048 ({S[p,mn]["wins"]/2048:.2%})' for p in profiles]
  lines.append(f'| {mn} | '+' | '.join(vals)+' |')
 lines+=['','全部预设差异，单位百分点；区间含0时不能确认方向：','',
 '| 匪条件 | 比较 | 终局增量 [同时95%区间] | 首日出匪增量 [同时95%区间] |','|---|---|---:|---:|']
 for c in data['contrasts']:
  aa,mn=c['control'];bb,_=c['treatment'];vals=[]
  for metric in ('win','day1_mafia_exile'):
   v=c[metric];x,y=v['counts'];lo,hi=v['precision']['ci_simultaneous'];vals.append(f'{(y-x)/2048*100:+.2f} [{lo*100:+.2f}, {hi*100:+.2f}]')
  lines.append(f'| {mn} | {aa}→{bb} | {vals[0]} | {vals[1]} |')
 lines+=['','**本轮结论：**新q50相对旧规则没有任何终局差异获得56项同时区间的方向支持，不能称为稳定提升。自刀后活匪复制非匪金水时，新q0→新q50从755→650胜，即36.87%→31.74%，下降5.13百分点，同时区间[−9.38,−0.83]。其余主要q增量的终局区间包含0。新q100会更多拆掉假金水资格，但尚未证明因此普遍提高最终胜率。\n\n这些是完整终局收益，不凭首日多出匪就判定更优。即便某条件q100点估计最高，也没有证明对所有反制最优；若收益随q上升，当前证据也不要求人为选择混合。最优混合需要双方策略与最佳回应分析，不能由三个点自动插值得出。','',
 '## 4. 私人条件覆盖与假金水资格','',
 '下面每列分别表示完整对局数量、是否有一次初始抽样、该抽样是否报告、之后被查杀才报告；“合格假金水”按v34公开资格门离线核查，未在行动器开启额外金水优先。','',
 '| 匪条件 | 新q | 私人分支适用局 | 一次抽样局 | 抽样后报告局 | 后续本人防御报告局 | 最终有活警报告局 | 假B仍通过公开资格局 |','|---|---|---:|---:|---:|---:|---:|---:|']
 for mn in NAMES:
  for p in ('dead_q0','dead_q50','dead_q100'):
   x=S[p,mn];lines.append(f'| {mn} | {p} | {x["private_scope"]} | {x["draw_games"]} | {x["first_draw_reports"]} | {x["self_defense_reports"]} | {x["live_report_games"]} | {x["fake_gold_eligible"]} |')
 lines+=['','**q实际作用的例子：**自刀且活匪静默时，legacy虽含旧q50，却2048局全部有活警报告，因为没有活假警触发旧随机分支，原先的主动报验路径直接生效。新q50在明确私人条件下抽样，2048次抽样有1007次报告（49.17%）；新q0为0次、新q100为2048次。故不能把旧q50和新q50视为同一个概率干预。\n\n两匪保假B且假B接力时，合格假B随q0／q50／q100为2048／1041／0局。这说明公开假共识确实被警方回应打破，却没有自动转成稳定终局收益；当前民方仍按冻结接收器行动，没有按新q重新估计来源。\n\n首死者在警队外且跳警，是警察私下确定的信息；平民不能直接读到“自刀”标签。q改变公开报告、归票和以后刀路，表中资格变化是策略造成的信息变化，不是身份认证。假金水为匪只是离线评估，不作为规则输入。','',
 '## 5. 暴露与完整续局','',
 '| 匪条件 | 方案 | 首日出匪率 | 首日出警率 | 活警公开数／局 | 次夜死警率 |','|---|---|---:|---:|---:|---:|']
 for mn in NAMES:
  if mn.startswith('late_'):continue
  for p in ('legacy','dead_q0','dead_q50','dead_q100'):
   x=S[p,mn];lines.append(f'| {mn} | {p} | {x["exiles"]/2048:.2%} | {x["police_exiles"]/2048:.2%} | {x["public_cops"]:.3f} | {x["night2_cop_death"]:.2%} |')
 lines+=['','**同发牌的实际例子（seed=207000002，自刀复制非匪金水）：**q0下，真警首日没有公开，白天错出16号平民，但次夜匪刀到9号平民，随后三天出了剩余三个匪，好人最终胜。新q50的抽样选择回应：2号真警公开查杀6号，首日正确放逐6号匪；但第二夜2号就被刀，后面出现两次错出平民，最终警队先被杀完。这个例子展示短期进步和长期损失如何并存，也包含后续归票差异，不能把全部损失归因于暴露一个因素。\n\n暴露成本没有从模型中删除：所有夜晚和投票仍运行到终局。过程指标不能单独识别暴露的因果中介，策略改变也可能影响当日错误归票及后续协调。次夜统计包含夜间直接终局，不等于“已公开警察被刀的条件概率”。','',
 '## 6. 打平衡的取舍','',
 '**本轮窄对照：**新q50条件下，first_live在自刀复制非匪金水650→884胜（+11.43百分点，同时区间[+6.85,+15.91]）；两匪保第三匪545→731胜（+9.08，[+3.42,+14.67]，不接力／接力两列本批终局数组相同，应视为重复覆盖而非两次独立发现）。但自刀活匪静默386→288胜（−4.79，[−7.54,−1.98]），普通刀复制金水477→436胜（−2.00，[−3.61,−0.37]）。因此继续保留为小型条件候选，不设统一比例，不单凭自刀列挑策略。\n\n根据v34结果，first_live不升级默认规则；本轮仅在新q50下保留一个对照，避免继续大篇幅扩展。收益变号就保留为局部候选，若后续广泛负收益可降低研究优先级。当前未训练平衡混合权重，不能把它叫均衡组成。',
 'conditional_gold暂不追加实验，并不删除旧证据；其优先接收与原归票重复的问题需要有新信息收益假设后再重启。主接收器仍维持原信息更新。','',
 '## 7. 验证与复现','',
 '- 本次实际测试命令 `python -m pytest tests -q`：401项通过（50.03秒），含11项新测试。',
 f'- {a["replays"]}条预定完整重放、{a["baseline_replays"]}次v34兼容、{a["ballots"]}次样本投票约束、{a["next_day_checks"]}次第二日起正常接收核对、{a["logic_prefixes"]}个身份支持前缀、{a["interval_crosschecks"]}项独立区间核验；另{a["case_replays"]}个验收内事后案例重放。没有独立重跑全部正式游戏。',
 f'- {a["ordinary_trace_equalities"]}对普通刀新q／legacy轨迹完全相同（含训练和留出，三个新q共享比较）；所有局至多一次q抽样，普通轮至多一活警公开，次日起无风险优先残留。',
 '- 命令：`python scripts/run_private_response_v35.py --smoke`、`python scripts/run_private_response_v35.py`、`python scripts/analyze_private_response_v35.py`、`python scripts/build_private_response_report_v35.py`。运行器只接受新输出目录。',
 '- 冻结源码、参数、协议在results/v35/source及freeze.json，原始逐局结果train.json.gz／holdout.json.gz，覆盖／案例results/v35_diagnostics.json，验证results/v35_validation.json。',
 '- [逐局阅读版](private_response_cases_v35.md)展示原规则和新q的胜负变化。案例按事后解释类型选已有验收内首例，不是额外独立确认。所有角色标签仅供读者复盘。','',
 '## 8. 下一步的判断边界','',
 '目前保留私人条件与q0／q50／q100三个冻结候选，尚无依据将q100设为统一默认；legacy也保留。下一步建议先审计同样公开真实查杀后，平民当日及后续如何采纳、金水来源如何更新，找出为什么拆掉假共识仍没转成优势；不马上扩大q网格或继续扩展打平衡。\n\n先按终局和覆盖决定该私人条件的回应是否值得保留；普通刀分支完全不变，不能说整体游戏已达到均衡。下一步若研究条件混合，应明确哪一个私人分支、哪一个局部随机源，以及匪方知道该概率后可作何回应。平民信任模型重训需要另外冻结来源生成与概率，不能把本批验收再当最终验证。',
 '首死真警分支仍需保留跳藏权衡；信用、复杂来源票型、跨日委托、公开怀疑、金水假跳挡刀、遗言制度、白天报匪继续独立待办。','']
 (ROOT/'docs/private_response_results_v35.md').write_text('\n'.join(lines))
 case=['# v35：私人条件回应的具体续局','', '验收内按事后类型取首例，用于解释，不是新增独立验证。座位从1开始。','']
 for e in a['examples']:
  case += [f'## {e["label"]}：{e["profile"]}/{e["mafia"]}，seed={e["seed"]}','', '最终'+('好人胜。' if e['win'] else '匪胜。'),'']
  for z in e['response_audit']:
   if z['draw'] is not None:case.append(f'- {z["player"]+1}号警察首次局部抽样u={z["draw"]:.4f}，q={z["q"]}，'+('真实回应。' if z['reported'] else '隐藏。'))
   elif z['reported']:case.append(f'- {z["player"]+1}号警察因本人被查杀防御回应。')
  for t in e['transcript']:
   p=t['payload'];event=t['event']
   if t['day']==1 and event in {'message','speech_extension','last_words_extension','final_call'} and p['kind'] in {'report','accuse','relay'}:
    tar='—' if p['target'] is None else str(p['target']+1);act={'report':'报查杀' if p['verdict'] else '报金水','accuse':'正式归票','relay':'接力归票'}[p['kind']]
    case.append(f'- {p["speaker"]+1}号（实际{e["roles_evaluation_only"][p["speaker"]]}，{p["context"]}）{act}{tar}。')
   if event=='day_death':case.append(f'- 第{t["day"]}日放逐{p["victim"]+1}号（实际{e["roles_evaluation_only"][p["victim"]]}）。')
  recorded={t['day'] for t in e['transcript'] if t['event']=='night_death'}
  for night in e['nights']:
   p=night['target'];case.append(f'- 第{night["day"]}夜刀{p+1}号（实际{e["roles_evaluation_only"][p]}）'+('，夜间直接终局。' if night['day'] not in recorded else '。'))
  case.append('')
 (ROOT/'docs/private_response_cases_v35.md').write_text('\n'.join(case))
 print('reports written')

if __name__=='__main__':main()
