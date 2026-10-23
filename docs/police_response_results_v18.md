# v18 真警是否应回应悍跳：完整方法与结果报告

日期2026-10-23。4警4匪8民。主问题是“有发言机会时，一名真警回应已知假警是否值得”。本报告区分逻辑保证、固定策略模拟收益、有限经验矩阵证书。

## 本轮关键结果：条件策略，不能只看总胜率

1. A报B金水的来源偏序已按本轮假设进入底层逻辑。额外查杀不会绕过约束。这一逻辑保证与实际收益的关系要分别评估。
2. 首夜未死警、前置假查杀分支支持真警回应：logical_keep到logical_answer，late从27.90%到31.34%（+3.44个百分点，近似95%区间[+2.18,+4.70]），伪装刀从20.79%到28.59%（+7.80，[+6.46,+9.14]）。这符合“及时争夺假警控场”的机制方向，但只适用于当前有限声明协议。
3. 首夜已死警分支反向：同一early策略下，新增回应的终局差约为late -22.06个百分点、伪装刀 -27.71个百分点（该互补分支为事后诊断）。所以包含该分支的总体logical_answer反而下降，不能把总体负值解释成警队完整时不该对跳。
4. late_counter首日回应机会为0：末位匪徒位于所有警察之后。该列不能用于证明当轮回应是否有效。伪装刀counter有45.26%首日回应机会。两个early列有93.36%和98.27%机会，answer实际响应比例完全匹配，干预真实发生。
5. 组合参考信念不是成熟的信用系统：无主动悍跳时logical三行样本零胜，首日误出警约67%–70%。它按声明约束数身份，却没有给唯一警察声明的战略选择及无人反对正确建模，容易把真警声明者排到高风险。这个负结果不否定金水来源偏序，说明不能仅靠约束均匀计数就决定出人。
6. 主实验self规则首日实际响应为0，因为early假查杀指向通常已发言的首位非队友。它在后续天数仍可发生，但不能用首日结果回答正常原地自辩是否有效。另冻结小型定向探针修复覆盖，单独报告，不混入原留出矩阵。

## 先读参数与策略字典

| 好人行 | 中文含义 | 真假声明推理 | 真警遇悍跳 |
|---|---|---|---|
| fixed_keep | 旧信用＋不额外回应 | 0.5/0.75来源信用 | 保留原发言 |
| fixed_answer | 旧信用＋一名真警回应 | 同上 | 下一名有机会的真警回应 |
| logical_keep | 逻辑约束＋不额外回应 | 合法身份分配参考边际 | 保留原发言 |
| logical_answer | 逻辑约束＋一名真警回应 | 同上 | 下一名有机会的真警回应 |
| logical_self | 逻辑约束＋本人自辩 | 同上 | 只有被查杀真警轮到时回应 |

全部使用二人内推、v17新发言时序、equal首夜位置模型与inspect_gap验人；票史评分关闭。keep并非永远隐藏：原有警队发言人与后续验人公布仍保留，只是不因悍跳新增回应。这样主要比较回应机制，避免混入v17特定安静票型的40%利用收益。

| 匪方名称部分 | 中文含义与动作 |
|---|---|
| safe_late | 非匪首位发言优先，然后争取末四位与末位匪徒控制 |
| posterior_decoy | 首夜选择抑制旧位置后验的伪装刀；后续无公开声明者可追时用late |
| quiet | 无主动悍跳，仍保护队友、公开怀疑和集中投票 |
| counter | 当日最后一名匪看到外队警察声明后，假查杀声明者 |
| early | 当日首名匪主动假查杀发言顺序首位非队友，不知道其警/民身份 |

六列是两种刀法×三种白天动作。例如safe_late_early为late刀＋首名匪主动假查杀。没有增加改变发言顺序的出轮次抢话规则。随机刀counter单独校准，不参与主矩阵。

## 底层逻辑与数值到底是什么

本轮限定：平民不假跳警；非匪警察如实报验，不把匪报金水。故A报B金水蕴含“A好 ⇒ A真警 ⇒ B好”；在任何与这些假设相容的证据E下，P(B好|E)≥P(A好|E)。额外查杀不会推翻不等式，只会改变各声明真假假设。该条件逻辑已经建立，但本轮没有证明平民假跳无收益。

