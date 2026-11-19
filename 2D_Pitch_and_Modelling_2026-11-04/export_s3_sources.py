"""Export bilingual source cards for S3.1–S3.3 without changing any model."""
from pathlib import Path
import hashlib
import json
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
REPO = HERE.parent / '2D_Shared_Policy_2026-11-11/backend'
sys.path.insert(0, str(REPO / 'tools'))
from soccer2d import Model
from Utils import CourseSpecs as c

m = Model()
measured = {r['action']: r for r in json.loads((REPO / 'verification/development/navigation/motion-result.json').read_text())}
skills = {r['fixture']: r for r in json.loads((REPO / 'verification/development/navigation/skills-result.json').read_text())}
for action, axis, expected in [('walk', 0, m.walk_speed), ('back', 0, m.back_speed),
                              ('step_left', 1, m.left_speed), ('step_right', 1, m.right_speed)]:
    record = measured[action]
    assert math.isclose(abs(record['displacement'][axis])/record['seconds'], expected)
assert skills['shoot']['max_ball_displacement'] == m.shot_range
assert skills['pass']['max_ball_displacement'] == m.pass_range

def card(title, rows, source, color=0):
    return {'title': title, 'rows': rows, 'source': source, 'color': color}

data = {
 '3_1': {
  'EN': ('Pitch and rules | Data sources', 'S3.1 · Course dimensions, rule references and modelling choices', [
    card('Pitch dimensions', [f'Playing area: {c.PITCH_LENGTH:g} × {c.PITCH_WIDTH:g} m',
      f'Border strip: {c.BORDER_WIDTH:g} m on each side',
      f'Including border: {c.PITCH_LENGTH+2*c.BORDER_WIDTH:g} × {c.PITCH_WIDTH+2*c.BORDER_WIDTH:g} m (derived)',
      f'Line width: {c.LINE_WIDTH:.2f} m (model choice)'],
      'Source: Project specification p. 3; CourseSpecs.py'),
    card('Goal dimensions', [f'Clear width: {c.GOAL_WIDTH:g} m', f'Clear height: {c.GOAL_HEIGHT:g} m',
      f'Depth: {c.GOAL_DEPTH:g} m', 'Post radius: 0.05 m (model choice)'],
      'Source: Project specification p. 3; CourseGoal.proto'),
    card('Pitch markings', [f'Goal area: {c.GOAL_AREA_LENGTH:g} × {c.GOAL_AREA_WIDTH:g} m',
      f'Penalty area: {c.PENALTY_AREA_LENGTH:g} × {c.PENALTY_AREA_WIDTH:g} m',
      f'Penalty mark: {c.PENALTY_MARK_DISTANCE:g} m from goal line',
      f'Centre circle diameter: {c.CENTRE_CIRCLE_DIAMETER:g} m'],
      'Source: Project specification p. 3, Table 1'),
    card('Rules and current 2D settings', ['Reference: course-linked RoboCup HL 2025 rules',
      'Implemented: clock, goals, exits and restarts', 'Goal-line crossing: the whole ball must pass',
      f'Half: {m.half_seconds:g} s; READY: {m.ready_seconds:g} s (test settings)'],
      'Source: Project specification App. A; MatchEngine.py; soccer2d.py', 3),
   ], 'Rule implementation is partial. Test timings and geometry choices are not additional course requirements.'),
  'ZH': ('球场与规则｜数据来源', '3.1 · 区分课程尺寸、规则依据与建模选择', [
    card('球场尺寸', [f'比赛区域：{c.PITCH_LENGTH:g} × {c.PITCH_WIDTH:g} m',
      f'场外边带：四周各 {c.BORDER_WIDTH:g} m',
      f'含边带总尺寸：{c.PITCH_LENGTH+2*c.BORDER_WIDTH:g} × {c.PITCH_WIDTH+2*c.BORDER_WIDTH:g} m（推导值）',
      f'线宽：{c.LINE_WIDTH:.2f} m（建模选择）'], '来源：项目说明第 3 页；CourseSpecs.py'),
    card('球门尺寸', [f'净宽：{c.GOAL_WIDTH:g} m', f'净高：{c.GOAL_HEIGHT:g} m',
      f'深度：{c.GOAL_DEPTH:g} m', '球门柱半径：0.05 m（建模选择）'],
      '来源：项目说明第 3 页；CourseGoal.proto'),
    card('球场标线', [f'球门区：{c.GOAL_AREA_LENGTH:g} × {c.GOAL_AREA_WIDTH:g} m',
      f'罚球区：{c.PENALTY_AREA_LENGTH:g} × {c.PENALTY_AREA_WIDTH:g} m',
      f'罚球点：距球门线 {c.PENALTY_MARK_DISTANCE:g} m',
      f'中圈直径：{c.CENTRE_CIRCLE_DIAMETER:g} m'], '来源：项目说明第 3 页，表 1'),
    card('规则与当前二维设置', ['规则参考：课程链接的 RoboCup HL 2025 规则',
      '当前实现：计时、进球、出界和重新开球', '进球几何条件：整个足球越过球门线',
      f'半场 {m.half_seconds:g} s；READY {m.ready_seconds:g} s（测试设置）'],
      '来源：项目说明附录 A；MatchEngine.py；soccer2d.py', 3),
   ], '当前仅实现部分规则。测试时长、线宽和球门柱半径不是新增的课程要求。'),
 },
 '3_2': {
  'EN': ('Ball model | Data sources', 'S3.2 · Required size, assumed motion and previous simulation results', [
    card('Size from the course', ['Circumference: 45 cm', f'Diameter: approximately {c.BALL_DIAMETER:.2f} m',
      f'Model radius: {c.BALL_RADIUS:.2f} m (diameter ÷ 2)',
      'Colour: black-and-white or bright orange'], 'Source: Project specification p. 3; CourseSpecs.py'),
    card('Motion assumptions', [f'Rolling deceleration: {m.rolling_deceleration:.2f} m/s²',
      f'Kick direction noise: σ = {m.kick_noise_radians:.2f} rad',
      'Post-contact velocity scale: 0.35', 'These are model choices, not measurements.'],
      'Source: soccer2d.py, Model and _roll_ball()', 3),
    card('Previous Webots kick tests', [f'Shot fixture ball displacement: {m.shot_range:.3f} m',
      f'Pass fixture ball displacement: {m.pass_range:.3f} m',
      'Values reused as 2D kick-distance parameters.',
      'Pass fixture included contact with the receiver.'],
      'Source: verification/development/navigation/skills-result.json', 1),
    card('Values calculated for the example', ['Chosen initial speed: 0.50 m/s (not measured)',
      f'Stopping time: 0.50 / {m.rolling_deceleration:.2f} = {0.5/m.rolling_deceleration:.3f} s',
      f'Stopping distance: 0.50² / (2 × 0.35) = {0.5**2/(2*m.rolling_deceleration):.3f} m',
      'Curves and points are generated by the 2D model.'],
      'Source: export_motion_models.py; constant-deceleration equations', 3),
   ], 'Single-fixture displacements are not general kick ranges. Rolling and contact assumptions are not physically calibrated.'),
  'ZH': ('足球模型｜数据来源', '3.2 · 区分课程尺寸、运动假设与以往仿真结果', [
    card('尺寸来自课程要求', ['周长：45 cm', f'直径：约 {c.BALL_DIAMETER:.2f} m',
      f'模型半径：{c.BALL_RADIUS:.2f} m（直径 ÷ 2）', '颜色：黑白拼块或亮橙色'],
      '来源：项目说明第 3 页；CourseSpecs.py'),
    card('运动参数属于假设', [f'滚动减速度：{m.rolling_deceleration:.2f} m/s²',
      f'踢球方向噪声：标准差 {m.kick_noise_radians:.2f} rad',
      '碰撞后速度缩放系数：0.35', '以上均为模型设定，不是实测结果。'],
      '来源：soccer2d.py 的 Model 与 _roll_ball()', 3),
    card('以往 Webots 踢球测试', [f'射门测试中的球位移：{m.shot_range:.3f} m',
      f'传球测试中的球位移：{m.pass_range:.3f} m', '当前二维模型将其作为踢球距离参数。',
      '传球测试包含接球队员触球。'], '来源：verification/development/navigation/skills-result.json', 1),
    card('示例图中的计算值', ['演示初速度：0.50 m/s（人为选取）',
      f'停止时间：0.50 / 0.35 = {0.5/m.rolling_deceleration:.3f} s',
      f'停止距离：0.50² / (2 × 0.35) = {0.5**2/(2*m.rolling_deceleration):.3f} m',
      '曲线和圆点由二维模型计算生成。'],
      '来源：export_motion_models.py；匀减速公式', 3),
   ], '单次测试位移不代表普遍的踢球射程；滚动与碰撞假设尚未完成物理标定。'),
 },
 '3_3': {
  'EN': ('Robot model | Data sources', 'S3.3 · NAO6 reference, measured motion rates and planar approximation', [
    card('NAO6 reference and 2D representation', ['Robot type: NAO6; four robots per team',
      'Reference dimensions: 574 × 311 × 275 mm',
      'Representation: planar collision discs; no robot mesh',
      '2D discs do not reproduce the full 3D body.'],
      'Source: Project specification p. 1; Kickoff slides p. 5'),
    card('Mean rates from Webots tests', [f'Forward / backward: {m.walk_speed:.5f} / {m.back_speed:.5f} m/s',
      f'Side-step left / right: {m.left_speed:.5f} / {m.right_speed:.5f} m/s',
      f'Turn left / right: {math.degrees(m.left_turn):.2f} / {math.degrees(m.right_turn):.2f} °/s',
      'Translation tests: 8 s; rotation tests: 4 s', 'Mean rate = displacement or angle change ÷ time'],
      'Source: verification/development/navigation/motion-result.json', 1),
    card('Action timing from motion files', [f'Shot: {m.shot_seconds:.3f} s — Shoot.motion',
      f'Pass: {m.pass_seconds:.3f} s — LongPass.motion', 'Current settings use the final asset timestamps.',
      'They are not total task-completion times.'],
      'Source: Wenao/motions/{Shoot,LongPass}.motion', 2),
    card('2D model choices', [f'Collision disc radius: {m.robot_radius:.2f} m (assumed)',
      f'Simulation step: {m.dt:.2f} s (chosen)', 'Pose: position (x, y) and heading θ',
      'Planar motion: body velocities rotated into world axes',
      'Illustration: 35° heading; arrow lengths are schematic'],
      'Source: soccer2d.py; export_motion_models.py', 3),
   ], 'These are simulation rates, not real NAO6 calibration. The 2D model omits balance, falls and joint dynamics.'),
  'ZH': ('机器人模型｜数据来源', '3.3 · 区分 NAO6 参考资料、仿真测量与二维简化', [
    card('NAO6 参考与二维表示', ['机器人类型：NAO6；每队 4 台', '参考外形尺寸：574 × 311 × 275 mm',
      '表示方式：二维碰撞圆盘，不加载机器人网格', '二维圆盘不等于完整的三维机器人。'],
      '来源：项目说明第 1 页；启动课第 5 页'),
    card('平均速度来自 Webots 测试', [f'前进 / 后退：{m.walk_speed:.5f} / {m.back_speed:.5f} m/s',
      f'左 / 右侧移：{m.left_speed:.5f} / {m.right_speed:.5f} m/s',
      f'左 / 右转：{math.degrees(m.left_turn):.2f} / {math.degrees(m.right_turn):.2f} °/s',
      '平移测试各 8 s；转向测试各 4 s', '平均速度 = 位移或转角 ÷ 测试时间'],
      '来源：verification/development/navigation/motion-result.json', 1),
    card('动作时间来自文件', [f'射门：{m.shot_seconds:.3f} s — Shoot.motion',
      f'传球：{m.pass_seconds:.3f} s — LongPass.motion', '当前配置取动作文件的末时间戳。',
      '它们不是完成一次射门或传球的总用时。'], '来源：Wenao/motions/{Shoot,LongPass}.motion', 2),
    card('二维模型中的选择', [f'碰撞圆盘半径：{m.robot_radius:.2f} m（假设）',
      f'仿真步长：{m.dt:.2f} s（选定值）', '姿态表示：平面位置 (x, y) 与朝向 θ',
      '平面运动：把机体速度旋转到世界坐标系', '绘图示意：朝向 35°；箭头长度不表示实测速度'],
      '来源：soccer2d.py；export_motion_models.py', 3),
   ], '这里的速度来自仿真，不是真机标定；二维模型没有表示平衡、摔倒和关节动力学。'),
 },
}

