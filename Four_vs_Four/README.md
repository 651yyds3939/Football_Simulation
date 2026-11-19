# 2D 四对四机器人足球

## 直接看

双击 `demo.html`，用 Chrome 或 Edge 打开即可。无需 Python、Webots 或联网。这是完整比赛的离线回放：蓝队使用本轮配合策略，红队使用上一轮策略，示例包含一次指定队友接球。

默认32倍，可选最高128倍；支持暂停、拖动进度、逐帧查看和点击球员。“Team targets / 球队目标点”虚线显示实际决策目标，可以关闭。目标点不是走过的轨迹，也不代表已完成传球。

## 重新运行

安装 Python 3.8 或更新版本，不需要额外 Python 依赖。

- Windows：双击 `start_windows.bat`。
- Ubuntu/Linux：在本目录运行 `bash start.sh`。
- macOS：在本目录运行 `python3 run.py --open`。

程序先全速计算比赛，再打开浏览器回放。128倍下十分钟比赛约五秒播完，比赛实际时长以画面时钟和结果文件为准。

也可以在本目录运行：

```sh
python run.py --open
python run.py --seed 28 --language zh --open
python run.py --red-policy coordinated --blue-policy previous --seed 222000 --open
python run.py --red-policy coordinated --blue-policy previous --seed 222000 --batch 20 --no-replay
```

- `coordinated`：本轮接应、让位和保守短传策略，默认双方均使用。
- `previous`：上一轮策略，供对照。
- `baseline`：基础TeamPolicy策略。
- `--batch 20 --no-replay`：全速批量计算20个种子，不渲染。

结果自动保存在新建的 `runs/match_时间/` 中：`metrics.json` 为比分和源码哈希，`replay.html` 为回放，`scene.json` 为轨迹。批量模式只给第一场生成回放；`--no-replay` 不记录轨迹。修改代码后需要重新生成，旧HTML不会自动更新。

## 这次改了什么

无球队员根据到达时间、对手距离和线路寻找接应点，短暂保持目标，进入争球区时局部让位。补位可以使用原有的倒退、侧移等动作，减少不必要的大转身。短传只在附近队友朝向合适、线路清楚且压力允许时触发；接球队员先准备，实际踢到球后再接近，踢空则取消等待。

守门员保持防线、后卫保护后方仍是正常分工，不会让所有人一起追球。没有提高机器人速度、踢球力量或传球距离。

## 效果和不足

带短传的候选100场对上一轮：31胜32负37平；12次定向传球尝试、11次指定接球队员接触、10次带后续脚下接触。加上比赛阶段保护后的最终版本，在另外30个种子交换颜色的60场中为22胜22负16平，出现6次带脚下接触的短传。

配合有了可执行的短传，但还很少；展示例接球后仍需长时间转向，尚未稳定转化为推进。整体胜率没有明显提升，拥堵和无人近球仍会发生。更细步长的小样本表现也不稳定。二维使用精确位置和简化接触，不模拟摔倒、平衡或相机误差，不能代表Webots或真机成绩。

主要文件：`run.py` 为入口；`TeamTactics.py` 为本轮配合策略；`TeamNavigation.py` 为无球导航和半场重新安装导航；`PreviousTactics.py` 为上一轮对照；`TeamPolicy.py`、`Navigation.py` 为基础决策和执行；`soccer2d.py` 为运动、接触和传球消息状态；`MatchEngine.py` 为阶段、规则和比分。这些Python模块在 `backend/Wenao/controllers/Utils/` 或 `backend/tools/` 中。