当A与B都在本人合法投票候选中时，程序按“先考虑来源A，再考虑其金水B”处理，链式保护允许传递；互相假金水形成环时不把所有候选排空，环内按风险与公开顺序。私人查杀、禁止自投、PK候选限制仍优先。两方共同给C金水只有在假设集保证至少一方真时才构成确定非匪；双假方仍允许。

fixed平民信用：被他人当天公开报金水且未被查杀赋0.75，其余0.5，门槛0.6；同信用沿用较晚建议。警察认队友1、非队友0。这些是未经校准的操作权重，不是客观身份概率。logical不用这些固定阈值计算身份：它按均匀发牌数计算满足所有可见真假声明约束的角色分配，并取座位为匪的边际比例。

组合计数包含“非匪声明者必须为警察，真警金水非匪、查杀为匪，平民观察者知道自己非警非匪”。所有可见白天与遗言report/police纳入，重复声明只是同一约束。它不建模匪方选择声明的概率或真警保持沉默的战略似然，因此是组合参考信念，不是已校准的战略后验。未把无人回应自动当100%真警。

logical平民优先考虑该参考边际风险高者，使用原位置排序和名单作同风险破同分；不因后发言自动覆盖。真警仍使用共享验人，有私人查杀先投查杀；实际已回应者可以优先投已知假声明者。

例：A报B金水，C查杀B。系统不会因查杀直接把B降到来源A之下，而比较“A真则B好且C可能假”与“C真则B匪且A必假”等一致假设。被查杀真警轮到时可说“我是警察，A是假警”，这里police是角色声明，accuse是假警指认，不伪造新的验人结果。

## 样本与指标

正式对局158,720；5×6主矩阵，训练1024局/格seed149000000起，留出4096局/格seed150000000起；随机刀counter校准1024局/行seed151000000起。三段独立且不复用旧实验，阶段内共享发牌seed。先保存训练解再读取留出，未用留出扩池。

回应机会：首日第一个匪方警察声明之后，普通发言轮是否仍有至少一名真警未发言。该标签由裁判离线统计，绝不提供给策略；同一列各好人行可配对。真实响应仅发生在自己的合法普通发言时点，不添加保证回应窗口。自辩策略需要被攻击者本人尚未发言，因此机会更窄。

下文比例为好人终局胜率。0/4096仅表示样本无胜局，单侧95%二项上界约0.073%；不是总体概率严格零。配对区间为探索性Wald近似，未对全部对比多重校正；原始文件也保留Hoeffding界。

## 留出总体胜率

| 行 | safe_late_quiet | safe_late_counter | safe_late_early | posterior_decoy_quiet | posterior_decoy_counter | posterior_decoy_early |
|---|---:|---:|---:|---:|---:|---:|
| fixed_keep | 3.32% | 3.34% | 3.34% | 1.10% | 1.10% | 1.10% |
| fixed_answer | 3.32% | 3.10% | 3.00% | 1.10% | 0.59% | 0.71% |
| logical_keep | 0.00% | 0.05% | 27.03% | 0.00% | 0.02% | 23.27% |
| logical_answer | 0.00% | 0.05% | 22.17% | 0.00% | 0.00% | 19.24% |
| logical_self | 0.00% | 0.05% | 28.20% | 0.00% | 0.02% | 26.22% |

## 回应覆盖与公开回应人数

