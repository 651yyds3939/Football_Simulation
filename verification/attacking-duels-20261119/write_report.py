from pathlib import Path
from collections import Counter
import json,hashlib
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
def read(name):return json.loads((H/name).read_text())
r=read('comparison-v3.json');v=r['validation'];h=r['headon'];t=r['holdout'];a,b=t['baseline'],t['candidate']
def table(summary1,summary2):
 rows=[('红方进球',summary1['outcomes'].get('GOAL',0),summary2['outcomes'].get('GOAL',0)),('蓝方推进左门',summary1['outcomes'].get('CLEARED_GOAL',0),summary2['outcomes'].get('CLEARED_GOAL',0)),('超时',summary1['outcomes'].get('TIMEOUT',0),summary2['outcomes'].get('TIMEOUT',0)),('出界',summary1['outcomes'].get('OUT',0),summary2['outcomes'].get('OUT',0)),('首次对抗突破',summary1['first_contest_results'].get('BROKE_THROUGH',0),summary2['first_contest_results'].get('BROKE_THROUGH',0)),('首次对抗丢球',summary1['first_contest_results'].get('LOST',0),summary2['first_contest_results'].get('LOST',0)),('超过20秒的贴球僵持',summary1['stalls_over_20s'],summary2['stalls_over_20s']),('反抢后向前推进0.30米',summary1['productive_regain_runs'],summary2['productive_regain_runs'])]
 return '| 指标 | 本轮基线 | 新策略 |\n| --- | ---: | ---: |\n'+'\n'.join('| '+str(n)+' | '+str(x)+' | '+str(y)+' |' for n,x,y in rows)
