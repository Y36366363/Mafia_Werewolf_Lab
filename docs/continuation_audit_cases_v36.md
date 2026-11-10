# v36：查杀、金水和续局的逐局审计

以下角色只供读者复盘；所有策略只读自身Observation。案例来自既有／新批内首例，不增加独立验收。座位从1开始。

## historical/dead_q0/self_copy_early，seed=207000002（predeclared_previous_case）

最终好人胜。

- 第1日：1号（实际mafia，last_words）报金水2。
- 第1日：1号（实际mafia，last_words）内推—，名单3,4。
- 第1日：6号（实际mafia，day）报金水2。
- 第1日：6号（实际mafia，day）正式归票16。
- 第1日放逐16号（实际civilian）。
- 第2日：10号（实际police，day）报查杀7。
- 第2日：10号（实际police，day）内推—，名单6。
- 第2日：10号（实际police，day）正式归票6。
- 第2日放逐6号（实际mafia）。
- 第3日：11号（实际police，day）报查杀7。
- 第3日：11号（实际police，day）内推—，名单7。
- 第3日：11号（实际police，day）正式归票7。
- 第3日放逐7号（实际mafia）。
- 第4日：14号（实际police，day）报查杀8。
- 第4日：14号（实际police，day）内推—，名单8。
- 第4日：14号（实际police，day）正式归票8。
- 第4日放逐8号（实际mafia）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀1号（mafia）；验6号（mafia）。
- 第2夜：刀9号（civilian）；验7号（mafia）。
- 第3夜：刀10号（police）；验5号（civilian）。
- 第4夜：刀11号（police）；验8号（mafia）。

真实可执行查杀的首轮平民票：

- 第2日查杀7号：0/6张合法平民票跟该目标；其他票实际身份{'mafia': 6}。
- 第3日查杀7号：6/6张合法平民票跟该目标；其他票实际身份{}。
- 第4日查杀8号：6/6张合法平民票跟该目标；其他票实际身份{}。

同一金水发言的双目标（若有）：


## historical/dead_q50/self_copy_early，seed=207000002（predeclared_previous_case）

最终匪胜。

- 第1日：1号（实际mafia，last_words）报金水2。
- 第1日：1号（实际mafia，last_words）内推—，名单3,4。
- 第1日：2号（实际police，day）报查杀6。
- 第1日：2号（实际police，day）内推—，名单6。
- 第1日：2号（实际police，day）正式归票6。
- 第1日：6号（实际mafia，day）报金水2。
- 第1日：6号（实际mafia，day）正式归票16。
- 第1日放逐6号（实际mafia）。
- 第1日：6号（实际mafia，last_words）报金水9。
- 第1日：6号（实际mafia，last_words）内推—，名单10,11。
- 第2日：2号（实际police，last_words）报查杀7。
- 第2日：10号（实际police，day）报查杀7。
- 第2日：10号（实际police，day）内推—，名单7。
- 第2日：10号（实际police，day）正式归票7。
- 第2日放逐7号（实际mafia）。
- 第3日：11号（实际police，day）报金水4。
- 第3日：11号（实际police，day）内推—，名单12,13。
- 第3日：4号（实际civilian，day）正式归票11。
- 第3日：4号（实际civilian，day）接力归票12。
- 第3日放逐12号（实际civilian）。
- 第4日：14号（实际police，day）报金水5。
- 第4日：14号（实际police，day）内推—，名单13,15。
- 第4日：5号（实际civilian，day）正式归票13。
- 第4日：5号（实际civilian，day）接力归票13。
- 第4日放逐13号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀1号（mafia）；验6号（mafia）。
- 第2夜：刀2号（police）；验7号（mafia）。
- 第3夜：刀10号（police）；验4号（civilian）。
- 第4夜：刀11号（police）；验5号（civilian）。
- 第5夜：刀14号（police）；验8号（mafia）。

真实可执行查杀的首轮平民票：

- 第1日查杀6号：8/8张合法平民票跟该目标；其他票实际身份{}。
- 第2日查杀7号：8/8张合法平民票跟该目标；其他票实际身份{}。

