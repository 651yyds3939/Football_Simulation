本轮正面对抗与绕行带球调试记录：`../docs/ATTACKING_DUELS_2026-11-19.md`。其中包含120个正面开局、1000个独立开局与失败方案；下方为历史详细说明。

本次反抢与回追更新见 `../docs/COUNTERPRESS_TUNING_2026-11-19.md`；以下保留历史记录。

本地第二轮策略更新见 `../docs/STRATEGY_TUNING_ROUND2_2026-11-19.md`；以下保留历史说明。

> 2026-11-19 更新：当前版本支持可框选的出生矩形，二维防守策略已独立调整，尚未同步到三维。最新结果见根目录 README 和 docs/DEFENCE_TUNING_2026-11-19.md；以下保留详细历史记录。

# 共用 Python 决策的一攻一防二维测试

## 启动

本版需要 Python 3.8 或更新版本，只用标准库，不需要安装 Webots、ROS、Conda 或 pip 包。Ubuntu 可直接使用自带的 Python 3。运行：

```bash
bash start.sh
```

或者：

```bash
python3 server.py --open
```

浏览器会打开终端打印的 `http://127.0.0.1:端口/`。不要直接双击 `viewer.html`，它需要连接 Python 服务。保持终端运行；终端按 `Ctrl+C` 停止服务。整个服务只在本机运行，不需要互联网。

实时决策在 Python 中计算，浏览器只提交控制命令和画图，不含另一套 JavaScript 决策或运动模型。

## Windows 启动