text='''# 正面对抗与带球突破调试记录（2026-11-19）

本轮针对“双方碰到一起后进攻方很容易丢球，被蓝方反推进左门”，只修改独立二维工程。三维工程没有改动，也没有自动同步本次策略。此次是规则策略调试，不是强化学习训练。

## 结论

正面争球有所改善，仍不能保证撞上后突破。保留防守方的预判、争球与回追，未降低防守速度、设置随机输赢或给进攻方增加推球力。双方行走、转向、足球滚动、身体排斥和踢球计算与本轮基线相同。

## 原因与修正

1. 原进攻在球门方向上推进，近球阶段缺少持续的绕行方向。增加 `EVADE_DRIBBLE`：目标路线被堵、对手距球0.65–1.8米且位于前方时，在左右两条路中比较路长、转向量、障碍和边线空间。选择后保持同一侧路，避免逐帧左右换向；越过原防守位置0.30米、接近路点或与球分离时解除计划。被断后清除旧计划。
2. 旧带球朝向容差可达25度，选了侧路也可能仍直走。绕行使用进入4度、退出10度的朝向容差；普通带球和射门容差保留。
3. 原进攻约3秒就侧移脱困，防守约8秒；侧移不带球，容易主动让出争球位置。现在只有球确实处在进攻方正前脚窗时才保持争球至8秒，与已有防守保持时间一致；脚位失效仍在3秒后尝试重定位，避免盲目死顶。
4. 距离太近时不启动大角度绕行。无必要时不绕行：球门路线已清晰就继续推进。界面黄色虚线和黄色目标点表示意图中的足球侧路，不会把足球移动到该点。

代码入口：`TeamPolicy.py` 的 `carry_around()`、`unblock_duel()`；`Navigation.py` 的 `EVADE_DRIBBLE` 分支；`DefensivePlan.py` 的带球阈值。`server.py` 只增加显示用球路目标，不参与策略反馈。

## 怎样判断，不再只看最终进球

- 首次进攻对抗：红方已有独占主动脚部触球证据，双方距离小于0.65米、双方距球均小于0.60米，且红方尚未首次丢球。
- 首次丢球：蓝方具有最近一次主动脚部触球记录，连续至少0.24秒独占前方脚窗；仅身体碰到球不算。
- 突破：红方具有最近一次主动脚部触球记录，独占脚窗至少0.24秒，身体超过蓝方0.25米、球超过蓝方0.35米。仅足球弹过去不算。
- 正面身体接触：首次丢球或突破之前，圆盘身体实际接触，双方朝向彼此的误差均小于60度、距球均小于0.40米，红方尚未越过蓝方。
- 同时触球不指定唯一控球者；终局进球不代替首次对抗的成败。上述仍是二维脚窗代理，不是经过真机标定的控球判定。
- 策略会改变是否相撞，所以除各组统计外，另列同一开局中新旧都发生正面接触的交集，避免把“绕开了”说成“碰撞后赢了”。

## 120个正面接近专项开局

双方从约0.6–0.9米身体间距开始正面接近球，120局均发生了符合定义的正面身体接触。它们是专项诊断样本，参与了版本选择，不是独立保留集。

'''+table(h['baseline'],h['candidate'])+'''

新策略首次对抗中：32次突破、85次丢球、2次未解决，另1次最终进球但未满足严格突破测量条件。对比基线3次突破、117次丢球。这比“碰上必输”好，但正面开局仍明显偏向防守方。

## 240个版本选择验证开局

此表为裁判初始化修正前的开发比较，最终同规则验证见下方1000局与上方200局。

'''+table(v['baseline'],v['candidate'])+'''

这些开局用于比较多个版本和选择参数，不能当作未参与选择的最终测试。

## 1000个独立保留开局

种子90000–90999，三类开局交替：中场、门前、边路。位置、朝向和随机种子逐局一致，每局180秒，物理步长0.04秒。最终源码在保留测试前冻结，摘要见 `selected-before-holdout.json`。训练种子80000–80159，验证种子83000–83239，专项种子86000–86119。

'''+table(a,b)+'\n\n'
extra_a=read('baseline-headon-holdout-final.json')['summary'];extra_b=read('production-headon-holdout-final.json')['summary']
section='## 200个独立正面开局复测\n\n最终源码冻结后另用种子96000–96199生成200个正面接近开局，未参与版本选择；200局均发生实际正面身体接触。\n\n'+table(extra_a,extra_b)+'\n\n首次对抗突破2→43，丢球198→151，另6局最终进球但未测得严格突破。正面对抗仍然以丢球居多；该专项超时从0增加到2，也保留在表中。\n\n'
text=text.replace('## 240个版本选择验证开局',section+'## 240个版本选择验证开局')
p=t['paired_frontal_contact_in_both']
text+=f"同一开局中新旧策略都发生正面身体接触的交集为 **{p['runs']}局**：\n\n| 首次正面接触后结果 | 基线 | 新策略 |\n| --- | ---: | ---: |\n"
for key,label in [('LOST','丢球'),('BROKE_THROUGH','突破'),('UNRESOLVED','未解决'),('GOAL_WITHOUT_MEASURED_BREAK','最终进球但未测得严格突破')]:text+=f"| {label} | {p['baseline_results'].get(key,0)} | {p['candidate_results'].get(key,0)} |\n"
text+='\n这部分才直接回答“双方确实正面碰到一起之后如何”。条件交集本身受策略影响，因此它是描述性结果；全量固定开局结果也同时保留。\n\n'
base=read('baseline-holdout-final.json')['runs'];new=read('production-holdout-final.json')['runs']
text+='### 按区域复查\n\n| 区域 | 基线红方进球 | 新红方进球 | 基线超时 | 新超时 | 基线长僵持 | 新长僵持 |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
for index,name in enumerate(['中场','门前','边路']):
 x=base[index::3];y=new[index::3];text+=f"| {name} | {sum(z['outcome']=='GOAL' for z in x)} | {sum(z['outcome']=='GOAL' for z in y)} | {sum(z['outcome']=='TIMEOUT' for z in x)} | {sum(z['outcome']=='TIMEOUT' for z in y)} | {sum(z['longest_stall_seconds']>20 for z in x)} | {sum(z['longest_stall_seconds']>20 for z in y)} |\n"