同一金水发言的双目标（若有）：

- 第3日4号：普通accuse归11号，relay归12号；最终本人首轮投12号。

## fresh/dead_q0/self_copy_early，seed=210000004（gold_dual_action）

最终匪胜。

- 第1日：3号（实际mafia，last_words）报金水4。
- 第1日：3号（实际mafia，last_words）内推—，名单6,7。
- 第1日：5号（实际mafia，day）报金水4。
- 第1日：5号（实际mafia，day）正式归票2。
- 第1日：4号（实际civilian，day）接力归票2。
- 第1日放逐2号（实际civilian）。
- 第2日：15号（实际police，last_words）报金水4。
- 第2日：7号（实际police，day）报金水4。
- 第2日：7号（实际police，day）内推—，名单16,1。
- 第2日：7号（实际police，day）正式归票5。
- 第2日放逐5号（实际mafia）。
- 第3日：8号（实际police，day）报金水1。
- 第3日：8号（实际police，day）内推—，名单9,10。
- 第3日：1号（实际civilian，day）正式归票8。
- 第3日：1号（实际civilian，day）接力归票9。
- 第3日放逐9号（实际civilian）。
- 第4日：13号（实际police，day）报金水16。
- 第4日：13号（实际police，day）内推—，名单10,11。
- 第4日：16号（实际civilian，day）正式归票10。
- 第4日：16号（实际civilian，day）接力归票10。
- 第4日放逐10号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀3号（mafia）；验3号（mafia）。
- 第2夜：刀15号（police）；验4号（civilian）。
- 第3夜：刀7号（police）；验1号（civilian）。
- 第4夜：刀8号（police）；验16号（civilian）。
- 第5夜：刀13号（police）；验6号（civilian）。

真实可执行查杀的首轮平民票：


同一金水发言的双目标（若有）：

- 第3日1号：普通accuse归8号，relay归9号；最终本人首轮投9号。

## fresh/dead_q0/self_copy_team_relay，seed=210000004（gold_dual_action）

最终匪胜。

- 第1日：3号（实际mafia，last_words）报金水5。
- 第1日：3号（实际mafia，last_words）内推—，名单4,6。
- 第1日：11号（实际mafia，day）报金水5。
- 第1日：11号（实际mafia，day）正式归票2。
- 第1日：5号（实际mafia，day）接力归票2。
- 第1日放逐2号（实际civilian）。
- 第2日：15号（实际police，last_words）报金水4。
- 第2日：7号（实际police，day）报金水4。
- 第2日：7号（实际police，day）内推—，名单16,1。
- 第2日：7号（实际police，day）正式归票11。
- 第2日放逐11号（实际mafia）。
- 第3日：8号（实际police，day）报金水1。
- 第3日：8号（实际police，day）内推—，名单9,10。
- 第3日：1号（实际civilian，day）正式归票8。
- 第3日：1号（实际civilian，day）接力归票9。
- 第3日放逐9号（实际civilian）。
- 第4日：13号（实际police，day）报金水16。
- 第4日：13号（实际police，day）内推—，名单10,12。
- 第4日：16号（实际civilian，day）正式归票10。
- 第4日：16号（实际civilian，day）接力归票10。
- 第4日放逐10号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀3号（mafia）；验3号（mafia）。
- 第2夜：刀15号（police）；验4号（civilian）。
- 第3夜：刀7号（police）；验1号（civilian）。
- 第4夜：刀8号（police）；验16号（civilian）。
- 第5夜：刀13号（police）；验5号（mafia）。

真实可执行查杀的首轮平民票：


同一金水发言的双目标（若有）：

- 第3日1号：普通accuse归8号，relay归9号；最终本人首轮投9号。

## fresh/dead_q50/self_copy_early，seed=210000002（unfollowed_truth_hit）

最终匪胜。

