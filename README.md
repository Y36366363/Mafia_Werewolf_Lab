# Mafia / Werewolf Lab

研究隐藏身份游戏中的策略与均衡，建立可验证的教学任务，最终检验推理训练向德州扑克的迁移。当前实现警匪游戏；狼人杀技能尚未加入。

**已实现可运行裁判、观察权限、完整对局、小模型精确求解、16人固定策略实验和反制评估。完整16人GTO与人类教学效果尚未得到验证。**

163项测试通过（含SciPy独立核对）。最新v10新增232,960次16人终局模拟，加入由全部好人执行的首日公共协调协议，分别训练集中目标、分散目标和警察跟随时点的匪方回应，并对7×13扩展经验矩阵求精确受限混合均衡。三类低权重回应的经验排序均在独立留出复现，但权重差未超出保守误差界；公共协调基线仍过于可预测而不晋级；训练受限值27.41%，冻结混合留出下界26.74%、上界30.64%。结论限于冻结候选和经验矩阵，见[最新实验报告](docs/equilibrium_results_v10.md)。

## 使用

Python 3.10+，运行和有理数求解不依赖第三方包。在项目根目录执行：

```sh
python3 -m mafia_lab demo --seed 20261010 --pk
python3 -m mafia_lab tiny
python3 -m mafia_lab controls
python3 -m unittest discover -s tests -v
python3 -m mafia_lab suite --config configs/experiment_v02.json --output results/reproduction_current
python3 scripts/run_signal_counter.py
python3 scripts/verify_results.py
python3 scripts/run_large_game_v04.py --output results/v04_reproduction --workers 4
python3 scripts/verify_large_game_v04.py results/v04 --replay --output results/v04_integrity_audit.json
python3 scripts/build_large_game_report_v04.py
python3 scripts/run_refinement_v05.py --output results/v05_reproduction --workers 4
python3 scripts/analyze_restricted_matrix_v05.py
python3 scripts/verify_refinement_v05.py results/v05 --replay --output results/v05_integrity_audit.json
python3 scripts/build_refinement_report_v05.py
python3 scripts/run_local_pool_v06.py --output results/v06_reproduction --workers 4
python3 scripts/analyze_local_pool_v06.py
python3 scripts/verify_local_pool_v06.py results/v06 --replay --output results/v06_integrity_audit.json
python3 scripts/build_local_pool_report_v06.py
python3 scripts/run_adaptive_v07.py --output results/v07_reproduction --workers 4
python3 scripts/analyze_adaptive_v07.py
python3 scripts/verify_adaptive_v07.py results/v07 --replay --output results/v07_integrity_audit.json
python3 scripts/build_adaptive_report_v07.py
python3 scripts/run_crossfit_v08.py --output results/v08_reproduction --workers 4
python3 scripts/analyze_crossfit_v08.py
python3 scripts/verify_crossfit_v08.py results/v08 --replay --output results/v08_integrity_audit.json
python3 scripts/build_crossfit_report_v08.py
python3 scripts/run_replication_v09.py --output results/v09_reproduction --workers 4
python3 scripts/analyze_replication_v09.py
python3 scripts/verify_replication_v09.py results/v09 --replay --output results/v09_integrity_audit.json
python3 scripts/build_replication_report_v09.py
python3 scripts/run_equilibrium_v10.py --output results/v10_reproduction --workers 4
python3 scripts/analyze_equilibrium_v10.py
python3 scripts/verify_equilibrium_v10.py results/v10 --replay --output results/v10_integrity_audit.json
python3 scripts/build_equilibrium_report_v10.py
```

`demo` 输出完整对局的公开发言和票型；其中验人声明不代表裁判认证。最外层结果包含赛后评价标签。`suite` 会完整重算实验并覆盖指定输出目录中的同名结果；使用新目录保留不同版本。

精确复现已冻结v02时，先 `cd results/v02/source`，再运行 `python3 -m mafia_lab suite --config configs/experiment_v02.json --output ../reproduction`。v03脚本重跑会覆盖其输出路径中的同名结果；当时源码、脚本和配置已单独保存在 `results/v03_source/`。v04拒绝覆盖已完成的结果目录，精确复现命令见最新报告；其 `source/` 保留完整源码、入口脚本和规范化配置。

