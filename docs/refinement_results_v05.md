# v05：16人局策略拆分、提名顺序反制与受限混合分析

日期：2026-10-11。主配置和全部敏感性配置均为4警、4匪、8民。

本轮完成 **114,944局真实终局模拟**：11种好人策略×7种匪策略，每格训练256局、独立留出1,024局，另有全16人规则敏感性。独立核验覆盖170个实验单元、680个条件摘要、142项配对统计，并用归档代码重放340局。

这些结果是冻结策略池内的终局胜率和反制关系。它们不是16人完整GTO、行为策略纳什均衡、完整最佳回应或教学迁移证据。

## 主要结论

**公开跟随形成的全掩护仍泄露“谁先发起”。**在 `cover100` 下，匪方从综合评分改为追踪第一提名者，好人胜率由30.47%降至9.96%，差值-20.51 ★pp。平民都跟票并没有抹掉发言顺序，最早暴露共同目标的人仍可成为警察代理信号。

**随机全掩护能反制追发起者，却形成新的可利用结构。**把平民目标从公开跟随改为随机，面对追发起者时由9.96%升至85.55%，差值+75.59 ★pp；面对综合反制却从30.47%降至2.93%。训练回应链进一步呈现循环：`cover100/origin_mimic` 9.96% → `random_inspect/origin_mimic` 86.91% → `random_inspect/combined_split` 3.32%。因此当前最重要的结构是反制循环，而不是单一最佳声明规则。

**v04中票型验人的增益没有在全掩护基线上复现。**v04是在50%提名且双方使用票型投票的组合上再加入定向验人；本轮干净的 `inspect_only` 相对`cover100`，七个对手的点估计为-0.29至+5.08pp，没有一项通过139项家族界。这说明原增益依赖当时的策略组合或交互，尚不能归因于验人规则本身。只开警察票型投票、只开平民票型投票或双方都开，整体没有形成稳健收益；双方都开在综合、只看票型和假跳对手下分别显著降低13.09、15.62和15.92pp。当前评分不应升级为默认投票法。

**75%频率没有改善当前最差结构。**平民掩护从100%降到75%，面对综合及综合散票反制分别显著下降15.14和14.65pp。只把警察无查杀提名率降到75%未产生通过家族界的收益。继续调单一固定频率的价值有限，下一步应研究依赖公开序位与历史的局部随机化。

**首夜分支解释了风险集中位置。**在 `cover100/origin_mimic` 中，首死警察时好人胜率5.11%，首死平民时12.50%；`random_inspect/origin_mimic` 对应73.30%和94.05%。这些是自然条件分支，不是对首死身份的随机干预；它们适合定位后续受控实验，不能单独当因果效应。

## 留出胜率矩阵

所有单元均为独立留出种子的好人终局胜率，每格1,024局。

| 好人策略 | 综合 | 追发起者 | 只看票型 | 综合+散票 | 发起者+散票 | 发起者半频 | 发起者假跳 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cover100 | 30.47% | 9.96% | 34.86% | 30.47% | 10.06% | 26.56% | 51.56% |
| cover100_random | 2.93% | 85.55% | 62.11% | 3.32% | 91.50% | 97.95% | 100.00% |
| inspect_only | 31.05% | 15.04% | 34.86% | 30.76% | 9.96% | 28.91% | 51.27% |
| police_vote | 21.48% | 7.91% | 25.29% | 30.76% | 10.55% | 17.68% | 35.64% |
| civilian_vote | 23.63% | 9.38% | 26.95% | 18.46% | 7.52% | 25.39% | 51.56% |
| both_vote | 17.38% | 7.71% | 19.24% | 18.55% | 7.71% | 17.19% | 35.64% |
| inspect_police_vote | 31.15% | 15.04% | 34.86% | 31.25% | 10.74% | 29.10% | 51.17% |
| cover75 | 15.33% | 10.25% | 45.61% | 15.82% | 10.55% | 23.24% | 43.55% |
| police75 | 32.42% | 9.47% | 25.98% | 32.81% | 10.35% | 25.78% | 54.49% |
| both75 | 18.46% | 8.69% | 33.98% | 19.73% | 9.47% | 23.05% | 49.51% |
| random_inspect | 7.42% | 86.91% | 64.94% | 3.32% | 91.31% | 97.75% | 99.80% |

## 预声明好人策略比较

数值为后项减前项的好人胜率百分点。★表示家族95% Hoeffding区间不跨0；该界同时覆盖139项预声明比较，半宽约12.98pp。

