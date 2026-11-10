"""Readable information-flow audit with historical and fresh evidence separated."""
import json
from pathlib import Path
from run_continuation_audit_v36 import load_json_gz
ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'results/v36';a=json.loads((ROOT/'results/v36_diagnostics.json').read_text())
    fresh=load_json_gz(out/'fresh.json.gz');manifest=json.loads((out/'manifest.json').read_text())
    S={(s['phase'],s['profile'],s['mafia']):s for s in a['summaries']}
    lines=['# v36：真实查杀采纳、金水归票与完整续局审计（2026-11-10）','',
    '本轮没有改策略。8,192个旧留出完整重放用于解释机制，另4,096局使用新种子的对局作固定策略确认。收益损失并非只有“公开警察被刀”一条路径：首日来源候选规则、后续金水的双重正式声明、固定续局公开规则都需要分别解释。','',
    '## 1. 先读策略／指标字典','',
    '- **dead_q0 / dead_q50**：继承v35，仅在警察私知首死跳警者不是队友时，一次初始回应概率0%／50%；私人自辩优先。q不是信用或来源后验；本轮没加q网格，也没加打平衡。',
    '- **self_copy_early**：首死匪给非匪金水，第一活匪复制并错归票。**self_copy_team_relay**：两匪共同给第三匪金水，假金水可接力。延续全部既有后续策略。',
    '- **真实查杀**：离线验证报告者为警察，内容匹配该警察已知的某次真实验人；当前不含平民假跳或警察假报队友验人。可以是旧验人今天重申，不要求一定为昨夜最新一次。真假标签不交给平民。',
    '- **可执行查杀**：该报告在本轮投票之前已公开、目标仍存活。放逐后才有的遗言不许倒灌到此前投票；PK新声明只能进入PK及以后。',
    '- **跟票／采纳**：实际票与某个报告目标一致，只衡量动作一致，不证明投票者信任来源。投向另一个匪不算跟这条查杀，但不能因此称为错投。',
    '- **report**是验人声明；**accuse**是正式归票；**shortlist**是备选名单；**relay**是授权接力。一个来源可以报告T匪、却因另有已知匪正式归U；必须分别检查。',
    '- **current proposal**指今天有资格进入接收器的建议；旧事实仍在历史不等于今天继续强制执行。原目标已出局时不继续追它是正常处理。',
    '- **compare_live_conflicting_sources**：现有策略在活来源互相冲突时，优先从这些来源本人中挑目标，然后用既有排序选人。它是一项候选集策略，不是“逻辑上今天只能出来源”的定理。',
    '- **金水来源链**记录哪位来源在哪天保哪位玩家，死亡、私下反证、当天新报验与接力分别更新；不将任何死亡认证为身份。',
    '- **q(I)**可作为未来条件策略：I是行动时可用信息集，q可由少量参数或条件表控制。不追求永久固定百分比；动态形式仍需双方反制和独立留出验证。本轮没有训练动态q。','',
    '## 2. 方法、版本与证据范围','',
    f'实际完成{manifest["games"]:,}次完整模拟：**8,192次旧留出全重放＋4,096次新对局**；耗时{manifest["elapsed_seconds"]:.1f}秒。旧批来自v35已查看的207000000起2048个发牌种子，四单元共享发牌；新批210000000起1024个发牌种子，四单元共享。另8局最终smoke。',
    '所有旧对局逐一匹配原v35完整轨迹、首夜及终局，不是只抽样检查。审计器只记录合法Observation、调用原策略，不增抽随机数、不改变返回动作。新批4个单元各3个预定种子，另用原API完整重放。',
    '新批仅预设两匪条件q0→q50的最终胜率／首日出匪，共4项同时95%配对Clopper–Pearson联合界。旧审计和玩家票、重复报告均只描述，不把相关票或历史重放称为独立新证据。',
    '审计开发阶段纠正了“所有真报告都等于最新验人”的错误验证假设：原策略会合法重申旧活查杀；失败开发快照单列，不计入完成批次。另一个8局开发smoke在增加错投角色标签前完成，单列保留；角色标签始终只用于离线评价。','',
    '## 3. 首日：真实查杀究竟被怎样采纳？','',
    '| 数据 | 匪条件 | q50真实可执行查杀局 | 平民全部跟此目标 | 平民多数跟此目标 | 当日出此目标 | 这些条件局最终好人胜 |','|---|---|---:|---:|---:|---:|---:|']
    for phase in ('historical','fresh'):
        for mn in ('self_copy_early','self_copy_team_relay'):
            s=S[phase,'dead_q50',mn]
            lines.append(f'| {phase} | {mn} | {s["day1_true_alive_hit_games"]} | {s["day1_all_civ_follow"]} | {s["day1_majority_civ_follow"]} | {s["day1_hit_target_exiled"]} | {s["day1_hit_terminal_wins"]} |')
    lines+=['',
    '两个匪条件共享Nature和局部抽样，因此同为263／117局不是两次独立身份样本。多数是严格超过半数，跟票目标出局还可能由警队票促成。上述是真查杀条件下的描述，不代表未知来源在实战中的可信度。','',
    '| 数据／匪条件 | 跟该真查杀的平民票 | 改投另一个匪 | 改投真警 | 其他目标 |','|---|---:|---:|---:|---:|']
    for phase in ('historical','fresh'):
        for mn in ('self_copy_early','self_copy_team_relay'):
            s=S[phase,'dead_q50',mn];other=s['day1_other_vote_roles']
            follow=s['day1_vote_reasons'].get('aligned_with_hit',0)
            lines.append(f'| {phase}/{mn} | {follow} | {other.get("mafia",0)} | {other.get("police",0)} | {sum(v for k,v in other.items() if k not in ("mafia","police"))} |')
    lines+=['',
    '**主要瓶颈：**非匪金水复制条件的旧批2104张相关平民票中，279跟原查杀、937投另一个匪、888投真警。其余1825票均进入“比较活来源”分支。新批936票中127跟查杀、422投别匪、387投真警，呈现相同动作结构。不能把所有未跟票算错，但也不能把这些损失全部归于晚上的暴露。',
    '两匪保匪条件还受到“先考虑保金水的来源、再考虑其金水”的保护顺序影响；它可能把票引向另一个匪，也可能与来源排序共同造成错投。平民不知道谁是真警，不能用离线标签直接修成“永远听真警”。',
    '来源间不能都真，只能证明存在不相容性；现有接收器进一步把票优先限制在来源本人，这一步是策略假设。排序还继承未完整覆盖自刀的首刀位置先验，本轮没有分别消融这两个因素，不能声称已经找出唯一原因。','',
    '## 4. 同样公开查杀后的后续采纳、旧信息与新金水','',
    '| 数据／条件／q | 第二日起真查杀轮次 | 合法相关平民票 | 跟该查杀票 | 原查杀目标仍活的后续轮次 | 原报告历史丢失 | 当天重申旧活查杀次数 |','|---|---:|---:|---:|---:|---:|---:|']
    for phase in ('historical','fresh'):
        for mn in ('self_copy_early','self_copy_team_relay'):
            s=S[phase,'dead_q50',mn]
            lines.append(f'| {phase}/{mn}/q50 | {s["later_hit_episodes"]} | {s["later_eligible_civilian_ballots"]} | {s["later_follow_civilian_ballots"]} | {s["old_hit_alive_rounds"]} | {s["old_hit_history_missing"]} | {s["repeated_old_true_hit_reports"]} |')
    lines+=['',
    '这些是日／目标合并后的首轮事件数，仍在同局相关，不能当独立样本。首个查杀目标已死的大量轮次不再追它是正常现象；目标仍活时，历史没有被删除。旧来源今天没有提案，也不等于信息被抹掉：活警可能重新报告同一旧验人，或明确改归另一已知匪。',
    '查杀跟票在第二日起通常更高，但不等于来源被死亡认证。来源入选、当前建议与实际票仍由原规则决定；本轮未恢复死一方轮出另一方。','',
    '## 5. 金水的两套正式动作与固定续局','',
    '| 数据／匪条件 | 金水同一发言slot同时accuse＋relay | 两目标不同 | 不同时最终本人票跟relay | 第二日起真警报金水次数 | 其中无活私人已知匪 |','|---|---:|---:|---:|---:|---:|']
    for phase in ('historical','fresh'):
        for mn in ('self_copy_early','self_copy_team_relay'):
            s=S[phase,'dead_q50',mn]
            lines.append(f'| {phase}/{mn} | {s["civil_dual_calls"]} | {s["civil_dual_disagreements"]} | {s["dual_disagreement_actual_matches_relay"]} | {s["day2plus_good_reports"]} | {s["good_report_no_live_private_bad"]} |')
    lines+=['',
    '**这里确有尚未统一的行动接口：**金水普通accuse沿用旧座位排序，relay则根据授权名单和接收器另算；两者可在同一个信息时点说出不同目标。被计入的不一致样本中，本人实际票全部跟relay。因而不能只读accuse就说其投了真警；但这类冲突声明将来会污染票型／来源学习，应该先明确是一项还是两项正式动作。',
    '例如旧局207000002第三日，11号警察报4号金水并给12、13号内推；4号同slot普通accuse指11号，relay却归12号，最后实际票投12号。没有新消息夹在这两个输出之间，是两个旧选择器叠加，不能用“听完后续发言合法改票”解释。如果一个动作想表达怀疑、另一个想表达最终归票，需要明确区分；当前两个字段都被当作正式目标。',
    '**续局也受固定公开规则约束：**第二日起既有规则自动安排一名活警报验，即使当日没有活匪跳警。上表全部报金水事件所在日都没有活匪普通轮跳警；其中很多时点也没有仍活的私人已知匪。因此当前q比较是在“首日可藏、后续大体自动公开”的续局下完成，并非已经优化的长期跳藏。',
    '这不是已经证明每次报金水都不好，也不是全部损失的因果分解；但它限制了“第一日应该选多大q”的解释。本轮只审计，没有改这些续局行为。','',
    '## 6. 新鲜确认：原终局差异是否稳定？','',
    '| 新批条件，各1024局 | q0好人胜 | q50好人胜 | 增量 [同时95%区间，百分点] | q0→q50首日出匪 |','|---|---:|---:|---:|---:|']
    for c in fresh['contrasts']:
        v=c['win'];x,y=v['counts'];lo,hi=v['precision']['ci_simultaneous'];e=c['day1_mafia_exile']['counts']
        lines.append(f'| {c["mafia"]} | {x} ({x/1024:.2%}) | {y} ({y/1024:.2%}) | {(y-x)/1024*100:+.2f} [{lo*100:+.2f}, {hi*100:+.2f}] | {e[0]}→{e[1]} |')
    lines+=['',
    '新批没有确认终局差异的稳定方向：复制非匪金水仍为下降点估计，但区间含0；保匪接力净差0，其中94局好人由输变赢、94局由赢变输，不能说回应无效。首日出匪提升仍获同时区间支持。不要将v35旧负增益说成已在新批精确复现，也不继续追加种子追显著性。',
    f'既有v35中q50已实际回应的{a["q50_q100_existing_hash_matches"]}对q50／q100记录完整轨迹一致，其中{a["q50_q100_true_hit_matches"]}对有可执行真查杀。这些跨匪条件共享种子，只是旧哈希一致性检查，没有重跑全部q100。说明相同已实现发言下，两者当前后续行为相同；现有平民尚未根据不同公开q重学来源似然。','',
    '## 7. 验证、案例和复现','',
    '- 实际测试：python -m pytest tests -q，410项通过（63.95秒），含9项新时点／旧事实／影子执行测试。',
    f'- 所有8192历史轨迹完整匹配v35；4096新模拟中另{a["fresh_baseline_replays"]}次原API直接重放。{a["ballot_checks"]}次好人票约束核验、{a["interval_crosschecks"]}项独立区间交叉检查；另{a["case_replays"]}条事后说明案例重放、{a["numeric_credit_guard_replays"]}次完整样本验证数值信用助手未被调用。未独立重跑全部新批。',
    '- 原配置虽继承source_credit=True字段，当前routing=evidence；两个信用数值助手在所查完整样本中未调用，审计未启用新信用权重。不要把历史配置字段直接当成当前信用分在决定投票。',
    '- 冻结源／协议／输入哈希见results/v36/freeze.json及source；完整压缩结果historical.json.gz／fresh.json.gz；统计和细节results/v36_diagnostics.json；核验results/v36_validation.json。',
    '- 命令：python scripts/run_continuation_audit_v36.py --smoke；python scripts/run_continuation_audit_v36.py；python scripts/analyze_continuation_audit_v36.py；python scripts/build_continuation_audit_report_v36.py。输出目录须为新目录，防止覆盖。',
    '- [逐局阅读版](continuation_audit_cases_v36.md)给出信息、公开动作、当日票及全部夜刀／验人的顺序。角色仅供离线复盘；说明类型在读结果后选取，不作确认性检验。','',
    '## 8. 对动态q和下一步的含义','',
    '你提出的动态q是合适的后续策略表达：按合法信息集设q(I)，条件或对手回应改变后允许概率改变；不必追求一个永远正确的小数。本轮没有训练该函数，也没有证据让某个固定q直接成为均衡。',
    '下一步建议优先只审计／消融“活来源冲突为何把查杀目标挤出候选集”，保持私人反证、PK和来源真假不认证。金水同slot双正式目标也需统一语义，尤其在重新引入票型学习前；固定day2以后自动公开另作独立机制对照。不要把这几项同时修好后仅靠胜率上涨解释原因。',
    '打平衡保留小型条件候选，本轮未新增相关实验；信用、更多q点和更大策略池不推进。所有结果仍是固定代理的受限策略评估，无新均衡／GTO结论。','']
    (ROOT/'docs/continuation_audit_results_v36.md').write_text('\n'.join(lines))
    cases=['# v36：查杀、金水和续局的逐局审计','','以下角色只供读者复盘；所有策略只读自身Observation。案例来自既有／新批内首例，不增加独立验收。座位从1开始。','']
    for e in a['cases']:
        cases += [f'## {e["phase"]}/{e["profile"]}/{e["mafia"]}，seed={e["seed"]}（{e["label"]}）','', '最终'+('好人胜。' if e['win'] else '匪胜。'),'']
        for t in e['transcript']:
            p=t['payload'];event=t['event'];day=t['day']
            if event in ('message','speech_extension','last_words_extension','final_call') and p['kind'] in {'report','accuse','relay','shortlist'}:
                target='—' if p['target'] is None else str(p['target']+1)
                act={'report':'报查杀' if p['verdict'] else '报金水','accuse':'正式归票','relay':'接力归票','shortlist':'内推'}[p['kind']]
                extra='，名单'+','.join(str(x+1) for x in p['targets']) if p['kind']=='shortlist' else ''
                cases.append(f'- 第{day}日：{p["speaker"]+1}号（实际{e["roles_evaluation_only"][p["speaker"]]}，{p["context"]}）{act}{target}{extra}。')
            if event=='day_death':cases.append(f'- 第{day}日放逐{p["victim"]+1}号（实际{e["roles_evaluation_only"][p["victim"]]}）。')
        cases += ['','每夜实际动作（包括夜间直接终局）：','']
        checks={x['day']:x['target'] for x in e['inspections']}
        for night in e['nights']:
            target=night['target'];check=checks[night['day']]
            cases.append(f'- 第{night["day"]}夜：刀{target+1}号（{e["roles_evaluation_only"][target]}）；验{check+1}号（{e["roles_evaluation_only"][check]}）。')
        cases += ['','真实可执行查杀的首轮平民票：','']
        for h in e['hits']:
            if h['round']=='first':
                cases.append(f'- 第{h["day"]}日查杀{h["target"]+1}号：{h["follow"]}/{h["eligible"]}张合法平民票跟该目标；其他票实际身份{h["other_vote_roles"]}。')
        cases += ['','同一金水发言的双目标（若有）：','']
        for z in e['duals']:
            if z['disagreement']:
                actual='弃票' if z['actual_vote'] is None else str(z['actual_vote']+1)+'号'
                cases.append(f'- 第{z["day"]}日{z["speaker"]+1}号：普通accuse归{z["accuse"]+1}号，relay归{z["relay"]+1}号；最终本人首轮投{actual}。')
        cases.append('')
    (ROOT/'docs/continuation_audit_cases_v36.md').write_text('\n'.join(cases).rstrip()+'\n')
    print('reports written')

if __name__=='__main__':main()
