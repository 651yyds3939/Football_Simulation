# 角色支援策略实验


## 实验内容

- 二维工具复用 `TeamPolicy`、`Navigator` 和 `MatchEngine`，用于快速比较角色行为。
- 可选 `support_mode=possession` 在对手明显更接近足球时，让非追球前锋回撤支援；距离优势只是控球代理。
- 默认仍使用 baseline；未验证有效的候选不作为比赛默认配置。
- 模型、动作速度与来源记录保持可追溯，不能将简化二维结果作为真机性能。

## 对照怎样隔离

默认仍为baseline。候选只改变指定队伍非追球前锋的支援目标，不改变双方运动能力、射门条件、球模型、守门/后卫逻辑或裁判。距离优势只是控球代理，不是真实控球测量。

当前候选在本轮三维场次中退化，拒绝设为默认；以下候选命令用于复现失败结果，不是推荐比赛配置。

- 每个seed分别让RED、BLUE使用候选，对手始终使用baseline；开球和初始布局相同。
- 同seed两场是相关配对样本，不是完全独立的两个重复。
- 各球员使用独立的踢球噪声流，防止一队动作数量改变另一队的随机序列。
- 无候选自对弈用于检查标签/配置不改变轨迹，不用来证明收益。
- 原始事件、可选1 Hz观测、逐场结果、配置、源文件散列与源码快照一起保存。
- Webots每个球员的命令日志记录实际 `support_mode`，不只相信运行器参数。

## 模型与局限

二维沿用9×6 m几何、0.07 m球半径、整球越线和当前比赛状态机。机器人用平面圆盘近似；球使用滚动减速、局部推球和圆盘阻挡。没有关节、平衡、踢腿接触全过程、球的高度或身体犯规。

| 参数 | 来源/初值 | 限制 |
| --- | --- | --- |
| 前进约0.08525 m/s及其他方向的平均速度 | 已有 `verification/development/navigation/motion-result.json` | 一次隔离场景的均值，不是真机标定或完整动作调度 |
| 射门/传球参考距离约0.406/0.305 m | 已有 `verification/development/navigation/skills-result.json` | 传球值含接球者影响，不是自由滚动射程，仍需标定 |
| 射门4.8 s、传球3.299 s | 当前动作文件时长 | 等待结束再检查脚下是否仍有球，没有完整踢腿轨迹 |
| 球减速度0.35 m/s²、误差0.04 rad、圆盘半径0.15 m、反射系数0.35 | 显式模型假设 | 未物理标定；减速度另外用0.2/0.5做敏感性检查 |
| 观测 | 完整真值 | 不验证独立感知，适用阶段需导师确认 |

二维不随机制造“跌倒”。圆盘重叠暴露不是Webots接触或跌倒，模型传接也不是物理传接成功。每半场摆阵是声明的夹具，不计自主列队。

默认二维为300秒半场、READY 10秒；三维本轮为300秒半场、READY 45秒。均为开发实验赛程，不宣称已经完成课程全部正式规则。

## 实际使用

仓库根目录执行，每次采用新输出目录：

```bash
conda activate robotics-tdp

# 无需启动Webots，20场二维配对实验
python tools/run_policy_experiment.py \
  --seeds 27 28 29 30 31 32 33 34 35 36 --trace \
  --output runs/support_2d_next_01

# 球模型敏感性：双方同时采用同一模型假设
python tools/run_policy_experiment.py \
  --seeds 27 28 29 30 31 32 33 34 35 36 \
  --rolling-deceleration .2 --output runs/support_friction_next_01

# 三维固定基线
python tests/run_webots_check.py --match --locomotion guarded --diagnostics \
  --half-seconds 300 --ready-seconds 45 --stuck-seconds 120 \
  --reset-formation --seed 27 --output runs/support_3d_baseline_next_01

# 仅红队使用候选，蓝队仍为baseline
python tests/run_webots_check.py --match --locomotion guarded --diagnostics \
  --support-mode possession --candidate-team RED \
  --half-seconds 300 --ready-seconds 45 --stuck-seconds 120 \
  --reset-formation --seed 27 --output runs/support_3d_candidate_next_01
```

交换候选队改为 `--candidate-team BLUE`，另用新输出目录。二维读取 `summary.json`；三维用已有工具：

```bash
python tools/evaluate_run.py runs/support_3d_candidate_next_01 \
  --output runs/support_3d_candidate_next_01/metrics.json
python tools/analyze_multiplayer_run.py runs/support_3d_candidate_next_01 \
  --output runs/support_3d_candidate_next_01/multiplayer-analysis.json

# 同时核对种子、源码、动作、赛程和每位球员的实际配置
python tools/compare_support_runs.py \
  runs/support_3d_baseline_next_01 runs/support_3d_candidate_next_01 \
  --output runs/support_3d_candidate_next_01/comparison.json
```

不因一场进球或单项覆盖指标改善而自动接纳。需要同时看得失球、有效比赛时间、拥堵、角色任务、失稳与单人回归。若收益不明确或三维退化，保留baseline默认。

本次逐场原始数据、源码快照和验证记录已完整归档到工作区外。后续优先：支援退化原因、后卫/守门交接专项、双人传接、观测约束、步态专项和硬件接口；每轮只研究一项假设。
