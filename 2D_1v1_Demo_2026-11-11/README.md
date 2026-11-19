# 2D football: one attacker, one defender, one ball

## 打开和展示

解压整个压缩包，双击 `index.html`，用 Chrome、Edge、Firefox 或 Safari 等现代浏览器打开。无须联网、Webots、ROS、Python、Conda 或本地服务器。Windows、macOS 和 Linux 均可通过浏览器打开。

Ubuntu 终端也可以运行：

```bash
xdg-open index.html
```

1. 点击 **Play / 开始**。红方进攻右侧球门，蓝方尝试拦截并向左解围。
2. **Playback / 播放速度** 默认 2×。切回 1× 可观察原始仿真速度，倍速不会更改运动参数。
3. 默认 **Random attack vs defence / 随机攻防**。**New random setup / 随机新开局** 会改变种子、足球位置、球员位置及初始朝向，结果由交互产生。**Repeat seed / 重测当前种子** 则复现同一开局。
4. 暂停后可以拖动球员或足球。也可以选择标为“固定”的中场、边路或门前场景，用于重复对照；固定场景中只改种子通常只影响踢球噪声，不一定改变最终结果。
5. 点击右上角 **中文 / English** 切换语言。
6. 右侧显示当前状态、足球位置、最近触球和射门/解围触球次数。可以下载本次运行的 JSON 记录。

解围后继续攻防，不会因为一次解围就结束。完成解围的简化判据为蓝方完成解围触球，之后足球向左移动至少 0.18 m；此时增加解围计数，红方继续找球和进攻。

进球、出界或达到每轮 180 秒仿真时间时才结束本轮。默认开启 **Auto next round / 自动下一轮**，结束后展示结果 3 秒，再生成随机开局继续运行。取消勾选可停在结果处。右侧累计进球与完成解围次数，下载数据包含当前轨迹和最近 50 次已切换开局的摘要。重测种子或手工修改场景/种子会清空本次累计。

随机开局不等于随机指定胜负，也不保证每次结果类别都不同。相同种子与设置应产生相同轨迹；不同开局可以出现进球、解围后继续争抢或长时间僵持。当前策略仍存在僵持，不能据此宣称攻防能力已成熟。

## 与现有项目的关系

沿用课程球场和球门尺寸，以及原项目中已记录的 Webots 平均运动速度、动作时间与部分球运动参数。这个小演示采用单独编写的一攻一防控制逻辑；它不是原四对四控制器的原样移植，也不是 Webots 三维仿真录像。

二维模型使用精确位置，只检查平面运动与球员交互，不模拟相机、关节、平衡或摔倒。当前简化接触、踢球范围和运动参数不代表真实 NAO6 已标定的性能。来源与建模选择见 `MODEL_NOTES.md`、`model_parameters.json`。

## Open and present

Extract the ZIP and open **index.html** in a modern browser. No installation, network connection, Python, ROS, Webots or local server is required.

- Press **Play**. Red attacks the right goal; blue intercepts and clears left.
- The default scene randomizes ball/player positions and headings. **New random setup** generates a fresh seed; **Repeat seed** reproduces the current starting scene.
- Three explicitly labelled fixed scenes remain available for controlled comparisons. Changing only their seed may leave the outcome unchanged.
- Default playback is **2×**. Change to **1×** for simulated real-time motion. The multiplier changes viewing time only.
- Pause to drag a player or the ball. Manual edits are identified in exported run data.
- Switch between English and Chinese with the top-right button.
- Download run data as JSON for positions, states, contacts and outcomes.

Clearances are counted and play continues. A clearance requires a defender kick contact followed by at least 0.18 m leftward ball travel. Rounds end on a goal, an exit or a 180-second simulation timeout. With **Auto next round** enabled, a new random round begins after a 3-second result display. Uncheck it to retain the final state.

The session counts actual goals and completed clearances; exported data includes the current trajectory and up to 50 previous round/setup summaries. Repeating a seed or manually changing the scene/seed resets session totals. Different seeds change initial conditions, not predetermined winners. Stalemates remain possible and have not been eliminated.

This is an independent 1v1 planar demonstration using selected parameters from the existing project. It does not port the existing 4v4 policy or demonstrate real NAO6 perception, dynamics or balance. See **MODEL_NOTES.md** for sources and limits.

## Files

| File | Purpose |
|---|---|
| `index.html` | Complete simulator, controller logic, drawing and bilingual interface; works by itself |
| `model_parameters.json` | Embedded model values, assumptions and original source hashes |
| `MODEL_NOTES.md` | Parameter sources, state policies and model limits |
| `README.md` | Opening and presentation instructions |

Sharing the ZIP preserves the documentation. Sharing just `index.html` is sufficient to run the demonstration.
