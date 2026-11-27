# Football Simulation 项目说明（SBH 分支）

更新日期：2026-11-27  
适用版本：SBH 分支，编写时基于提交 `bbee9cd`。本文介绍已有功能与使用方式；前锋改进部分为后续工作建议，不代表已完成的新功能。

## 1. 项目目标

本项目提供二维机器人足球仿真环境，用于观察和比较机器人接近足球、带球、射门、拦截、回追与团队配合行为。通过固定种子、浏览器回放和运行记录，可以复现失败场景，并比较策略调整前后的效果。

项目包含一攻一防（1v1）实时测试和四对四（4v4）比赛计算。二维模型用于快速验证策略；Webots 三维仿真及真实机器人验证是独立环节，不能直接用二维成绩替代。

## 2. 主要功能

| 模块 | 当前功能 | 主要用途 |
| --- | --- | --- |
| 1v1 实时测试 | 随机开局、重复种子、出生区域设置、带球绕行、防守拦截、运行数据下载 | 观察单次攻防及复现问题 |
| 4v4 比赛 | 比赛计算、接应点选择、局部让位、保守短传、策略对照及批量运行 | 检查团队配合与比赛结果 |
| 离线回放 | 暂停、进度查看、倍速播放；部分回放支持逐帧和球员查看 | 展示与行为分析 |
| 模型与验证资料 | 场地及运动模型图、参数来源、历史实验记录 | 理解模型假设和追踪改动 |

## 3. 快速开始

### 3.1 获取当前分支

在 GitHub 选择 **SBH** 分支，再使用 **Code → Download ZIP** 下载并完整解压。不要在压缩包内直接运行程序。

只看已有 HTML 回放时，无需安装 Python 或 Webots。重新计算比赛需要 Python 3.8 或更新版本，日常仿真使用 Python 标准库。

### 3.2 直接观看回放

用 Chrome 或 Edge 打开仓库根目录中的文件：

- [1v1 五例回放](Football_1v1_Demo.html)
- [1v1 七例对抗回放](Football_1v1_Cases_3-3-1.html)
- [4v4 中文回放](Football_4v4_Demo_ZH.html)
- [4v4 英文回放](Football_4v4_Demo.html)

这些文件是预先生成的回放。修改 Python 策略后，需要重新运行并生成新的回放，已有 HTML 不会自动变化。

### 3.3 运行 1v1

Windows 下双击 [1v1 启动脚本](2D_Shared_Policy_2026-11-11/start_windows.bat)。浏览器打开后点击 **Play**，保持终端窗口开启。浏览器未自动打开时，复制终端显示的网址访问。

- **New random setup**：生成新的开局。
- **Repeat seed**：重复当前种子，便于对照。
- **Spawn rectangles**：设置双方出生矩形区域。
- **Download run data**：保存当前运行记录。
- **Fast test ×20**：批量测试并查看总体结果。

Linux 可在 `2D_Shared_Policy_2026-11-11` 目录运行 `bash start.sh`。修改策略后应重新启动服务，仅刷新网页不会加载新的 Python 代码。

### 3.4 运行 4v4

Windows 下双击 [4v4 启动脚本](Four_vs_Four/start_windows.bat)。程序先计算比赛，再打开浏览器播放结果。

以下命令均从仓库根目录运行；Windows 可将 `python` 替换为 `py -3`，macOS/Linux 可替换为 `python3`：

```sh
python Four_vs_Four/run.py --seed 27 --language zh --open
python Four_vs_Four/run.py --red-policy coordinated --blue-policy previous --seed 222000 --open
python Four_vs_Four/run.py --red-policy coordinated --blue-policy previous --seed 222000 --batch 20 --no-replay
```

本分支支持的策略选项：`coordinated`（接应与短传策略，默认双方使用）、`previous`（上一轮对照策略）、`baseline`（基础策略）。

结果位于 `Four_vs_Four/runs/match_时间/`：

- `metrics.json`：比分及源码哈希等结果信息。
- `replay.html`：浏览器回放。
- `scene.json`：轨迹数据。

批量运行只为第一场生成回放；使用 `--no-replay` 时不记录回放轨迹。

## 4. 目录与代码入口

