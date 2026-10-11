# Mafia / Werewolf Lab

研究隐藏身份游戏中的策略与均衡，建立可验证的教学任务，最终检验推理训练向德州扑克的迁移。当前实现警匪游戏；狼人杀技能尚未加入。

**已实现可运行裁判、观察权限、完整对局、小模型精确求解、16人固定策略实验和反制评估。完整16人GTO与人类教学效果尚未得到验证。**

61项测试通过（含可选SciPy独立核对）；v02与v03共完成101,632次终局模拟。最关键的反例：共同内推对旧对手好人胜率93.85%，杀手加入追刀提名者后降至3.22%。完整解释见实验报告。

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
```

`demo` 输出完整对局的公开发言和票型；其中验人声明不代表裁判认证。最外层结果包含赛后评价标签。`suite` 会完整重算实验并覆盖指定输出目录中的同名结果；使用新目录保留不同版本。

精确复现已冻结v02时，先 `cd results/v02/source`，再运行 `python3 -m mafia_lab suite --config configs/experiment_v02.json --output ../reproduction`。v03脚本重跑会覆盖同名v03结果；当前源码和冻结参数未变时可确定性复算。

可选安装 `analysis` 依赖用于 SciPy/HiGHS 独立交叉验证；没有 SciPy 时仅跳过这一项，仍执行有理数证书和跨裁判逐项核对。

## 当前范围

| 层次 | 实现 | 证据含义 |
| --- | --- | --- |
| 1警1匪2民 | 全部机会分支、18×8策略池、有理数矩阵解 | 明确受限模型的精确结果，非全动作GTO |
| 2警1匪3民、2警2匪4民 | 完整到终局的模拟与合法性测试 | 死警遗言、自刀机制的过渡模型 |
| 4警4匪8民首日 | 同一首夜状态配对改变遗言 | 固定后续策略下的条件胜率差 |
| 16人反制 | 7×7策略池，训练选回应、独立种子评估；另测追刀提名者 | 候选池内找到的利用和反利用 |
| 机制比较 | PK、3/4遗言、方向、近远验人、位置刀、自刀 | 固定策略下的开局胜率比较 |

用户确认：匪胜条件为警察全灭；好人胜以匪全灭建模；夜晚共同验一人；不翻身份；允许自刀和假跳警。首夜被刀警察得到当夜验人。遗言包含夜死和白天放逐、前三次死亡可说；四次作为对照。发言从最近死者旁开始；左右固定方向均支持。基线同时投票、唯一最高票出局；PK变体对平票者再发言和复投，仍平则无人出局。

## 文档与结果

- [首轮实验报告](docs/experiment_report_v02.md)：实测结果、样本数、误差与下一步。
- [框架与策略目录](docs/framework_v01.md)：模块边界、完整回合、策略的具体决策规则。
- [规则合同](docs/rules_and_first_experiments_20261010.md)：用户确认、实验假设及未实现变体。
- [精确小模型](docs/tiny_model.md)：限制条件、18×8矩阵及证书解释。
- [方法审计](docs/methodology_audit_20261010.md)：独立验证与结论边界。
- [原始研究设计](docs/mafia_research_design_20261010.md)：长期路线与教学目标。
- [实验配置](configs/experiment_v02.json) 与 [结果清单](results/v02/manifest.json)：固定预算、随机种子、源码及结果哈希。
- [提名信号反制](results/signal_counter_v03.json)：后续公开行动也会泄露信息的针对性测试。
- [最终产物核验](results/final_integrity_audit.json)：哈希、原始样本分母和报告统计复算。

v01的弱策略基线及补充实验保留；v02修正了警察误信队外验人的问题。两版源码快照分别位于各自结果目录的 `source/`，与对应manifest哈希绑定。当前代码另外支持追刀提名者的 `signals` 行动规则。

沿用 AIP 与 Poker Analysis 的 `GameSpec → AlgorithmSpec → SolverArtifact → IndependentEvaluationReport → PromotionDecision` 思路。当前模块不直接导入其他项目代码。解析概率、固定策略胜率、受限均衡和完整声明游戏均衡分别标注；未经认证的模拟结果不自动成为教学标准答案。
