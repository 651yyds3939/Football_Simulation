"""Illustrate the existing ball and planar robot models without changing them."""
from pathlib import Path
from dataclasses import asdict
import hashlib
import json
import math
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT/'2D_Shared_Policy_2026-11-11/backend/tools'))
from soccer2d import Model, Simulation
from Utils.CourseSpecs import BALL_RADIUS

INK, TEAL, MUTED, GOLD = '#203f45', '#166f70', '#637d80', '#c68826'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})
model = Model()


def header(fig, title, subtitle):
    fig.text(.05, .94, title, color=INK, weight='bold', size=23)
    fig.text(.05, .895, subtitle, color=MUTED, size=11)


def save(fig, stem):
    for ext in ['png', 'svg', 'pdf']:
        fig.savefig(HERE/f'{stem}.{ext}', dpi=300, facecolor='white')
    plt.close(fig)


# The free-rolling data use the actual existing integration routine. Other
# bodies are away from the path; there are no policies or artificial kicks.
sim = Simulation(candidate='baseline', model=model)
for p in sim.players.values():
    p['position'] = [3, 2.5, .334]
sim.ball = [0, 0, BALL_RADIUS]
v0 = .5
sim.velocity = [v0, 0, 0]
times, positions, speeds = [0.], [0.], [v0]
for step in range(1, 11):
    sim._roll_ball()
    times.append(step*model.dt)
    positions.append(sim.ball[0])
    speeds.append(math.hypot(*sim.velocity[:2]))
times, positions, speeds = map(np.array, (times, positions, speeds))
a = model.rolling_deceleration
stop_time, stop_distance = v0/a, v0*v0/(2*a)
capped = np.minimum(times, stop_time)
expected_position = v0*capped-.5*a*capped*capped
max_error = float(np.max(np.abs(positions-expected_position)))
assert max_error < 1e-9

fig = plt.figure(figsize=(14, 8))
header(fig, 'Ball motion model | 2D',
       'Ground-plane rolling, simplified contact and kick impulses · Owner: E')
ax = fig.add_axes([.05, .42, .43, .4])
ax.add_patch(Rectangle((-.25, -.27), 1.1, .64, fc='#edf4ef', ec='#dce7df'))
ax.add_patch(Circle((0, 0), BALL_RADIUS, fc='white', ec=INK, lw=1.5))
ax.add_patch(Circle((0, 0), BALL_RADIUS*.28, fc=INK, ec='none'))
ax.annotate('', xy=(.62, 0), xytext=(.09, 0), arrowprops={'arrowstyle': '->', 'color': TEAL, 'lw': 2.4})
ax.text(.34, .065, 'Velocity v', ha='center', color=TEAL, size=12)
ax.annotate('', xy=(-.19, -.13), xytext=(.38, -.13), arrowprops={'arrowstyle': '->', 'color': GOLD, 'lw': 2})
ax.text(.12, -.21, 'Rolling deceleration opposes motion', ha='center', color=GOLD, size=10)
ax.text(0, .19, 'Ball diameter ≈ 0.14 m', ha='center', color=INK, size=11)
ax.text(.03, .115, '(x, y)', color=INK, size=10)
ax.set_xlim(-.3, .9)
ax.set_ylim(-.32, .42)
ax.set_aspect('equal')
ax.axis('off')
fig.text(.055, .39, 'STATE AND ASSUMPTIONS', color=TEAL, weight='bold', size=11)
fig.text(.055, .34, r'$\mathbf{s}_{ball} = (x, y, v_x, v_y)$', color=INK, size=15)
fig.text(.055, .285, r'$\dot{\mathbf{p}}=\mathbf{v},\quad\dot{\mathbf{v}}=-a\,\mathbf{v}/\|\mathbf{v}\|$  until stopped',
         color=INK, size=13)
fig.text(.055, .235, f'Example: v₀ = {v0:.2f} m/s; a = {a:.2f} m/s² (assumed).', color=MUTED, size=11)
fig.text(.055, .19, f'Expected stop: {stop_time:.3f} s; travel: {stop_distance:.3f} m.', color=INK, size=11)
fig.text(.055, .135, 'Schematic arrows show direction; their lengths are illustrative.', color=MUTED, size=9)

dense = np.linspace(0, 2, 400)
tc = np.minimum(dense, stop_time)
for bounds, ylabel, ref, actual in [([.58, .54, .36, .26], 'Distance travelled (m)',
                                    v0*tc-.5*a*tc*tc, positions),
                                   ([.58, .18, .36, .26], 'Speed (m/s)',
                                    np.maximum(0, v0-a*dense), speeds)]:
    chart = fig.add_axes(bounds)
    chart.plot(dense, ref, color='#9daeb0', lw=1.4, ls='--', label='Constant-deceleration reference')
    chart.plot(times, actual, color=TEAL, marker='o', ms=4, lw=1.5, label='Existing 2D model samples')
    chart.axvline(stop_time, color=GOLD, lw=.9, alpha=.8)
    chart.set(xlim=(0, 2), xlabel='Time (s)', ylabel=ylabel)
    chart.grid(alpha=.16)
    if ylabel.startswith('Distance'):
        chart.set_title('Free-rolling example (no contacts)', loc='left', color=INK, size=12, pad=10)
        chart.legend(frameon=False, fontsize=8, loc='lower right')
fig.text(.05, .055, 'Source: existing soccer2d.py. This is a model consistency example, not physical friction calibration or hardware validation.',
         color=MUTED, size=9)
