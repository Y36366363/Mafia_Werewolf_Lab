"""Render the complete frozen v04 results and prespecified comparisons."""
import json
from math import log, sqrt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mafia_lab.statistics import paired_summary
from scripts.verify_large_game_v04 import validate_directory


def pct(x):
    return f"{100*x:.2f}%"


def delta(x):
    return f"{100*x:+.2f}"


def bounds(values):
    return f"[{100*values[0]:+.2f}, {100*values[1]:+.2f}]"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                       "| " + " | ".join(["---"] * len(headers)) + " |"] +
                      ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    folder = ROOT / "results/v04"
    audit = validate_directory(folder)
    read = lambda name: json.loads((folder / f"{name}.json").read_text())
    manifest, train, test, sensitivity = map(read, ("manifest", "train", "test", "sensitivity"))
    config = manifest["config"]
    selection = train["selection"]
    cells = {(c["good"], c["mafia"]): c for c in test["cells"]}
    contrasts = test["all_prespecified_contrasts"]
    contrast_index = {(r["side"], r["control"], r["treatment"], r["fixed_opponent"]): r["paired"]
                      for r in contrasts}
    good_names, mafia_names = test["matrix"]["good"], test["matrix"]["mafia"]
    mafia_labels = ["信号模仿", "频率模仿", "票型模仿", "综合模仿", "综合半频", "综合假查杀"]
    count16 = sum(c["n"] for report in (train, test, sensitivity) for c in report["cells"]
                  if sum(c["rules"][k] for k in ("police", "mafia", "civilians")) == 16)
    count12 = manifest["executed_games"] - count16
    cover = contrast_index["good", "uncovered", "cover100", "combined_mimic"]
    ballot = [contrast_index["good", "hit_mix50", "ballot_mix50", m]["delta"] for m in mafia_names]
    inspect = [contrast_index["good", "ballot_mix50", "inspect_mix50", m]["delta"] for m in mafia_names]
    text = ["# v04：16人局的平民掩护、角色混合与票型反制实验", "",
            "日期：2026-10-11。全部结论对应下面列出的固定策略、规则和独立留出样本。", "",
            f"本轮完成 **{manifest['executed_games']:,}局真实终局模拟**，其中**16人局{count16:,}局**、"
            f"12人迁移对照{count12:,}局。主实验为4警4匪8民、11×6策略矩阵；"
            "每格训练256局、留出评估1,024局。训练、评估与规则敏感性使用互不重叠的种子块。"
            f"各格共享开局种子用于配对，合计{audit['distinct_seed_units']:,}个不同种子单位；"
            "不能把全部执行局数当作同一结论的独立样本量。", "",
            "本轮完成策略评估和候选池内反制。提名概率是预设的局部行为参数；没有求出均衡频率，"
            "没有计算完整最佳回应或16人GTO，也没有验证教学向德州扑克的迁移。", "",
            "## 主要发现与保留决策", "",
            f"**全员平民掩护值得保留，但不能推成普遍最优。**训练选出的稳健纯方案 `cover100` "
            f"在综合反制下将好人胜率从{pct(cells['uncovered', 'combined_mimic']['summary']['rate'])}"
            f"提高到{pct(cells['cover100', 'combined_mimic']['summary']['rate'])}，差值{delta(cover['delta'])}pp，"
            f"115项同时校正的95%有界区间为{bounds(cover['ci95_familywise_hoeffding'])}pp。"
            "不过在只使用票型的匪策略下，它反而从71.00%降至33.59%。掩护收益取决于对手利用哪种信息。", "",
            "**少量掩护容易被频率反制。**50%掩护面对仅识别提名者的匪策略有55.86%胜率，"
            "面对综合反制仅6.54%；100%掩护则由55.66%降至30.08%。因此增加掩护后，"
            "还必须让杀手识别提名频率、共同目标及历史票型，才能检验优势能保留多少。", "",
            "**随机少说不能自动提高收益。**把警察提名率固定降到50%，在6个对手中有3个胜率下降、"
            "3个上升。改为有活查杀时必提名，6个点估计均回升，2项通过保守家族区间；"
            "这支持继续研究按私有信息选择发言时机，没有支持50%这个频率本身最优。", "",
            f"**当前票型投票规则暂不升级为默认策略。**相同其他条件下，6个对手的胜率差均为负"
            f"（{delta(min(ballot))}至{delta(max(ballot))}pp），3项家族区间排除0。"
            "不能据此断言票型信息无用：这里测试的是会误伤好人共同投票的特定评分。"
            f"把历史评分用于选择验人目标后，相对已有票型投票方案，6个点估计均改善"
            f"（{delta(min(inspect))}至{delta(max(inspect))}pp），其中4项通过家族区间。"
            "保留定向验人为候选；还需要单独测试它与没有票型投票干预的组合。", "",
            "**规则小改动不能直接外推。**另一批16人样本中，全掩护对综合反制胜率30.47%；"
            "加入PK为31.35%，改四次遗言为30.27%。12人相同策略为39.84%。"
            "这些是特定组合的敏感性结果，12人胜率不能代替16人结论。", "",
            "下一轮仍以16人为主，优先拆开警察与平民的票型投票开关、加入只定向验人的干净对照；"
            "在全掩护附近搜索行动频率，并给匪方加入区分提名发起者/跟随者、伪装历史票型的回应。"
            "全掩护的随机目标对照也应补齐，以区分身份掩护与公开协调。所有新选择另用训练和留出种子，"
            "当前结果不能重复充当下一轮独立验证。", "",
            "## 1. 可执行策略与规则", "",
            "警察全灭则匪胜，匪全灭则好人胜；不采用人数持平胜利。每晚共同验人、共同刀人；"
            "首夜死亡警察收到当夜结果；不翻身份。基线前三次死亡有遗言，固定方向发言，"
            "同时投票，唯一最高票放逐；平票直接入夜。所有候选本轮自刀率固定为0，"
            "允许自刀的裁判规则和旧版自刀结果仍保留，本轮不重新评价自刀。", "",
            "警察和平民未提名时均使用同一个普通身份声明。警察若选择提名，有活查杀时优先该目标；"
            "投票始终优先合法候选中的已验匪。无活查杀时，从合法未知目标按公开顺序形成共同目标。"
            "平民提名的public版本跟随当日公开提名多数"
            "（并列随机，无提名时选发言序首个其他存活者），random版本随机选其他存活者。"
            "平民不能辨认真警，也可能跟随匪方提名。", "",
            table(["好人策略", "平民提名率", "警察无活查杀提名率", "有活查杀提名率", "票型投票", "票型验人", "掩护目标"],
                  [[p["name"], pct(p["civilian_cover_probability"]), pct(p["police_nominate_probability"]),
                    pct(p["hit_nominate_probability"]), "开" if p["vote_reasoning"] else "关",
                    "开" if p["inspect_reasoning"] else "关", p["cover_target"]] for p in config["good_policies"]]), "",
            "票型启发式：警察依据私有已验匪的历史同票率给未知目标加分，保留已知身份约束；"
            "原共同目标在历史分并列最高时优先。平民只看反复同票的公开关系，至少两个共同轮次才加分，"
            "上限0.5。该分数可能误伤好人协调，不是身份后验。票型验人单独开关；"
            "无历史时两个投票开关状态完全相同。", "",
            table(["简称", "匪方策略", "信息评分", "白天声明"],
                  [[label, p["name"], p["inference"],
                    "首位存活队友假查杀" if p["bluff"] == "always" else f"每名匪以{pct(p['nomination_probability'])}概率提名"]
                   for label, p in zip(mafia_labels, config["mafia_policies"])]), "",
            "匪方信号分看是否提名/跳警；频率分再看提名频率和共同目标；票型分看某人过去投己方匪的比例；"
            "综合分合并这些特征。评分同时用于夜刀、白天提名或假查杀对象及投票，属于整套信息反制。"
            "它只读公开记录及己方名单。每个发言者每天至多一个提名样本；每天只保留最后公开的完整票型，"
            "首轮票收齐前不可读取。精确系数见归档策略源码。", "",
            "## 2. 独立留出胜率矩阵", "",
            "所有数值为好人终局胜率，每格1,024局。这里只描述全部候选；候选选择发生在训练集。", "",
            table(["好人策略"] + mafia_labels,
                  [[g] + [pct(cells[g, m]["summary"]["rate"]) for m in mafia_names] for g in good_names]), "",
            "v04的匪方发言/投票评分、普通声明和部分协调细节有明确版本变更，"
            "所以不要直接用v03百分比减去v04百分比解释单个新增特性的因果效果。下面全部使用v04内部配对对照。", "",
            "## 3. 训练选择后的反制链", "",
            f"训练选择：基线 `{selection['baseline_good']}` → 匪回应 `{selection['mafia_response']}` → "
            f"好人回应 `{selection['good_response']}` → 匪再回应 `{selection['second_mafia_response']}`。"
            f"训练中最大化最差胜率的纯方案是 `{selection['robust_pure_good']}`，"
            f"其训练最强对手为 `{selection['robust_train_worst_mafia']}`。这些名字在首个留出对局之前已保存。", ""]
    rows = []
    for r in test["selected_heldout_comparisons"]:
        a, b, stats = cells[tuple(r["control"])], cells[tuple(r["treatment"])], r["paired"]
        rows.append([r["name"], " / ".join(r["control"]), " / ".join(r["treatment"]),
                     f"{pct(a['summary']['rate'])} → {pct(b['summary']['rate'])}", delta(stats["delta"]),
                     bounds(stats["ci95_normal"]), bounds(stats["ci95_hoeffding"])])
    text += [table(["比较", "起点：好人/匪", "终点：好人/匪", "好人胜率", "差值pp", "逐点正态95%", "逐点有界95%"], rows), "",
             "训练选择的回应和再回应可能相同，这只表示这次候选池搜索没有找到另一项回应。"
             "三个回应链区间是逐点区间，不属于以下115项预声明比较的家族区间。", "",
             "## 4. 全部预声明配对比较", "",
             f"下表单位为好人胜率百分点（pp），均为后项减前项。**★**表示家族95% Hoeffding区间不跨0；"
             f"它同时覆盖预先冻结的{len(contrasts)}项比较，共享种子不破坏此联合界。"
             f"每项保守半宽约{100*sqrt(2*log(2*len(contrasts)/.05)/config['test']['n']):.2f}pp。"
             "无★不等于没效果；小差值可能需要更多样本。逐点正态区间仅作探索性描述。", ""]

    def contrast_cell(side, a, b, other):
        s = contrast_index[side, a, b, other]
        lo, hi = s["ci95_familywise_hoeffding"]
        return delta(s["delta"]) + (" ★" if lo > 0 or hi < 0 else "")

    text += [table(["好人：前项 → 后项"] + mafia_labels,
                   [[f"{r['control']} → {r['treatment']}"] +
                    [contrast_cell("good", r["control"], r["treatment"], m) for m in mafia_names]
                    for r in config["good_contrasts"]]), "",
             "`ballot_mix50 → ballot_low25` 同时降低平民与警察常规提名率，应解释为组合变化。"
             "`cover50 → fixed_mix50` 同时把警察有/无活查杀两种提名率从1降到0.5，测试统一降低提名率。"
             "其余好人对照按单一参数/开关变化解释；票型投票开关同时适用于警察和平民，"
             "不能分别归因于其中某个角色。", "",
             table(["固定好人"] + [f"{r['control']} → {r['treatment']}" for r in config["mafia_contrasts"]],
                   [[g] + [contrast_cell("mafia", r["control"], r["treatment"], g)
                            for r in config["mafia_contrasts"]] for g in good_names]), "",
             "匪方对照中负值意味着好人胜率下降，即匪方获益。更多特征或更复杂评分不保证更强，"
             "必须按实际对照判断。", "",
             "## 5. 配置与规则敏感性", "",
             "使用第三组独立的1,024个种子，只测试训练选出的稳健纯方案与基线，以及两个训练固定对手。"
             "16人PK、四次遗言与标准规则按同种子配对。12人是3警3匪6民的迁移结果，"
             "身份分配已变，不能把差值单独归因于某种行动技巧。", ""]
    rows = []
    reference = {(c["good"], c["mafia"]): c for c in sensitivity["cells"] if c["rules"] == config["rules"]}
    for cell in sensitivity["cells"]:
        label = next(v["name"] for v in config["sensitivity"]["rule_variants"] if v["rules"] == cell["rules"])
        ci = cell["summary"]["ci95_wilson"]
        stats = paired_summary(reference[cell["good"], cell["mafia"]]["raw_outcomes"], cell["raw_outcomes"])
        rows.append([label, cell["good"], cell["mafia"], pct(cell["summary"]["rate"]),
                     f"[{pct(ci[0])}, {pct(ci[1])}]", delta(stats["delta"]), bounds(stats["ci95_normal"])])
    text += [table(["配置", "好人", "匪", "好人胜率", "逐点Wilson95%", "相对同批16标准pp", "配对正态95%"], rows), "",
             "敏感性表的区间均为逐点探索性区间，未加入115项家族保证；标准行的零差值是同一数据与自身相减。", "",
             "## 6. 可复查证据", "",
             "101项完整测试通过（包括SciPy独立LP交叉核对）。独立脚本从原始0/1结果重算每格胜率、"
             "Wilson区间、配对计数、正态/有界区间、家族区间、训练选择和局数；"
             "独立审计已通过148个实验单元、118项配对统计，并用归档源码重放296条首尾种子对局，"
             "检查真实终局与夜数。源码哈希在各阶段结束时保持不变。", "",
             f"- [结果清单](../results/v04/manifest.json)：{manifest['executed_games']:,}局，"
             f"运行{manifest['elapsed_seconds']:.1f}秒，源码SHA256 `{manifest['source_sha256']}`。",
             "- [独立审计](../results/v04_integrity_audit.json)、[训练选择](../results/v04/selection_before_test.json)、"
             "[完整留出原始结果](../results/v04/test.json)、[规则敏感性](../results/v04/sensitivity.json)。",
             "- [冻结协议](large_game_protocol_v04.md)、[配置](../results/v04/source/config.json)、"
             "[策略源码](../results/v04/source/mafia_lab/strategies_v04.py)。", "",
             "复现时使用新输出路径，已完成结果不会覆盖。即使未来当前策略发生变化，也可运行归档入口：", "",
             "```sh", "python3 results/v04/source/scripts/run_large_game_v04.py \\",
             "  --config results/v04/source/config.json --output results/v04_reproduction --workers 4",
             "python3 scripts/verify_large_game_v04.py results/v04 --replay --output results/v04_integrity_audit.json",
             "python3 scripts/build_large_game_report_v04.py", "```", ""]
    (ROOT / "docs/large_game_results_v04.md").write_text("\n".join(text), encoding="utf-8")
    print("docs/large_game_results_v04.md")


if __name__ == "__main__":
    main()
