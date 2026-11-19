"""Export a source-labelled summary of the existing 2D model parameters."""
from pathlib import Path
import argparse
import json
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language', choices=['zh', 'en'], default='zh')
args = parser.parse_args()
translations = (json.loads((HERE / 'data_sources_en.json').read_text())
                if args.language == 'en' else {})
ROOT = HERE.parent
REPO = ROOT / '2D_Shared_Policy_2026-11-11/backend'
sys.path.insert(0, str(REPO / 'tools'))
from soccer2d import Model

model = Model()
records = json.loads((REPO / 'verification/development/navigation/motion-result.json').read_text())
measured = {row['action']: row for row in records}
rates = [
    ('前进', 'walk', abs(measured['walk']['displacement'][0]), 8, model.walk_speed, 'm/s'),
    ('后退', 'back', abs(measured['back']['displacement'][0]), 8, model.back_speed, 'm/s'),
    ('左侧移', 'step_left', abs(measured['step_left']['displacement'][1]), 8, model.left_speed, 'm/s'),
    ('右侧移', 'step_right', abs(measured['step_right']['displacement'][1]), 8, model.right_speed, 'm/s'),
    ('左转', 'left20', abs(measured['left20']['yaw_degrees']), 4, math.degrees(model.left_turn), '°/s'),
    ('右转', 'right20', abs(measured['right20']['yaw_degrees']), 4, math.degrees(model.right_turn), '°/s'),
]
for _, action, movement, seconds, rate, _ in rates:
    assert measured[action]['seconds'] == seconds
    assert math.isclose(movement / seconds, rate, rel_tol=1e-10)

def final_timestamp(name):
    row = (REPO / 'Wenao/motions' / name).read_text().strip().splitlines()[-1]
    minutes, seconds, millis = map(int, row.split(',')[0].split(':'))
    return minutes * 60 + seconds + millis / 1000

assert final_timestamp('Shoot.motion') == model.shot_seconds
assert final_timestamp('LongPass.motion') == model.pass_seconds

FONT = FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyh.ttc'))
BOLD = FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyhbd.ttc'))
if args.language == 'en':
    FONT = FontProperties(family='DejaVu Sans')
    BOLD = FontProperties(family='DejaVu Sans', weight='bold')
INK, MUTED = '#203d47', '#5d707b'
TEAL, BLUE, GOLD, PURPLE = '#147c79', '#346ab0', '#ad6c19', '#7357a3'
fig = plt.figure(figsize=(16, 13.5), facecolor='#f3f6f8')
ax = fig.add_axes([0, 0, 1, 1])
ax.set(xlim=(0, 16), ylim=(0, 13.5))
ax.axis('off')

def text(x, y, s, size=12, color=INK, bold=False, **kwargs):
    s = translations.get(s, s)
    if args.language == 'en':
        assert not any('\u4e00' <= char <= '\u9fff' for char in s), s
    return ax.text(x, y, s, fontsize=size, color=color,
                   fontproperties=BOLD if bold else FONT, va='top', **kwargs)

def box(x, y, w, h, face='white', edge='#dce4e9', radius=.13):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
        boxstyle=f'round,pad=0,rounding_size={radius}', linewidth=1,
        facecolor=face, edgecolor=edge))

def tag(x, y, label, color):
    text(x, y, label, size=10.5, color=color, bold=True, ha='right')

text(.65, 12.94, '二维足球模型｜数据来源与使用边界', 27, bold=True)
text(.68, 12.30, '课程规格、仿真测量、动作文件与建模假设分别标注，便于追溯与后续验证。', 13, MUTED)
for x, label, color in [( .65, '课程规格', TEAL), (4.40, 'Webots 测量', BLUE),
                         (8.15, '动作文件', PURPLE), (11.90, '假设 / 推导', GOLD)]:
    box(x, 11.35, 3.42, .52, face='white', edge='#e0e7ec')
    text(x+.19, 11.76, label, 12, color, True)

box(.65, 4.14, 7.22, 6.87)
box(8.12, 4.14, 7.22, 6.87)
text(.95, 10.68, '足球：哪些是要求，哪些是演示条件？', 17, bold=True)
text(8.42, 10.68, '机器人：当前动作在仿真中的表现', 17, bold=True)

