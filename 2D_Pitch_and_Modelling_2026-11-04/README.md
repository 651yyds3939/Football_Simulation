# S3.1–S3.3: 2D model figures

| Task | PNG | PDF | SVG |
|---|---|---|---|
| 3.1 Pitch geometry | [PNG](S3_1_pitch_2d_en.png) | [PDF](S3_1_pitch_2d_en.pdf) | [SVG](S3_1_pitch_2d_en.svg) |
| 3.2 Ball motion model | [PNG](S3_2_ball_model_2d_en.png) | [PDF](S3_2_ball_model_2d_en.pdf) | [SVG](S3_2_ball_model_2d_en.svg) |
| 3.3 Robot planar model | [PNG](S3_3_robot_model_2d_en.png) | [PDF](S3_3_robot_model_2d_en.pdf) | [SVG](S3_3_robot_model_2d_en.svg) |

[Empty pitch without annotations](pitch_2d_clean.png) is also available.

These figures describe the current 2D abstractions. Ball deceleration and disc dimensions include assumptions; motion rates come from existing Webots measurements, not calibrated hardware. The diagrams do not establish full course acceptance, physical friction calibration or NAO6 dynamics validation.

[Chinese work-package notes](S3_二维建模与验证任务说明.md) distinguish existing components and outstanding work.

## Data sources / 数据来源

Separate source cards keep S3.1–S3.3 readable. Each image distinguishes course requirements, simulation measurements, derived values and modelling choices.

| Topic / 内容 | 中文图片 | English image | PDF |
|---|---|---|---|
| 3.1 Pitch, goals, markings and rules / 球场、球门、标线与规则 | [中文](S3_1_Data_Sources_ZH.png) | [English](S3_1_Data_Sources_EN.png) | [中文](S3_1_Data_Sources_ZH.pdf) · [EN](S3_1_Data_Sources_EN.pdf) |
| 3.2 Ball size and motion / 足球尺寸与运动 | [中文](S3_2_Data_Sources_ZH.png) | [English](S3_2_Data_Sources_EN.png) | [中文](S3_2_Data_Sources_ZH.pdf) · [EN](S3_2_Data_Sources_EN.pdf) |
| 3.3 Robot reference and motion / 机器人参考与运动 | [中文](S3_3_Data_Sources_ZH.png) | [English](S3_3_Data_Sources_EN.png) | [中文](S3_3_Data_Sources_ZH.pdf) · [EN](S3_3_Data_Sources_EN.pdf) |

The brief overview also includes pitch and goal dimensions: [中文](2D_Data_Sources_Simple_ZH.png) · [English](2D_Data_Sources_Simple_EN.png).

Source details and limitations: [来源核对说明](S3_数据来源说明.md). Regenerate the six topic figures with `python export_s3_sources.py` using the configured Python environment. File hashes are recorded in `s3_data_sources_manifest.json`.