| 行 | 匪方 | 有机会比例 | 实际响应比例 | 平均回应警察人数（非净新增） | 首日误出警 |
|---|---|---:|---:|---:|---:|
| fixed_keep | safe_late_quiet | 0.00% | 0.00% | 0.000 | 0.00% |
| fixed_keep | safe_late_counter | 0.00% | 0.00% | 0.000 | 0.00% |
| fixed_keep | safe_late_early | 93.36% | 0.00% | 0.000 | 0.00% |
| fixed_keep | posterior_decoy_quiet | 0.00% | 0.00% | 0.000 | 20.36% |
| fixed_keep | posterior_decoy_counter | 45.26% | 0.00% | 0.000 | 20.65% |
| fixed_keep | posterior_decoy_early | 98.27% | 0.00% | 0.000 | 20.65% |
| fixed_answer | safe_late_quiet | 0.00% | 0.00% | 0.000 | 0.00% |
| fixed_answer | safe_late_counter | 0.00% | 0.00% | 0.000 | 0.00% |
| fixed_answer | safe_late_early | 93.36% | 93.36% | 0.934 | 0.00% |
| fixed_answer | posterior_decoy_quiet | 0.00% | 0.00% | 0.000 | 20.36% |
| fixed_answer | posterior_decoy_counter | 45.26% | 45.26% | 0.453 | 20.65% |
| fixed_answer | posterior_decoy_early | 98.27% | 98.27% | 0.983 | 27.51% |
| logical_keep | safe_late_quiet | 0.00% | 0.00% | 0.000 | 67.19% |
| logical_keep | safe_late_counter | 0.00% | 0.00% | 0.000 | 59.30% |
| logical_keep | safe_late_early | 93.36% | 0.00% | 0.000 | 27.66% |
| logical_keep | posterior_decoy_quiet | 0.00% | 0.00% | 0.000 | 69.58% |
| logical_keep | posterior_decoy_counter | 45.26% | 0.00% | 0.000 | 67.70% |
| logical_keep | posterior_decoy_early | 98.27% | 0.00% | 0.000 | 27.51% |
| logical_answer | safe_late_quiet | 0.00% | 0.00% | 0.000 | 67.19% |
| logical_answer | safe_late_counter | 0.00% | 0.00% | 0.000 | 59.30% |
| logical_answer | safe_late_early | 93.36% | 93.36% | 0.934 | 25.78% |
| logical_answer | posterior_decoy_quiet | 0.00% | 0.00% | 0.000 | 69.58% |
| logical_answer | posterior_decoy_counter | 45.26% | 45.26% | 0.453 | 67.70% |
| logical_answer | posterior_decoy_early | 98.27% | 98.27% | 0.983 | 24.00% |
| logical_self | safe_late_quiet | 0.00% | 0.00% | 0.000 | 67.19% |
| logical_self | safe_late_counter | 0.00% | 0.00% | 0.000 | 59.30% |
| logical_self | safe_late_early | 93.36% | 0.00% | 0.000 | 27.66% |
| logical_self | posterior_decoy_quiet | 0.00% | 0.00% | 0.000 | 69.58% |
| logical_self | posterior_decoy_counter | 45.26% | 0.00% | 0.000 | 67.70% |
| logical_self | posterior_decoy_early | 98.27% | 0.00% | 0.000 | 27.51% |

字段extra_police_exposed_day1保存的是police回应消息数，并非相对keep的净新增暴露；原本就会报验的人也可能被计入。因此该数不能直接估计因回应多牺牲了几名警察。回应与暴露/验人释放的因果分解尚未完成。

## 预声明配对效果：只看有回应机会的首日分支

response_fixed为fixed_answer减fixed_keep；response_logical为logical_answer减logical_keep；team_answer_minus_self为logical_answer减logical_self。来源机制差异logical_keep_minus_fixed与logical_answer_minus_fixed分别在相同回应规则下比较组合约束。效果是完整策略（包括后续白天）的终局差，不能纯归因首日某一动作。