| 前项 → 后项 | 综合 | 追发起者 | 只看票型 | 综合+散票 | 发起者+散票 | 发起者半频 | 发起者假跳 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cover100 → cover100_random | -27.54 ★ | +75.59 ★ | +27.25 ★ | -27.15 ★ | +81.45 ★ | +71.39 ★ | +48.44 ★ |
| cover100 → inspect_only | +0.59 | +5.08 | +0.00 | +0.29 | -0.10 | +2.34 | -0.29 |
| cover100 → police_vote | -8.98 | -2.05 | -9.57 | +0.29 | +0.49 | -8.89 | -15.92 ★ |
| cover100 → civilian_vote | -6.84 | -0.59 | -7.91 | -12.01 | -2.54 | -1.17 | +0.00 |
| cover100 → both_vote | -13.09 ★ | -2.25 | -15.62 ★ | -11.91 | -2.34 | -9.38 | -15.92 ★ |
| police_vote → both_vote | -4.10 | -0.20 | -6.05 | -12.21 | -2.83 | -0.49 | +0.00 |
| civilian_vote → both_vote | -6.25 | -1.66 | -7.71 | +0.10 | +0.20 | -8.20 | -15.92 ★ |
| inspect_only → inspect_police_vote | +0.10 | +0.00 | +0.00 | +0.49 | +0.78 | +0.20 | -0.10 |
| cover100 → cover75 | -15.14 ★ | +0.29 | +10.74 | -14.65 ★ | +0.49 | -3.32 | -8.01 |
| cover100 → police75 | +1.95 | -0.49 | -8.89 | +2.34 | +0.29 | -0.78 | +2.93 |
| cover100 → both75 | -12.01 | -1.27 | -0.88 | -10.74 | -0.59 | -3.52 | -2.05 |
| cover100_random → random_inspect | +4.49 | +1.37 | +2.83 | +0.00 | -0.20 | -0.20 | -0.20 |

`police_vote → both_vote`是加入平民票型投票的边际效果；`civilian_vote → both_vote`是加入警察票型投票的边际效果。`inspect_only → inspect_police_vote`测试在定向验人之外再改警察投票。

## 预声明匪方反制比较

负值表示新匪策略使好人胜率下降，即匪方获益。`split`同时改变四名匪的白天投票分布，并不改变其夜刀评分。

| 固定好人 | combined_mimic → origin_mimic | combined_mimic → combined_split | origin_mimic → origin_split | origin_mimic → origin_half | origin_mimic → origin_fake |
| --- | --- | --- | --- | --- | --- |
| cover100 | -20.51 ★ | +0.00 | +0.10 | +16.60 ★ | +41.60 ★ |
| cover100_random | +82.62 ★ | +0.39 | +5.96 | +12.40 | +14.45 ★ |
| inspect_only | -16.02 ★ | -0.29 | -5.08 | +13.87 ★ | +36.23 ★ |
| police_vote | -13.57 ★ | +9.28 | +2.64 | +9.77 | +27.73 ★ |
| civilian_vote | -14.26 ★ | -5.18 | -1.86 | +16.02 ★ | +42.19 ★ |
| both_vote | -9.67 | +1.17 | +0.00 | +9.47 | +27.93 ★ |
| inspect_police_vote | -16.11 ★ | +0.10 | -4.30 | +14.06 ★ | +36.13 ★ |
| cover75 | -5.08 | +0.49 | +0.29 | +12.99 ★ | +33.30 ★ |
| police75 | -22.95 ★ | +0.39 | +0.88 | +16.31 ★ | +45.02 ★ |
| both75 | -9.77 | +1.27 | +0.78 | +14.36 ★ | +40.82 ★ |
| random_inspect | +79.49 ★ | -4.10 | +4.39 | +10.84 | +12.89 |

追发起者并非普遍更强：它压制公开跟随，却被随机掩护反向利用。半频提名和假跳多数使好人胜率上升，说明这些伪装在当前执行规则下付出的白天协调成本大于隐蔽收益。

## 训练选择与留出回应链

训练阶段选择：`cover100` → `origin_mimic` → `random_inspect` → `combined_split`。训练最大化最差纯方案为 `inspect_police_vote`，其训练最强对手为 `origin_split`。

| 比较 | 起点 | 终点 | 胜率 | 差值pp | 逐点正态95% | 逐点有界95% |
| --- | --- | --- | --- | --- | --- | --- |
| respond_to_mafia | cover100 / origin_mimic | random_inspect / origin_mimic | 9.96% → 86.91% | +76.95 | [+74.26, +79.65] | [+68.46, +85.44] |
| mafia_counter_response | random_inspect / origin_mimic | random_inspect / combined_split | 86.91% → 3.32% | -83.59 | [-85.86, -81.32] | [-92.08, -75.11] |
| robust_at_train_worst | cover100 / origin_split | inspect_police_vote / origin_split | 10.06% → 10.74% | +0.68 | [+0.05, +1.32] | [-7.80, +9.17] |

这些回应链是训练选择后的逐点评价，不属于139项家族界。纯策略“稳健”只表示训练矩阵中最大化最差单元；留出集中 `inspect_police_vote/origin_split` 为10.74%，相对`cover100/origin_split`仅+0.68pp，保守有界区间仍跨0。

## 首夜条件分支

四个分支在每个主矩阵单元中分别有相同的自然分母：首死警察352、首死平民672、首验中匪341、首验好人683。首夜尚无公开历史且本轮自刀率为0，因此各策略共享相同首夜动作分布。