- 第1日：7号（实际mafia，last_words）报金水10。
- 第1日：7号（实际mafia，last_words）内推—，名单11,12。
- 第1日：8号（实际mafia，day）报金水10。
- 第1日：8号（实际mafia，day）正式归票6。
- 第1日：12号（实际police，day）报查杀8。
- 第1日：12号（实际police，day）内推—，名单8。
- 第1日：12号（实际police，day）正式归票8。
- 第1日：10号（实际civilian，day）接力归票12。
- 第1日放逐12号（实际police）。
- 第1日：12号（实际police，last_words）报查杀8。
- 第2日：16号（实际police，day）报查杀8。
- 第2日：16号（实际police，day）内推—，名单8。
- 第2日：16号（实际police，day）正式归票8。
- 第2日放逐8号（实际mafia）。
- 第3日：2号（实际police，day）报查杀9。
- 第3日：2号（实际police，day）内推—，名单9。
- 第3日：2号（实际police，day）正式归票9。
- 第3日放逐9号（实际mafia）。
- 第4日：4号（实际police，day）报金水11。
- 第4日：4号（实际police，day）内推—，名单3,5。
- 第4日：11号（实际civilian，day）正式归票3。
- 第4日：11号（实际civilian，day）接力归票3。
- 第4日放逐3号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀7号（mafia）；验8号（mafia）。
- 第2夜：刀10号（civilian）；验10号（civilian）。
- 第3夜：刀16号（police）；验9号（mafia）。
- 第4夜：刀2号（police）；验11号（civilian）。
- 第5夜：刀4号（police）；验13号（civilian）。

真实可执行查杀的首轮平民票：

- 第1日查杀8号：0/8张合法平民票跟该目标；其他票实际身份{'police': 8}。
- 第2日查杀8号：7/7张合法平民票跟该目标；其他票实际身份{}。
- 第3日查杀9号：7/7张合法平民票跟该目标；其他票实际身份{}。

同一金水发言的双目标（若有）：


## fresh/dead_q50/self_copy_early，seed=210000130（truth_hit_exile_then_loss）

最终匪胜。

- 第1日：6号（实际mafia，last_words）报金水7。
- 第1日：6号（实际mafia，last_words）内推—，名单8,10。
- 第1日：9号（实际mafia，day）报金水7。
- 第1日：9号（实际mafia，day）正式归票5。
- 第1日：13号（实际police，day）报查杀9。
- 第1日：13号（实际police，day）内推—，名单9。
- 第1日：13号（实际police，day）正式归票9。
- 第1日：7号（实际civilian，day）接力归票9。
- 第1日放逐9号（实际mafia）。
- 第1日：9号（实际mafia，last_words）报金水10。
- 第1日：9号（实际mafia，last_words）内推—，名单12,13。
- 第2日：13号（实际police，last_words）报金水8。
- 第2日：2号（实际police，day）报金水8。
- 第2日：2号（实际police，day）内推—，名单14,15。
- 第2日：8号（实际civilian，day）正式归票14。
- 第2日：8号（实际civilian，day）接力归票14。
- 第2日放逐14号（实际civilian）。
- 第3日：4号（实际police，day）报查杀11。
- 第3日：4号（实际police，day）内推—，名单11。
- 第3日：4号（实际police，day）正式归票11。
- 第3日放逐11号（实际mafia）。
- 第4日：5号（实际police，day）报金水12。
- 第4日：5号（实际police，day）内推—，名单7,10。
- 第4日：12号（实际civilian，day）正式归票5。
- 第4日：12号（实际civilian，day）接力归票7。
- 第4日放逐7号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀6号（mafia）；验9号（mafia）。
- 第2夜：刀13号（police）；验8号（civilian）。
- 第3夜：刀2号（police）；验11号（mafia）。
- 第4夜：刀4号（police）；验12号（civilian）。
- 第5夜：刀5号（police）；验15号（mafia）。

真实可执行查杀的首轮平民票：

- 第1日查杀9号：5/8张合法平民票跟该目标；其他票实际身份{'police': 3}。
- 第3日查杀11号：7/7张合法平民票跟该目标；其他票实际身份{}。

同一金水发言的双目标（若有）：

