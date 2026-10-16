# v10：公共协调、专门反制与扩展矩阵受限均衡

> 2026-10-16证据更正：留出开发隔离、协调实现、回应时点与误差界的解释以[更正记录](evidence_corrections_20261016.md)为准。以下数值及历史报告保留；不能继续将该评估集称为开发过程完全未读的最终验证。

本轮在4警、4匪、8民上执行232,960局完整对局。训练矩阵使用46,592局，在读取留出前冻结三类匪方回应和双方混合；独立留出矩阵使用186,368局。矩阵规模为7种好人策略×13种匪策略。

## 阶段结论

**三类针对性回应都学到低权重版本，而且选择在留出中完全复现。**集中目标回应选择`concentration_w2`，分散目标回应选择`dispersion_w2`，警察跟随时点回应选择`follow_w2`。三个家族的训练最优权重在留出各自目标策略上仍取得最低经验胜率；不过相邻权重差小于本轮保守误差界，因此这里只确认排序复现，不能确认`w2`本身是稳定最优强度。更强权重在本批样本中没有带来更强反制。

**新增的非探测公共协调协议没有成为强基线。**首日由所有好人执行“前半提出、后半收敛”，第二日起恢复普通推理。立即释放、公开目标后跟随、晚位跟随三种版本的留出最差胜率分别为10.84%、9.67%、8.20%，均未进入混合支持。固定公共程序虽然提高同步程度，但公开可预测性让`origin`反制稳定利用它，因此本候选不晋级。

**训练扩展矩阵存在精确零间隙的受限混合解。**经验训练值为27.41%；好人以2/3选择`crossfit_table`、1/3选择`probe_w8_anchor`，匪方以104/147选择`combined_det`、43/147选择`origin_det`。精确分数单纯形及逐纯策略重算的训练上下界均为421/1536，间隙为0。这里的“精确”只指给定经验矩阵的代数求解。

**冻结训练混合在独立留出上的价值大体稳定，但支持尚未收敛。**冻结好人混合的留出最差列为26.74%，冻结匪混合的留出最佳回应为30.64%，样本外间隙为3.89%。留出事后受限值为28.80%；好人支持仍是`crossfit_table + probe_w8_anchor`，但权重改为415/521与106/521；匪方支持变为`origin_det + concentration_w2`。价值接近而匪方支持漂移，下一轮仍需增量扩池。

**当前最稳健纯策略仍是交叉拟合表。**其留出最差胜率为26.86%，最差对手已经从普通`combined`转为新学到的`concentration_w2`。集中探测的纯策略最差胜率只有16.16%，但它对多列匪策略收益很高，所以作为混合中的补充策略仍有价值。

## 三类回应的独立留出

| 回应家族 | 目标策略 | 训练选择 | 留出最优 | 各权重下好人胜率 |
| --- | --- | --- | --- | --- |
| concentrated_target | probe_w8_anchor | concentration_w2 | concentration_w2 | concentration_w2=36.43% / concentration_w4=36.62% / concentration_w8=36.62% |
| dispersed_targets | probe_w8_diverse | dispersion_w2 | dispersion_w2 | dispersion_w2=35.99% / dispersion_w4=37.11% / dispersion_w8=36.43% |
| police_follow_timing | coord_deliberative_public | follow_w2 | follow_w2 | follow_w2=28.91% / follow_w4=30.42% / follow_w8=31.69% |

## 留出纯策略摘要

| 好人策略 | 最差胜率 | 最差对手 | 13列平均胜率 |
| --- | --- | --- | --- |
| crossfit_table | 26.86% | concentration_w2 | 40.32% |
| coord_deliberative_immediate | 10.84% | origin_det | 25.29% |
| coord_deliberative_public | 9.67% | origin_det | 23.37% |
| coord_deliberative_late | 8.20% | origin_det | 22.09% |
| probe_w8_diverse | 18.65% | combined_det | 29.02% |
| probe_w8_anchor | 16.16% | origin_det | 40.12% |
| probe_w8_pair | 14.16% | origin_det | 35.46% |

