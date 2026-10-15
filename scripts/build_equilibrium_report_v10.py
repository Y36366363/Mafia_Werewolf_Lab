"""Build the Chinese v10 report from frozen results and audit."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(x): return f"{100*x:.2f}%"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v10"
    manifest = json.loads((folder / "manifest.json").read_text())
    selection = json.loads((folder / "selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "holdout.json").read_text())
    analysis = json.loads((folder / "analysis.json").read_text())
    audit = json.loads((ROOT / "results/v10_integrity_audit.json").read_text())
    good, mafia = holdout["matrix"]["good"], holdout["matrix"]["mafia"]
    cells = {(c["good"], c["mafia"]): c for c in holdout["cells"]}
    train_eq = selection["restricted_train_equilibrium"]
    frozen = holdout["frozen_train_mixture_evaluation"]
    post = holdout["posthoc_holdout_restricted_equilibrium"]

    lines = ["# v10：公共协调、专门反制与扩展矩阵受限均衡", "",
             f"本轮在4警、4匪、8民上执行{manifest['executed_games']:,}局完整对局。"
             f"训练矩阵使用{manifest['train_games']:,}局，在读取留出前冻结三类匪方回应和双方混合；"
             f"独立留出矩阵使用{manifest['holdout_games']:,}局。矩阵规模为7种好人策略×13种匪策略。", "",
             "## 阶段结论", "",
             "**三类针对性回应都学到低权重版本，而且选择在留出中完全复现。**集中目标回应选择"
             "`concentration_w2`，分散目标回应选择`dispersion_w2`，警察跟随时点回应选择`follow_w2`。"
             "三个家族的训练最优权重在留出各自目标策略上仍取得最低经验胜率；不过相邻权重差小于本轮"
             "保守误差界，因此这里只确认排序复现，不能确认`w2`本身是稳定最优强度。更强权重在本批"
             "样本中没有带来更强反制。", "",
             "**新增的非探测公共协调协议没有成为强基线。**首日由所有好人执行“前半提出、后半收敛”，"
             "第二日起恢复普通推理。立即释放、公开目标后跟随、晚位跟随三种版本的留出最差胜率分别为"
             f"{pct(analysis['pure_holdout_scores']['coord_deliberative_immediate']['worst'])}、"
             f"{pct(analysis['pure_holdout_scores']['coord_deliberative_public']['worst'])}、"
             f"{pct(analysis['pure_holdout_scores']['coord_deliberative_late']['worst'])}，均未进入混合支持。"
             "固定公共程序虽然提高同步程度，但公开可预测性让`origin`反制稳定利用它，因此本候选不晋级。", "",
             "**训练扩展矩阵存在精确零间隙的受限混合解。**经验训练值为"
             f"{pct(train_eq['value'])}；好人以2/3选择`crossfit_table`、1/3选择`probe_w8_anchor`，匪方以"
             "104/147选择`combined_det`、43/147选择`origin_det`。精确分数单纯形及逐纯策略重算的训练"
             "上下界均为421/1536，间隙为0。这里的“精确”只指给定经验矩阵的代数求解。", "",
             "**冻结训练混合在独立留出上的价值大体稳定，但支持尚未收敛。**冻结好人混合的留出最差列"
             f"为{pct(frozen['fixed_good_mixture_lower'])}，冻结匪混合的留出最佳回应为"
             f"{pct(frozen['fixed_mafia_mixture_upper'])}，样本外间隙为"
             f"{pct(frozen['out_of_sample_gap'])}。留出事后受限值为{pct(post['value'])}；好人支持仍是"
             "`crossfit_table + probe_w8_anchor`，但权重改为415/521与106/521；匪方支持变为"
             "`origin_det + concentration_w2`。价值接近而匪方支持漂移，下一轮仍需增量扩池。", "",
             "**当前最稳健纯策略仍是交叉拟合表。**其留出最差胜率为"
             f"{pct(analysis['pure_holdout_scores']['crossfit_table']['worst'])}，最差对手已经从普通"
             "`combined`转为新学到的`concentration_w2`。集中探测的纯策略最差胜率只有"
             f"{pct(analysis['pure_holdout_scores']['probe_w8_anchor']['worst'])}，但它对多列匪策略收益很高，"
             "所以作为混合中的补充策略仍有价值。", "",
             "## 三类回应的独立留出", "",
             table(["回应家族", "目标策略", "训练选择", "留出最优", "各权重下好人胜率"],
                   [[family, item["target_good"], item["selected_train"], item["selected_holdout"],
                     " / ".join(f"{name}={pct(rate)}" for name, rate in item["rates"].items())]
                    for family, item in analysis["response_holdout"].items()]), "",
             "## 留出纯策略摘要", "",
             table(["好人策略", "最差胜率", "最差对手", "13列平均胜率"],
                   [[g, pct(analysis["pure_holdout_scores"][g]["worst"]),
                     analysis["pure_holdout_scores"][g]["worst_opponent"],
                     pct(analysis["pure_holdout_scores"][g]["mean"])] for g in good]), "",
             "## 留出矩阵", "", "每格2,048个自然开局，好人终局胜率。", "",
             table(["好人策略"] + mafia,
                   [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia] for g in good]), "",
             "## 受限混合证书与边界", "",
             table(["量", "结果"],
                   [["训练经验矩阵值", f"{pct(train_eq['value'])} ({train_eq['value_exact']})"],
                    ["训练精确间隙", train_eq["gap_exact"]],
                    ["冻结好人混合留出下界", f"{pct(frozen['fixed_good_mixture_lower'])} ({frozen['fixed_good_mixture_lower_exact']})"],
                    ["冻结匪混合留出上界", f"{pct(frozen['fixed_mafia_mixture_upper'])} ({frozen['fixed_mafia_mixture_upper_exact']})"],
                    ["样本外回应间隙", f"{pct(frozen['out_of_sample_gap'])} ({frozen['out_of_sample_gap_exact']})"],
                    ["留出事后受限值", f"{pct(post['value'])} ({post['value_exact']})"]]), "",
             f"固定加权逐种子收益的20项家族Hoeffding 95%半宽为"
             f"{pct(analysis['bounded_mean_half_widths']['familywise_95_over_20_response_checks'])}。"
             "样本外间隙与该保守误差量级相近，因此不能把3.89pp直接解释为真实可利用度。更关键的是，"
             "这些混合要求阵营在局前共享同一个秘密策略索引；普通规则未必提供这种相关装置。", "",
             "本轮结果依次属于：固定策略胜率、候选池内经验最优回应、经验矩阵受限均衡。它没有枚举完整"
             "声明空间、没有证明遗憾收敛，也没有给出未限制最佳回应，因此不是完整游戏GTO。", "",
             f"独立核验重算{audit['checked_train_cells']}个训练单元、"
             f"{audit['checked_holdout_cells']}个留出单元、3条回应选择、训练与留出事后两个精确零间隙"
             f"证书及冻结混合上下界，并重放{audit['sampled_game_replays']}局；全部通过。", "",
             "## 复查入口", "",
             "- [冻结协议](equilibrium_protocol_v10.md)、[配置](../configs/equilibrium_v10.json)、"
             "[结果清单](../results/v10/manifest.json)。",
             "- [留出前选择与训练均衡](../results/v10/selection_before_holdout.json)、"
             "[留出矩阵](../results/v10/holdout.json)、[分析](../results/v10/analysis.json)。",
             "- [独立核验](../results/v10_integrity_audit.json)、"
             "[归档策略源码](../results/v10/source/mafia_lab/strategies_v10.py)。", "",
             "```sh", "python3 scripts/run_equilibrium_v10.py --output results/v10_reproduction --workers 4",
             "python3 scripts/analyze_equilibrium_v10.py",
             "python3 scripts/verify_equilibrium_v10.py results/v10 --replay --output results/v10_integrity_audit.json",
             "python3 scripts/build_equilibrium_report_v10.py", "```", ""]
    out = ROOT / "docs/equilibrium_results_v10.md"
    out.write_text("\n".join(lines))
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
