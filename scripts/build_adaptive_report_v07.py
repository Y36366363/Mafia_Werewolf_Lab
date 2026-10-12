"""Build the Chinese v07 report from frozen results."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(value): return "—" if value is None else f"{100 * value:.2f}%"
def pp(value): return f"{100 * value:+.2f}"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v07"
    config = json.loads((ROOT / "configs/adaptive_v07.json").read_text())
    holdout = json.loads((folder / "holdout.json").read_text())
    initiator = json.loads((folder / "initiator.json").read_text())
    training = json.loads((folder / "table_selection_before_test.json").read_text())
    analysis = json.loads((folder / "analysis.json").read_text())
    audit = json.loads((ROOT / "results/v07_integrity_audit.json").read_text())
    cells = {(c["good"], c["mafia"]): c for c in holdout["cells"]}
    icells = {(c["treatment"], c["mafia"]): c for c in initiator["cells"]}
    good, mafia = holdout["matrix"]["good"], holdout["matrix"]["mafia"]
    opponents = config["initiator_experiment"]["opponents"]
    rules = [t for t in config["initiator_experiment"]["treatments"] if t.get("rule")]

    lines = ["# v07：实时票差、公开平民首发与训练生成条件表", "",
             "本轮在4警、4匪、8民上执行156,672局完整对局。其中46,080局用于训练九单元条件概率表，"
             "24,576局使用独立种子评估4×6策略矩阵，86,016局在4,096个固定首验中匪状态上比较"
             "警察早释放、静默和五种平民首发规则。所有对局采用新增的公开顺序投票规则。", "",
             "## 阶段结论", "",
             "**实时票差约束消除了固定散票的大部分协调损失，但没有形成稳定匪方收益。**固定3+1在"
             "四种好人策略下使好人胜率增加0.39至1.66pp。`combined_live_margin`把匪方多票回合的散票率"
             "从固定3+1的99.9%–100%压至16.9%–26.1%，但相对`combined`的好人胜率差仍为-0.10至"
             "+1.07pp；四项逐点95%区间均跨0。只在全场最后一票安全时装饰的`combined_live_final`散票率"
             "为3.0%–5.7%，胜率也与协调基线接近。当前结论是“票差门控避免明显送票”，不是“装饰票已"
             "证明能提高匪方胜率”。", "",
             "**公开顺序投票揭示了原`coordinate`并不总是同票。**综合评分基线仍有44.8%–64.3%的"
             "匪方多票回合出现不同目标，因为同分时各行动者使用独立本地随机数。`live_margin`同时改变了"
             "同分破局和装饰条件，因此这里的胜率比较是完整投票策略比较，不能把差值只归因于最后一张"
             "装饰票。下一版应先规定一个所有匪可由公开信息和队友身份共同计算的确定性主目标。", "",
             "**训练生成表在训练集改善、留出集失败。**初始表的训练最差胜率为"
             f"{pct(analysis['training_initial_worst'])}，两轮坐标回应后升至"
             f"{pct(analysis['training_final_worst'])}；冻结表在全新留出集的最差胜率却只有"
             f"{pct(analysis['heldout_worst_rates']['learned_table'])}。人工`confirm_mix`达到"
             f"{pct(analysis['heldout_pure_maximin']['rate'])}，继续保持纯候选第一。"
             "这说明128个训练种子上逐单元反复优化产生明显选择偏差，冻结与留出机制成功拦截了错误晋级。", "",
             "**平民首发的无条件收益很小，警察早释放明显更强。**五种规则只有在首位发言者为平民时启动，"
             "启动率47.95%；在全部4,096个首验中匪状态中，偶然对齐率仅2.93%–3.61%。相对静默，规则的"
             "好人胜率增益为0.15–0.54pp，而警察早释放为2.54–2.98pp。平民规则的逐点正态区间多为正，"
             "但按18项比较计算的家族Hoeffding半宽为5.67pp，所有规则差值均不能排除0，因此不晋级为"
             "首日默认动作。", "",
             "## 冻结条件概率表", "",
             table(["公开条件", "早位", "中位", "晚位"],
                   [["一名同目标发起者"] + [pct(x) for x in training["cover_table"][:3]],
                    ["至少两名同目标发起者"] + [pct(x) for x in training["cover_table"][3:]],
                    ["警察无查杀提名"] + [pct(x) for x in training["police_table"]]]), "",
             "概率表只读取本日公开提名支持数和自己的公开发言分位。平民在没有公开提名时随机选择合法目标；"
             "警察有存活查杀时仍以100%概率提名。训练更新顺序、每个候选的原始结局与选择评分均保存在"
             "训练选择文件中。", "",
             "## 公开顺序投票留出矩阵", "",
             "每格1,024局，好人终局胜率。", "",
             table(["好人策略"] + mafia,
                   [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia] for g in good]), "",
             "## 匪方散票频率", "",
             "分母是至少两名存活匪实际投出非空票的回合；它描述最终匪票是否分裂，并非所有分裂都由装饰"
             "条件触发。", "",
             table(["好人策略", "综合基线", "固定3+1", "实时票差", "最终一票安全"],
                   [[g, pct(cells[g, "combined"]["mafia_split_rate"]),
                     pct(cells[g, "combined_one_decoy"]["mafia_split_rate"]),
                     pct(cells[g, "combined_live_margin"]["mafia_split_rate"]),
                     pct(cells[g, "combined_live_final"]["mafia_split_rate"])] for g in good]), "",
             "## 平民首发规则", "",
             table(["处理"] + opponents,
                   [[name] + [pct(icells[name, m]["summary"]["rate"]) for m in opponents]
                    for name in ["silent", "early"] + [t["name"] for t in rules]]), "",
             table(["公开规则", "启动数", "对齐数", "全部状态对齐率", "对齐后胜率范围"],
                   [[t["rule"], icells[t["name"], opponents[0]]["activated"],
                     icells[t["name"], opponents[0]]["aligned"],
                     pct(icells[t["name"], opponents[0]]["aligned"] / icells[t["name"], opponents[0]]["n"]),
                     f"{pct(min(icells[t['name'],m]['conditional_aligned']['rate'] for m in opponents))}–"
                     f"{pct(max(icells[t['name'],m]['conditional_aligned']['rate'] for m in opponents))}"]
                    for t in rules]), "",
             "`cycle`按首位平民座位与公开死者锚点在其余四条规则间轮换。对齐后的胜率仍是自然筛选分支，"
             "只能解释无条件增益为何稀薄，不能作为玩家知道“已对齐”时可执行的策略结果。", "",
             "## 方法边界与下一步", "",
             "本轮公开顺序投票是新规则变体，不能直接与v06同时投票胜率比较。`live_margin`保证的只是行动"
             "瞬间主目标仍唯一领先，后续票仍可能改变结果；`live_final`才提供最终票表保证。训练表是有限"
             "网格坐标回应，不是CFR遗憾收敛。所有胜率均为冻结启发式续局的策略评估，并非完整游戏GTO。", "",
             "下一阶段应先修复匪方主目标的公共确定性破同分规则，再把训练拆为互不复用的坐标子批次或使用"
             "交叉拟合，减少逐单元重用128个种子造成的过拟合。平民首发若继续研究，应优化“覆盖率×对齐"
             "收益”的组合，而不是继续报告稀有对齐分支。", "",
             f"独立核验重算360个训练候选单元的选择路径、24个留出单元、21个首发单元和4,096个开局，"
             f"并重放{audit['sampled_game_replays']}局；全部通过。", "",
             "## 复查入口", "",
             "- [冻结协议](adaptive_protocol_v07.md)、[配置](../configs/adaptive_v07.json)、"
             "[结果清单](../results/v07/manifest.json)。",
             "- [训练选择与冻结表](../results/v07/table_selection_before_test.json)、"
             "[留出矩阵](../results/v07/holdout.json)、[首发原始结果](../results/v07/initiator.json)、"
             "[探索性分析](../results/v07/analysis.json)。",
             "- [独立核验](../results/v07_integrity_audit.json)、"
             "[归档策略源码](../results/v07/source/mafia_lab/strategies_v07.py)。", "",
             "```sh", "python3 scripts/run_adaptive_v07.py --output results/v07_reproduction --workers 4",
             "python3 scripts/analyze_adaptive_v07.py",
             "python3 scripts/verify_adaptive_v07.py results/v07 --replay --output results/v07_integrity_audit.json",
             "python3 scripts/build_adaptive_report_v07.py", "```", ""]
    output = ROOT / "docs/adaptive_results_v07.md"
    output.write_text("\n".join(lines))
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
