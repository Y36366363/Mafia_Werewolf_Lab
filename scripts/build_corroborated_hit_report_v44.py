"""Verify v44 archives and render results and examples."""
from collections import Counter
import gzip
import json
from pathlib import Path

from run_corroborated_hit_v44 import ROOT, digest, load_spec, play, save_gzip, save_json
from run_succession_copy_v43 import play as play_v43


OUT = ROOT/'results/v44'


def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    freeze = json.loads((folder/'freeze.json').read_text())
    for path,sha in manifest['files'].items():
        assert digest(folder/path)==sha
    for rel,sha in freeze['assets'].items():
        assert digest(ROOT/rel)==sha
        if folder==OUT:
            assert digest(folder/'source'/rel)==sha
    for rel,sha in freeze['parents'].items():
        parent = ROOT/rel
        assert digest(parent)==sha
        for name,h in json.loads(parent.read_text())['assets'].items():
            assert digest(ROOT/name)==digest(parent.parent/'source'/name)==h
    return manifest,freeze


def read_gzip(path):
    with gzip.open(path) as stream:
        return json.load(stream)


M,F = verify(OUT)
verify(ROOT/'results/v44_smoke')
S = json.loads((OUT/'summary.json').read_text())
D = read_gzip(OUT/'pairs.json.gz')
CASES = read_gzip(OUT/'cases.json.gz')
N = S['n']
SPEC = load_spec(F['config'])
old_case = read_gzip(ROOT/'results/v43/cases.json.gz')['lost_unique_police']['copy_agreement']
assert CASES['v43_replay']['copy_base']['trace'] == old_case['trace']
for arm,copy in [('copy_base',True),('old_base',False)]:
    for i in (0,N//2,N-1):
        row = D[arm][i]
        assert play_v43(SPEC,'1/2',(copy,True),row['seed'])['trace']==row['trace']

flips = [(a,b) for a,b in zip(D['copy_base'],D['copy_coordinate'],strict=True)
         if a['win'] and not b['win']]
ambiguous_flips = sum(a['exile_roles'].get('2') == b['exile_roles'].get('2') == 'mafia'
                      and a['exile']['2'] != b['exile']['2']
                      and a['exile_roles'].get('3') == 'mafia' and b['exile_roles'].get('3') == 'civilian'
                      for a,b in flips)
if flips:
    CASES['coordination_loss'] = {}
    for arm,row in zip(('copy_base','copy_coordinate'),flips[0],strict=True):
        detail = play(SPEC,F['config']['q'],F['config']['arms'][arm],row['seed'],True)
        assert detail['trace']==row['trace']
        CASES['coordination_loss'][arm] = detail
    save_gzip(ROOT/'results/v44_coordination_loss_case.json.gz',CASES['coordination_loss'])

LABELS = {'copy_base':'复制基线','copy_shared':'复制＋共同查杀',
          'copy_coordinate':'复制＋警队协调','copy_both':'复制＋两项',
          'old_base':'旧报告基线','old_shared':'旧报告＋共同查杀'}
ROLES = {'police':'警','mafia':'匪','civilian':'民','none':'无人'}


def share(num,den=N):
    return '无机会' if not den else f'{num:,}/{den:,}（{100*num/den:.2f}%）'


def seat(p):
    return '弃票' if p is None else f'{int(p)+1}号'


def report():
    lines = [
        '# v44 共同查杀优先与警队归票协调', '',
        '2026-11-18。4 警 4 匪 8 民。', '',
        '## 策略与指标字典', '',
        '| 名称 | 实际动作 |', '|---|---|',
        '| 基线 | 继承 v43 的公开唯一一致优先。若两名合资格来源都和遗言匹配，回原接收器，合并或比较各来源的正式归票。 |',
        '| 复制／旧报告 | 同在既有接续发言槽。复制对手可复述当夜遗言的验人，含查杀队友。旧报告对手继续报首日旧查杀。两者仍正式归旧目标。 |',
        '| 共同查杀 | 第二日起，同一观察中至少两名可用活跳警者当天的最新普通验人一致查杀某人，且没有可用来源给此人报过金水，平民优先投他。私人反证、本人身份、合法 PK 名单和金水保护优先。遗言独自不凑两名活来源。 |',
        '| 警队协调 | 第二日起在已有归票窗口，警察私知至少两名合法活匪时，对每个候选模拟正式归票后能吸引多少平民式投票。最高估计优先，同分维持旧目标，再以发言顺序定夺。保留真实验人和原有发言预算。 |',
        '| 预估票数 | 整数，一次发言时重新算，从 0 到尚不知身份的在场座位数。把这些座位逐一视作假设平民，使用当时的公开信息和待发布归票。排除警察队友和私知匪，无法剔除未识别的匪。估计值与实际票分开。 |',
        '| 跟真警归票 | 该合法目标与平民的实际票相同。真警仅供赛后评估，改归后目标本身也会变。共同查杀可能和某个形式上的真警归票不同。 |',
        '| 共同查杀票 | 通过共同证据和私人约束的一张投票机会。出现多次可能共用同一来源或同一对局，非独立发牌。 |',
        '| q=1/2 | 原有首日私人条件的 50% 回应概率，范围 0–1。没有累计信用变化。 |', '',
        '警察的正式归票和验人是不同消息。协调组只替换一条已有正式归票的对象，继续沿用警队在该目标合法且私下已知是匪时的一致出票。平民和警队的预测均不读取隐藏角色。共同查杀规则在当前两方都承认同一目标的语义下优先协调出该人。由于可能两名活来源都在说谎，它提供可执行的优先级，真正的身份确定仍要求至少一个来源诚实。', '',
        '## 上一轮的 413 局与 15 号例子', '',
        'v43 每组 2,048 局中有 413 局接续者确能复制另一份验人，另外 1,635 局没有改报机会。复制条件下，413 局开关唯一一致优先都是 773/1,571 张跟真警、103 局第二日出匪、0 胜。其余 1,635 局的跟票 9,363→10,548，第二日出匪 1,383→1,576，终局 79→90。整批提高来自这部分。', '',
        '旧接收器为每个来源先取正式归票。只有找不到合法正式归票才取查杀。因此 4 号报 16 匪并归 16，6 号也报 16 匪却归 15，程序只看到 16 和 15 两份执行建议；唯一一致层发现两个匹配者便退回原合并，发言顺序选了 15。共同验人记录还在公开历史里，却没有独立的共同查杀优先级。', '',
        '修复把两项判断分开。有两份可用报告一致时，优先处理共同被查杀者。警队改归另一私知匪的试验仍有意义，尤其当场上还没形成共同查杀、多个目标都已被警方确认时。', '',
        '## 实验方法与留出结果', '',
        f'全新种子 227000000–227002047，{N:,} 组、{M["games"]:,} 局。另 24 局冒烟。六组首日轨迹逐局相同。在原警队规则下，开关共同查杀的对局第二日首轮前公开轨迹逐局相同。'
        '警队协调会改变公开目标，双开组警察预计平民使用双开组接收器。五项配对终局差用双向二项边际精确区间合成同时 95% 区间，单侧边际尾概率 0.0025。', '',
        '| 策略 | 第二日出匪／警／民／无人 | 第二日首轮跟真警归票 | 终局好人胜 |',
        '|---|---:|---:|---:|',
    ]
    for arm,row in S['arms'].items():
        d = row['counts']
        ex = '/'.join(f"{row['day2'].get(r,0):,}" for r in ('mafia','police','civilian','none'))
        lines.append(f"| {LABELS[arm]} | {ex} | {share(d.get('day2_follows',0),d.get('day2_opportunities',0))} | {share(row['wins'])} |")
    lines += ['', '| 预定终局比较 | 负转胜／胜转负 | 差值与 95% 同时区间（百分点） | 第二日投前前缀变化 |',
              '|---|---:|---:|---:|']
    for key,row in S['contrasts'].items():
        a,b = key.split('_to_')
        lo,hi = row['precision']['ci_simultaneous']
        delta = 100*(row['gains']-row['losses'])/N
        lines.append(f"| {LABELS[a]} → {LABELS[b]} | {row['gains']}／{row['losses']} | "
                     f"{delta:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {row['changed_prefixes']} |")
    lines += ['', '| 策略 | 第二日共同查杀机会（指匪／警／民） | 第二日实际因共同证据改票 | 全续局警方可协调归票槽 | 实际改归（第二日／全续局） | 预估支持累计增票 | 全续局核验警票 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for arm,row in S['arms'].items():
        d = row['counts']
        ex = '／'.join(f"{d.get('day2_common_'+r,0):,}" for r in ('mafia','police','civilian'))
        moves = sum(d.get('day2_actual_change_'+r,0) for r in ROLES)
        lines.append(f"| {LABELS[arm]} | {ex} | {moves:,} | {d['eligible_calls']:,} | "
                     f"{d.get('day2_changed_calls',0):,}／{d.get('changed_calls',0):,} | {d.get('projected_gain',0):,} | {d.get('police_alignment_checks',0):,} |")
    shared = S['contrasts']['copy_base_to_copy_shared']
    turns = shared['day2_transitions']
    selected = S['arms']['copy_coordinate']['counts']
    copy_delta = S['arms']['copy_coordinate']['day2']['mafia']-S['arms']['copy_base']['day2']['mafia']
    lines += ['', f"复制对手下，开共同查杀后第二日有 {turns.get('civilian_to_mafia',0)} 局由出民改为出匪，"
              f"{turns.get('police_to_mafia',0)} 局由出警改为出匪，终局多 {shared['gains']-shared['losses']} 胜。"
              '终局区间跨零。旧报告对手下本批未触发共同查杀，整体轨迹相同。', '',
              f"单开警队协调，第二日多出匪 {copy_delta} 局，全续局正式改归 {selected.get('changed_calls',0)} 次。"
              f"这批 {len(flips)} 场由胜转负中，{ambiguous_flips} 场是第二天换出另一名匪，第三天才从出匪转成出民。"
              '这是选人时的目标局限。估计当日能聚多少票，没有衡量放逐谁会改变活匪后续能做什么。'
              '本轮终局证据还不足以决定采用该协调规则。', '',
              '预计票数的合计表示在每个当时的前缀里，实际公布对象相对旧对象的估计差。警方最后出票在该目标合法、仍为私知匪时逐票核对。终局效果以留出为准。', '',
              '## 概率信用与研究边界', '',
              '30∶70 是你提到的示例，本轮未把它写成参数。后续可以分别确定资格门槛、分差到跟随概率的映射，以及个人独立抽样产生的分票。概率是行动选择概率，不能直接当作某人是真警的概率。', '',
              f"专项 2 项与全库 445 项测试均通过。实际运行 `python -m pytest tests/test_corroborated_hit_v44.py -q`、`python -m pytest tests -q`、`python scripts/run_corroborated_hit_v44.py --smoke`、`python scripts/run_corroborated_hit_v44.py` 和 `python scripts/build_corroborated_hit_report_v44.py`。"
              f"正式耗时 {M['elapsed']:.1f} 秒，{M['sample_replays']} 次当批抽样重放、{M['case_replays']} 次详细案例重放（含旧例重放）、2 次协调失利例详细重放、6 次继承 v43 接口重放。"
              '同时核验了冻结源码、原始数据哈希与十项统计区间边际。固定两种接续对手，尚未加入两匪串联假报同一查杀的专门反制。', '',
              '[逐局案例](corroborated_hit_cases_v44.md)']
    return '\n'.join(lines)+'\n'


def show_cases():
    lines = ['# v44 通俗逐局解释', '', '座位从 1 开始，角色仅用于赛后说明。']
    for name, rows in CASES.items():
        title = {'public_hit':'首次改变第二日放逐的共同查杀', 'coordination':'首次改变第二日归票的警队协调',
                 'v43_replay':'15 号与 16 号历史局的成对重放',
                 'coordination_loss':'第二日同样出匪，续局却失利'}[name]
        seed = rows['copy_base']['seed']
        lines.extend(['',f'## {title}（{seed}）','',
                      '| 策略 | 第二日首轮票 | 第二日放逐 | 终局 |','|---|---|---|---|'])
        for arm,row in rows.items():
            votes = next(e['payload'] for e in row['events'] if e['day']==2 and e['event']=='votes')
            counts = Counter(seat(target) for target in votes.values())
            target = row['exile'].get('2')
            rendered = '无人' if target is None else seat(target)+ROLES[row['roles'][target]]
            lines.append(f"| {LABELS[arm]} | {'、'.join(f'{p} {n}票' for p,n in counts.most_common())} | {rendered} | {'胜' if row['win'] else '负'} |")
        if name in {'coordination','coordination_loss'}:
            row = next(r for r in rows['copy_coordinate']['calls'] if r['day']==2 and r['original']!=r['target'])
            estimates = '、'.join(f'{seat(p)}得{n}票' for p,n in row['predicted'].items())
            lines.extend(['',f"{seat(row['speaker'])}警预估 {estimates}，因此将正式归票从"
                          f"{seat(row['original'])}改为{seat(row['target'])}。两人均是其私知活匪。"
                          '预估来自该次发言前缀，实际票见上表。'])
            if name=='coordination_loss':
                lines.extend(['','7 号警都报查杀 2 号。原组当天归并出 2，第三日出 6，第四日出 11。'
                              '协调组当天改归 6 并把他推出，留下 2 号。第三日另一名活匪 11 号获得既有接续机会，'
                              '重报对 16 号的旧假查杀。好人日间出了 16 号民，第四天才出了 2 号，11 号活到终局。'
                              '这解释了同样出一个已知匪，后续却不同。'])
        else:
            changes = [r for r in rows['copy_shared']['common'] if r['day']==2 and r['first']
                       and r['actual']!=r['baseline']]
            if changes:
                first = changes[0]
                lines.extend(['',f"{len(changes)} 张平民首轮票被共同查杀改写。例如{seat(first['player'])}从"
                              f"{seat(first['baseline'])}转投{seat(first['actual'])}。"])
    return '\n'.join(lines).rstrip()+'\n'


reports = [(ROOT/'docs/corroborated_hit_results_v44.md',report()),
           (ROOT/'docs/corroborated_hit_cases_v44.md',show_cases())]
for path,text in reports:
    path.write_text(text)
extra = [Path(__file__).resolve(),*(path for path,_ in reports)]
save_json(ROOT/'results/v44_analysis_manifest.json',
          {str(path.relative_to(ROOT)):digest(path) for path in extra})