## 留出矩阵

每格2,048个自然开局，好人终局胜率。

| 好人策略 | combined_det | origin_det | echo_det | echo_mimic_det | concentration_w2 | concentration_w4 | concentration_w8 | dispersion_w2 | dispersion_w4 | dispersion_w8 | follow_w2 | follow_w4 | follow_w8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| crossfit_table | 27.59% | 32.03% | 43.46% | 31.15% | 26.86% | 28.37% | 28.42% | 49.12% | 50.59% | 50.63% | 50.78% | 52.00% | 53.17% |
| coord_deliberative_immediate | 21.44% | 10.84% | 33.20% | 36.23% | 18.02% | 20.12% | 20.12% | 22.80% | 23.54% | 23.58% | 31.49% | 33.01% | 34.38% |
| coord_deliberative_public | 19.38% | 9.67% | 32.42% | 35.64% | 16.65% | 18.85% | 18.90% | 19.97% | 20.61% | 20.65% | 28.91% | 30.42% | 31.69% |
| coord_deliberative_late | 18.70% | 8.20% | 32.91% | 36.47% | 16.02% | 18.12% | 18.16% | 15.58% | 16.06% | 16.02% | 28.56% | 30.42% | 31.93% |
| probe_w8_diverse | 18.65% | 21.34% | 48.14% | 36.04% | 20.65% | 21.63% | 21.88% | 35.99% | 37.11% | 36.43% | 21.29% | 27.15% | 30.96% |
| probe_w8_anchor | 36.62% | 16.16% | 58.50% | 50.83% | 36.43% | 36.62% | 36.62% | 28.17% | 28.56% | 28.56% | 53.17% | 54.79% | 56.49% |
| probe_w8_pair | 28.56% | 14.16% | 57.62% | 42.87% | 32.62% | 33.69% | 33.74% | 28.47% | 28.91% | 28.96% | 39.60% | 43.90% | 47.85% |

## 受限混合证书与边界

| 量 | 结果 |
| --- | --- |
| 训练经验矩阵值 | 27.41% (421/1536) |
| 训练精确间隙 | 0 |
| 冻结好人混合留出下界 | 26.74% (1643/6144) |
| 冻结匪混合留出上界 | 30.64% (92233/301056) |
| 样本外回应间隙 | 3.89% (5863/150528) |
| 留出事后受限值 | 28.80% (153663/533504) |

固定加权逐种子收益的20项家族Hoeffding 95%半宽为4.04%。样本外间隙与该保守误差量级相近，因此不能把3.89pp直接解释为真实可利用度。更关键的是，这些混合要求阵营在局前共享同一个秘密策略索引；普通规则未必提供这种相关装置。

本轮结果依次属于：固定策略胜率、候选池内经验最优回应、经验矩阵受限均衡。它没有枚举完整声明空间、没有证明遗憾收敛，也没有给出未限制最佳回应，因此不是完整游戏GTO。

独立核验重算91个训练单元、91个留出单元、3条回应选择、训练与留出事后两个精确零间隙证书及冻结混合上下界，并重放182局；全部通过。

## 复查入口

- [冻结协议](equilibrium_protocol_v10.md)、[配置](../configs/equilibrium_v10.json)、[结果清单](../results/v10/manifest.json)。
- [留出前选择与训练均衡](../results/v10/selection_before_holdout.json)、[留出矩阵](../results/v10/holdout.json)、[分析](../results/v10/analysis.json)。
- [独立核验](../results/v10_integrity_audit.json)、[归档策略源码](../results/v10/source/mafia_lab/strategies_v10.py)。

```sh
python3 scripts/run_equilibrium_v10.py --output results/v10_reproduction --workers 4
python3 scripts/analyze_equilibrium_v10.py
python3 scripts/verify_equilibrium_v10.py results/v10 --replay --output results/v10_integrity_audit.json
python3 scripts/build_equilibrium_report_v10.py
```
