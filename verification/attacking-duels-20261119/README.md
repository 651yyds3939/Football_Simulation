# 正面对抗调试证据

此目录记录2026-11-19的独立二维进攻策略调试。正式运行目录是仓库根目录的 `2D_Shared_Policy_2026-11-11`，此处的各个 `*-app` 是隔离快照，勿作为启动入口。

正式报告：`../../docs/ATTACKING_DUELS_2026-11-19.md`。

- `baseline-app`：本轮开始前的代码；`baseline-corrected-app`：同一旧策略加公共开放比赛裁判初始化修正。
- `production-app`：最终冻结代码；`selected-before-holdout.json`保存最终源码摘要，`selected-before-initial-holdout.json`保留裁判修正之前的摘要。
- `baseline-holdout-final.json`与`production-holdout-final.json`：使用相同裁判的1000个固定保留开局。
- `baseline-headon-holdout-final.json`与`production-headon-holdout-final.json`：200个独立正面开局。
- `comparison-v3.json`：包括两个版本都实际发生正面接触的配对交集。
- `*-v3.json`：部分是裁判初始化修正前的诊断或版本选择数据，见报告，不能替代最终文件。
- `evaluate_geometry_v1.py` / `evaluate_v2.py` / `evaluate_v3.py`：从脚窗几何、主动触球证据到严格正面接触的观察器。正式比较使用v3，两边口径相同。
- `out-diagnostics.json`：解释修正前11次OUT，6次真实门口边缘出界、5次旧重开来源保护误判。原始结果保留，没有覆盖或静默改计分。
- `invariants.json`：物理文件逐字节一致、防守预判函数未变、20个开局反转球员处理顺序后的逐步一致性。
- `regression-check.json`、浏览器检查、`package-check.json`、`delivery-check.json`：交付验证。

训练和验证反复使用同一组布局，试验次数不能当作同样多的独立样本。五个分享回放也属于挑选示例，不是成功率测试。日志、截图和生成的验证网页由仓库忽略规则保留在本地。