| 好人 / 匪 | 首死警 | 首死民 | 首验匪 | 首验好人 |
| --- | --- | --- | --- | --- |
| cover100 / origin_mimic | 5.11% | 12.50% | 6.16% | 11.86% |
| random_inspect / origin_mimic | 73.30% | 94.05% | 92.96% | 83.89% |
| random_inspect / combined_split | 1.14% | 4.46% | 4.69% | 2.64% |
| inspect_police_vote / origin_split | 5.68% | 13.39% | 7.04% | 12.59% |
| inspect_only / combined_mimic | 27.84% | 32.74% | 21.11% | 36.02% |

`cover100/origin_mimic`中首验匪反而低于首验好人，说明“查中”并不会自动转化成收益：公开提名顺序同时帮助匪方定位发起者。`random_inspect/origin_mimic`中首验匪则更有利。后续应固定同一首夜状态，直接干预警察的发言时点，才能区分验人价值与选择偏差。

## 冻结候选矩阵的受限混合解

对训练胜率矩阵做精确有理数零和求解，得到的是有限候选计划的矩阵均衡。它要求一个只对同阵营可见的赛前装置，把同一个策略编号发给所有好人；普通警匪局没有这种装置，因此该解不能直接作为可执行GTO。它仍可判断反制循环是否需要混合。

训练矩阵值为28.52%。好人混合为 `police75` 75.40%、`random_inspect` 24.60%；匪方混合为 `combined_mimic` 72.62%、`origin_mimic` 27.38%。

把训练选出的两边混合权重原样用于留出集，期望好人胜率为26.89%，逐点正态95%区间[25.19%, 28.59%]。该好人混合面对留出集中最差的单一匪策略为 `combined_split`，胜率25.56%。这比任何单个方案更好地覆盖了公开/随机掩护的相反弱点，但相关团队混合假设尚不可执行。

## 16人规则敏感性

| 规则 | 好人 | 匪 | 好人胜率 |
| --- | --- | --- | --- |
| 16_reference | cover100 | combined_mimic | 29.59% |
| 16_reference | cover100 | origin_split | 14.16% |
| 16_reference | inspect_police_vote | combined_mimic | 28.71% |
| 16_reference | inspect_police_vote | origin_split | 15.72% |
| 16_pk | cover100 | combined_mimic | 30.66% |
| 16_pk | cover100 | origin_split | 14.45% |
| 16_pk | inspect_police_vote | combined_mimic | 30.18% |
| 16_pk | inspect_police_vote | origin_split | 15.82% |
| 16_four_last_words | cover100 | combined_mimic | 29.49% |
| 16_four_last_words | cover100 | origin_split | 14.16% |
| 16_four_last_words | inspect_police_vote | combined_mimic | 28.71% |
| 16_four_last_words | inspect_police_vote | origin_split | 15.72% |
| 16_reverse_direction | cover100 | combined_mimic | 27.83% |
| 16_reverse_direction | cover100 | origin_split | 10.55% |
| 16_reverse_direction | inspect_police_vote | combined_mimic | 28.52% |
| 16_reverse_direction | inspect_police_vote | origin_split | 11.62% |

PK和四次遗言没有改变主要排序。反向发言在追发起者对手下进一步降低两项好人策略的胜率，说明发言方向会改变谁更常成为第一提名者；位置机制需要在两个方向都检验。

## 下一阶段

1. 构造无需阵营秘密相关装置的局部混合：玩家仅按自己的座位、发言序位和公开历史抽样，逼近矩阵混合对反制循环的覆盖效果。

2. 固定相同首夜状态，分别干预首验中匪后的早提名、晚提名、静默及由平民先发起，直接估计首日信息释放时点。

3. 将匪方散票细分为不牺牲主要放逐目标的有限伪装，并加入识别“第一发起者可能是匪诱饵”的好人反制。

4. 在这些局部策略形成稳定反制池后，再使用CFR式增量扩池；每轮只把训练中发现的回应放入下一版，并用全新留出种子验收，避免在同一批结果上反复优化。

## 复查入口

- [冻结协议](refinement_protocol_v05.md)、[配置](../configs/refinement_v05.json)、[结果清单](../results/v05/manifest.json)。
- [完整留出原始结果](../results/v05/test.json)、[条件与规则敏感性](../results/v05/sensitivity.json)、[受限矩阵解](../results/v05/restricted_matrix_solution.json)。
- [独立核验](../results/v05_integrity_audit.json)、[归档策略源码](../results/v05/source/mafia_lab/strategies_v05.py)。

```sh
python3 scripts/run_refinement_v05.py --output results/v05_reproduction --workers 4
python3 scripts/analyze_restricted_matrix_v05.py
python3 scripts/verify_refinement_v05.py results/v05 --replay --output results/v05_integrity_audit.json
python3 scripts/build_refinement_report_v05.py
```