old=json.loads((ROOT/'verification/counterpress-20261119/production-holdout-v3.json').read_text())['summary'];newold=read('production-old-cohort-v3.json')['summary']
text+='\n### 裁判初始化修正前的历史开局回归（归档）\n\n种子60000–60999是已经使用过的历史测试，不当作新的独立成功率证据。下表是在本轮后段裁判修正之前计算的归档结果，不能作为当前裁判版本的最终数据；当前正式比较采用上方修正后的1000局和200局：\n\n| 结果 | 本轮基线 | 新策略 |\n| --- | ---: | ---: |\n'
for key,label in [('GOAL','红方进球'),('CLEARED_GOAL','蓝方进左门'),('TIMEOUT','超时'),('OUT','出界')]:text+=f"| {label} | {old['outcomes'].get(key,0)} | {newold['outcomes'].get(key,0)} |\n"
text+='''
## 未采用的方案与限制

- 只增加争球等待时间，有一定改善，但不是完整的过人能力；没有采用12秒、16秒等单纯等待对手先让位的思路。
- 持续向球侧小步挪动，有些版本提高进球数，却显著增加长僵持，未采用。例如专项120局中，有版本进100球，但74局发生长僵持、18局超时。
- 距离过近仍强行启动大角度绕行，有版本在专项120局中出现52次出界，未采用。
- 预测对手到达时间的路径代价没有表现出足够稳定的额外收益，正式版本保留较简单的路线选择。
- 有效脚窗保持8秒，仍可能被利用成等待战术；没有宣称已实现护球、假动作或稳定的一对一过人。近身转向期间不能同时行走，仍可能丢球。
- 出界、超时没有算成防守胜利。新的出界或局部退步应查看上表，不用进球增长掩盖。
- 精确位置、圆盘身体、简化脚窗及平均动作速度，均限制结果。不能推断三维平衡、视觉或NAO真机性能。

## 开放比赛初始化的公平性修正

后段复查发现：最初1000局中的11个OUT包含6个红方越过门口边缘的真实出界，以及5个蓝方先触球后合法进左门却被旧开球来源保护误判为重开。旧场景虽然直接进入PLAYING，仍保留了“从开球开始”的裁判来源状态；此时把首个触球的蓝方误当成了开球者。

新增显式 `restart_goal_guard`：真正的重开仍启用“直接把重开球踢入自家球门不得分”的规则；独立1v1开放比赛开局不启用这个来源保护。新增4项测试分别覆盖蓝方先触球进球、红方进球、红方开放比赛乌龙有效，以及真实重开直接乌龙仍被拒绝。没有取消实际比赛规则。

本轮策略参数没有因此调整。保留原始修正前数据；随后新旧策略均使用相同修正后的裁判，重新计算1000个保留开局和200个独立正面对抗开局。最终比较文件以 `-final.json` 结尾。这样不会把只修复新策略的裁判误判当作策略收益。

## 测试与交付

- 50项行为、终局、反抢、回防、出生区域及开放比赛判球回归检查；出生区域覆盖5000个种子。
- 旧终局测试曾假设第一帧必须发生平移；新策略可能先转向。更新后的测试同时检查位置和朝向，仍要求运行时间前进、身体姿态发生变化；历史测试保留原样。
- 观察器v1只使用脚窗几何，v2增加主动脚部触球证据，v3增加严格正面接触。试验文件保留各自版本，最终表只用v3相同比较口径，不混合。
- 浏览器检查中英状态、黄色球路目标、重复种子、出生区域框选、批量接口、移动布局、离线导出、终局停止与连续运行；详见本轮JSON。
- 五例单文件HTML已重建：第三例种子349，在21.80秒发生正面接触，36.44秒满足突破条件，最后进球；未先发生蓝方独占主动脚部控制。例子经过挑选，不代替成功率测试。
- 原MP4/MKV保留为历史视频，没有重新录制。Windows入口保留，但本轮没有声称在真实Windows系统执行过。
- 关闭旧Python服务后重新启动；仅刷新旧网页不会加载新策略。压缩包与运行文件逐字节核对。没有提交或推送Git。

## 证据位置

本轮目录：`verification/attacking-duels-20261119/`。

- `evaluate_v3.py`、三组`*-layouts.json`：可重复开局与观察口径。
- `baseline-holdout-final.json`、`production-holdout-final.json`、`comparison-v3.json`：逐局及配对统计。
- `headon-baseline-v3.json`、`production-headon-v3.json`：120个正面对抗开局。
- `selected-before-holdout.json`：最终测试前冻结源码。
- `regression-check.json`、`browser-check.json`、`attacking-browser-check.json`、`endurance-check.json`、`package-check.json`、`delivery-check.json`：交付验证。

'''
(ROOT/'docs/ATTACKING_DUELS_2026-11-19.md').write_text(text)
# Main README keeps concise current facts and links historical cohorts separately.
p=ROOT/'README.md';body=p.read_text().replace('第三例展示反抢后进球','第三例展示正面对抗后突破进球')
start=body.index('当前增加了绕行带球') if '当前增加了绕行带球' in body else body.index('本轮新增了进攻方的');end=body.index('修改后需要关闭旧 Python 服务',start)
new=f'''当前增加了绕行带球：球门路线被堵时提前选择侧路并保持方向；已经贴近时避免强行大角度转向。有效脚下争球不再约3秒就主动侧移让位；脚位失效时仍及时重定位。被断后保留丢球反抢，进球或出界后停止动作。

200个独立正面接近开局均发生实际正面接触：首次突破2→43，首次丢球198→151，长僵持14→9，超时0→2。正面对抗仍以丢球居多。新的1000个独立保留开局中，红方进球{a['outcomes'].get('GOAL',0)}→{b['outcomes'].get('GOAL',0)}，超时{a['outcomes'].get('TIMEOUT',0)}→{b['outcomes'].get('TIMEOUT',0)}，长僵持{a['stalls_over_20s']}→{b['stalls_over_20s']}，出界{a['outcomes'].get('OUT',0)}→{b['outcomes'].get('OUT',0)}。正面争球仍然偏向防守，不保证撞上后能突破。

最新记录见 [正面对抗与带球突破](docs/ATTACKING_DUELS_2026-11-19.md)，包含新旧都实际正面接触的配对统计。历史记录：[反抢与回追](docs/COUNTERPRESS_TUNING_2026-11-19.md)、[出生区域与预判拦截](docs/DEFENCE_TUNING_2026-11-19.md)、[第二轮策略调试](docs/STRATEGY_TUNING_ROUND2_2026-11-19.md)。不同轮次的开局不同，各表仅比较本表的配对基线。

'''
p.write_text(body[:start]+new+body[end:])
# Archive's README stays short and Windows-only.
p=ROOT/'2D_Shared_Policy_2026-11-11/README.md';body=p.read_text();start=body.index('## 本次更新与测试');end=body.index('## 打不开怎么办',start)
new=f'''## 本次更新与测试（2026-11-19）

- 路线被堵时，红方会尝试侧路带球；页面显示 **绕行带球**，黄色虚线是希望足球走的路线。
- 已经贴近时不强行大转身，有效争球时不会过早侧移让球；被断后回追。
- 进球或出界后停止动作。

200个独立正面对抗开局：首次突破从2次增加到43次，首次丢球从198次减少到151次。仍有很多对抗会失败，并非碰上就能突破。

另外1000个相同的新开局，每局最多180秒：

| 结果 | 更新前 | 更新后 |
| --- | ---: | ---: |
| 红方进球 | {a['outcomes'].get('GOAL',0)} | {b['outcomes'].get('GOAL',0)} |
| 超时 | {a['outcomes'].get('TIMEOUT',0)} | {b['outcomes'].get('TIMEOUT',0)} |
| 超过20秒的僵持 | {a['stalls_over_20s']} | {b['stalls_over_20s']} |
| 出界 | {a['outcomes'].get('OUT',0)} | {b['outcomes'].get('OUT',0)} |

这是简化二维结果，最近触球不等于稳定控球，超时也不算防守胜利。更新后先关闭旧黑色窗口，再双击启动文件；只刷新网页不会加载新策略。

'''
p.write_text(body[:start]+new+body[end:])
p=ROOT/'2D_Shared_Policy_2026-11-11/README_DETAILED_LOCAL.md';body=p.read_text();prefix='本轮正面对抗与绕行带球调试记录：`../docs/ATTACKING_DUELS_2026-11-19.md`。其中包含120个正面开局、1000个独立开局与失败方案；下方为历史详细说明。\n\n'
if not body.startswith(prefix):p.write_text(prefix+body)
print('Report and README updates written')
