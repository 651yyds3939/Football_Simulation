# Webots 四对四策略接入

这个目录提供启动器、共享战术适配和测试。启动器在临时工程里引用已有的 Webots 世界、NAO 模型、动作和原控制器。默认从上一级工作区的 `Webots_Robotics_TDP` 读取，也可用 `--source` 指定目录。

运行需要 Webots R2023b 和能运行原场景的 Python 环境。在仓库根目录执行：

```sh
conda activate robotics-tdp
python Webots_3D/run.py --tactics support --team RED
```

上述命令只给红队接入接应、封线和让位，蓝队使用原策略。省略 `--tactics` 时使用 `baseline`。省略 `--team` 时，所选策略应用于双方。交互运行默认使用带站稳检查的 `guarded` 动作调度，可用 `--locomotion legacy` 切换做对照。加 `--mode=pause` 可打开暂停状态世界。临时工程与 Webots 一起结束。

| 模式 | 内容 |
| --- | --- |
| `baseline` | 原 3D 控制策略 |
| `support` | 共享接应、补位、封线和拥堵让位 |
| `flow` | 再加入带球绕行、追滚动球和门将封角 |
| `passing` | 在 `flow` 基础上试用共享短传选路与出脚前的线路检查 |

2D 和 3D 在运行时导入同一个 `Flow.py`。3D 的观测来自现有 Supervisor 广播，执行沿用现有导航、走路和转身动作、带球和站稳调度。竞赛裁判与比赛计时沿用原场景。二维快速侧拨、边走边转、瞬间停球和直接摆位属于二维仿真行为。实验的短传距离使用已有 3D 观察值约 0.305 米，球减速度仍为估计值。出脚前复查发生在 `LongPass.motion` 开始之前。接球和挡球是否成功由仿真中的实际接触决定，现有裁判的触球归属属于近似判断。

## 对照测试

```sh
python -m unittest Webots_3D.test_adapter
python Webots_3D/run.py --check --match --tactics flow --team RED --locomotion guarded --reset-formation --output Webots_3D/runs/flow-red
python Webots_3D/run.py --check --match --scenario crowd --tactics support --team RED --locomotion guarded --output Webots_3D/runs/crowd
python Webots_3D/test_campaign.py --duration 3600 --output Webots_3D/runs/hour
python Webots_3D/report.py Webots_3D/runs/hour
```

固定开局可选 `crowd`（争球）、`defence`（防守）、`passing`（短传）、`keeper`（低速来球）和 `keeper-shot`（门前快速来球）。夹具设置开局站位和球的初始状态，随后运行实际 Webots 控制器。批测按相同种子对照原策略、接应模式、完整接入模式和短传模式，候选换红蓝队。每场使用独立输出目录，保存模式、源码哈希、比分、球与球员的轨迹和动作日志。若批测进程被打断，可用相同参数加 `--resume` 接着运行，累计时长从最后一条完整记录继续。

## 2026-11-25 验证结果

短场批测累计实际运行 61 分 18 秒，中断空档未计入。19 场均跑完，每半场 120 秒，比分均为 0:0。三个种子各换边运行一次 `support`，与该种子的 `baseline` 比较。六组对照里，最长围球停滞五组缩短，另一组相差 0.08 秒。六组的站立到倒地转换均减少。四场 `passing` 短场未触发共享短传出脚指令。另测的种子 29 蓝方也未触发。

完整时钟对照采用种子 29，每半场 600 秒，准备阶段 45 秒，死球超时 120 秒，由球员自行从场边入场。

| 红蓝策略 | 比分 | 采样球路 | 最长围球停滞 | 观察到的倒地转换 |
| --- | ---: | ---: | ---: | ---: |
| `baseline` 双方 | 0:0 | 21.99 m | 33.32 s | 9 |
| `flow` 双方 | 0:0 | 14.36 m | 66.24 s | 19 |
| `support` 双方 | 0:1 | 18.40 m | 123.12 s | 28 |
| `support` 红队，`baseline` 蓝队 | 0:1 | 19.71 m | 43.32 s | 14 |

围球停滞按双方各有至少一名球员距球小于 0.50 m、水平球速小于 0.045 m/s、球仍在同一个 0.08 m 半径内的连续 `PLAYING` 样本计算。倒地转换由裁判采样姿态判断，短暂跌倒可能漏采。完整时钟下，接入策略后停滞和倒地均增加，因此默认保留原策略，候选由命令参数启用。

- 无对手射门回归（种子 27，`flow` 红队）在 118.36 仿真秒进球，起身恢复动作 0 次。
- 固定短传开局中，`passing` 红队的前锋 A 启动 `LongPass.motion`，前锋 B 收到接球广播。裁判记录 A 在开局后约 2.24 秒触球，B 在约 3.28 秒触球。
- 固定快速来球开局中，原门将和 `flow` 门将在约 0.52 秒触球，该开局双方均未失球。该用例验证一次具体来球下的动作，守门成功率需要多种来球复测。
