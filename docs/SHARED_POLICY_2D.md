# 二维与 Webots 共用策略

`Utils/TeamPolicy.py` 与 `Utils/Navigation.py` 是纯 Python 行为、导航模块。`Utils/PolicyProfile.py` 为二维和三维创建相同配置的策略对象与导航器，统一 `legacy/guarded`、射门瞄准设置和可选实验名单。

`Base/SoccerController.py` 继续使用 Webots 的观测、IMU 和关节执行器。默认名单为空，保持原来的八台机器人观测。只有实验显式设置 `TDP_ACTIVE_PLAYERS` 时，才筛选策略可见名单。

配套实时二维工具位于本工作区的仓库同级目录：

```text
../2D_Shared_Policy_2026-11-11/
```

运行该目录的 `bash start.sh`。它默认直接导入本仓库的 Python 文件，浏览器仅显示和控制；没有单独的 JavaScript 策略。配套压缩包附有可移植源代码快照，移走原工作区后仍可运行。详细用法见工具目录的 README。

## 快速筛选

```bash
python3 ../2D_Shared_Policy_2026-11-11/server.py \
  --batch 20 --scenario random --seed 27 --seconds 180 \
  --locomotion guarded --output runs/shared_2d_baseline_01
```

使用新输出目录。改动后用相同种子、时长和配置再次运行。输出包含逐场结果、实际计算耗时、虚拟仿真时长、代码 SHA-256 和第一场完整 HTML 回放。

## 相同输入下的三维决策检查

```bash
python tests/run_shared_policy_webots.py --seconds 12 --locomotion guarded \
  --output runs/shared_3d_inputs_01
python tools/check_policy_trace.py runs/shared_3d_inputs_01
```

此实验在临时世界中运行原来的 RedForwardA、BlueDefender 两个控制器，将其他六台停在场外并从策略观测中排除。保存实际输入、滤波后朝向、配置、行为、目标、请求动作和导航阶段。校验工具按同样顺序重放输入，检查输出一致。

正常运行默认不开详细输入记录。可用 `TDP_POLICY_TRACE=1` 启用，它不改变策略选择。

## 验证范围

本次短 Webots 实验记录的 95 条导航请求经共用模块重算后全部一致。82 项单元与回归检查通过。打包快照与工作区的源文件哈希一致，相同种子和设置下二维结果一致。浏览器的实时计算、拖动开局、批量计算和离线回放也已检查。

这不等于运动轨迹一致。Webots 仍有 IMU 滤波、站稳等待、动作切换、碰撞与摔倒恢复；二维用平均速度、圆盘和简化接触。二维用于快速找策略问题，三维用于验证物理执行。没有证明真机可迁移，也没有给出一般性攻防成功率。

## 贴身僵持修正

二维碰撞剩余位移与共用策略的遇堵让位记录见 [贴身争球僵持排查](DUEL_CONGESTION.md)。该次单元与回归检查为 89 项，短 Webots 门前接口检查为 95 条决策请求一致。这个三维门前用例不覆盖贴身侧移，因此不能据此认定新让位动作在三维中已稳定。

## 被突破后的回防

共用策略包含 `RECOVER_DEFENCE`，避免防守球员被突破后仍沿解围流程先转半圈。三维固定压力检查为 `python tests/run_shared_policy_webots.py --scenario breakaway --seconds 12 --output runs/recovery_3d_01`，再使用前述 `check_policy_trace.py` 检查记录。二维的同名预设现已改为球门侧斜向拦截开局，不再预先把防守者放在身后。

该次 95 项回归检查通过；三维回防场景 252 条决策请求一致，且原控制器实际执行倒退。该修改减少动作等待，没有证明整体防守成功率提高。详细条件、前后对照和未保留的试验见 [回防响应排查](DEFENSIVE_RECOVERY.md)。

## 近距离封堵与断球

当前增加共用 `CHALLENGE` 决策，修正近球转向导致错过触球窗口的问题，并区分进攻换位与防守覆盖球路。二维执行器另有身体/足球穿透约束和双方同时触球组合修正。两类修改的对照、同模型旧策略测试及剩余失败见 [封堵与断球验证](DEFENSIVE_CHALLENGE.md)。

当前 105 项回归检查通过，24 秒 Webots 正面对抗用例有 150 条实际决策请求一致。该三维用例发生过红方起身，尚不能证明完整对抗稳定。二维固定演示可用 `bash start.sh --scenario block`，便携包新增 `defence_replay.html` 用于离线展示。

## 最新：提前预判拦截与球门侧出生

新增共用 `DefensivePlan.py` 和 `DEFENSIVE_INTERCEPT`，用现有动作平均速度估计到达时间，在接触前移动到预测球路。所有二维内置开局均保证防守者比进攻者和足球更接近右侧球门，默认播放速度为 8 倍。

113 项回归检查通过；新增 24 秒 Webots 拦截用例的 446 条实际输入重算一致。相同 100 个新开局下，红方进球 82→63、蓝方进球 18→33、超时 0→4。贴身僵持仍存在，不将超时算作防守成功。条件、对照方法和限制见 [预判拦截验证](PREDICTIVE_DEFENCE.md)。
