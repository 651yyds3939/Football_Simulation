# 2D Four vs Four

四对四平面机器人足球。独立于一攻一防版本和 Webots 三维工程，使用本目录内的 Python 策略及二维运动模型。

## 最简单的使用方法

只看效果：双击 `demo.html`，用 Chrome 或 Edge 打开，无需安装软件或联网。这是一次完整比赛的真实计算回放，不能在回放中修改策略。默认 32 倍，可选择最高 128 倍。

重新计算比赛需要 Python 3.8 或更新版本，无需额外 Python 依赖：

- Windows：双击 `start_windows.bat`。
- Ubuntu/Linux：运行 `bash start.sh`。
- macOS：可用 Python 3 运行 `python3 run.py --open`；本次未在 macOS 或 Windows 上实测。

启动后先全速计算，再自动打开浏览器回放。界面可暂停、拖动进度、逐帧查看、点击球员检查状态。球员速度不会因播放倍速而改变。128倍下十分钟比赛约五秒即可播完，屏幕快结束不代表只计算了五秒；以比赛时钟和结果文件为准。

在本目录打开终端也可以运行：

```sh
python run.py --open
python run.py --seed 28 --open
python run.py --red-policy coordinated --blue-policy baseline --batch 20 --no-replay
python run.py --red-policy baseline --blue-policy baseline --seed 27 --open
```

`coordinated` 是本次候选策略，`baseline` 是修改前的策略。默认双方使用候选策略。`--batch 20 --no-replay` 连续计算 20 个种子，不渲染，适合快速测试。完整比赛默认每半场 300 秒，计算步长 0.2 秒。

如需中文界面，运行 `python run.py --language zh --open`。每次修改策略后重新运行生成新的回放，旧 HTML 不会自动更新。

结果在自动新建的 `runs/match_时间/` 中：`replay.html` 是离线回放，`scene.json` 是轨迹，`metrics.json` 是结果和源码哈希。批量运行只为第一场生成回放；`--no-replay` 不保存轨迹。

## 本次改进与实际效果

候选策略忽略接球队员离球超过 0.60 米的传球交接，避免其他队员等待难以到达的传球；后卫的非追球站位更靠近本方球门。保留原运动、接触、射门和裁判模型，没有提高速度或强制进球。

独立的 50 个种子、交换红蓝双方共 100 场：候选策略对基线 **33 胜、32 负、35 平，进球 124:121**。没有证据表明整体胜率明显提高。平均无人近球时间有所减少，多人拥堵略有增加。候选策略仍需继续测试，传接球和密集争抢尚未解决。

这是精确位置输入下的二维简化模型，没有关节平衡、摔倒、相机误差或真实硬件接口，不能作为 Webots 或真机比赛性能证明。传球的模型滚动距离约 0.305 米，不能据此宣称已实现数米传球。

主要文件：`run.py` 管理比赛和输出；`backend/tools/soccer2d.py` 计算运动和接触；`backend/Wenao/controllers/Utils/TeamPolicy.py` 为基础决策；`TeamTactics.py` 为本次候选改动；`Navigation.py` 将决策目标转为动作；`MatchEngine.py` 执行阶段、计时和判球；两个 `soccer2d_viewer*.html` 为中英文回放界面。
