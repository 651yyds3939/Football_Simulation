# Webots 四对四策略接入

这个目录提供启动器、共享战术适配和测试。启动器在临时工程里引用已有的 Webots 世界、NAO 模型、动作和原控制器。默认从上一级工作区的 `Webots_Robotics_TDP` 读取，也可用 `--source` 指定目录。

运行需要 Webots R2023b 和能运行原场景的 Python 环境。在仓库根目录执行：

```sh
conda activate robotics-tdp
python Webots_3D/run.py --tactics flow
```

可加 `--mode=pause` 打开暂停状态世界，或加 `--team RED` 只将红队设为候选。默认双方使用所选策略和带站稳检查的 `guarded` 动作调度。可用 `--locomotion legacy` 切换调度做对照。临时工程与 Webots 一起结束。

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

固定开局可选 `crowd`（争球）、`defence`（防守）、`passing`（短传）和 `keeper`（面对初始滚动来球）。夹具设置开局站位和球的初始状态，随后运行实际 Webots 控制器。批测按相同种子对照原策略、接应模式、完整接入模式和短传模式，候选换红蓝队。每场使用独立输出目录，保存模式、源码哈希、比分、球与球员的轨迹和动作日志。
