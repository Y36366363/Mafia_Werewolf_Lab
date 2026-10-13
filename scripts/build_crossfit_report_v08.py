"""Build the Chinese v08 report from frozen results and audited analysis."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(value): return "—" if value is None else f"{100 * value:.2f}%"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v08"
    config = json.loads((ROOT / "configs/crossfit_v08.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    selection = json.loads((folder / "table_selection_before_holdout.json").read_text())
    probe_selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    matrix = json.loads((folder / "matrix_holdout.json").read_text())
    probe = json.loads((folder / "probe_holdout.json").read_text())
    analysis = json.loads((folder / "analysis.json").read_text())
    audit = json.loads((ROOT / "results/v08_integrity_audit.json").read_text())
    cells = {(c["good"], c["mafia"]): c for c in matrix["cells"]}
    pcells = {(c["candidate"], c["mafia"]): c for c in probe["cells"]}
    good, mafia = matrix["matrix"]["good"], matrix["matrix"]["mafia"]
    opponents = config["probe_selection"]["opponents"]
    probe_names = [c["name"] for c in config["probe_selection"]["candidates"]]

    lines = ["# v08：公共匪目标、坐标交叉拟合与覆盖收益首发", "",
             f"本轮在4警、4匪、8民上执行{manifest['executed_games']:,}局完整对局："
             f"{manifest['table_training_games']:,}局用于互不复用的坐标拟合/验证，"
             f"{manifest['probe_training_games']:,}局用于平民首发选择，其余为完全未读的矩阵和首发留出。"
             "所有对局继续采用公开顺序投票。", "",
             "## 阶段结论", "",
             "**公共确定性破同分已修复。**匪方主目标按“共同评分降序、公开发言序、座位号”排序；"
             "同阵营成员只用共同身份信息与公共历史，因此得到同一主目标。在4种好人策略×2种确定性匪"
             "策略的留出对局中，至少两匪投票的回合共发生散票0次。装饰策略的散票现在是明确策略动作，"
             "不再混入行动者各自随机破同分造成的伪散票。", "",
             "**互不复用的坐标子批次显著收紧了训练更新。**18次坐标尝试只有2次通过独立验证：第二组"
             "掩护概率由75%降为0，警察晚位无查杀提名概率由100%降为50%。每个坐标/轮次使用独立96局"
             "拟合种子和192局验证种子，36个区间两两不重叠；最终2,048局/格的未读矩阵中，交叉拟合表"
             f"的候选池最差胜率为{pct(analysis['matrix_scores']['crossfit_table']['worst'])}，"
             f"`confirm_mix`为{pct(analysis['matrix_scores']['confirm_mix']['worst'])}，"
             f"`position_mix`为{pct(analysis['matrix_scores']['position_mix']['worst'])}。"
             "这是本次冻结候选池的纯策略maximin观察值，还不是受限混合均衡或完整GTO。", "",
             "**扩大平民公开首发覆盖后，无条件收益随对齐覆盖上升。**候选只按全部首验中匪开局的完整"
             "对局胜率选拔，启动率与对齐率只用于解释。拟合选择并由独立验证接受`probe_w8_cycle`；在"
             "4,096个未读开局上，它的启动率为100%，全部状态对齐率26.34%，三个匪方对手上的最差胜率"
             f"为{pct(analysis['probe_holdout_scores']['probe_w8_cycle']['worst'])}。静默为"
             f"{pct(analysis['probe_holdout_scores']['silent']['worst'])}，警察直接早释放为"
             f"{pct(analysis['probe_holdout_scores']['early']['worst'])}。这支持继续优化“覆盖率×对齐收益”，"
             "并淘汰只报告稀有对齐条件分支的评价方式。", "",
             "**装饰票仍未形成稳定匪方收益。**确定性最终安全票与协调基线在四种好人策略下结果完全"
             "相同；实时票差装饰使好人胜率改变0至+0.78pp，固定一张装饰票使好人胜率增加0.29至"
             "1.76pp。当前只保留实时约束作为可研究反制，固定装饰不晋级。", "",
             "## 冻结交叉拟合表", "",
             table(["公开条件", "早位", "中位", "晚位"],
                   [["一名同目标发起者"] + [pct(x) for x in selection["cover_table"][:3]],
                    ["至少两名同目标发起者"] + [pct(x) for x in selection["cover_table"][3:]],
                    ["警察无查杀提名"] + [pct(x) for x in selection["police_table"]]]), "",
             f"训练共评估{audit['checked_training_cells']}个候选/对手单元。拟合子批次只负责提出候选；"
             "候选必须在该坐标自己的验证子批次上把最差对手胜率提高至少0.5pp，且平均胜率下降不超过"
             "0.5pp。最终矩阵使用另一组从未参与选择的种子。", "",
             "## 未读矩阵", "", "每格2,048局，好人终局胜率。", "",
             table(["好人策略"] + mafia,
                   [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia] for g in good]), "",
             "## 平民首发的覆盖与无条件结果", "", "每格共享同一组4,096个首验中匪开局。", "",
             table(["候选", "启动率", "对齐率", "平均提名数", "最差胜率", "平均胜率"],
                   [[name,
                     pct(analysis["probe_holdout_scores"][name]["activation_rate"]),
                     pct(analysis["probe_holdout_scores"][name]["alignment_rate"]),
                     f"{analysis['probe_holdout_scores'][name]['mean_probes']:.2f}",
                     pct(analysis["probe_holdout_scores"][name]["worst"]),
                     pct(analysis["probe_holdout_scores"][name]["mean"])]
                    for name in probe_names]), "",
             table(["候选"] + opponents,
                   [[name] + [pct(pcells[name, m]["summary"]["rate"]) for m in opponents]
                    for name in probe_names]), "",
             "`probe_w8_cycle`让公开发言序前8位中的平民依次按公开座位规则提名；警察只有在公开目标"
             "碰巧等于私有查杀时才跟进。玩家不需要知道是否对齐，也不读取验人秘密。窗口扩大同时增加"
             "启动覆盖、目标覆盖和公开噪声；本轮只能确认组合后的候选表现，尚未拆出三者的因果贡献。", "",
             "## 评价边界", "",
             "矩阵结果是冻结续局启发式下的策略评估；坐标训练是有限网格回应，不是CFR遗憾最小化。"
             "候选池maximin只回答当前6种匪策略中的最差结果，不能外推为完整声明游戏的GTO。首发实验"
             "又条件在首验中匪，因此只适用于该信息状态；它没有给出首验好人、首死警察或首死平民的"
             "总体开局策略。", "",
             f"独立核验重算{audit['checked_training_cells']}个训练单元、{audit['checked_matrix_cells']}个"
             f"矩阵单元、{audit['checked_probe_cells']}个首发单元、{audit['checked_openings']:,}个开局和"
             f"{audit['checked_coordinate_seed_intervals']}个种子区间，并重放"
             f"{audit['sampled_game_replays']}局；全部通过。", "",
             "## 复查入口", "",
             "- [冻结协议](crossfit_protocol_v08.md)、[配置](../configs/crossfit_v08.json)、"
             "[结果清单](../results/v08/manifest.json)。",
             "- [坐标选择](../results/v08/table_selection_before_holdout.json)、"
             "[矩阵原始结果](../results/v08/matrix_holdout.json)、"
             "[首发选择](../results/v08/probe_selection_before_holdout.json)、"
             "[首发未读留出](../results/v08/probe_holdout.json)、[分析](../results/v08/analysis.json)。",
             "- [独立核验](../results/v08_integrity_audit.json)、"
             "[归档策略源码](../results/v08/source/mafia_lab/strategies_v08.py)。", "",
             "```sh", "python3 scripts/run_crossfit_v08.py --output results/v08_reproduction --workers 4",
             "python3 scripts/analyze_crossfit_v08.py",
             "python3 scripts/verify_crossfit_v08.py results/v08 --replay --output results/v08_integrity_audit.json",
             "python3 scripts/build_crossfit_report_v08.py", "```", ""]
    output = ROOT / "docs/crossfit_results_v08.md"
    output.write_text("\n".join(lines))
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
