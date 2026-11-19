"""Export empty, scale-correct 2D pitch plans from the current CourseSpecs."""
from pathlib import Path
import hashlib
import importlib.util
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT/'2D_Shared_Policy_2026-11-11/backend/Wenao/controllers/Utils/CourseSpecs.py'
spec = importlib.util.spec_from_file_location('pitch_specs', SOURCE)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})
FIELD, BORDER, WHITE, INK, ACCENT = '#2b7657', '#174b3e', '#f3f6e7', '#203f45', '#166f70'


def pitch(ax):
    length, width, line = c.PITCH_LENGTH, c.PITCH_WIDTH, c.LINE_WIDTH
    ax.add_patch(Rectangle((-length/2-c.BORDER_WIDTH, -width/2-c.BORDER_WIDTH),
                           length+2*c.BORDER_WIDTH, width+2*c.BORDER_WIDTH,
                           facecolor=BORDER, edgecolor='none'))
    ax.add_patch(Rectangle((-length/2, -width/2), length, width, facecolor=FIELD, edgecolor='none'))
    for i in range(12):
        if i % 2:
            ax.add_patch(Rectangle((-length/2+i*length/12, -width/2), length/12, width,
                                   facecolor='white', edgecolor='none', alpha=.025))
    # Outermost edges are the configured pitch boundary; line paint lies inside.
    for x, y, w, h in [(-length/2, -width/2, length, line),
                       (-length/2, width/2-line, length, line),
                       (-length/2, -width/2, line, width),
                       (length/2-line, -width/2, line, width),
                       (-line/2, -width/2, line, width)]:
        ax.add_patch(Rectangle((x, y), w, h, facecolor=WHITE, edgecolor='none'))
    ax.add_patch(Circle((0, 0), c.CENTRE_CIRCLE_DIAMETER/2, facecolor=WHITE, edgecolor='none'))
    ax.add_patch(Circle((0, 0), c.CENTRE_CIRCLE_DIAMETER/2-line, facecolor=FIELD, edgecolor='none'))
    ax.add_patch(Circle((0, 0), line, facecolor=WHITE, edgecolor='none'))
    for sign in [-1, 1]:
        gx = sign*length/2
        for depth, span in [(c.PENALTY_AREA_LENGTH, c.PENALTY_AREA_WIDTH),
                            (c.GOAL_AREA_LENGTH, c.GOAL_AREA_WIDTH)]:
            x = gx if sign < 0 else gx-depth
            for xx, yy, w, h in [(x, -span/2, depth, line),
                                  (x, span/2-line, depth, line),
                                  (x+depth-line if sign < 0 else x, -span/2, line, span)]:
                ax.add_patch(Rectangle((xx, yy), w, h, facecolor=WHITE, edgecolor='none'))
        ax.add_patch(Circle((gx-sign*c.PENALTY_MARK_DISTANCE, 0), line,
                            facecolor=WHITE, edgecolor='none'))
        x = gx-c.GOAL_DEPTH if sign < 0 else gx
        ax.add_patch(Rectangle((x, -c.GOAL_WIDTH/2), c.GOAL_DEPTH, c.GOAL_WIDTH,
                               facecolor='#adc8bd', edgecolor=WHITE, linewidth=.8, alpha=.45))
        for xx in [x+i*.1 for i in range(1, 6)]:
            ax.plot([xx, xx], [-c.GOAL_WIDTH/2, c.GOAL_WIDTH/2], color=WHITE, lw=.35, alpha=.4)
        for i in range(1, 20):
            yy=-c.GOAL_WIDTH/2+i*c.GOAL_WIDTH/20
            ax.plot([x, x+c.GOAL_DEPTH], [yy, yy], color=WHITE, lw=.35, alpha=.4)
        # Goal opening is 2.6 m between inner post faces. Radius follows the local PROTO.
        for yy in [-c.GOAL_WIDTH/2-.05, c.GOAL_WIDTH/2+.05]:
            ax.add_patch(Circle((gx, yy), .05, facecolor=WHITE, edgecolor='none', zorder=4))
    ax.set_aspect('equal')
    ax.axis('off')