ball_rows = [
    (9.96, '直径约 0.14 m', '课程规格', TEAL,
     '项目说明第 3 页：周长约 45 cm，直径约 14 cm。'),
    (9.02, '示例初速度 0.50 m/s', '演示初始条件', GOLD,
     '绘图时选取，用于展示滚动过程；没有经过测量。'),
    (8.08, f'滚动减速度 {model.rolling_deceleration:.2f} m/s²', '建模假设', GOLD,
     '来自当前二维模型配置，尚未通过滚动实验标定。'),
    (7.14, f'停止时间 {0.5/model.rolling_deceleration:.3f} s', '公式推导', GOLD,
     't = v0 / a = 0.50 / 0.35；依赖上述假设。'),
    (6.20, f'停止距离 {0.5**2/(2*model.rolling_deceleration):.3f} m', '公式推导', GOLD,
     's = v0² / (2a) = 0.50² / (2 × 0.35)。'),
]
for y, title, label, color, detail in ball_rows:
    text(.97, y, title, 14, bold=True)
    tag(7.54, y-.01, label, color)
    text(.97, y-.38, detail, 10.6, MUTED)
    ax.plot([.97, 7.54], [y-.73]*2, color='#e7edf0', lw=.8)
text(.97, 5.20, '曲线与圆点来自哪里？', 12, TEAL, True)
text(.97, 4.83, '虚线：同一假设下的理论公式；圆点：二维程序计算值。\n两者吻合说明实现一致，不能证明真实足球的物理性能。',
     10.6, MUTED, linespacing=1.7)

text(8.43, 10.07, '位移 / 转角 ÷ 仿真时间 → 平均速度', 11, BLUE, True)
text(8.43, 9.66, '动作', 10, MUTED)
text(10.00, 9.66, '原始测量与计算', 10, MUTED)
text(15.00, 9.66, '图中数值', 10, MUTED, ha='right')
for i, (label, action, movement, seconds, rate, unit) in enumerate(rates):
    y = 9.25 - .44*i
    text(8.43, y, label, 11.2, bold=True)
    measure_unit = '°' if unit == '°/s' else ' m'
    text(10.00, y, f'{movement:.5f}{measure_unit} / {seconds} s', 10.8, MUTED)
    text(15.00, y, f'{rate:.2f}' + ' °/s' if unit == '°/s' else f'{rate:.5f} m/s',
         11.2, BLUE, True, ha='right')
ax.plot([8.43, 15.00], [6.55]*2, color='#e7edf0', lw=.8)
text(8.43, 6.31, '动作文件的末时间戳 → 当前模型时长', 11, PURPLE, True)
text(8.43, 5.91, f'射门：Shoot.motion → {model.shot_seconds:.3f} s', 11.4)
text(8.43, 5.52, f'传球：LongPass.motion → {model.pass_seconds:.3f} s', 11.4)
text(8.43, 5.13, '这些是动作时间轴值，不是成功射门或传球的总耗时。', 10.2, MUTED)
text(8.43, 4.70, f'碰撞圆盘半径 {model.robot_radius:.2f} m', 11.4, bold=True)
tag(15.00, 4.70, '建模假设', GOLD)
text(8.43, 4.36, '示意朝向 35° 为绘图选值；箭头长度不代表实测速度。', 10.2, MUTED)

box(.65, 2.49, 14.69, 1.35, face='#e9f2f3', edge='#d4e6e7')
text(.97, 3.55, '当前证据能说明什么？', 14, TEAL, True)
text(.97, 3.14, '速度来自单项 Webots 测试，属于当前模型与动作资产的平均表现；不是 NAO6 官方性能或真机标定结果。', 11.5)
text(.97, 2.78, '二维模型用于快速测试决策。平衡、摔倒和关节动力学未被表示；假设参数仍需重复实验验证。', 11.5)

text(.72, 2.16, '可追溯文件（相对于 Robotics_TDP 根目录）', 12, bold=True)
sources = [
    '课程规格：TDP_Project_Specification_2026_27.pdf，第 3 页',
    '运动测量：Webots_Robotics_TDP/verification/development/navigation/motion-result.json',
    '动作文件：Webots_Robotics_TDP/Wenao/motions/{Shoot,LongPass}.motion',
    '模型参数：Webots_Robotics_TDP/tools/soccer2d.py → Model',
    '图表生成：2D_Pitch_and_Modelling_2026-11-04/export_motion_models.py',
]
for i, line in enumerate(sources):
    text(.75, 1.79-i*.265, line, 9.1, MUTED)
text(15.30, .22, '数据来源说明 · 2026-11-04', 9, MUTED, ha='right')

stem = HERE / f'2D_Model_Data_Sources_{args.language.upper()}'
fig.savefig(stem.with_suffix('.png'), dpi=240, facecolor=fig.get_facecolor())
fig.savefig(stem.with_suffix('.pdf'), facecolor=fig.get_facecolor())
plt.close(fig)
print(stem.with_suffix('.png'))
print(stem.with_suffix('.pdf'))
