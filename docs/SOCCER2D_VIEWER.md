# 二维足球可视化场景

日期：2026-11-02。入口是 `tools/view_soccer2d.py`，使用现有二维模型和策略生成比赛，再导出无需联网的 HTML 回放。默认基线对基线、四对四，不启动 Webots 或 ROS。

## 打开已有场景

根目录已生成 `2D足球可视化场景_2026-11-02.html`，可以双击并用浏览器打开。

英文版另存为根目录 `2D_Football_Viewer_EN_2026-11-04.html`，按钮、角色、动作、阶段、事件与说明均为英文。中文版保留。两版使用相同 seed 27 的比赛记录，位置、事件和结果一致。

界面提供：

- 按实际几何比例绘制的球场、球门、球门区、罚球区和足球。
- 红蓝双方各四个球员，以及编号、角色和朝向。
- 比分、比赛阶段、半场和时间。
- 球员实际决策标签、动作选择、踢球准备剩余时间和球员／足球状态。
- 播放／暂停、逐帧、时间线、0.5—32 倍查看速度和循环。
- 球轨迹、传球意图连线与可点击的比赛事件。

`G` 是守门员，`D` 是后卫，`A/B` 是两个前锋。点击球员或右侧列表选中，空格播放，左右键逐帧。默认暂停，点击播放开始。

## 重新生成

从工程目录执行，每次使用不存在的新输出目录：

```bash
cd Webots_Robotics_TDP
conda activate robotics-tdp

python tools/view_soccer2d.py \
  --seed 27 \
  --output runs/scene2d_next_01 \
  --open
```

`--open` 尝试调用默认浏览器。也可手动打开输出目录中的 `replay.html`。HTML 内嵌完整记录，不依赖 CDN、额外服务器或浏览器插件。其他常用参数：

```bash
# 改变初始布局／噪声种子
python tools/view_soccer2d.py --seed 28 --output runs/scene2d_seed28_01 --open

# 生成英文界面，默认界面语言仍为中文
python tools/view_soccer2d.py --language en --seed 27 --output runs/scene2d_en_next_01 --open

# 更短的开发赛程，参数改变会记录在 manifest 中
python tools/view_soccer2d.py --half-seconds 120 --output runs/scene2d_short_01 --open
```

默认 `--candidate baseline`，双方均为基线。历史 `possession` 支援候选只在显式指定 `--candidate possession --candidate-team RED` 时启用；该候选此前三维退化，不作为推荐策略。修改策略后应重新生成场景。

## 输出与实现

| 文件 | 作用 |
|---|---|
| `replay.html` | 可直接打开的完整回放 |
| `scene.json` | 帧、几何、动作／行为和事件 |
| `result.json` | 模型原有逐场结果 |
| `manifest.json` | 配置、采样时间、Python 版本和源码散列 |
| `source_snapshot/` | 本轮实际运行的工具与相关策略源码 |

`soccer2d.py` 的可选 observer 只记录已经产生的状态，不额外调用策略、不选择动作。帧包含初始状态、各个 0.2 秒模型步和最终 FINISHED 状态。播放器按记录选帧，不在重置摆放间插值，也不通过播放速度修改比赛结果。

## 验证和边界

- seed 27、两个 300 秒半场的默认场景得到 3009 帧，约 601.6 仿真秒，结果 0:0。
- 原始无可视化基线与启用记录的完整结果一致；现有 78 项逻辑检查通过。
- 浏览器检查覆盖八个球员、播放／暂停、逐帧、时间线、选择、循环、终场和事件跳转；390 像素宽视口无横向溢出。
- 这是当前简化模型真实产生的数据回放，不是实时浏览器控制，也不是 Webots 三维录像。不能拖动球或机器人改变比赛。
- 模型采用平面圆盘、简化接触和真值观测，不验证 NAO 关节、平衡、跌倒、相机定位和硬件。
- 进球／触球／传球等含义仍受模型假设限制；不能把行为标签或一次触球当成真实技能成功。

二维模型的参数来源和原有局限见 [机制提取与实验](POLICY_EXPERIMENTS.md)。