| 对比 | 匪方 | 分支n | 终局差pp | 近似95%区间pp | 改善/恶化 |
|---|---|---:|---:|---:|---:|
| response_fixed | safe_late_early | 3824 | -0.37 | [-1.04,+0.31] | 80/94 |
| response_fixed | posterior_decoy_counter | 1854 | -1.13 | [-1.82,-0.44] | 11/32 |
| response_fixed | posterior_decoy_early | 4025 | -0.40 | [-0.71,-0.08] | 13/29 |
| response_logical | safe_late_early | 3824 | -5.23 | [-6.49,-3.97] | 207/407 |
| response_logical | posterior_decoy_counter | 1854 | -0.05 | [-0.16,+0.05] | 0/1 |
| response_logical | posterior_decoy_early | 4025 | -4.12 | [-5.45,-2.80] | 289/455 |
| logical_keep_minus_fixed | safe_late_early | 3824 | +23.98 | [+22.46,+25.50] | 1006/89 |
| logical_keep_minus_fixed | posterior_decoy_counter | 1854 | -2.32 | [-3.00,-1.63] | 0/43 |
| logical_keep_minus_fixed | posterior_decoy_early | 4025 | +22.39 | [+21.03,+23.74] | 937/36 |
| logical_answer_minus_fixed | safe_late_early | 3824 | +19.12 | [+17.73,+20.50] | 799/68 |
| logical_answer_minus_fixed | posterior_decoy_counter | 1854 | -1.24 | [-1.74,-0.74] | 0/23 |
| logical_answer_minus_fixed | posterior_decoy_early | 4025 | +18.66 | [+17.43,+19.89] | 766/15 |
| team_answer_minus_self | safe_late_early | 3824 | -6.49 | [-7.70,-5.27] | 164/412 |
| team_answer_minus_self | posterior_decoy_counter | 1854 | -0.05 | [-0.16,+0.05] | 0/1 |
| team_answer_minus_self | posterior_decoy_early | 4025 | -7.13 | [-8.33,-5.93] | 172/459 |

## 首验金水与查杀分支

| 行 | 匪方 | 未死警验金水n | 该分支胜率 | 未死警验查杀n | 该分支胜率 |
|---|---|---:|---:|---:|---:|
| fixed_keep | safe_late_quiet | 1804 | 2.99% | 959 | 3.34% |
| fixed_keep | safe_late_counter | 1804 | 3.05% | 959 | 3.34% |
| fixed_keep | safe_late_early | 1804 | 3.05% | 959 | 3.34% |
| fixed_keep | posterior_decoy_quiet | 1844 | 0.27% | 888 | 4.50% |
| fixed_keep | posterior_decoy_counter | 1844 | 0.27% | 888 | 4.50% |
| fixed_keep | posterior_decoy_early | 1844 | 0.27% | 888 | 4.50% |
| fixed_answer | safe_late_quiet | 1804 | 2.99% | 959 | 3.34% |
| fixed_answer | safe_late_counter | 1804 | 2.61% | 959 | 3.34% |
| fixed_answer | safe_late_early | 1804 | 4.38% | 959 | 3.86% |
| fixed_answer | posterior_decoy_quiet | 1844 | 0.27% | 888 | 4.50% |
| fixed_answer | posterior_decoy_counter | 1844 | 0.27% | 888 | 2.14% |
| fixed_answer | posterior_decoy_early | 1844 | 0.05% | 888 | 3.15% |
| logical_keep | safe_late_quiet | 1804 | 0.00% | 959 | 0.00% |
| logical_keep | safe_late_counter | 1804 | 0.00% | 959 | 0.00% |
| logical_keep | safe_late_early | 1804 | 26.33% | 959 | 30.87% |
| logical_keep | posterior_decoy_quiet | 1844 | 0.00% | 888 | 0.00% |
| logical_keep | posterior_decoy_counter | 1844 | 0.00% | 888 | 0.11% |
| logical_keep | posterior_decoy_early | 1844 | 20.88% | 888 | 20.61% |
| logical_answer | safe_late_quiet | 1804 | 0.00% | 959 | 0.00% |
| logical_answer | safe_late_counter | 1804 | 0.00% | 959 | 0.00% |
| logical_answer | safe_late_early | 1804 | 29.38% | 959 | 35.04% |
| logical_answer | posterior_decoy_quiet | 1844 | 0.00% | 888 | 0.00% |
| logical_answer | posterior_decoy_counter | 1844 | 0.00% | 888 | 0.00% |
| logical_answer | posterior_decoy_early | 1844 | 26.95% | 888 | 31.98% |
| logical_self | safe_late_quiet | 1804 | 0.00% | 959 | 0.00% |
| logical_self | safe_late_counter | 1804 | 0.00% | 959 | 0.00% |
| logical_self | safe_late_early | 1804 | 28.55% | 959 | 31.60% |
| logical_self | posterior_decoy_quiet | 1844 | 0.00% | 888 | 0.00% |
| logical_self | posterior_decoy_counter | 1844 | 0.00% | 888 | 0.11% |
| logical_self | posterior_decoy_early | 1844 | 26.30% | 888 | 22.75% |

