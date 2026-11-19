# 本轮验证数据

最终比较使用 `baseline-holdout-v3.json` 与 `production-holdout-v3.json`，汇总见 `holdout-comparison.json`。`selected-before-holdout.json` 保存最终保留测试前冻结的源码摘要。

`train-layouts.json`、`validation-layouts.json`、`holdout-layouts.json` 分别是筛选、验证和最终保留开局。`steal-layouts.json` 是从训练场景截取的80个被断球位置，仅作定点压力测试。

部分早期补充测试发生观测脚本错误，已移入 `invalid-observer/`，不得用其中的朝向、触球或累计时长统计判断策略效果。修正后脚本增加逐局时长覆盖断言，最终比较使用版本3重新计算。

候选源码保存在各 `*-app` 目录。当前实际交付源码在仓库根目录的 `2D_Shared_Policy_2026-11-11`；`production-app` 保存冻结的策略版本。
