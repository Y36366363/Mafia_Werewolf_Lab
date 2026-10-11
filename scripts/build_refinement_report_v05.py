"""Build the Chinese v05 results report from independently verified artifacts."""
import json
from fractions import Fraction
from math import log, sqrt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_refinement_v05 import validate_directory


def pct(value):
    return f"{100 * value:.2f}%"


def pp(value):
    return f"{100 * value:+.2f}"


def ci(values):
    return f"[{100 * values[0]:+.2f}, {100 * values[1]:+.2f}]"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |"] +
                      ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v05"
    audit = validate_directory(folder)
    saved_audit = ROOT / "results/v05_integrity_audit.json"
    if saved_audit.exists():
        replay_audit = json.loads(saved_audit.read_text())
        if replay_audit.get("source_sha256") == audit["source_sha256"]:
            audit["archived_game_replays"] = replay_audit["archived_game_replays"]
    read = lambda name: json.loads((folder / f"{name}.json").read_text())
    manifest, train, test, sensitivity, matrix_solution = map(
        read, ("manifest", "train", "test", "sensitivity", "restricted_matrix_solution"))
    config = manifest["config"]
    good, mafia = test["matrix"]["good"], test["matrix"]["mafia"]
    cells = {(c["good"], c["mafia"]): c for c in test["cells"]}
    contrasts = {(r["side"], r["control"], r["treatment"], r["fixed_opponent"]): r["paired"]
                 for r in test["all_prespecified_contrasts"]}
    selection = train["selection"]
    labels = ["综合", "追发起者", "只看票型", "综合+散票", "发起者+散票", "发起者半频", "发起者假跳"]
    family_n = len(test["all_prespecified_contrasts"])

    def effect(side, a, b, opponent):
        stats = contrasts[side, a, b, opponent]
        lo, hi = stats["ci95_familywise_hoeffding"]
        return pp(stats["delta"]) + (" ★" if lo > 0 or hi < 0 else "")

    lines = ["# v05：16人局策略拆分、提名顺序反制与受限混合分析", "",
             "日期：2026-10-11。主配置和全部敏感性配置均为4警、4匪、8民。", "",
             f"本轮完成 **{manifest['executed_games']:,}局真实终局模拟**：11种好人策略×7种匪策略，"
             "每格训练256局、独立留出1,024局，另有全16人规则敏感性。"
             f"独立核验覆盖{audit['checked_cells']}个实验单元、{audit['checked_branch_summaries']}个条件摘要、"
             f"{audit['checked_paired_contrasts']}项配对统计，并用归档代码重放"
             f"{audit['archived_game_replays']}局。", "",
             "这些结果是冻结策略池内的终局胜率和反制关系。它们不是16人完整GTO、行为策略纳什均衡、"
             "完整最佳回应或教学迁移证据。", "",
             "## 主要结论", "",
             "**公开跟随形成的全掩护仍泄露“谁先发起”。**在 `cover100` 下，匪方从综合评分改为追踪"
             f"第一提名者，好人胜率由{pct(cells['cover100','combined_mimic']['summary']['rate'])}降至"
             f"{pct(cells['cover100','origin_mimic']['summary']['rate'])}，差值"
             f"{effect('mafia','combined_mimic','origin_mimic','cover100')}pp。"
             "平民都跟票并没有抹掉发言顺序，最早暴露共同目标的人仍可成为警察代理信号。", "",
             "**随机全掩护能反制追发起者，却形成新的可利用结构。**把平民目标从公开跟随改为随机，"
             f"面对追发起者时由{pct(cells['cover100','origin_mimic']['summary']['rate'])}升至"
             f"{pct(cells['cover100_random','origin_mimic']['summary']['rate'])}，差值"
             f"{effect('good','cover100','cover100_random','origin_mimic')}pp；"
             f"面对综合反制却从{pct(cells['cover100','combined_mimic']['summary']['rate'])}降至"
             f"{pct(cells['cover100_random','combined_mimic']['summary']['rate'])}。"
             "训练回应链进一步呈现循环：`cover100/origin_mimic` 9.96% → "
             "`random_inspect/origin_mimic` 86.91% → `random_inspect/combined_split` 3.32%。"
             "因此当前最重要的结构是反制循环，而不是单一最佳声明规则。", "",
             "**v04中票型验人的增益没有在全掩护基线上复现。**v04是在50%提名且双方使用票型投票的"
             "组合上再加入定向验人；本轮干净的 `inspect_only` 相对"
             "`cover100`，七个对手的点估计为-0.29至+5.08pp，没有一项通过139项家族界。"
             "这说明原增益依赖当时的策略组合或交互，尚不能归因于验人规则本身。只开警察票型投票、"
             "只开平民票型投票或双方都开，整体没有形成稳健收益；双方都开在综合、"
             "只看票型和假跳对手下分别显著降低13.09、15.62和15.92pp。当前评分不应升级为默认投票法。", "",
             "**75%频率没有改善当前最差结构。**平民掩护从100%降到75%，面对综合及综合散票反制"
             "分别显著下降15.14和14.65pp。只把警察无查杀提名率降到75%未产生通过家族界的收益。"
             "继续调单一固定频率的价值有限，下一步应研究依赖公开序位与历史的局部随机化。", "",
             "**首夜分支解释了风险集中位置。**在 `cover100/origin_mimic` 中，首死警察时好人胜率"
             "5.11%，首死平民时12.50%；`random_inspect/origin_mimic` 对应73.30%和94.05%。"
             "这些是自然条件分支，不是对首死身份的随机干预；它们适合定位后续受控实验，不能单独当因果效应。", "",
             "## 留出胜率矩阵", "",
             "所有单元均为独立留出种子的好人终局胜率，每格1,024局。", "",
             table(["好人策略"] + labels,
                   [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia] for g in good]), "",
             "## 预声明好人策略比较", "",
             f"数值为后项减前项的好人胜率百分点。★表示家族95% Hoeffding区间不跨0；"
             f"该界同时覆盖{family_n}项预声明比较，半宽约"
             f"{100 * sqrt(2 * log(2 * family_n / .05) / config['test']['n']):.2f}pp。", "",
             table(["前项 → 后项"] + labels,
                   [[f"{c['control']} → {c['treatment']}"] +
                    [effect("good", c["control"], c["treatment"], m) for m in mafia]
                    for c in config["good_contrasts"]]), "",
             "`police_vote → both_vote`是加入平民票型投票的边际效果；`civilian_vote → both_vote`是加入警察"
             "票型投票的边际效果。`inspect_only → inspect_police_vote`测试在定向验人之外再改警察投票。", "",
             "## 预声明匪方反制比较", "",
             "负值表示新匪策略使好人胜率下降，即匪方获益。`split`同时改变四名匪的白天投票分布，"
             "并不改变其夜刀评分。", "",
             table(["固定好人"] + [f"{c['control']} → {c['treatment']}" for c in config["mafia_contrasts"]],
                   [[g] + [effect("mafia", c["control"], c["treatment"], g)
                            for c in config["mafia_contrasts"]] for g in good]), "",
             "追发起者并非普遍更强：它压制公开跟随，却被随机掩护反向利用。半频提名和假跳多数使好人"
             "胜率上升，说明这些伪装在当前执行规则下付出的白天协调成本大于隐蔽收益。", "",
             "## 训练选择与留出回应链", "",
             f"训练阶段选择：`{selection['baseline_good']}` → `{selection['mafia_response']}` → "
             f"`{selection['good_response']}` → `{selection['second_mafia_response']}`。训练最大化最差纯方案为"
             f" `{selection['robust_pure_good']}`，其训练最强对手为 `{selection['robust_train_worst_mafia']}`。", ""]
    selected_rows = []
    for row in test["selected_heldout_comparisons"]:
        a, b = cells[tuple(row["control"])], cells[tuple(row["treatment"])]
        selected_rows.append([row["name"], " / ".join(row["control"]), " / ".join(row["treatment"]),
                              f"{pct(a['summary']['rate'])} → {pct(b['summary']['rate'])}",
                              pp(row["paired"]["delta"]), ci(row["paired"]["ci95_normal"]),
                              ci(row["paired"]["ci95_hoeffding"])])
    lines += [table(["比较", "起点", "终点", "胜率", "差值pp", "逐点正态95%", "逐点有界95%"], selected_rows), "",
              "这些回应链是训练选择后的逐点评价，不属于139项家族界。纯策略“稳健”只表示训练矩阵中"
              "最大化最差单元；留出集中 `inspect_police_vote/origin_split` 为10.74%，相对"
              "`cover100/origin_split`仅+0.68pp，保守有界区间仍跨0。", "",
              "## 首夜条件分支", "",
              "四个分支在每个主矩阵单元中分别有相同的自然分母：首死警察352、首死平民672、首验中匪341、"
              "首验好人683。首夜尚无公开历史且本轮自刀率为0，因此各策略共享相同首夜动作分布。", ""]
    branch_keys = ["first_dead_police", "first_dead_civilian", "first_check_mafia", "first_check_good"]
    branch_labels = ["首死警", "首死民", "首验匪", "首验好人"]
    branch_cells = [("cover100", "origin_mimic"), ("random_inspect", "origin_mimic"),
                    ("random_inspect", "combined_split"), ("inspect_police_vote", "origin_split"),
                    ("inspect_only", "combined_mimic")]
    lines += [table(["好人 / 匪"] + branch_labels,
                    [[f"{g} / {m}"] + [pct(cells[g, m]["conditional"][k]["rate"]) for k in branch_keys]
                     for g, m in branch_cells]), "",
              "`cover100/origin_mimic`中首验匪反而低于首验好人，说明“查中”并不会自动转化成收益：公开"
              "提名顺序同时帮助匪方定位发起者。`random_inspect/origin_mimic`中首验匪则更有利。"
              "后续应固定同一首夜状态，直接干预警察的发言时点，才能区分验人价值与选择偏差。", "",
              "## 冻结候选矩阵的受限混合解", "",
              "对训练胜率矩阵做精确有理数零和求解，得到的是有限候选计划的矩阵均衡。它要求一个只对"
              "同阵营可见的赛前装置，把同一个策略编号发给所有好人；普通警匪局没有这种装置，因此该解"
              "不能直接作为可执行GTO。它仍可判断反制循环是否需要混合。", "",
              f"训练矩阵值为{pct(matrix_solution['train_value'])}。好人混合为 " +
              "、".join(f"`{name}` {pct(float(Fraction(value)))}" for name, value in matrix_solution["good_mixture"].items()) +
              "；匪方混合为 " +
              "、".join(f"`{name}` {pct(float(Fraction(value)))}" for name, value in matrix_solution["mafia_mixture"].items()) + "。", "",
              f"把训练选出的两边混合权重原样用于留出集，期望好人胜率为"
              f"{pct(matrix_solution['heldout_at_train_mixtures']['mean'])}，逐点正态95%区间"
              f"[{pct(matrix_solution['heldout_at_train_mixtures']['ci95_normal'][0])}, "
              f"{pct(matrix_solution['heldout_at_train_mixtures']['ci95_normal'][1])}]。"
              f"该好人混合面对留出集中最差的单一匪策略为 `{matrix_solution['heldout_good_mixture_worst_pure_mafia']['name']}`，"
              f"胜率{pct(matrix_solution['heldout_good_mixture_worst_pure_mafia']['rate'])}。"
              "这比任何单个方案更好地覆盖了公开/随机掩护的相反弱点，但相关团队混合假设尚不可执行。", "",
              "## 16人规则敏感性", ""]
    variant_name = {json.dumps(v["rules"], sort_keys=True): v["name"]
                    for v in config["sensitivity"]["rule_variants"]}
    lines += [table(["规则", "好人", "匪", "好人胜率"],
                    [[variant_name[json.dumps(c["rules"], sort_keys=True)], c["good"], c["mafia"],
                      pct(c["summary"]["rate"])] for c in sensitivity["cells"]]), "",
              "PK和四次遗言没有改变主要排序。反向发言在追发起者对手下进一步降低两项好人策略的胜率，"
              "说明发言方向会改变谁更常成为第一提名者；位置机制需要在两个方向都检验。", "",
              "## 下一阶段", "",
              "1. 构造无需阵营秘密相关装置的局部混合：玩家仅按自己的座位、发言序位和公开历史抽样，"
              "逼近矩阵混合对反制循环的覆盖效果。", "",
              "2. 固定相同首夜状态，分别干预首验中匪后的早提名、晚提名、静默及由平民先发起，直接估计"
              "首日信息释放时点。", "",
              "3. 将匪方散票细分为不牺牲主要放逐目标的有限伪装，并加入识别“第一发起者可能是匪诱饵”"
              "的好人反制。", "",
              "4. 在这些局部策略形成稳定反制池后，再使用CFR式增量扩池；每轮只把训练中发现的回应放入"
              "下一版，并用全新留出种子验收，避免在同一批结果上反复优化。", "",
              "## 复查入口", "",
              f"- [冻结协议](refinement_protocol_v05.md)、[配置](../configs/refinement_v05.json)、"
              "[结果清单](../results/v05/manifest.json)。",
              "- [完整留出原始结果](../results/v05/test.json)、[条件与规则敏感性](../results/v05/sensitivity.json)、"
              "[受限矩阵解](../results/v05/restricted_matrix_solution.json)。",
              "- [独立核验](../results/v05_integrity_audit.json)、"
              "[归档策略源码](../results/v05/source/mafia_lab/strategies_v05.py)。", "",
              "```sh", "python3 scripts/run_refinement_v05.py --output results/v05_reproduction --workers 4",
              "python3 scripts/analyze_restricted_matrix_v05.py",
              "python3 scripts/verify_refinement_v05.py results/v05 --replay --output results/v05_integrity_audit.json",
              "python3 scripts/build_refinement_report_v05.py", "```", ""]
    # Imported here to keep the exact rational weights visible in the prose.
    output = ROOT / "docs/refinement_results_v05.md"
    output.write_text("\n".join(lines))
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