1. 安装 Python 3.8 或更新版本，参考 [Python 官方 Windows 安装说明](https://docs.python.org/3/using/windows.html)。不需要安装 Webots、Conda 或额外的 Python 包。
2. 将 ZIP **完整解压**到一个文件夹，不要在压缩包内直接运行。
3. 双击 `start_windows.bat`。脚本自动查找 `py -3` 或 `python`，启动本机服务并打开浏览器；未找到合适的 Python 时会提示安装。
4. 在网页点击 **Play** 开始。运行期间保持命令窗口打开；在该窗口按 `Ctrl+C` 停止。若 Windows 随后询问是否终止批处理，输入 `Y` 并回车。

也可以在解压目录打开 PowerShell 或命令提示符，运行：

```powershell
py -3 server.py --open
```

若只有 `python` 命令，则运行 `python server.py --open`。脚本支持带空格的目录。启动后浏览器没有自动打开时，将命令窗口打印的 `http://127.0.0.1:端口/` 复制到浏览器地址栏。

仅播放现成演示时，直接双击 `example_replay.html` 即可，不需要 Python。`viewer.html` 是实时界面，需要通过上述服务打开。

Windows 启动入口与文件编码已做兼容处理，尚未在真实 Windows 系统上实测。这里的兼容范围是二维测试包；完整 Webots 三维项目还需要单独配置 Webots 与控制器环境。

## 共用哪些代码

```text
                   相同的世界状态、朝向和策略配置
                                |
              PolicyProfile.py：创建同一套策略与导航器
                                |
                  TeamPolicy.py：行为、目标、踢球意图
                                |
                  Navigation.py：走路、转向、侧移、踢球请求
                           /            \
                二维执行适配器          Webots 执行适配器
                平面平均速度模型        关节动作、IMU 与安全调度
                        |                    |
                更新二维世界状态        更新三维世界状态
```

浏览器底部显示实际加载的代码来源、策略 SHA-256 前缀和配置。`guarded` 对应射门目标伸入球门 0.30 m；`legacy` 对应原来的 0 m。两边必须使用相同配置再做比较。

目录位于原项目旁时，默认直接导入相邻 `Webots_Robotics_TDP` 的真实 Python 文件，不使用另写的决策副本。移到其他电脑后自动使用包内 `backend/` 的同版本快照。`python3 server.py --bundled --open` 可强制验证打包快照。

当前复用的是策略、导航和配置。二维不复现 Webots 的 IMU 滤波、站稳等待、步态阶段门控、关节执行、接触动力学或摔倒恢复。输入轨迹在运行中发生差异后，后续决策也可能不同。共用代码不代表两种环境会有相同的进球率。

## 当前不足：转向、步态与硬件验证

当前交付定位为一攻一防的二维策略测试原型，可用于可视化、重复开局和快速对照测试。完整三维对抗、长期运动稳定性及真机迁移仍需验证。

防守者有时需要较长时间原地转向，期间对手继续推进，导致拦截窗口丢失。原因包括当前动作执行方式、转向速度近似和策略选点，尚不能将失球全部归因于物理硬件：

| 层级 | 当前限制及影响 |
| --- | --- |
| 二维运动模型 | 行走、侧移和转向是互斥动作；执行转向时没有主动平移。左右转速统一近似为约 4.2–4.3°/s，尚未按每种转向动作分别建模，因此部分场景可能高估转向耗时。 |
| Webots 动作执行 | 行走、转向由不同的 `.motion` 关节轨迹执行；普通转向通常等待当前动作完成后再切换。尚未实现统一的边走边转步态，动作衔接和站稳等待也可能增加反应时间。 |
| 防守策略 | 预判可以提前占位，但预测存在误差。横向距离大、被突破或临时需要大角度转向时，仍可能无法及时拦截；近球还存在僵持和重复调整。 |
| 真机硬件 | 尚未测量实验室 NAO6 的转向速度、步态与接口。当前二维参数和 Webots 结果不能作为真机能力上限，也没有证明真机无法边走边转。 |

按当前二维左转近似，转 90° 约需 **21 秒仿真时间**；如果进攻方以当前约 0.085 m/s 的速度持续直行，同期可前进约 **1.8 m**。这是模型参数推算，实际过程还受接触、停顿和路径影响。8 倍播放只缩短观看时间，不改变双方在仿真中的相对运动能力。

NAO 官方 NAOqi 的 `moveToward(x, y, theta)` 支持组合平移与旋转速度输入，具备边走边转的控制接口；实验室固件、接口可用性与具体性能仍待确认。[官方运动接口说明](https://doc.aldebaran.com/2-5/naoqi/motion/control-walk-api.html) 当前 Webots 控制器没有接入该步态能力。两份控制同一组腿部关节的动作文件也不能简单同时播放来代替统一步态。

后续优先分别测量各转向动作，修正二维速度近似；在 Webots 中验证小角度边走边转的步态及其速度、转弯半径和跌倒情况，再把验证后的运动能力同步到二维并复测防守。现阶段保留这些已知限制，不将二维成功率直接用于三维或真机。

## 操作

- **Play / 开始**：实时运行，默认 **8 倍速**。可选 1、2、4、8、16、32、64 倍；加速仅增加每秒计算的步数，不修改机器人速度参数。
- **New random setup / 随机新开局**：更换位置、朝向和种子。
- **Repeat seed / 重测当前种子**：复现同一个开局。
- **Fast test ×20 / 快速测试 20 次**：暂停显示，直接让 Python 尽快计算连续 20 个种子，显示结果与实际耗时。随机场景会改变位置；固定场景只改变踢球噪声，结果类别可能相同。
- **Export HTML replay / 导出 HTML 回放**：用同一套 Python 决策算完当前场景，再保存单个 HTML。该文件可以直接双击、离线分享；这是回放，不能在没有 Python 的情况下修改策略或开局。
- **Download run data / 下载数据**：保存输入配置、代码来源哈希、轨迹、行为和事件。
- 暂停后可拖动球员或足球，到目标位置松开鼠标后提交。重叠位置会被拒绝。

解围只记录事件，继续攻防。进球、出界或本轮到时才结束。可开启自动下一轮。

## 最新：球门侧出生与预判拦截

所有内置开局均保证蓝方比红方和足球更靠近右侧球门中心，并且位于两者的右侧，不重叠。随机种子可以复现；暂停后的拖动属于自定义设置，可以构造不利位置。`shot` 已改为门前攻防，`breakaway` 已改为斜向拦截，不再把防守者预先放在进攻者身后。

新增共用 `DefensivePlan.py`：依据球速或持球者朝向预测球路，比较现有前进、后退、侧移与转向动作的预计耗时，提前选择拦截点。界面显示 **Predictive interception / 预判拦截**，蓝色虚线指向拦截目标。到达覆盖位置后再面向来球，近球时尝试断球或解围；没有新增瞬间转身、提高速度或指定胜者。

同一批未参与调整的种子 347–446、每轮 180 秒、相同新开局与原二维运动模型：旧策略红方进球 82、蓝方进球 18；新策略红方进球 63、蓝方进球 33、超时 4。超时不算防守成功。贴身纠缠平均累计时间从 7.13 s 增至 9.51 s，仍有失球和僵持，这些是二维模型中的结果。

默认 8 倍播放，初始暂停，点击 Play 开始。观察防守成功例子可运行 `bash start.sh --scenario random --seed 355`；观察随机攻防可直接运行 `bash start.sh`，再点击 New random setup。两边都有进球可能。仅离线展示可双击 `defence_replay.html`（种子 355）或 `example_replay.html`（种子 347 的进攻成功）。

当前 113 项回归检查通过，包括 5000 个随机出生检查。24 秒 Webots 拦截检查中 446 条输入重算一致；这验证共用接口，不代表二维、三维和真机的防守成功率相同。以下各节保留前期试验记录，其统计对应旧代码或旧开局。

## 双方挤在球旁怎么办

时间继续增加、足球几乎不动，属于攻防僵持；时间也完全停止时，先检查是否暂停、切到后台，或 Python 服务已退出。

原卡球修正加入了 **DUEL_ESCAPE / Create space / 遇堵让位**。当前版本在双方贴近、足球没有离开半径 0.06 m 的参考范围时，持球进攻者约 3 秒后尝试换位；防守者通常等待 8 秒，并朝球路方向调整，侧移目标不越过球路。脚前确实可触球的防守者可以在同一参考窗口保持最多 14 秒施压。每次侧移目标最多 0.12 m，执行窗口最多 8 秒；实际位移仍受动作速度、碰撞和执行器限制。参考位置更新会重新计时，因此这些阈值不保证总纠缠时间小于 14 秒。它们是策略假设，不是课程规定或真机标定值。

没有强制移动足球、提高机器人速度或规定哪方获胜。修改同时进入 Webots 使用的 `TeamPolicy.py` 和 `Navigation.py`；二维碰撞修正只影响二维执行器。

更新后必须在旧终端按 `Ctrl+C` 停止服务，再重新运行启动脚本，并打开新终端打印的网址。仅刷新网页不会重新加载已经导入的 Python 策略。

上一次卡球修正的对照中，同条件 20 个种子（27–46，随机开局、每轮 180 秒、guarded/centre）的超时由 6 次降至 1 次。另 100 个种子（47–146）的超时由 28 次降至 13 次，仍存在失败场景。这是简化二维模型内的前后对照，不能作为三维或真机成功率。后续回防修改的结果见下一节，应按各次源代码哈希区分。

可在页面选择 `random`、种子 `28`、时长 `180`，观察遇堵让位和后续攻防；种子 `37` 仍可能反复僵持，应保留为后续改进用例。下载 JSON 可保留种子、模型、代码哈希和全过程；不要只换开局而丢弃失败记录。

## 被突破后先转半圈的问题

原防守球员被突破后，仍尝试绕到球后、面向解围方向，再开始移动。现增加共用的 **RECOVER_DEFENCE / Recover goal-side / 回防球门侧**：先到足球与本方球门之间，再恢复普通抢球和解围。导航可以直接倒退回撤，已面向回防目标则前进；目标在侧面时，调整到较近的前进或后退方向，避免总是先转完整半圈。

此前二维 `breakaway` 故意把防守者放在身后，用于测量回撤响应；最新预设改为球门侧斜向拦截。已被突破的情况仍可暂停后拖动构造。此前固定场景仍然丢球：倒退约 0.034 m/s，对手带球约 0.085 m/s，即使立即行动也不足以追上已经领先的球员。

上一轮单独修改回防响应时，100 个相同种子（47–146）的结果为修改前红方进球 82、蓝方进球 5、超时 13；修改后为 83、5、12。该次修改没有证明整体防守变好。之后又进行了下节的近距离封堵和断球修改。

12 秒 Webots 被突破场景中，原控制器实际执行倒退，防守球员躯干位置向本方球门侧移动约 0.26 m；252 条输入记录重算一致。95 项回归检查通过。这不是完整三维防守成功率或真机验证。

## 近距离封堵与断球

当前新增 **CHALLENGE / Challenge the ball / 封堵与断球**：防守者接近持球者时保持球路覆盖，近距离优先侧移调整；球进入现有脚前可触范围后，直接用前进行走尝试捅球，不先停下来追求精确射门姿态。进攻者停滞后尝试换位，防守者的调整优先回到球路，避免双方一起避让而主动让出通道。

二维执行器也修正了两个问题：机器人向足球靠近时不能继续穿过球所在的身体区域；多个脚同时触球时组合它们的作用方向，不再只让某个略近的机器人或名字排序决定整次推进。单机器人原运动速度、脚前接触范围和踢球参数保持原值。这仍是简化接触模型，没有获得真机标定。

在未参与调整的种子 147–246、每轮 180 秒、guarded/centre 的 100 次测试中：

| 版本 | 红方进球 | 蓝方进球 | 超时 | 每局平均累计近距离纠缠 |
| --- | ---: | ---: | ---: | ---: |
| 修改前 | 89 | 4 | 7 | 15.34 s |
| 仅修正二维执行，保留旧策略 | 86 | 7 | 7 | 12.81 s |
| 修正执行并使用新策略 | 79 | 17 | 4 | 7.01 s |

“近距离纠缠”指双方间距小于 0.40 m，且双方距球均小于 0.50 m；表内时间是每局累计时间的平均值，不是最长持续时长。改善来自模型和策略两部分，不能全部归因于策略。仍有 4 次超时，部分固定侧向用例仍会较长时间卡球，不能保证每次断球成功。

观察固定正面封堵场景：

```bash
bash start.sh --scenario block --seed 27
```

Windows 启动脚本同样支持 `start_windows.bat --scenario block --seed 27`。或在网页下方选择 **Frontal challenge (fixed)**。这个固定例子中蓝方能够断球并向左推进；不要把单个例子当成整体成功率。随机攻防选 `random`，其中仍有大量进攻方突破和进球。

只做离线展示时，双击 `defence_replay.html`，无需 Python；最新文件是由同一套 Python 策略计算出的种子 355 预判防守回放。

105 项回归检查通过。24 秒 Webots 正面对抗用例完成，150 条实际决策请求重算一致；蓝方实际执行了前进和侧移。该三维用例中红方出现一次起身动作，不能据此宣称碰撞倒地问题已经解决，也不能把二维成功率用于三维或真机。

## 快速批量测试

```bash
python3 server.py --batch 20 --scenario random --seed 27 --seconds 180 \
  --locomotion guarded --output runs/baseline_01
```

输出目录必须是新目录，防止覆盖基线。得到 `metrics.json` 和第一场完整的 `replay.html`。计算尽快执行，不受浏览器播放倍速限制。输出同时记录仿真时间与实际计算时间。

改动后用同样的种子、时长、配置复测：

```bash
python3 server.py --batch 20 --scenario random --seed 27 --seconds 180 \
  --locomotion guarded --output runs/candidate_01
```

## 修改和三维验证

在原工作区主要修改：

```text
Webots_Robotics_TDP/Wenao/controllers/Utils/TeamPolicy.py
Webots_Robotics_TDP/Wenao/controllers/Utils/Navigation.py
Webots_Robotics_TDP/Wenao/controllers/Utils/DefensivePlan.py
```

修改后重启 Python 服务，并重新加载 Webots 控制器，避免还在运行旧版本。一次修改一个问题。先比较相同种子下的二维目标、动作切换、触球与结果，再做三维对照。不要只比较某一次是否进球。

普通 Webots 世界默认使用 `legacy`。如果二维选择 `guarded`，三维也应显式使用相同配置，例如在原项目根目录运行 `TDP_LOCOMOTION=guarded TDP_FINISHING_AIM=centre ./launch.sh`。这不会把普通四对四世界自动变成一攻一防；一攻一防接口检查使用下一节的独立测试入口。

原仓库新增的短三维接口检查：

```bash
cd ../Webots_Robotics_TDP
conda activate robotics-tdp
python tests/run_shared_policy_webots.py --seconds 12 --locomotion guarded \
  --output runs/shared_policy_3d_01
python tools/check_policy_trace.py runs/shared_policy_3d_01
```

该检查使用原来的两个物理控制器，其他六台停在场外并从策略观测中排除。它记录 Webots 实际输入，再由共用 Python 模块重算，检查行为、目标、请求动作和导航阶段是否一致。它不是完整攻防成功率验收，也不验证二维和三维轨迹一致。

## 分享和系统要求

实时版：分享整个 ZIP；接收方需要 Python 3.8+，在浏览器打开服务网址。无第三方 Python 依赖。已在当前 Ubuntu 上验证；Windows 双击 `start_windows.bat`，macOS 使用 `python3 server.py --open`，尚未在这两个系统实测。

纯展示：分享导出的单个 `replay.html`，不需要 Python。包内 `example_replay.html` 为种子 347 的进攻成功，`defence_replay.html` 为种子 355 的预判防守成功，两者均由共用策略计算并明确标为离线回放。


## English quick start

Run `python3 server.py --open` and keep the terminal open. Only Python 3.8+ and a browser are required; there are no third-party dependencies. The browser displays states computed by the same Python `TeamPolicy` and `Navigator` modules used by Webots. It does not contain a parallel JavaScript policy.

On Windows, install Python, extract the entire ZIP, then double-click `start_windows.bat`. Keep its console open and stop with Ctrl+C. Alternatively run `py -3 server.py --open`. Windows has not been tested on a native system. The included `example_replay.html` opens directly without Python for offline playback.

Use **Fast test ×20** for compute-bound policy screening, or the `--batch` command above. **Export HTML replay** produces an offline, shareable single-file recording computed by Python. Live scene editing and new policy calculations require the server.

The adjacent original workspace is preferred automatically. A portable source snapshot is used when that workspace is absent, or when `--bundled` is selected. Restart after code edits; match the `guarded`/`legacy` and finishing settings across environments. Policy/navigation are shared; physics, motion scheduling, sensing and stability are not.

### Current limitations

This delivery is a 2D policy-testing prototype. Translation and turning are mutually exclusive in the current 2D executor; the Webots controller plays separate joint-motion files and normally completes a turn before switching actions. The 2D model uses a coarse turning rate of about 4.2–4.3 degrees/s: a 90-degree turn takes about 21 simulated seconds, during which an attacker walking continuously at 0.085 m/s could advance about 1.8 m. Prediction reduces some missed interceptions, but cannot remove all motion delays, forecast errors or close-contact stalls. Playback speed does not change these relative capabilities.

These limitations have not been established as physical NAO6 hardware limits. NAOqi supports combined translation and rotation through `moveToward(x, y, theta)`; laboratory firmware, interfaces and performance remain unverified. Further work is to measure individual turn motions, validate a coordinated walking-and-turning gait in Webots, then update the 2D motion estimates. Full 3D match stability and hardware performance have not been demonstrated.