INK, MUTED = '#203d47', '#607380'
COLORS = ['#147c79', '#346ab0', '#7357a3', '#ad6c19']
exports = []
for task, languages in data.items():
    for language, (title, subtitle, cards, footer) in languages.items():
        regular = (FontProperties(family='DejaVu Sans') if language == 'EN' else
                   FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyh.ttc')))
        bold = (FontProperties(family='DejaVu Sans', weight='bold') if language == 'EN' else
                FontProperties(fname=str(Path.home() / '.local/share/fonts/winfonts/msyhbd.ttc')))
        fig = plt.figure(figsize=(16, 10.2), facecolor='#f3f6f8')
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set(xlim=(0, 16), ylim=(0, 10.2))
        ax.axis('off')
        texts = []
        def label(x, y, s, size, color=INK, weight=False, max_width=14.5):
            artist = ax.text(x, y, s, va='top', fontsize=size, color=color,
                            fontproperties=bold if weight else regular)
            texts.append((artist, max_width))
        label(.65, 9.65, title, 28, weight=True)
        label(.68, 8.98, subtitle, 14, MUTED)
        for i, item in enumerate(cards):
            x, y = (.65 if i % 2 == 0 else 8.15), (4.85 if i < 2 else 1.05)
            ax.add_patch(FancyBboxPatch((x, y), 7.2, 3.5,
                boxstyle='round,pad=0,rounding_size=0.16', facecolor='white',
                edgecolor='#dce4e9', linewidth=1))
            label(x+.3, y+3.18, item['title'], 19, COLORS[item['color']], True, 6.6)
            for j, row in enumerate(item['rows']):
                label(x+.31, y+2.55-j*.43, row, 14.2, max_width=6.58)
            label(x+.31, y+.42, item['source'], 9.5, MUTED, max_width=6.58)
        label(.72, .65, footer, 11.2, MUTED)
        # Fit long English source labels while keeping main parameter text large.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for artist, max_width in texts:
            width = artist.get_window_extent(renderer).width / fig.dpi
            if width > max_width:
                artist.set_fontsize(artist.get_fontsize()*max_width/width)
        fig.canvas.draw()
        stem = f'S{task}_Data_Sources_{language}'
        for ext in ['png', 'pdf']:
            target = HERE / f'{stem}.{ext}'
            fig.savefig(target, dpi=240, facecolor=fig.get_facecolor())
            exports.append(target.name)
        plt.close(fig)
        print(stem)

(HERE / 's3_data_sources_manifest.json').write_text(json.dumps({
    'scope': 'Source diagrams only; no simulation or controller changes',
    'languages': ['EN', 'ZH'], 'exports': exports,
    'source_documents': ['TDP_Project_Specification_2026_27.pdf, pp. 1, 3, 6 (App. A)',
                         'TDP_Kickoff_Slides_2026_27.pdf, p. 5'],
    'source_records': ['verification/development/navigation/motion-result.json',
                       'verification/development/navigation/skills-result.json'],
    'rule_scope': 'Course-linked reference and current partial implementation; not a full rules compliance claim',
    'model_assumptions_are_not_hardware_measurements': True,
    'source_sha256': {str(path.relative_to(WORKSPACE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [WORKSPACE/'TDP_Project_Specification_2026_27.pdf',
                     WORKSPACE/'TDP_Kickoff_Slides_2026_27.pdf',
                     REPO/'tools/soccer2d.py',
                     REPO/'Wenao/controllers/Utils/CourseSpecs.py',
                     REPO/'Wenao/controllers/Utils/MatchEngine.py',
                     REPO/'Wenao/protos/CourseGoal.proto',
                     REPO/'Wenao/motions/Shoot.motion',
                     REPO/'Wenao/motions/LongPass.motion',
                     REPO/'verification/development/navigation/motion-result.json',
                     REPO/'verification/development/navigation/skills-result.json']},
}, indent=2)+'\n')
