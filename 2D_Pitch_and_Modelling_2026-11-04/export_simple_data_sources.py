"""Create short presentation versions of the parameter provenance graphic."""
from pathlib import Path
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '2D_Shared_Policy_2026-11-11/backend/tools'))
from soccer2d import Model

m = Model()
ink, muted = '#203d47', '#607380'
colors = ['#147c79', '#346ab0', '#7357a3', '#ad6c19']
content = {
    'EN': {
        'title': 'Where do the numbers come from?',
        'subtitle': 'S3.1 Pitch and rules · S3.2 Ball · S3.3 Robot',
        'cards': [
            ('Course requirements', ['Pitch: 9 × 6 m', 'Goal: width 2.6 × height 1.2 × depth 0.6 m', 'Ball diameter ≈ 0.14 m'],
             'Source: Project specification, page 3'),
            ('Webots motion tests', [
                f'Forward / backward: {m.walk_speed:.3f} / {m.back_speed:.3f} m/s',
                f'Side-step left / right: {m.left_speed:.3f} / {m.right_speed:.3f} m/s',
                f'Turn left / right: {math.degrees(m.left_turn):.2f} / {math.degrees(m.right_turn):.2f} °/s'],
             'Source: Displacement or angle change ÷ test time'),
            ('Motion files', [f'Shot: {m.shot_seconds:.3f} s', f'Pass: {m.pass_seconds:.3f} s'],
             'Source: Final timestamps in Shoot.motion / LongPass.motion'),
            ('Model assumptions', [f'Ball deceleration: {m.rolling_deceleration:.2f} m/s²',
                f'Robot disc radius: {m.robot_radius:.2f} m', 'Example ball speed: 0.50 m/s'],
             'Chosen model values — not measured'),
        ],
        'footer': 'Webots measurements describe simulation behaviour, not real NAO6 performance.',
    },
    'ZH': {
        'title': '这些数据从哪里来？',
        'subtitle': '3.1 球场与规则 · 3.2 足球 · 3.3 机器人',
        'cards': [
            ('课程要求', ['球场：9 × 6 m', '球门：宽 2.6 × 高 1.2 × 深 0.6 m', '足球直径约 0.14 m'], '来源：课程项目说明，第 3 页'),
            ('Webots 仿真测试', [
                f'前进 / 后退：{m.walk_speed:.3f} / {m.back_speed:.3f} m/s',
                f'左 / 右侧移：{m.left_speed:.3f} / {m.right_speed:.3f} m/s',
                f'左 / 右转：{math.degrees(m.left_turn):.2f} / {math.degrees(m.right_turn):.2f} °/s'],
             '来源：仿真中的位移或转角 ÷ 测试时间'),
            ('动作文件', [f'射门：{m.shot_seconds:.3f} s', f'传球：{m.pass_seconds:.3f} s'],
             '来源：Shoot.motion / LongPass.motion 的末时间戳'),
            ('模型假设', [f'足球减速度：{m.rolling_deceleration:.2f} m/s²',
                f'机器人圆盘半径：{m.robot_radius:.2f} m', '演示用足球初速度：0.50 m/s'],
             '人为设定的模型数值，尚未实测'),
        ],
        'footer': 'Webots 测量值反映仿真表现，不能当作真实 NAO6 的性能。',
    },
}

for language, data in content.items():
    regular = (FontProperties(family='DejaVu Sans') if language == 'EN' else
               FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyh.ttc')))
    bold = (FontProperties(family='DejaVu Sans', weight='bold') if language == 'EN' else
            FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyhbd.ttc')))
    fig = plt.figure(figsize=(16, 9), facecolor='#f3f6f8')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 16), ylim=(0, 9))
    ax.axis('off')
    def label(x, y, value, size=17, color=ink, weight=False):
        ax.text(x, y, value, va='top', fontsize=size, color=color,
                fontproperties=bold if weight else regular)
    label(.7, 8.48, data['title'], 31, weight=True)
    label(.73, 7.78, data['subtitle'], 16, muted)
    for i, (title, rows, source) in enumerate(data['cards']):
        x, y = (.7 if i % 2 == 0 else 8.15), (4.35 if i < 2 else 1.23)
        ax.add_patch(FancyBboxPatch((x, y), 7.15, 2.82,
            boxstyle='round,pad=0,rounding_size=0.16', facecolor='white',
            edgecolor='#dce4e9', linewidth=1))
        label(x+.3, y+2.52, title, 21, colors[i], True)
        for j, row in enumerate(rows):
            label(x+.32, y+1.9-j*.43, row, 16)
        label(x+.32, y+.45, source, 10.7, muted)
    label(.75, .7, data['footer'], 13.5, muted)
    stem = HERE / f'2D_Data_Sources_Simple_{language}'
    for extension in ['png', 'pdf']:
        fig.savefig(stem.with_suffix('.'+extension), dpi=240, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(stem.with_suffix('.png'))
