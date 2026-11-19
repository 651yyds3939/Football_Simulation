"""Write an evidence-linked report after the frozen holdout run completes."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
d=json.loads((H/'holdout-comparison.json').read_text());b=d['baseline'];c=d['candidate']
def count(s,k):return s['outcomes'].get(k,0)
rows=[('红方进右门',count(b,'GOAL'),count(c,'GOAL')),('蓝方推进左门',count(b,'CLEARED_GOAL'),count(c,'CLEARED_GOAL')),('超时',count(b,'TIMEOUT'),count(c,'TIMEOUT')),('出界',count(b,'OUT'),count(c,'OUT')),('超过20秒贴身僵持',b['stalls_over_20s'],c['stalls_over_20s']),('平均防守转向时间（秒）',round(b['mean_turn_seconds'],2),round(c['mean_turn_seconds'],2)),('平均落在球后时间（秒）',round(b['mean_behind_ball_seconds'],2),round(c['mean_behind_ball_seconds'],2)),('有控球证据的0.5米退球局数',b['controlled_retreat_runs'],c['controlled_retreat_runs'])]
text='''# 1v1 第二轮策略调试记录 · 2026-11-19

本轮从上一轮结束版本继续调试，基准不是最初下载的项目。开始时间为 05:02:02 UTC；最终交付检查和结束时间见同目录验证数据。仅修改独立二维工程，三维工程没有同步。

## 采用的改动

1. **统一争球脱困计时。** 原来有球脚位中的 `CHALLENGE` 可以保护14秒，`unblock_duel` 却设置8秒后尝试换位，前者遮蔽后者。将保护时间改为8秒，球位移动超过0.06米仍会重新计时，避免正常推进时过早放弃争球。没有增加任何推力或移动速度。
2. **按有限拦截时间选择回防动作。** `DefensivePlan.recovery_action()` 比较转身后还能推进的距离与直接前进、退行、侧移的覆盖量。最多考虑未来10秒；只有覆盖优势超过0.08米时才改选平移动作。已到目标点则站定，原本适合直接走的路线照常走。步态仍然分开转向和行走。
3. **消除重合朝向点产生的虚假转向。** `Navigation.angle_to()` 在目标与自身重合时返回0，避免 `atan2(0,0)` 被解释为固定世界朝向。

另外修复了批量测试导出的 `replay.html` 只有初始画面的问题：现在会重算并保存首局完整过程，终局和时间与批量结果核对一致。

代码：`2D_Shared_Policy_2026-11-11/backend/Wenao/controllers/Utils/DefensivePlan.py`、`Navigation.py`、`TeamPolicy.py`。进攻函数的AST与本轮基准相同，`soccer2d.py` 逐字节相同。双方的接触规则和速率相同。

## 如何筛选

- 固定时间步0.04秒，每局最多180仿真秒；无显示批量计算，不等待动画。
- 首轮筛选30组候选，每组180个相同开局：种子10000–10179。
- 另一批300个开局用于验证：13000–13299。验证后保存 `selected-before-holdout.json`，再跑最终保留测试。
- 最终1000个开局：20000–20999。前后使用完全相同的位置、朝向和种子，没有按结果挑选测试局。
- 三种出生分布轮换：默认中场、近球门、边路。各矩形和完整初始布局在验证目录的 `*-layouts.json`、`*-groups.json` 中保存。近球门预设的球门侧距离余量为0.20米，其余为0.25米。
- 关闭回放轨迹保存的快速模式，已与正常记录模式在180局逐局核对一致，见 `invariants.json`。它只省去显示数据记录，不改变物理步长。
- 这是人为设计策略的批量对照调试，不是运行后自行学习的强化学习系统。

## 最终1000局配对结果

| 指标 | 本轮开始 | 本轮交付 |
| --- | ---: | ---: |
'''
text+='\n'.join(f'| {label} | {x} | {y} |' for label,x,y in rows)+'\n'
text+='''
“蓝方推进左门”是球实际进入左门的终局；不是所有解围，也不能把超时、出界算入防守胜率。退球指标是脚下独占接触证据后球向左至少0.5米，可能随后仍被红方进球。僵持定义为双方都接近足球、身体距离较近且足球没有明显离开锚点；不代表所有类型的无效等待。

### 分布分别查看

| 出生分布 | 局数 | 红方进球 前→后 | 蓝方推进左门 前→后 | 超时 前→后 | 长僵持 前→后 |
| --- | ---: | --- | --- | --- | --- |
'''
for name,g in d['groups'].items():
 x,y=g['baseline'],g['candidate'];text+=f"| { {'default':'默认中场','near':'近球门','wide':'边路'}[name]} | {x['runs']} | {count(x,'GOAL')}→{count(y,'GOAL')} | {count(x,'CLEARED_GOAL')}→{count(y,'CLEARED_GOAL')} | {count(x,'TIMEOUT')}→{count(y,'TIMEOUT')} | {x['stalls_over_20s']}→{y['stalls_over_20s']} |\n"
change=d['blue_left_goal_change'];text+=f"\n蓝方推进左门的净变化为 {change['percentage_points']:+.2f} 个百分点；配对样本的描述性95%区间为 {change['paired_normal_95_interval_pp'][0]:+.2f} 至 {change['paired_normal_95_interval_pp'][1]:+.2f} 个百分点。主要依据是具体耗时与僵持变化，不将小幅终局比例变化包装成普遍能力提升。\n"
text+='''
## 未采用的尝试

- 遇到身体阻挡就退开：长僵持减少，但超时明显增加，丢失控球窗口。
- 连续没有位置进展才退开：部分结果变好，但独立验证的长僵持增加，不合并。
- 放宽转向阈值、扩大近身挑战范围：部分开局漏球、超时增加。
- 更早进入失位回防：减少转向，却更容易过早放弃有效争球。
- 进攻绕人：试验了锁定绕行方向与多种绕行宽度，但增加出界、超时，未替换现有进攻。
- 压力下改用带球解围：收益很小，未增加额外状态与参数。

全部试验结果保存在验证目录，而非只保留成功局。没有把上述实验开关或大段未采用分支留在交付导航代码中。

## 验证和交付

- 新增7项回防、镜像球门、重合朝向点、争球计时回归检查。
- 保留出生矩形5000个种子的约束测试及既有9项几何检查。
- 浏览器检查：默认8倍、重复种子、编辑/拖动矩形、非法区域、批量测试、中英文、手机宽度和离线导出。
- 连续自动开局测试、解压包自包含检查及5例HTML离线回放检查，结果见 `delivery-check.json`。
- ZIP中的使用说明保持简短Windows步骤，完整调试解释保留在本地文档。历史视频未重新录制。

证据目录：[strategy-tuning-20261119-round2](../verification/strategy-tuning-20261119-round2/)。主要数据为 `baseline-holdout.json`、`production-holdout.json`、`holdout-comparison.json`、`selected-before-holdout.json`、`invariants.json` 和各轮 `*-summary.json`。

## 剩余超时局的复查

最终87个超时局，按最后30秒轨迹作事后诊断：70局为双方靠近球且球基本静止，16局仍有推进，1局是分离状态下的对齐等待。本轮开始的83个超时局中，相同口径分别为61、21、1局；末端静止拥挤的超时增加了9局。这是明确的回退，过程中的长僵持减少不等于所有卡球都解决。这里采用0.65米邻近和0.10米球位范围，口径比“超过20秒贴身僵持”宽，不能与59局直接等同。

从新增超时中抽取5局延长到600秒，仍然全部超时；没有把延长比赛后的结果混入180秒对照。因此核心剩余问题是局部控球与接触脱困，不能只靠延长比赛解决。详见 `baseline-timeout-diagnostics.json`、`timeout-diagnostics.json` 和 `extended-timeout-diagnostics.json`。

另外在隔离实验目录检查“先留脚前空间，再横向对齐”，并分别冻结进攻或防守导航进行对照。该试验没有直接放进交付版本，后续须使用新开局检验对双方的影响，不能只凭解决一个卡点就合并。

验证集300局中，上一阶段交付候选为蓝方推进左门172局、红方105局、超时20局、出界3局。脚前空间0.20米的试验：

| 实验范围 | 蓝方推进左门 | 红方进球 | 超时 | 长僵持 |
| --- | ---: | ---: | ---: | ---: |
| 仅防守导航改变，冻结进攻导航 | 183 | 105 | 12 | 14 |
| 仅进攻导航改变，冻结防守导航 | 138 | 127 | 34 | 23 |
| 双方导航都改变 | 148 | 128 | 24 | 10 |

两处关键差异是：先侧移可能被足球的身体碰撞代理挡住；但退开让位又改变抢球窗口。该0.20米门槛参考了当前圆盘模型的几何空间，不是测得的真实NAO足位参数。此表来自已使用过的验证集，不是新的最终保留测试。源码、参数和冻结导航来源见 `footspace-app/`、`footspace-validation-summary.json`、`footspace-ablation-provenance.json`，下一轮应针对这一路线设计新的独立开局。

## 下一步仍需解决

二维执行层使用既有动作均速，90度转身仍约需21仿真秒；退行速度也低于前进。完全被突破且没有位置优势后，策略不能保证追回来。当前回防只是减少不划算的转向，不是新步态，也没有实现边走边转。

精确位置、圆盘接触、足球滚动和踢球扰动都是简化模型，没有相机、关节平衡或摔倒。门前脱困和边路争球仍有失败样本；结果需要在三维和实际硬件上重新验证。后续应分别推进可执行的转向步态、可靠的抢球后控球、局部避让与视觉状态误差测试，不直接将二维比例当作课程验收结论。

## 复测

从仓库目录启动实时版：

```bash
python 2D_Shared_Policy_2026-11-11/server.py --open
```

先关闭旧服务再启动，单纯刷新网页不会重新导入Python策略。批量测试不受网页播放倍速限制：

```bash
python 2D_Shared_Policy_2026-11-11/server.py --batch 100 --seed 30000 --seconds 180 --output runs/round2_check_01
```

输出目录必须是新的。对照测试保持种子、出生矩形、时长和运动模型一致，再同时比较进球、出界、超时和轨迹。
'''
(ROOT/'docs/STRATEGY_TUNING_ROUND2_2026-11-19.md').write_text(text)
print(ROOT/'docs/STRATEGY_TUNING_ROUND2_2026-11-19.md')