## 随机刀counter校准

| 行 | n | 胜率 |
|---|---:|---:|
| fixed_keep | 1024 | 3.12% |
| fixed_answer | 1024 | 2.54% |
| logical_keep | 1024 | 0.00% |
| logical_answer | 1024 | 0.00% |
| logical_self | 1024 | 0.00% |

## 有限经验矩阵证书

训练：value=9/1024（0.88%），代数gap=0。
好人混合：`{'fixed_keep': '1'}`；匪方混合：`{'posterior_decoy_quiet': '1'}`。

留出事后诊断：value=45/4096（1.10%），代数gap=0。
好人混合：`{'fixed_keep': '1'}`；匪方混合：`{'posterior_decoy_quiet': '1'}`。

冻结训练混合在留出：lower=45/4096（1.10%），upper=45/4096（1.10%），gap=0.0000个百分点。

证书只对给定有限采样矩阵精确。均衡混合未必唯一；数值比例不是现实客观出招频率。完整团队协议的元混合还依赖开局如何协调抽样，未证明任意团队混合都能由独立平民实现。没有候选池外完整最佳回应搜索。

## 复现与验证

`python -m pytest -q`；`python scripts/run_police_response_v18.py --workers 4`；`python scripts/verify_police_response_v18.py results/v18 --replay --output results/v18_integrity_audit.json`。
审计pass：65个单元、44项冻结资产、195个抽样完整轨迹重放。不是全部模拟独立重跑，也不是独立引擎验证。

单元测试包括小配置完整角色分配与组合边际一致、额外查杀下的金水来源偏序、共同金水在至少一真前提下的确定性与双假例外、一名可回应警察与仅本人自辩的区别、假金水环不清空候选、未知身份置换不影响可见行动，以及各行回应机会配对。

## 尚未解决的问题

1. 真警沉默与回应机会的战略似然尚未加入；单跳无人回应的信用不能自动100%。
2. 好人假跳排除是本轮模型条件，并非收益支配证明；开放新动作时必须重审逻辑约束。
3. 当前回应只报角色并指出假警，没有同时公开全警队、完整验人/内推辩论或给假警下金水的复杂战术。
4. 固定票史两组件消融、合法改票豁免、一致投票伪装、信用污染仍在待办，未与本轮回应实验混做。
5. middle/late行为混合权重、遗言3/4/全员敏感性和白天报匪继续暂缓。

## 主实验覆盖审查与应如何使用结论

quiet列内同一推理模型的keep/answer/self原始指标完全一致，说明没有悍跳就不会触发额外回应。12个answer覆盖单元逐局核查机会与响应相等。额外保存4个从既有留出挑选的正/负解释轨迹，不能作为独立统计证据。材料results/v18_mechanism_diagnostics.json。
本轮主要回应是公开角色police并附假警指认accuse。如果该玩家原本会作为当日警队发言人报验，这次动作会替换报告，不会同时自动公布完整验人。故它是“最小角色回应”，不是所有合理对跳策略的代表；需要保留验人信息的对照。后续另做定向探针，检查移除这一限制以及让被攻击者尚未发言后，结果是否改变。
首夜未死警早假查杀的回应收益，与首夜已死警的暴露/信息成本相反，提示按警队存活状态分条件比“一律回应/一律隐藏”更合理。尚未验证组合后的条件策略，不能直接用分支最好结果拼成经过留出验收的新策略。
固定信用版在late早假查杀的未死警分支只提高1.05个百分点，在伪装刀下反而下降0.59个百分点，说明回应收益依赖平民如何理解新声明。真警提出反对并不自动让平民知道谁是真警。
独立于这些收益差，来源偏序是在排除好人假跳并约束真警如实金水的假设下成立；若将来允许好人故意把匪报好，则必须重新定义假设。不能以好人假跳“看起来收益低”替代策略支配证明。
建议下一步保留已验证的金水来源偏序，把它作为已有信用机制的约束，而不是用缺少发言策略似然的组合计数替换全部信用。先补真警/假警报告、回应和沉默的生成概率，再检验条件对跳；暂缓继续增加票史参数。
本轮234项主实验测试通过；增加定向探针测试后完整测试数在最终验证说明中报告。

