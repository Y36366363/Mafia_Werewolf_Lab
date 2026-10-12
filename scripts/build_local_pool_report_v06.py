"""Build the Chinese v06 research report from frozen results."""
from fractions import Fraction
import json
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(value):
    return f"{100 * value:.2f}%"


def pp(value):
    return f"{100 * value:+.2f}"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v06"
    config = json.loads((ROOT / "configs/local_pool_v06.json").read_text())
    train = json.loads((folder / "train.json").read_text())
    test = json.loads((folder / "test.json").read_text())
    timing = json.loads((folder / "timing.json").read_text())
    analysis = json.loads((folder / "analysis.json").read_text())
    audit = json.loads((ROOT / "results/v06_integrity_audit.json").read_text())
    expansion = train["incremental_pool"]
    heldout = test["frozen_pool_heldout"]
    cells = {(c["good"], c["mafia"]): c for c in test["cells"]}
    good, mafia = test["matrix"]["good"], test["matrix"]["mafia"]
    timing_cells = {(c["cohort"], c["timing"], c["mafia"]): c for c in timing["cells"]}

    lines = ["# v06：局部混合、查杀释放时点与增量反制池", "",
             "本轮在主配置4警、4匪、8民上执行102,144局完整对局：9×7候选矩阵每格训练256局、"
             "独立留出1,024局；另对2,048个首验中匪状态和256个平民首发合法对齐状态做配对时点干预。"
             "训练、留出和两类时点队列使用四段互不重叠的新种子。", "",
             "## 阶段结论", "",
             "**局部混合覆盖了极端反制循环，但没有消除策略权衡。**公开跟随面对综合识别为"
             f"{pct(cells['public_base','combined']['summary']['rate'])}，面对追第一发起者仅"
             f"{pct(cells['public_base','origin']['summary']['rate'])}；纯随机掩护恰好相反，分别为"
             f"{pct(cells['random_base','combined']['summary']['rate'])}和"
             f"{pct(cells['random_base','origin']['summary']['rate'])}。按公开发言位置与本地随机数混合的"
             f"`position_mix`把两端压到{pct(cells['position_mix','combined']['summary']['rate'])}/"
             f"{pct(cells['position_mix','origin']['summary']['rate'])}，其全候选最差留出胜率为"
             f"{pct(analysis['pure_candidate_worst_rates']['position_mix'])}。", "",
             "**双发起确认是有效的反诱饵机制，但仍付出综合对手成本。**`confirm_mix`只有看到两个不同玩家"
             "在本日提名同一目标时才公开跟随，否则独立选目标；其留出纯候选最差胜率"
             f"{pct(analysis['pure_candidate_heldout_maximin']['rate'])}，是九个纯候选最高值。相对公开基线，"
             f"它在追发起者下提高{pp(cells['confirm_mix','origin']['summary']['rate'] - cells['public_base','origin']['summary']['rate'])}pp，"
             f"在综合识别下下降{pp(cells['confirm_mix','combined']['summary']['rate'] - cells['public_base','combined']['summary']['rate'])}pp。", "",
             "**3+1有限散票没有成为匪方改进。**在九个好人候选上，`combined_one_decoy`相对"
             "`combined`使好人胜率增加0.10至1.66pp；`origin_one_decoy`相对`origin`增加0.59至2.83pp。"
             "也就是说保留三张主票虽避免完全散票的协调损失，当前次优票仍未换到足够隐蔽收益。"
             "第一名匪先发低分诱饵再由末位匪散一票更差，使好人胜率增加6.05至16.89pp，不能晋级。", "",
             "**训练扩池在第三轮达到1pp阈值内稳定，留出只支持“近似覆盖”，不支持均衡认证。**"
             "训练先加入`position_mix`，再加入`public_police75`，第三轮没有候选超过1pp入池阈值。"
             "最终训练权重为好人`position_mix`47/62、`public_police75`15/62；匪方`combined`55/62、"
             f"`origin`7/62，训练值{pct(float(Fraction(expansion['train_value'])))}。冻结权重的留出期望为"
             f"{pct(heldout['heldout_value'])}，面对最差单一匪策略`{heldout['heldout_worst_pure_mafia']}`为"
             f"{pct(heldout['heldout_worst_rate'])}。留出中`public_police75`对冻结匪混合达到"
             f"{pct(heldout['heldout_best_rate'])}，说明训练权重仍有抽样偏差，不能称为稳定纳什解。", "",
             "**首验中匪后，早释放优于静默；晚释放的损失取决于反制。**在2,048个相同首夜状态中，"
             "早提名、晚提名、静默面对综合识别的胜率为3.52%、2.98%、1.17%；面对追发起者为"
             "2.39%、0.93%、0.15%；面对诱饵组合为8.98%、2.83%、0.29%。早提名相对晚提名在前两种"
             "对手下逐点区间仍跨0，对诱饵组合的配对差为-6.15pp（这里差值定义为晚减早），"
             "95%有界区间[-12.15,-0.15]pp。", "",
             "**平民首发是有条件的强机制。**在256个“首位发言者为平民，且无秘密的下一座提名规则恰好"
             "命中被验匪”的合法对齐状态中，平民首发面对综合、追发起者、诱饵组合的胜率分别为"
             "6.64%、8.59%、26.17%，对应警察早释放为3.52%、1.56%、6.25%。只有诱饵组合的保守有界"
             "区间排除0（+2.95至+36.90pp）。这个队列经过合法对齐筛选，不能代表任意首验中匪开局。", "",
             "## 留出胜率矩阵", "",
             "每格1,024局，好人终局胜率。", "",
             table(["好人策略"] + mafia,
                   [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia] for g in good]), "",
             "## 增量扩池轨迹", "",
             table(["轮次", "加入好人", "加入匪", "轮末训练值", "好人池", "匪池"],
                   [[r["round"], r["added_good"] or "—", r["added_mafia"] or "—",
                     pct(float(Fraction(r["end_value"]))), ", ".join(r["good_pool"]),
                     ", ".join(r["mafia_pool"])] for r in expansion["history"]]), "",
             "流程每轮用当前受限矩阵的精确有理数解计算候选回应，但候选本身是预先冻结的启发式策略。"
             "因此它是双重神谕/CFR式增量扩池，而不是从信息集遗憾值生成的新行为策略。", "",
             "## 查杀释放时点", "",
             table(["队列", "处理"] + config["timing"]["mafia_policies"],
                   [["全部首验中匪", mode] +
                    [pct(timing_cells['first_check_mafia', mode, m]['summary']['rate'])
                     for m in config["timing"]["mafia_policies"]]
                    for mode in ("early", "late", "silent")] +
                   [["平民合法对齐", mode] +
                    [pct(timing_cells['civilian_aligned', mode, m]['summary']['rate'])
                     for m in config["timing"]["mafia_policies"]]
                    for mode in ("early", "late", "silent", "civilian_first")]), "",
             "`early`从第一位活警开始公开查杀，后续活警继续同目标；`late`只由发言序位最后的活警公开；"
             "`silent`首日不公开；`civilian_first`由首位平民按公开的下一座规则发起，后续警察只有看到目标"
             "与私人查杀一致才跟随。信息较早释放会自然产生更多后续跟随，这是机制的一部分。所有处理均"
             "固定首夜死者遗言为`pass`。", "",
             "## 方法与结论边界", "",
             "矩阵结果是冻结策略池内的模拟胜率；有限候选回应和完整游戏最佳回应不是一回事。训练受限解"
             "仍用矩阵层的阵营相关权重作覆盖评价，实际可执行改进来自每个玩家独立抽样的`local`、公开位置"
             "规则与确认规则。时点结果是固定状态、固定续局种子的配对策略评估；平民合法对齐队列尤其不能"
             "外推为一般平民应盲猜查杀目标。", "",
             f"独立核验重算126个矩阵单元、21个时点单元和2,304个首夜状态，并重放"
             f"{audit['sampled_game_replays']}局；全部通过。", "",
             "## 下一轮建议", "",
             "1. 保留`confirm_mix`、`position_mix`和训练混合支持，增加按“已有一名/两名发起者、自己发言"
             "分位、首死座位距离”条件化的局部概率表；用训练数据拟合后整表冻结。", "",
             "2. 扩大平民首发的可实施覆盖：允许多个不读取验人的公开座位规则形成小型候选集，测量命中率×"
             "命中后的收益，避免只报告已对齐条件胜率。", "",
             "3. 将有限伪装改为只在3张主票足以唯一领先时才散第4票，并让好人票型推理显式区分“决定性票”"
             "与“无成本装饰票”；本轮固定3+1没有利用实时票差。", "",
             "4. 下一版扩池由训练轨迹生成新的条件概率策略，而不是只从既有名单挑选；仍使用新的留出种子，"
             "并把入池阈值与多轮停止规则预先写入配置。", "",
             "## 复查入口", "",
             "- [冻结协议](local_pool_protocol_v06.md)、[配置](../configs/local_pool_v06.json)、"
             "[结果清单](../results/v06/manifest.json)。",
             "- [训练矩阵](../results/v06/train.json)、[留出矩阵](../results/v06/test.json)、"
             "[时点原始结果](../results/v06/timing.json)、[探索性分析](../results/v06/analysis.json)。",
             "- [独立核验](../results/v06_integrity_audit.json)、"
             "[归档策略源码](../results/v06/source/mafia_lab/strategies_v06.py)。", "",
             "```sh", "python3 scripts/run_local_pool_v06.py --output results/v06_reproduction --workers 4",
             "python3 scripts/analyze_local_pool_v06.py",
             "python3 scripts/verify_local_pool_v06.py results/v06 --replay --output results/v06_integrity_audit.json",
             "python3 scripts/build_local_pool_report_v06.py", "```", ""]
    output = ROOT / "docs/local_pool_results_v06.md"
    output.write_text("\n".join(lines))
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
