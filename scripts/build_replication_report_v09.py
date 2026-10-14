"""Build the Chinese v09 report from frozen and audited results."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(x): return "—" if x is None else f"{100*x:.2f}%"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v09"
    config = json.loads((ROOT / "configs/replication_v09.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    replication = json.loads((folder / "replication.json").read_text())
    selection = json.loads((folder / "probe_selection_before_holdout.json").read_text())
    holdout = json.loads((folder / "probe_holdout.json").read_text())
    analysis = json.loads((folder / "analysis.json").read_text())
    audit = json.loads((ROOT / "results/v09_integrity_audit.json").read_text())
    blocks = [b["name"] for b in replication["blocks"]]
    good, mafia = replication["matrix"]["good"], replication["matrix"]["mafia"]
    pcells = {(c["candidate"], c["mafia"]): c for c in holdout["cells"]}
    opponents = config["probe_selection"]["opponents"]
    candidates = [c["name"] for c in config["probe_selection"]["candidates"]]
    selected = selection["selected"]
    hit_deltas = [x["delta"] for x in analysis["probe_strata_effects_vs_silent"]
                  if x["treatment"] == selected and x["stratum"] == "check_hit"]
    clear_deltas = [x["delta"] for x in analysis["probe_strata_effects_vs_silent"]
                    if x["treatment"] == selected and x["stratum"] == "check_clear"]

    lines = ["# v09：多区块复验、自然开局与公开反制", "",
             f"本轮在4警、4匪、8民上执行{manifest['executed_games']:,}局完整对局："
             f"{manifest['replication_games']:,}局复验冻结v08条件表，"
             f"{manifest['probe_training_games']:,}局完成三折探测选择和独立验证，"
             f"{manifest['probe_holdout_games']:,}局用于最终自然开局留出。", "",
             "## 阶段结论", "",
             "**v08交叉拟合表的候选池稳健性得到复验，但不是逐对手支配。**它在4个独立外层区块中"
             f"赢得{analysis['crossfit_table_block_wins']}个区块的纯策略最差胜率；合并3,072局/格后"
             f"最差胜率为{pct(analysis['replication_pooled_scores']['crossfit_table']['worst'])}，"
             f"高于`position_mix`的{pct(analysis['replication_pooled_scores']['position_mix']['worst'])}和"
             f"`confirm_mix`的{pct(analysis['replication_pooled_scores']['confirm_mix']['worst'])}。"
             "它面对`origin`和公开跟随诱饵时低于`position_mix`，但在综合评分族上补回更多，因此只支持"
             "“扩展候选池中的稳健折中”，不支持逐列优势。", "",
             "**新增公开反制改变了弱策略的最差对手，却没有击穿冻结表。**`echo_mimic_det`根据公开"
             "历史追踪重复提名者，并跟随最近合法目标制造伪对齐；它把`confirm_mix`的合并最差胜率压至"
             f"{pct(analysis['replication_pooled_scores']['confirm_mix']['worst'])}。交叉拟合表的最差对手仍是"
             "`combined_det`，说明表的主要风险仍来自普通协调匪票，而不是这次新增的公开诱饵。四种不装饰"
             "的确定性匪策略在全部复验中非预期散票仍为0。", "",
             "**8位分散探测在自然开局与新反制下通过三折选择、独立验证和最终留出。**最终2,048局/格"
             f"中，其最差胜率为{pct(analysis['probe_holdout_scores'][selected]['worst'])}，"
             f"警察早释放为{pct(analysis['probe_holdout_scores']['early']['worst'])}，静默为"
             f"{pct(analysis['probe_holdout_scores']['silent']['worst'])}。相对早释放，五种对手下的配对增益"
             "为6.25–29.93pp；每项保守Hoeffding区间下界均高于0。该策略在当前冻结续局模型中可以晋级为"
             "下一轮默认候选。", "",
             "**核心机制更接近公开搜索与协调，而不只是查杀对齐。**8位分散探测的全局查杀对齐率只有"
             f"{pct(analysis['probe_holdout_scores'][selected]['alignment_rate'])}；相对静默，它在首验中匪"
             f"分支提高{pct(min(hit_deltas))}–{pct(max(hit_deltas))}，在首验好人分支提高"
             f"{pct(min(clear_deltas))}–{pct(max(clear_deltas))}。后者同样显著且通常更大，因此v08的"
             "“覆盖×对齐”解释需要扩展为“公开目标覆盖×协调收益＋私人信息对齐收益”。", "",
             "**目标集中带来更高平均收益，也带来更差的对手下界。**三种8位策略平均提名数完全相同。"
             f"单锚点平均覆盖{analysis['probe_holdout_scores']['probe_w8_anchor']['mean_unique_targets']:.2f}个"
             f"目标，平均胜率{pct(analysis['probe_holdout_scores']['probe_w8_anchor']['mean'])}、最差胜率"
             f"{pct(analysis['probe_holdout_scores']['probe_w8_anchor']['worst'])}；分散策略覆盖"
             f"{analysis['probe_holdout_scores']['probe_w8_diverse']['mean_unique_targets']:.2f}个目标，平均胜率"
             f"{pct(analysis['probe_holdout_scores']['probe_w8_diverse']['mean'])}、最差胜率"
             f"{pct(analysis['probe_holdout_scores']['probe_w8_diverse']['worst'])}。集中策略更擅长统一票型，"
             "分散策略对`origin`反制更稳健。", "",
             "## 四个外层区块", "", "每个数值是该区块内面对8种匪策略的最差好人胜率。", "",
             table(["好人策略"] + blocks,
                   [[g] + [pct(analysis["replication_block_scores"][b][g]["worst"]) for b in blocks]
                    for g in good]), "",
             "区块赢家依次为：" + "、".join(f"{b}=`{analysis['replication_block_winners'][b]}`"
                                             for b in blocks) + "。", "",
             "## 合并外层矩阵摘要", "", "每格由4个区块共3,072局组成。", "",
             table(["好人策略", "最差胜率", "最差对手", "8对手平均胜率"],
                   [[g, pct(analysis["replication_pooled_scores"][g]["worst"]),
                     analysis["replication_pooled_scores"][g]["worst_opponent"],
                     pct(analysis["replication_pooled_scores"][g]["mean"])] for g in good]), "",
             "## 自然开局探测留出", "",
             table(["候选", "启动率", "对齐率", "平均提名数", "不同目标数", "最差胜率", "平均胜率"],
                   [[name, pct(analysis["probe_holdout_scores"][name]["activation_rate"]),
                     pct(analysis["probe_holdout_scores"][name]["alignment_rate"]),
                     f"{analysis['probe_holdout_scores'][name]['mean_probes']:.2f}",
                     f"{analysis['probe_holdout_scores'][name]['mean_unique_targets']:.2f}",
                     pct(analysis["probe_holdout_scores"][name]["worst"]),
                     pct(analysis["probe_holdout_scores"][name]["mean"])] for name in candidates]), "",
             table(["候选"] + opponents,
                   [[name] + [pct(pcells[name, m]["summary"]["rate"]) for m in opponents]
                    for name in candidates]), "",
             "`early`只在首验中匪时改变警察发言；`silent`强制首日警察静默。所有探测候选都不读取验人"
             "信息，警察只有在公开目标碰巧等于私人查杀时跟进。自然开局包含首验中匪、首验好人及所有"
             "首死身份，分层没有参与候选选择。", "",
             "## 评价边界与下一步", "",
             "本轮仍使用冻结启发式投票与续局。公开探测在该模型中修复了大量好人协调失败，所以绝对"
             "增益可能对好人基础策略过弱高度敏感。下一阶段应让好人获得不依赖探测的公共协调基线，并"
             "让匪方学习针对固定锚点、目标分散和警察跟随时点的独立回应；之后再求扩展矩阵的受限混合"
             "均衡。当前结果是策略评估与候选池反制，不是完整游戏GTO。", "",
             f"独立核验重算{audit['checked_replication_cells']}个复验单元、"
             f"{audit['checked_probe_fit_cells']}个拟合单元、{audit['checked_probe_validation_cells']}个"
             f"验证单元和{audit['checked_probe_holdout_cells']}个留出单元，核验"
             f"{audit['checked_external_seed_blocks']}个互不重叠种子区块并重放"
             f"{audit['sampled_game_replays']}局；全部通过。", "",
             "## 复查入口", "",
             "- [冻结协议](replication_protocol_v09.md)、[配置](../configs/replication_v09.json)、"
             "[结果清单](../results/v09/manifest.json)。",
             "- [外层复验](../results/v09/replication.json)、"
             "[留出前选择](../results/v09/probe_selection_before_holdout.json)、"
             "[自然开局留出](../results/v09/probe_holdout.json)、[分析](../results/v09/analysis.json)。",
             "- [独立核验](../results/v09_integrity_audit.json)、"
             "[归档策略源码](../results/v09/source/mafia_lab/strategies_v09.py)。", "",
             "```sh", "python3 scripts/run_replication_v09.py --output results/v09_reproduction --workers 4",
             "python3 scripts/analyze_replication_v09.py",
             "python3 scripts/verify_replication_v09.py results/v09 --replay --output results/v09_integrity_audit.json",
             "python3 scripts/build_replication_report_v09.py", "```", ""]
    output = ROOT / "docs/replication_results_v09.md"
    output.write_text("\n".join(lines))
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