## 有效补充探针：保留验人并允许被攻击者尚未发言

主实验读数后发现覆盖限制，另冻结5行×2种early刀法的1024局/格探针，总10240局，seed154000000起。它同时改变假查杀目标（优先尚未发言非队友）和回应内容（保留真实验人并指出假警），回应者保留私人查杀及反对假警的投票优先级。这是事后触发的探索性诊断，不是原主实验的独立预注册确认集；不得把两个改动分别归因或与主留出数值合并。
153百万seed的首次探针未正确识别report式回应者的反假警投票，已单独标为无效并保留源码/结果。以下只引用154百万修复探针。

| 好人行 | 匪方 | 总体胜率 | 首夜未死警胜率 | 实际指认假警 | 本人受查杀后自辩 |
|---|---|---:|---:|---:|---:|
| fixed_keep | safe_late_early | 4.10% | 3.75% | 0.00% | 0.00% |
| fixed_keep | posterior_decoy_early | 0.88% | 1.29% | 0.00% | 0.00% |
| fixed_answer | safe_late_early | 3.42% | 4.95% | 93.46% | 33.40% |
| fixed_answer | posterior_decoy_early | 0.59% | 0.86% | 99.22% | 34.18% |
| logical_keep | safe_late_early | 53.91% | 59.97% | 0.00% | 0.00% |
| logical_keep | posterior_decoy_early | 42.19% | 41.09% | 0.00% | 0.00% |
| logical_answer | safe_late_early | 24.22% | 35.08% | 93.46% | 33.40% |
| logical_answer | posterior_decoy_early | 22.95% | 33.48% | 99.22% | 34.18% |
| logical_self | safe_late_early | 33.50% | 37.03% | 33.40% | 33.40% |
| logical_self | posterior_decoy_early | 29.10% | 31.03% | 34.18% | 34.18% |

下表为首夜未死警分支的配对差（探索性近似区间）。

| 对比 | 匪方 | n | 差pp | 95%近似区间pp |
|---|---|---:|---:|---:|
| response_fixed | safe_late_early | 667 | +1.20 | [-0.46,+2.86] |
| response_fixed | posterior_decoy_early | 696 | -0.43 | [-1.37,+0.50] |
| response_logical | safe_late_early | 667 | -24.89 | [-28.86,-20.91] |
| response_logical | posterior_decoy_early | 696 | -7.61 | [-11.08,-4.15] |
| team_answer_minus_self | safe_late_early | 667 | -1.95 | [-4.56,+0.66] |
| team_answer_minus_self | posterior_decoy_early | 696 | +2.44 | [+0.07,+4.81] |

不能把此探针中较高的logical_keep胜率写成真警沉默有普遍优势：同一组合参考模型在无主动悍跳时几乎总误出真实声明者，先验/发言似然不完整。它能被固定假报方式利用，也能反向利用固定假报方式；这恰好说明需要先修复绝对信用，而非直接把参考模型的最优行为升级为默认规则。
具体算例：16人4警4匪8民、观察者为平民、仅A声明警察报B金水时，组合参考计数给A匪率58.33%、B匪率12.50%；若A报B查杀，给A匪率77.78%、B匪率38.89%。来源偏序在金水例中依然成立，但该绝对风险会让平民优先票A。原因是未建模真实检查目标选择和声明动作的概率，而假来源受到的真话约束更少。数学一致性不能代替正确的生成模型。
因此，本轮对回应策略的正式判断为：警队完整、假查杀方式和公众推理规则会改变收益；尚不足以把“必须一人回应”或“必须保持隐藏”定为既定策略。下一阶段优先增加真警/假警声明与回应的策略似然，保留真实验人、明确正常自辩覆盖，再验证单跳无人回应是否应有高信用。

有效探针审计pass：10单元、43冻结资产、30抽样完整重放。主实验158720局与有效探针10240局合计168960局；无效探针另存，不计入有效研究样本。最终完整测试237项通过。