| 路径 | 内容 |
| --- | --- |
| `2D_Shared_Policy_2026-11-11/` | 1v1 服务、网页界面和独立后端快照 |
| `Four_vs_Four/run.py` | 4v4 命令行与批量运行入口 |
| `Four_vs_Four/backend/Wenao/controllers/Utils/TeamTactics.py` | 4v4 接应、让位和短传配合 |
| `Four_vs_Four/backend/Wenao/controllers/Utils/TeamNavigation.py` | 4v4 无球导航 |
| `Four_vs_Four/backend/Wenao/controllers/Utils/PreviousTactics.py` | 上一轮对照策略 |
| 两个运行目录下的 `backend/Wenao/controllers/Utils/` | `TeamPolicy.py`、`Navigation.py`、`DefensivePlan.py`、`MatchEngine.py` 等决策、导航、防守与比赛模块 |
| 两个运行目录下的 `backend/tools/soccer2d.py` | 二维运动和接触模型 |
| `2D_Pitch_and_Modelling_2026-11-04/` | 场地、足球和机器人模型图及导出脚本 |
| `docs/` | 策略调整、模型限制及历史测试说明 |
| `verification/` | 验证数据、历史快照、实验与打包脚本 |

1v1 与 4v4 各自包含后端代码。修改其中一份不会自动修改另一份。开发前应确认正在运行的入口和实际导入的模块。

## 5. SBH 前锋工作建议

SBH 分支可围绕前锋的接近足球、带球突破、射门选择以及丢球后反抢开展实验。建议先用 1v1 隔离单项行为，再用 4v4 检查与队友配合时的表现。

| 建议用例 | 观察重点 | 建议记录 |
| --- | --- | --- |
| 无阻挡接近球门 | 能否稳定带球并完成射门 | 进球结果、耗时、失控情况 |
| 正面遭遇后卫 | 是否提前绕行、贴身时是否频繁转向 | 首次突破、首次丢球、僵持时间 |
| 边路推进 | 绕行路线是否导致出界 | 出界次数、推进方向、最终结果 |
| 丢球后反抢 | 能否及时回追并重新争球 | 恢复接触耗时及后续控球情况 |
| 4v4 接球后处理 | 接球后能否继续推进或射门 | 指定队友接触、后续脚下接触、推进或射门结果 |

上述用例是建议测试计划，本说明没有新增策略或执行新一轮仿真测试。最近触球不等于稳定控球，目标虚线也不等于已完成传球，应结合事件、轨迹和结果文件判断。

## 6. 对照测试与提交方法

1. 记录分支、提交号、运行命令、种子、仿真步长、时长和双方策略。
2. 保存修改前的基线结果，再修改一个明确的策略点。
3. 使用相同设置和同一组种子比较修改前后结果；4v4 可交换双方颜色，减少单侧开局影响。
4. 保留成功与失败案例，记录进球、丢球、出界、超时和僵持，不只选取成功回放。
5. 提交代码时附上改动目的、测试命令和结果路径。需合入主分支时，再发起从 SBH 到 main 的 Pull Request。

本文描述的是当前 SBH 版本。其他分支的文件、策略名和实验结果可能不同，使用前应核对分支；不能直接将 main 的新版模块名套用到本分支。

## 7. 已知限制

- 二维仿真使用精确位置和简化接触模型，不模拟相机误差、平衡、摔倒等真机因素。
- 行走与转向的处理会影响贴身对抗，仍可能出现僵持、转向过慢或防守失败。
- 当前 4v4 短传较少，接球后推进尚不稳定；已有说明未证明整体胜率明显提升。
- 播放倍速只改变观看速度，不提高机器人能力。
- 历史实验使用不同开局与设置，不同报告的数字不能直接混为同一组对照。
- 部分历史脚本引用旧工作区或外部资料路径，运行前需检查输入文件；图表再生成可能需要额外绘图库和字体。

## 8. 进一步阅读

- [仓库原有 README](README.md)
- [1v1 使用说明](2D_Shared_Policy_2026-11-11/README.md)
- [4v4 使用说明](Four_vs_Four/README.md)
- [带球与正面对抗记录](docs/ATTACKING_DUELS_2026-11-19.md)
- [4v4 团队配合记录](docs/FOUR_V_FOUR_TEAMWORK_2026-11-19.md)
- [已上传的中英文说明 PDF](2D机器人足球仿真_中英文说明.pdf)

本说明依据上述 SBH 分支文件整理，运行参数同时核对了 `Four_vs_Four/run.py`。
