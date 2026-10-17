#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
read = lambda name: json.loads((ROOT/name).read_text())
dead = read("results/v12/dead_police.json")
train = read("results/v12/selfkill_train.json")
holdout = read("results/v12/selfkill_holdout.json")
audit = read("results/v12_integrity_audit.json")
manifest = read("results/v12/manifest.json")


def pct(x):
    return f"{100*x:.2f}%"


def interval(values):
    return f"[{100*values[0]:+.2f}, {100*values[1]:+.2f}]"


labels = {
    "silent":"沉默", "truth":"真实报告", "teammate_clear":"队友金水",
    "trust_hidden":"信死者／活警隐藏", "skeptic_hidden":"不信死者／活警隐藏",
    "trust_single":"信死者／单警反驳", "trust_full":"信死者／四警反驳",
    "ordinary":"普通刀", "self_silent":"自刀沉默", "self_fake_hit":"自刀假查杀",
    "self_ally_clear":"自刀队友金水", "self_nonally_clear":"自刀未知非匪金水",
}

lines = [
"# v12：首夜死警声明与自刀可信度实验", "",
"日期：2026-10-17。主配置4警4匪8民。本报告只解释冻结有限策略下的模拟；不声称完整游戏GTO。", "",
"## 做了什么", "",
"本轮分为两个实验。死警实验先筛选首夜自然刀中警察的相同状态，再只改变死警遗言。首验中匪比较沉默与真实查杀；首验好人比较沉默、真实金水和给存活警察队友金水。每个状态队列4096个独立种子，所有处理逐种子配对。", "",
"自刀实验从首夜行动前比较普通刀、自刀沉默、自刀假查杀、自刀给队友假金水和自刀给随机未知非匪真金水。匪徒不能区分未知非匪中的警察和平民。好人池比较相信／怀疑死者，以及单警／四警公开反驳。训练矩阵每格1024局，留出矩阵每格4096局；训练混合在读取留出前冻结。", "",
"第一次正式批次发现首日反驳开关错误改变了第二日起的续局，第二批发现赛后目标身份统计混入白天放逐者遗言。两批均整体作废、原样保留并更换种子。正式结论只来自v12c。", "",
"## 首夜死警结果", "",
"| 首验 | 死警遗言 | 好人终局胜率 | 首日放逐匪 | 首日放逐警 | 首日放逐民 | 第二夜刀中警 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
for c in dead["cells"]:
    lines.append(f"| {'中匪' if c['cohort']=='hit' else '好人'} | {labels[c['good']]} | {pct(c['means']['win'])} | {pct(c['means']['day1_exile_mafia'])} | {pct(c['means']['day1_exile_police'])} | {pct(c['means']['day1_exile_civilian'])} | {pct(c['means']['night2_kill_police'])} |")
lines += ["", "四项预先指定终局比较的单位是百分点：", "",
"| 比较 | 变化 | 95%配对正态区间 | 95%家族正态近似区间 | 95%家族Hoeffding区间 |", "| --- | ---: | --- | --- | --- |"]
cn = {"hit_truth_minus_silent":"中匪：真报减沉默", "clear_truth_minus_silent":"验好：真报减沉默",
      "clear_teammate_minus_silent":"验好：队友金水减沉默", "clear_teammate_minus_truth":"验好：队友金水减真实金水"}
for x in dead["analysis"]:
    lines.append(f"| {cn[x['name']]} | {100*x['paired']['delta']:+.2f} | {interval(x['paired']['ci95_normal'])} | {interval(x['family_normal_approx'])} | {interval(x['family_hoeffding'])} |")
lines += ["",
"真实查杀把首日放逐匪从26.68%提高到100%，但终局胜率只增加0.02个百分点，配对结果为76局改善、75局恶化。当前证据因此不能按终局胜率淘汰沉默。这里的原因不是查杀没有改变首日，而是冻结续局中减少一名匪徒没有稳定转化为保护警察；匪胜条件只看警察是否全灭，剩余匪徒仍能每夜共同刀一人。这个反常结果要求下一步检查续局与胜负规则敏感性。", "",
"验到好人时，真实金水相对沉默观察到+0.24个百分点；给警察队友金水为+0.12个百分点。真实金水的家族正态近似区间排除0，但保守同时Hoeffding区间很宽。队友金水把首日放逐警从18.87%降到2.64%，同时把放逐民提高到64.60%；它保护警察，却把风险转移给平民，终局证据不足以判定优于真实金水。", "",
"## 自刀矩阵与可信度", "",
"留出矩阵中的数字均为好人终局胜率：", "",
"| 好人回应 | 普通刀 | 自刀沉默 | 自刀假查杀 | 自刀队友金水 | 自刀未知非匪金水 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
for cgood, row in zip(holdout["matrix"]["good"], holdout["matrix"]["rates_exact"]):
    vals = []
    for value in row:
        a,b = (value.split('/')+[None])[:2]
        vals.append(float(a)/float(b) if b else float(a))
    lines.append("| " + labels[cgood] + " | " + " | ".join(pct(v) for v in vals) + " |")

train_eq = train["restricted_empirical_equilibrium"]
frozen = holdout["frozen_train_mixture_on_holdout"]
post = holdout["restricted_empirical_equilibrium"]
lines += ["",
f"训练经验矩阵的精确有理数受限解为 `{train_eq['value_exact']}`={pct(train_eq['value'])}。好人混合为相信死者且隐藏 `{train_eq['good_mixture'].get('trust_hidden','0')}`、怀疑死者 `{train_eq['good_mixture'].get('skeptic_hidden','0')}`；匪方为普通刀 `{train_eq['mafia_mixture'].get('ordinary','0')}`、自刀队友金水 `{train_eq['mafia_mixture'].get('self_ally_clear','0')}`。这个gap为0只属于训练经验矩阵。", "",
f"把训练混合固定到留出矩阵后，下界为{pct(frozen['lower'])}，上界为{pct(frozen['upper'])}，gap为{100*frozen['gap']:.2f}个百分点。留出矩阵事后受限解的值为 `{post['value_exact']}`={pct(post['value'])}，匪方可用普通刀纯策略；这只是诊断，未反过来修改冻结混合。", "",
"自刀沉默使好人胜率从普通刀的4.35%升到17.63%，说明单纯牺牲一名匪在该策略池中明显不划算。自刀假查杀和给随机未知非匪金水也大多提高好人胜率。唯一尖锐反制是给存活匪队友假金水：相信死者的三个方案好人胜率均为0%，怀疑死者则为17.63%。因此自刀未必需要在留出事后解中取得正概率，也会作为一个池内偏离限制好人无条件相信死者。", "",
"假查杀的4096个留出目标中，2711个是平民、1385个是警察，接近合法随机非匪目标的2:1比例。假查杀平民时，四警和被查平民共五人各自拥有反对死者声明的私人理由；查到警察时为四名警察。但公开观察者看见的是未经认证的声明与站队，不能知道这五人都属于好人。", "",
"在自刀假查杀下，活警隐藏时好人胜率13.18%，单警反驳4.66%，四警反驳4.32%；第二夜刀中警察分别为32.54%、93.77%和100%。这不是对所有反驳话术的定理，但明确反驳了“多人站队即可无成本证明死者是自刀匪”：当前协议中，公开反驳把真实警察直接交给夜刀。", "",
"## 如何理解", "",
"1. 查杀的局部行动效果很强，但当前终局效果弱，不能直接删除沉默分支；应先诊断为何首日必出匪没有转化为整局优势。", "2. 金水目标改变了错误放逐落点。保护警察队友确实显著减少首日出警，却消耗平民掩护，暂时没有稳定终局优势。", "3. 自刀沉默可以作为明显较差的机制对照；不能据此删除全部自刀。队友假金水是对盲信死者的强针对性偏离。", "4. 受限均衡支持混合信任的动机，但不提供完整游戏中的自刀频率、exploitability或GTO。策略池外的条件信任、真假警历史一致性和更好的反驳协议仍可能改变结果。", "",
"## 验证与复现", "",
f"正式批次执行20,480局死警实验、20,480局自刀训练和81,920局自刀留出。全量回归测试178项通过。审计检查5个死警单元、40个自刀单元、30个冻结资产，并从冻结源码抽样重放{audit['sampled_full_replays']}局，全部通过。抽样重放不是全部对局的第二套独立模拟器。", "",
"```sh", "PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q", "PYTHONDONTWRITEBYTECODE=1 python scripts/run_declaration_v12.py --output results/v12_reproduction --workers 4", "PYTHONDONTWRITEBYTECODE=1 python scripts/verify_declaration_v12.py results/v12 --replay --output results/v12_integrity_audit.json", "python scripts/build_declaration_report_v12.py", "```", "",
"证据文件：[冻结协议](declaration_protocol_v12.md)、[配置](../configs/declaration_v12.json)、[死警原始结果](../results/v12/dead_police.json)、[自刀训练](../results/v12/selfkill_train.json)、[自刀留出](../results/v12/selfkill_holdout.json)、[审计](../results/v12_integrity_audit.json)。", "",
"两批无效执行分别保存在`results/v12_invalid_pre_fix`与`results/v12_invalid_metric`，不参与本报告数值。"
]

(ROOT/"docs/declaration_results_v12.md").write_text("\n".join(lines)+"\n")
print(ROOT/"docs/declaration_results_v12.md")
