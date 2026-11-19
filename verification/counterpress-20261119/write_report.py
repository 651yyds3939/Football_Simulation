"""Summarize the frozen, independently tested counterpress revision."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
read=lambda n:json.loads((H/n).read_text())
b=read('baseline-holdout-v3.json')['summary'];c=read('production-holdout-v3.json')['summary'];cmp=read('holdout-comparison.json')
rows=[('红方进右门',b['outcomes'].get('GOAL',0),c['outcomes'].get('GOAL',0)),('蓝方推进左门',b['outcomes'].get('CLEARED_GOAL',0),c['outcomes'].get('CLEARED_GOAL',0)),('超时',b['outcomes'].get('TIMEOUT',0),c['outcomes'].get('TIMEOUT',0)),('出界',b['outcomes'].get('OUT',0),c['outcomes'].get('OUT',0)),('超过20秒贴身僵持',b['stalls_over_20s'],c['stalls_over_20s']),('每局丢球后背向球时间（秒）',round(b['mean_attacker_wrong_heading_seconds'],2),round(c['mean_attacker_wrong_heading_seconds'],2)),('丢球窗口内平均朝向误差（度）',round(b['loss_weighted_attacker_heading_error_degrees'],2),round(c['loss_weighted_attacker_heading_error_degrees'],2)),('每局丢球后仍进行进攻对齐（秒）',round(b['mean_attacker_alignment_while_lost_seconds'],3),round(c['mean_attacker_alignment_while_lost_seconds'],3)),('红方重新取得独占脚下触球的局数',b['attacker_regain_runs'],c['attacker_regain_runs']),('反抢后向右推进至少0.30米的局数',b['attacker_productive_regain_runs'],c['attacker_productive_regain_runs']),('平均整局时长（秒）',round(b['mean_duration_seconds'],2),round(c['mean_duration_seconds'],2))]
s='''# 丢球反抢、回追朝向与1v1调试 · 2026-11-19

本轮从前一轮已交付版本继续，开始于14:54:02 UTC。最终结束时间及完整性记录见验证目录 `delivery-check.json`。仅修改 Football_Simulation；三维工程未同步，没有提交或推送Git。

## 修正的问题

### 丢球后仍按进攻流程走

旧进攻方即使已经被断球，也会调用接近球后方、面向右门、对脚位的进攻流程。因此回追时可能朝向右门或绕行接近点，无法区分“正在夺回球”和“已经控球准备进攻”。

新增 `TeamPolicy.counterpress()` 和 `COUNTERPRESS` 状态：

```text
PLAYING
  |
  +-- 对手最近触球、接近球，且比本方更近至少0.08米
  |     |
  |     v
  |   COUNTERPRESS / 丢球反抢
  |     +-- 远处：沿实际球速做有限预测（最多1秒、0.40米）
  |     +-- 先调整到球路方向，再接近；近处直接面向当前足球
  |     +-- 球在前脚可触及范围：尝试争球
  |     +-- 近身长时间没有推进：短暂换位脱困
  |     |
  |     +-- 本方最近触球，且球确实位于本方前脚窗口
  |           v
  +-------- 原有进攻：接近合适位置 -> 面向进攻方向 -> 带球/射门
```

最近触球包含身体碰球，不等于稳定控球。因此使用距离优势抑制误触发；仅身体碰到球、但球仍在身后，不视为已经夺回。该状态只在当前追球的前锋中启用，防守方原有预判与回防保留。

主要代码：`backend/Wenao/controllers/Utils/TeamPolicy.py`、`Navigation.py`、`DefensivePlan.py`，均位于实时版目录内。

### 近身对齐时身体挡住移动

合并了此前隔离验证的防守方脚前空间处理：球贴近身体且必须横向对齐时，先让出约0.20米前脚空间，再侧移。该规则用于防守争球和解围，没有应用到红方带球对齐，以免改变已经验证的进攻接触方式。

0.20米是当前圆盘代理的几何门槛：身体半径0.15米、球半径0.07米、前脚横向窗口0.12米，过渡约 sqrt(0.22²−0.12²)=0.184米。它是模型参数，不能当作真机足位测量。

### 进球后还显示FORMATION

旧流程在裁判判进球、切换为READY后，又计算了一次回阵型动作，随后场景才标记FINISHED。现在通过 `Simulation._stop_after_referee()` 适配钩子，在本次1v1进球或出界后停止继续发动作。终局统一显示 `FINISHED / 本轮结束`、`stand`，清除未完成的踢球动作；重复推进终局场景不会再移动球员。

该钩子默认不终止其他仿真适配器；1v1场景才在首次结果后停止。运动均速、踢球时长、接触、球滚动及噪声没有改变，相关函数的AST一致性记录见 `invariants.json`。

## 测试方式

- 训练筛选：50000–50239，240个固定开局，默认中场、近球门、边路轮换，多组候选使用相同布局比较。
- 独立验证：53000–53299，300个新开局，验证后冻结交付源码。
- 最终保留测试：60000–60999，1000个未参与参数选择的开局；每局180仿真秒、步长0.04秒，双方出生位置、朝向和种子逐局配对。
- 另从训练开局截取80个真实蓝方首次独占脚下触球的局面，检查丢球后的行为；这些属于定点压力测试，不混入1000局成绩。
- 无显示批量计算省去动画等待，保持模型步长。最终1000局候选计算约222秒，对应约432倍实时计算速度；网页默认8倍只控制观看速度。
- 为公平，最终基线也使用终局停止修复，主要对照比较的是策略变化，终局修复另外做回归检查。

### 统计脚本纠正

补充初始控球状态时曾引入采样缩进错误，导致部分补充测试只在最后采样一次。这些观测结果已明确弃用，列表在 `invalid-observer-results.json`。最终基线和交付版均用修正后的 `observer_schema=3` 重算，并逐局检查累计球员状态时长必须等于仿真时长减去终局时间步。错误数据没有混入下面的统计。

## 最终1000局结果

| 指标 | 本轮基线 | 本轮交付 |
| --- | ---: | ---: |
'''
s+='\n'.join(f'| {name} | {x} | {y} |' for name,x,y in rows)+'\n'
s+='''
“背向球”指球距离进攻方超过0.32米、上一独占脚下触球属于蓝方时，身体朝向与球的方位相差超过90度。统计为每局累计时间，包含必要转身过程，并非要求身体每一帧都严格正对足球。

“重新触球”只证明抢到了一个独占脚下触球窗口；“向右推进0.30米”进一步要求反抢后在蓝方下一次独占脚下触球前，由红方触球把球推进至少0.30米。后者从12局降到9局，不能宣称持续夺回球权能力已经提升。红方进球基本没变，本轮主要收益是朝向、流程一致性与超时减少。超时和出界不算防守胜利。

### 各出生区域

| 区域 | 局数 | 红方进球 前→后 | 蓝方推进左门 前→后 | 超时 前→后 | 长僵持 前→后 |
| --- | ---: | --- | --- | --- | --- |
'''
for name,g in cmp['groups'].items():
 x,y=g['baseline'],g['candidate'];s+=f"| { {'default':'中场','near':'门前','wide':'边路'}[name]} | {x['runs']} | {x['outcomes'].get('GOAL',0)}→{y['outcomes'].get('GOAL',0)} | {x['outcomes'].get('CLEARED_GOAL',0)}→{y['outcomes'].get('CLEARED_GOAL',0)} | {x['outcomes'].get('TIMEOUT',0)}→{y['outcomes'].get('TIMEOUT',0)} | {x['stalls_over_20s']}→{y['stalls_over_20s']} |\n"
s+='''
门前长僵持仍从16局增加到18局。整体改善不代表每种布局都改善；剩余重点是门前球位、反抢后控球和重新转向进攻。

## 未采用的尝试

直接追球、过宽松的控球切换虽然增加触球，却让贴身僵持和超时变多。扩大丢球距离门槛降低了反抢敏感度；用退行最短路线反抢又使身体朝向误差变大。额外的预测采样、转向承诺、较长夺球保护时间在训练集没有稳定收益，未保留到交付实现。各轮候选及失败结果均留在验证目录。

## 如何查看

关闭旧Python服务，再从仓库目录运行：

```bash
python 2D_Shared_Policy_2026-11-11/server.py --open
```

界面可看到“丢球反抢”“先转向足球，再回追”“沿球路接近足球”。球员箭头代表身体朝向，不是摄像头视线；允许有限朝向误差，转身仍需要实际时间。最近触球也不等于稳定控球。

五例离线演示和ZIP已按当前源码重新生成。第三例使用种子60078，展示被断球后反抢并最终进球；选出的成功例不代表总体成功率。历史MP4和MKV没有重新录制。

测试数据与脚本：[counterpress-20261119](../verification/counterpress-20261119/)。主要查看：

- `holdout-comparison.json`：前后分区统计。
- `baseline-holdout-v3.json`、`production-holdout-v3.json`：逐局数据。
- `selected-before-holdout.json`：保留测试前冻结的源码摘要。
- `policy-browser-check.json`：实际反抢中文、英文状态及终局停止检查。
- `delivery-check.json`：最终文件和测试完整性。

## 还存在的限制

当前是规则策略，不会在运行中自行学习。位置来自二维精确状态，控球判定仍是接触与距离估计，没有视觉噪声、关节平衡、摔倒或真机测试。丢球后可以正确选择追球方向，但同速追赶、慢速转身和被身体挡住的问题仍存在；反抢碰到球之后，如何持续控球并重新进攻仍需要继续优化。三维工程没有自动获得这些修改。
'''
(ROOT/'docs/COUNTERPRESS_TUNING_2026-11-19.md').write_text(s);print(ROOT/'docs/COUNTERPRESS_TUNING_2026-11-19.md')
