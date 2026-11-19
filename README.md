# 2D 机器人足球项目

二维项目已于 2026-11-19 整理到本目录。三维工程仍位于同级的 `../Webots_Robotics_TDP`，原文件与代码保持原位。

## 直接看演示

双击 [Football_1v1_Demo.html](Football_1v1_Demo.html)，用 Chrome 或 Edge 打开即可。文件内含五个固定回放，支持切换示例、暂停、进度拖动和倍速；不需要 Python、Webots 或联网。

[Football_1v1_Demo.mp4](Football_1v1_Demo.mp4) 和 `TDP-2026-11-12_16.21.10.mkv` 是已有的二维演示视频。

## 运行随机攻防测试

打开 [2D_Shared_Policy_2026-11-11](2D_Shared_Policy_2026-11-11/README.md) 文件夹：Windows 双击其中的 `start_windows.bat`；Ubuntu 可以在该文件夹运行 `bash start.sh`。实时测试需要 Python 3.8 或更新版本，使用标准库。

需要分享可运行版本时，发送 [2D_Shared_Policy_2026-11-11.zip](2D_Shared_Policy_2026-11-11.zip)。压缩包内保留简短的 Windows 使用说明；详细历史说明在本地 `2D_Shared_Policy_2026-11-11/README_DETAILED_LOCAL.md`，未放入压缩包。

## 主要内容

| 路径 | 用途 |
| --- | --- |
| `Football_1v1_Demo.html` | 五个示例的单文件离线回放，分享展示优先使用 |
| `2D_Shared_Policy_2026-11-11/` | Python 一攻一防实时版、浏览器界面及独立代码快照 |
| `2D_Shared_Policy_2026-11-11/backend/tools/soccer2d.py` | 二维运动、足球接触与比赛计算 |
| `2D_Shared_Policy_2026-11-11/backend/Wenao/controllers/Utils/` | 二维使用的策略、导航、预判拦截和比赛规则代码 |
| `2D_Shared_Policy_2026-11-11/backend/tools/view_soccer2d.py` | 原二维四对四回放生成器；同目录保留批量策略实验工具及界面模板 |
| `2D足球可视化场景_2026-11-02.html`、`2D_Football_Viewer_EN_2026-11-04.html` | 原四对四二维中英文回放 |
| `2D_1v1_Demo_2026-11-11/`、`2D_1v1_Demo_2026-11-11 (1)/` | 较早的独立 JavaScript 演示与原有副本，保留作历史对照 |
| `2D_Pitch_and_Modelling_2026-11-04/` | 球场、足球、机器人平面模型图片及导出脚本 |
| `S3_数据来源图片_中英文_2026-11-04/` | 六张中英文参数来源图 |
| `verification/` | 二维验证记录、对照数据、回放构建和打包脚本 |
| `docs/` | 二维策略、模型限制和历史测试说明的本地参考副本 |

## 二维与三维暂时独立

二维实时版现在从本目录的 `backend/` 导入策略和模型，使用分离时保存的同版本代码。此后修改三维工程不会自动更新二维，修改二维也不会自动更新三维。文件夹中的 `Wenao` 是保留的 Python 模块路径及少量来源参考文件，不是另一个完整 Webots 工程。

二维打包和五例回放构建分别使用 `verification/one-v-one-20261111/package_shared_policy.py` 和 `verification/simple-html-20261112/build_demo.py`。二者已按新目录工作，打包默认使用本地二维快照。

图表导出使用本地模型及复制的历史测量记录；涉及课程 PDF 来源核对的脚本继续读取上一级工作区的原始 PDF。图片再生成还需要已有的 Matplotlib、NumPy 和字体环境，日常查看图片、播放 HTML 或运行一攻一防不需要这些图表依赖。

原 `verification/` 中的三维输入重算、执行结果等记录留在原处；三维仓库内的共用代码、既有工具和测试也保留原位。`docs/` 及详细历史说明中的旧路径和命令代表当时的工程布局，当前二维入口以本页为准。重新组织后，请关闭旧 Python 服务，从新位置重新启动。

