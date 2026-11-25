# Football Simulation

[English](README.en.md)

`main` 是团队的 2D 仿真基线，包含 1v1 实时测试、4v4 比赛计算、浏览器回放和批量测试。Webots 3D 接入目前在 `LWY` 分支开发。

## Windows 快速开始

从 GitHub 的 `main` 分支选择 **Code → Download ZIP**，然后完整解压。已有本地仓库时，可以切到 `main` 并拉取更新。

| 想做什么 | 打开哪个文件 |
| --- | --- |
| 直接看 1v1 | 双击 [五例回放](Football_1v1_Demo.html) 或 [七例对抗回放](Football_1v1_Cases_3-3-1.html) |
| 直接看 4v4 | 双击 [中文回放](Football_4v4_Demo_ZH.html) 或 [英文回放](Football_4v4_Demo.html) |
| 重新运行 1v1 | 双击 [1v1 启动脚本](2D_Shared_Policy_2026-11-11/start_windows.bat)。网页打开后点 **Play**，可用 **New random setup** 换开局，或用 **Repeat seed** 重跑当前开局 |
| 重新运行 4v4 | 双击 [4v4 启动脚本](Four_vs_Four/start_windows.bat)。程序先计算整场，再打开回放 |

HTML 回放离线打开即可。重新计算比赛需安装 Python 3.8 或更新版本，使用 Python 标准库即可。安装后可在 CMD 或 PowerShell 输入 `py -3 --version` 检查，若系统使用 `python` 命令则输入 `python --version`。 [Python for Windows](https://www.python.org/downloads/windows/)

在仓库根目录的 CMD 或 PowerShell 中，可以指定开局和语言。若系统只有 `python` 命令，将每行开头的 `py -3` 换成 `python`。

```powershell
py -3 Four_vs_Four/run.py --seed 27 --language zh --open
py -3 Four_vs_Four/run.py --seed 27 --batch 20 --no-replay
```

4v4 的输出在 `Four_vs_Four/runs/match_*/`。终端的 `4V4_READY` 行会给出本次路径。浏览器没有自动打开时，可从该目录双击 `replay.html`。批测用 `--no-replay` 时，查看 `metrics.json`。1v1 实时版需要保持终端窗口打开，浏览器没有自动打开时，把终端显示的本地网址复制到浏览器。

Ubuntu / macOS 从仓库根目录可运行 `python3 Four_vs_Four/run.py --language zh --open` 或 `python3 2D_Shared_Policy_2026-11-11/server.py --open`。也可单独下载并解压 [4v4 运行包](Football_4v4.zip) 或 [1v1 运行包](2D_Shared_Policy_2026-11-11.zip)。

## 已完成和待改进

| 板块 | 当前能做什么 | 下一轮要验证或改进什么 |
| --- | --- | --- |
| **1v1** | 设置出生区域，复测同一种子，观察带球绕行、抢断和解围，下载运行记录。 | 补测正面贴身、被过后回追和慢转向导致的失位。 [1v1 实时版说明](2D_Shared_Policy_2026-11-11/README.md) |
| **4v4** | 八名球员使用 `flow` 策略完成比赛。可观察短趟、指定队友接球、拦截、门将封角及进球后复位。 | 减少长时间围球，验证接球后能否继续推进或射门，并检查门前封角和解围。 [4v4 实验与限制](Four_vs_Four/README.md) |
| **测试工具** | 固定种子回放、实时报表下载、4v4 批跑和结果导出。4v4 可输出 `metrics.json`、`replay.html`、`scene.json`。 | 为前锋、后卫、门将和团队策略建立固定用例，按同一开局、球员速度和步长比较修改前后。 |
| **3D 与真机** | 2D 使用精确位置和简化运动、接触模型。摄像头误差、平衡和摔倒留待 3D 与真机验证。3D 接入的实验在 `LWY`。 | 用 Webots 复测挑选出的行为，再核实 NAO6 的感知、动作、平衡和实际速度。 |

4v4 回放中的球员目标线显示策略计划。判断传球是否成功，查看事件或 `metrics.json` 中的指定队友脚下接球统计。回放倍速只改变观看时间。

## 五人分工与代码入口

以下为按甘特图映射到当前仓库的任务。第一轮每个分支交一组能重跑的用例和结果，策略改动可随同提交。

| 分支 | 甘特图任务 | 主要代码与建议交付 |
| --- | --- | --- |
| **SBH** | 4.2 前锋 | [`Flow.py`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py) 的 [`attack()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L413)、[`choose_carry()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L874)、[`find_shot()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L559)。测试绕过后卫、丢球与射门。 |
| **CJL** | 3.1 球场规则、3.5 可视化与批跑、4.3 后卫 | 后卫从 `DefensivePlan.py` 的 [`interception()`](Four_vs_Four/backend/Wenao/controllers/Utils/DefensivePlan.py#L58)、[`recovery_action()`](Four_vs_Four/backend/Wenao/controllers/Utils/DefensivePlan.py#L99) 和 [`Flow.defend()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L1130) 入手。用 [`CourseSpecs.py`](Four_vs_Four/backend/Wenao/controllers/Utils/CourseSpecs.py#L26)、[`MatchEngine.py`](Four_vs_Four/backend/Wenao/controllers/Utils/MatchEngine.py#L108) 验证进球、出界和复位，可视化与规则变更独立提交。 |
| **LXR** | 3.4 感知表示、4.1 导航、4.4 门将 | 当前 `flow` 门将从 [`Flow.keep_goal()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L1272) 和 [`TeamNavigation.py`](Four_vs_Four/backend/Wenao/controllers/Utils/TeamNavigation.py#L99) 的门将分支入手。用近角、远角固定来球测试横移和触球，记录观测接口。 |
| **ZYH** | 4.5 团队策略、P0 集成 | [`Flow.py`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py) 的 [`pick_chaser()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L376)、[`place_support()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L774)、[`offer_width()`](Four_vs_Four/backend/Wenao/controllers/Utils/Flow.py#L806)。验证主抢、接应、补位及实际接球，并组织 PR 评审。 |
| **LWY** | 2.3 接口、3.2–3.3 模型、3.6 验证、4.6–4.7 对照实验 | [`soccer2d.py`](Four_vs_Four/backend/tools/soccer2d.py#L26) 的足球和机器人模型，[`run_policy_experiment.py`](Four_vs_Four/backend/tools/run_policy_experiment.py#L42) 的批量对照，以及 `LWY` 分支上的 2D→3D 适配。维护共同基线和测试记录。 |

策略、导航和裁判模块在 [四对四控制器目录](Four_vs_Four/backend/Wenao/controllers/Utils/)，仿真模型和实验入口在 [工具目录](Four_vs_Four/backend/tools/)。`Flow.py` 由多个成员共用，第一轮按表内函数划分改动。各自从最新 `main` 同步到个人分支，复测后发 PR 到 `main`。PR 写上任务号、开局或种子、运行命令和修改前后的结果。

## 更多记录

- [1v1 七例对抗说明](docs/ONE_V_ONE_CASES_3_3_1_2026-11-19.md) · [1v1 带球与抢断测试](docs/ATTACKING_DUELS_2026-11-19.md)
- [4v4 策略更新与数据](Four_vs_Four/README.md) · [早期团队配合对照](docs/FOUR_V_FOUR_TEAMWORK_2026-11-19.md)
- [2D 场地与模型图](2D_Pitch_and_Modelling_2026-11-04/) · [中英文数据来源图](S3_数据来源图片_中英文_2026-11-04/) · [验证脚本与记录](verification/)