def horizontal(ax, x1, x2, y, label, extension_y=None, colour=INK):
    if extension_y is not None:
        for x in [x1, x2]:
            ax.plot([x, x], [extension_y, y+.03], color='#82999b', lw=.65)
    ax.annotate('', xy=(x1, y), xytext=(x2, y),
                arrowprops={'arrowstyle': '<->', 'color': colour, 'lw': 1})
    ax.text((x1+x2)/2, y+.11, label, ha='center', va='bottom', color=colour,
            fontsize=10, bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': 1.5})


def vertical(ax, y1, y2, x, label, extension_x=None, colour=INK):
    if extension_x is not None:
        for y in [y1, y2]:
            ax.plot([extension_x, x-.03], [y, y], color='#82999b', lw=.65)
    ax.annotate('', xy=(x, y1), xytext=(x, y2),
                arrowprops={'arrowstyle': '<->', 'color': colour, 'lw': 1})
    ax.text(x-.12, (y1+y2)/2, label, rotation=90, ha='right', va='center', color=colour,
            fontsize=10, bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': 1.5})


def save(fig, stem):
    for ext in ['png', 'svg', 'pdf']:
        fig.savefig(HERE/f'{stem}.{ext}', dpi=300, facecolor=fig.get_facecolor(),
                    metadata={'Creator': 'Robotics TDP pitch exporter'} if ext != 'svg' else None)
    plt.close(fig)


fig = plt.figure(figsize=(11, 8))
ax = fig.add_axes([0, 0, 1, 1])
pitch(ax)
ax.set_xlim(-5.5, 5.5)
ax.set_ylim(-4, 4)
save(fig, 'pitch_2d_clean')

fig = plt.figure(figsize=(16, 10), facecolor='white')
fig.text(.04, .945, 'Football pitch | 2D geometry', color=INK, size=24, weight='bold')
fig.text(.04, .908, 'Course dimensions in metres · Top view · No players or ball', color='#637d80', size=11)
ax = fig.add_axes([.025, .13, .72, .74])
pitch(ax)
ax.set_xlim(-6.55, 6.05)
ax.set_ylim(-4.75, 4.8)
horizontal(ax, -4.5, 4.5, 4.42, 'Pitch length 9.0 m', extension_y=3)
vertical(ax, -3, 3, -6.1, 'Pitch width 6.0 m', extension_x=-4.5)
horizontal(ax, -5.5, -4.5, -4.38, 'Border 1.0 m', extension_y=-3)
horizontal(ax, 4.5, 5.1, -4.38, 'Goal depth 0.6 m', extension_y=-1.3)
vertical(ax, -1.3, 1.3, 5.65, 'Opening 2.6 m', extension_x=4.5)
for label, point, target in [
    ('Penalty area\n2.0 × 5.0 m', (-1.7, 2.1), (-2.5, 2.1)),
    ('Goal area\n1.0 × 3.0 m', (-3.0, -.85), (-3.5, -.85)),
    ('Centre circle\nOuter diameter 1.5 m', (1.65, 1.15), (.52, .52)),
    ('Penalty mark\n1.5 m from goal line', (1.5, -1.8), (3, 0)),
]:
    ax.annotate(label, xy=target, xytext=point, ha='center', va='center', fontsize=9,
                color=INK, bbox={'boxstyle': 'round,pad=.4', 'fc': 'white', 'ec': '#d8e3df', 'alpha': .97},
                arrowprops={'arrowstyle': '-', 'color': '#edf3e9', 'lw': 1.0})
card = fig.add_axes([.775, .18, .2, .66])
card.axis('off')
card.text(0, 1, 'DIMENSION REGISTER', color=ACCENT, size=11, weight='bold', va='top')
rows = [('Pitch', '9.0 × 6.0 m'), ('Ground incl. border', '11.0 × 8.0 m'),
        ('Clear goal width', '2.6 m'), ('Clear goal height', '1.2 m*'),
        ('Goal depth', '0.6 m'), ('Goal area', '1.0 × 3.0 m'),
        ('Penalty area', '2.0 × 5.0 m'), ('Penalty mark distance', '1.5 m'),
        ('Centre circle diameter', '1.5 m'), ('Border', '1.0 m')]
for i, (name, value) in enumerate(rows):
    y = .91-i*.075
    card.text(0, y, name, color='#5f797b', size=9, va='top')
    card.text(1, y, value, color=INK, size=10, weight='bold', va='top', ha='right')
    card.plot([0, 1], [y-.045]*2, color='#e7eeea', lw=.7)
card.set_xlim(0, 1)
card.set_ylim(0, 1)
card.text(0, .13, '* Height is a 3D specification;\n  it is not visible in a top view.\n\nBall is not drawn.\nSpecified diameter: approx. 0.14 m.',
          color='#637d80', size=9, va='top', linespacing=1.6)
fig.text(.04, .065, 'Geometry source: current CourseSpecs.py. Pitch boundaries and centre-circle dimensions refer to outer line edges.',
         color='#637d80', size=9)
fig.text(.04, .04, 'Line width and post radius are modelling choices. This drawing checks geometry; it does not validate robot dynamics or sensing.',
         color='#637d80', size=9)
save(fig, 'pitch_2d_dimensions_en')

metadata = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'dimensions': {n: getattr(c, n) for n in dir(c) if n.isupper() and isinstance(getattr(c, n), (int, float))},
            'goal_post_radius': .05, 'goal_post_radius_source': 'CourseGoal.proto',
            'exports': ['pitch_2d_clean.png', 'pitch_2d_clean.svg', 'pitch_2d_clean.pdf',
                        'pitch_2d_dimensions_en.png', 'pitch_2d_dimensions_en.svg', 'pitch_2d_dimensions_en.pdf']}
(HERE/'geometry_manifest.json').write_text(json.dumps(metadata, indent=2)+'\n')
print('Exported clean and dimensioned pitch plans in PNG, SVG and PDF:', HERE)