可选安装 `analysis` 依赖用于 SciPy/HiGHS 独立交叉验证；没有 SciPy 时仅跳过这一项，仍执行有理数证书和跨裁判逐项核对。

## 当前范围

| 层次 | 实现 | 证据含义 |
| --- | --- | --- |
| 1警1匪2民 | 全部机会分支、18×8策略池、有理数矩阵解 | 明确受限模型的精确结果，非全动作GTO |
| 2警1匪3民、2警2匪4民 | 完整到终局的模拟与合法性测试 | 死警遗言、自刀机制的过渡模型 |
| 4警4匪8民首日 | 同一首夜状态配对改变遗言 | 固定后续策略下的条件胜率差 |
| 16人反制 | 7×7策略池，训练选回应、独立种子评估；另测追刀提名者 | 候选池内找到的利用和反利用 |
| 16人掩护与票型 | 11×6策略池，局部角色条件随机化、公开历史推理、匪方同步反制 | 独立留出验证，115项预声明配对比较，非均衡混合频率 |
| 16人策略拆分与顺序反制 | 11×7策略池，警/民票型拆分、验人单独开关、发起者识别、匪方散票 | 139项预声明比较、首夜条件分支、训练矩阵受限混合解 |
| 16人局部混合与信息时点 | 9×7候选池、独立本地抽样、双发起确认、有限3+1散票、固定首夜配对干预 | 新种子留出与增量扩池；非完整CFR/GTO |
| 16人公开票差与自适应表 | 公开顺序票、票差安全装饰、五种平民首发、训练生成条件表 | 独立留出拦截过拟合；规则变体策略评估，非完整GTO |
| 16人交叉拟合与覆盖收益 | 公共确定性匪目标、坐标独立拟合/验证、平民多窗口公开首发 | 完全未读留出；候选池纯策略评估，非受限混合或完整GTO |
| 16人多区块复验与自然开局 | 四组外层复验、公开重复提名追踪/诱饵、同窗口目标覆盖控制 | 三折选择和自然开局留出；机制拆分与候选池反制，非完整GTO |
| 16人公共协调与受限混合 | 好人公共协议、三类匪方专门回应、7×13经验矩阵精确解 | 冻结混合独立留出；有限候选受限均衡，非完整GTO |
| 机制比较 | PK、3/4遗言、方向、近远验人、位置刀、自刀 | 固定策略下的开局胜率比较 |

用户确认：匪胜条件为警察全灭；好人胜以匪全灭建模；夜晚共同验一人；不翻身份；允许自刀和假跳警。首夜被刀警察得到当夜验人。遗言包含夜死和白天放逐、前三次死亡可说；四次作为对照。发言从最近死者旁开始；左右固定方向均支持。基线同时投票、唯一最高票出局；PK变体对平票者再发言和复投，仍平则无人出局。

## 文档与结果