save(fig, 'S3_2_ball_model_2d_en')

fig = plt.figure(figsize=(14, 8))
header(fig, 'Robot motion model | 2D',
       'Planar pose, direction-dependent velocity and action duration · Owner: E')
ax = fig.add_axes([.045, .38, .45, .46])
ax.set_xlim(-.8, .9)
ax.set_ylim(-.7, .85)
ax.set_aspect('equal')
ax.axis('off')
ax.annotate('', xy=(.82, -.55), xytext=(-.65, -.55), arrowprops={'arrowstyle': '->', 'color': '#8fa6a7', 'lw': 1.4})
ax.annotate('', xy=(-.65, .72), xytext=(-.65, -.55), arrowprops={'arrowstyle': '->', 'color': '#8fa6a7', 'lw': 1.4})
ax.text(.82, -.59, 'World x', color=MUTED, ha='right')
ax.text(-.72, .74, 'World y', color=MUTED)
theta = math.radians(35)
ax.add_patch(Circle((0, 0), model.robot_radius, fc='#dcecea', ec=TEAL, lw=2))
ax.plot([0], [0], 'o', color=TEAL, ms=4)
ax.text(-.035, -.235, 'Robot pose (x, y, θ)', ha='center', color=INK, size=11)
ax.annotate('', xy=(.69*math.cos(theta), .69*math.sin(theta)), xytext=(0, 0),
            arrowprops={'arrowstyle': '->', 'color': TEAL, 'lw': 2.3})
ax.text(.59, .4, 'Forward v_f', color=TEAL, size=11)
ax.annotate('', xy=(-.43*math.sin(theta), .43*math.cos(theta)), xytext=(0, 0),
            arrowprops={'arrowstyle': '->', 'color': GOLD, 'lw': 2.1})
ax.text(-.5, .41, 'Lateral v_l', color=GOLD, size=11)
ax.plot([0, .36], [0, 0], color='#91a6a5', lw=1, ls='--')
ax.add_patch(Arc((0, 0), .56, .56, theta1=0, theta2=35, color=INK, lw=1.2))
ax.text(.29, .075, 'θ', color=INK, size=12)
ax.annotate('r = 0.15 m\n(disc assumption)', xy=(-.15, 0), xytext=(-.58, -.15),
            color=MUTED, size=9, arrowprops={'arrowstyle': '-', 'color': MUTED})

fig.text(.055, .34, 'PLANAR KINEMATICS', color=TEAL, size=11, weight='bold')
fig.text(.055, .28, r'$\dot{x}=v_f\cos\theta-v_l\sin\theta$', color=INK, size=14)
fig.text(.055, .225, r'$\dot{y}=v_f\sin\theta+v_l\cos\theta$', color=INK, size=14)
fig.text(.055, .17, r'$\dot{\theta}=\omega$', color=INK, size=14)
card = fig.add_axes([.57, .27, .37, .55])
card.axis('off')
card.set(xlim=(0, 1), ylim=(0, 1))
card.text(0, 1, 'CURRENT MODEL PARAMETERS', va='top', size=11, weight='bold', color=TEAL)
rows = [('Forward speed', f'{model.walk_speed:.5f} m/s'),
        ('Backward speed', f'{model.back_speed:.5f} m/s'),
        ('Left / right side-step', f'{model.left_speed:.5f} / {model.right_speed:.5f} m/s'),
        ('Left turn rate', f'{math.degrees(model.left_turn):.2f} deg/s'),
        ('Right turn rate', f'{math.degrees(model.right_turn):.2f} deg/s'),
        ('Shot duration', f'{model.shot_seconds:.3f} s'),
        ('Pass duration', f'{model.pass_seconds:.3f} s')]
for i, (label, value) in enumerate(rows):
    y = .87-i*.115
    card.text(0, y, label, color=MUTED, size=10, va='top')
    card.text(1, y-.037, value, color=INK, size=11, weight='bold', ha='right', va='top')
    card.plot([0, 1], [y-.08]*2, color='#e5ece9', lw=.8)
fig.text(.57, .21, 'Motion rates: existing isolated Webots measurements.\nAction durations: current motion assets. Disc radius: assumption.',
         color=MUTED, size=10, linespacing=1.6)
fig.text(.05, .07, 'No joint dynamics, balance or falls are represented. These are not calibrated NAO6 hardware parameters.', color=MUTED, size=10)
fig.text(.05, .04, 'Source: current soccer2d.py Model. Vector lengths in the schematic indicate direction, not measured velocity magnitude.', color=MUTED, size=9)
save(fig, 'S3_3_robot_model_2d_en')

source = ROOT/'2D_Shared_Policy_2026-11-11/backend/tools/soccer2d.py'
report = {'source': str(source.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'model': asdict(model), 'ball_example': {'v0': v0, 'time': times.tolist(),
           'distance': positions.tolist(), 'speed': speeds.tolist(), 'analytic_stop_seconds': stop_time,
           'analytic_stop_metres': stop_distance, 'max_position_error_metres': max_error,
           'physical_calibration': False}, 'robot_figure': 'Schematic of existing planar approximation; not new model validation',
          'controller_modified': False}
(HERE/'motion_models_manifest.json').write_text(json.dumps(report, indent=2)+'\n')
print('Exported S3.2 and S3.3 diagrams (PNG/SVG/PDF). Ball reference error:', max_error)