- 第4日12号：普通accuse归5号，relay归7号；最终本人首轮投7号。

## fresh/dead_q50/self_copy_early，seed=210000004（gold_dual_action）

最终匪胜。

- 第1日：3号（实际mafia，last_words）报金水4。
- 第1日：3号（实际mafia，last_words）内推—，名单6,7。
- 第1日：5号（实际mafia，day）报金水4。
- 第1日：5号（实际mafia，day）正式归票2。
- 第1日：4号（实际civilian，day）接力归票2。
- 第1日放逐2号（实际civilian）。
- 第2日：15号（实际police，last_words）报金水4。
- 第2日：7号（实际police，day）报金水4。
- 第2日：7号（实际police，day）内推—，名单16,1。
- 第2日：7号（实际police，day）正式归票5。
- 第2日放逐5号（实际mafia）。
- 第3日：8号（实际police，day）报金水1。
- 第3日：8号（实际police，day）内推—，名单9,10。
- 第3日：1号（实际civilian，day）正式归票8。
- 第3日：1号（实际civilian，day）接力归票9。
- 第3日放逐9号（实际civilian）。
- 第4日：13号（实际police，day）报金水16。
- 第4日：13号（实际police，day）内推—，名单10,11。
- 第4日：16号（实际civilian，day）正式归票10。
- 第4日：16号（实际civilian，day）接力归票10。
- 第4日放逐10号（实际civilian）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀3号（mafia）；验3号（mafia）。
- 第2夜：刀15号（police）；验4号（civilian）。
- 第3夜：刀7号（police）；验1号（civilian）。
- 第4夜：刀8号（police）；验16号（civilian）。
- 第5夜：刀13号（police）；验6号（civilian）。

真实可执行查杀的首轮平民票：


同一金水发言的双目标（若有）：

- 第3日1号：普通accuse归8号，relay归9号；最终本人首轮投9号。

## fresh/dead_q50/self_copy_team_relay，seed=210000002（unfollowed_truth_hit）

最终匪胜。

- 第1日：7号（实际mafia，last_words）报金水8。
- 第1日：7号（实际mafia，last_words）内推—，名单10,11。
- 第1日：9号（实际mafia，day）报金水8。
- 第1日：9号（实际mafia，day）正式归票6。
- 第1日：12号（实际police，day）报查杀8。
- 第1日：12号（实际police，day）内推—，名单8。
- 第1日：12号（实际police，day）正式归票8。
- 第1日：8号（实际mafia，day）接力归票6。
- 第1日放逐12号（实际police）。
- 第1日：12号（实际police，last_words）报查杀8。
- 第2日：16号（实际police，day）报查杀8。
- 第2日：16号（实际police，day）内推—，名单8。
- 第2日：16号（实际police，day）正式归票8。
- 第2日放逐16号（实际police）。
- 第3日：2号（实际police，day）报查杀8。
- 第3日：2号（实际police，day）内推—，名单8。
- 第3日：2号（实际police，day）正式归票8。
- 第3日放逐2号（实际police）。
- 第4日：4号（实际police，day）报查杀8。
- 第4日：4号（实际police，day）内推—，名单8。
- 第4日：4号（实际police，day）正式归票8。
- 第4日放逐4号（实际police）。

每夜实际动作（包括夜间直接终局）：

- 第1夜：刀7号（mafia）；验8号（mafia）。
- 第2夜：刀10号（civilian）；验10号（civilian）。
- 第3夜：刀15号（civilian）；验11号（civilian）。
- 第4夜：刀1号（civilian）；验13号（civilian）。

真实可执行查杀的首轮平民票：

- 第1日查杀8号：0/8张合法平民票跟该目标；其他票实际身份{'police': 8}。
- 第2日查杀8号：0/7张合法平民票跟该目标；其他票实际身份{'police': 7}。
- 第3日查杀8号：0/6张合法平民票跟该目标；其他票实际身份{'police': 6}。
- 第4日查杀8号：0/5张合法平民票跟该目标；其他票实际身份{'police': 5}。

同一金水发言的双目标（若有）：