- [v10最新实验报告](docs/equilibrium_results_v10.md)：公共协调、三类专门反制与扩展矩阵受限均衡。
- [v10冻结协议](docs/equilibrium_protocol_v10.md)、[配置](configs/equilibrium_v10.json)、[结果清单](results/v10/manifest.json)、[独立核验](results/v10_integrity_audit.json)：91个训练单元、91个留出单元、3条回应选择、2个精确矩阵证书和182局归档重放通过。
- [v09最新实验报告](docs/replication_results_v09.md)：多区块复验、自然开局探测与公开反制。
- [v09冻结协议](docs/replication_protocol_v09.md)、[配置](configs/replication_v09.json)、[结果清单](results/v09/manifest.json)、[独立核验](results/v09_integrity_audit.json)：128个复验单元、105个选择/验证单元、30个留出单元、9个种子区块和263局归档重放通过。
- [v08最新实验报告](docs/crossfit_results_v08.md)：公共匪目标、坐标交叉拟合与平民首发覆盖收益。
- [v08冻结协议](docs/crossfit_protocol_v08.md)、[配置](configs/crossfit_v08.json)、[结果清单](results/v08/manifest.json)、[独立核验](results/v08_integrity_audit.json)：476个训练单元、24个矩阵单元、21个首发单元、7,168个开局和81局归档重放通过。
- [v07最新实验报告](docs/adaptive_results_v07.md)：实时票差装饰、公开平民首发与训练生成条件表。
- [v07冻结协议](docs/adaptive_protocol_v07.md)、[配置](configs/adaptive_v07.json)、[结果清单](results/v07/manifest.json)、[独立核验](results/v07_integrity_audit.json)：360个训练候选单元、24个留出单元、21个首发单元、4,096个开局和63局归档重放通过。
- [v06最新实验报告](docs/local_pool_results_v06.md)：局部混合、反诱饵、有限散票、查杀释放时点与增量反制池。
- [v06冻结协议](docs/local_pool_protocol_v06.md)、[配置](configs/local_pool_v06.json)、[结果清单](results/v06/manifest.json)、[独立核验](results/v06_integrity_audit.json)：126个矩阵单元、21个时点单元、2,304个固定首夜状态与147局归档重放通过。
- [v05最新实验报告](docs/refinement_results_v05.md)：反制循环、角色拆分、首夜条件分支、全16人规则敏感性与受限矩阵混合解。
- [v05冻结协议](docs/refinement_protocol_v05.md)、[配置](configs/refinement_v05.json)、[结果清单](results/v05/manifest.json)、[独立核验](results/v05_integrity_audit.json)：170个实验单元、680个条件摘要、142项配对统计及340局归档重放通过。
- [v04最新实验报告](docs/large_game_results_v04.md)：完整矩阵、反制链、掩护/混合/票型效果、保留决策与规则敏感性。
- [v04实验协议](docs/large_game_protocol_v04.md)、[配置](configs/large_game_v04.json)、[结果清单](results/v04/manifest.json)、[独立核验](results/v04_integrity_audit.json)：148个实验单元、118项配对统计和296条归档重放通过。
- [首轮实验报告](docs/experiment_report_v02.md)：实测结果、样本数、误差与下一步。
- [框架与策略目录](docs/framework_v01.md)：模块边界、完整回合、策略的具体决策规则。
- [规则合同](docs/rules_and_first_experiments_20261010.md)：用户确认、实验假设及未实现变体。
- [精确小模型](docs/tiny_model.md)：限制条件、18×8矩阵及证书解释。
- [方法审计](docs/methodology_audit_20261010.md)：独立验证与结论边界。
- [原始研究设计](docs/mafia_research_design_20261010.md)：长期路线与教学目标。
- [实验配置](configs/experiment_v02.json) 与 [结果清单](results/v02/manifest.json)：固定预算、随机种子、源码及结果哈希。
- [提名信号反制](results/signal_counter_v03.json)：后续公开行动也会泄露信息的针对性测试。
- [最终产物核验](results/final_integrity_audit.json)：哈希、原始样本分母和报告统计复算。

v01的弱策略基线及补充实验保留；v02修正了警察误信队外验人的问题；v03展示提名信号可被追刀利用；v04加入掩护、局部混合和票型；v05拆分角色动作并加入发言顺序与散票反制；v06加入可执行本地混合、反诱饵确认、受控时点干预与增量扩池；v07加入公开顺序票、实时票差门控、公开平民规则和训练生成条件表；v08统一匪方主目标，并以不复用坐标子批次和未读留出选择条件表与覆盖型首发；v09用多区块复验和自然开局揭示公开探测的协调机制；v10加入好人公共协议、三类专门反制和扩展经验矩阵受限混合。各代冻结来源与结果分别保留。现有报告共记录1,308,928次终局执行；不同格子的共享种子不构成额外独立开局。

沿用 AIP 与 Poker Analysis 的 `GameSpec → AlgorithmSpec → SolverArtifact → IndependentEvaluationReport → PromotionDecision` 思路。当前模块不直接导入其他项目代码。解析概率、固定策略胜率、受限均衡和完整声明游戏均衡分别标注；未经认证的模拟结果不自动成为教学标准答案。
