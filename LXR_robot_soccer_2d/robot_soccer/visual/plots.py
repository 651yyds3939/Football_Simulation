"""Static figures for the ball demo and the sensor demo."""
from __future__ import annotations

import math
from typing import List, Sequence

from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon, Rectangle

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..environment.world import world_init
from ..geometry import is_finite, norm
from .pitch_view import AMBER, BLUE, draw_pitch, team_colour

PATH_COLOURS = [(0.0, 0.447, 0.741), (0.85, 0.325, 0.098), (0.929, 0.694, 0.125),
                (0.494, 0.184, 0.556), (0.466, 0.674, 0.188), (0.301, 0.745, 0.933),
                (0.635, 0.078, 0.184)]


def figure_pitch_ball_demo(results: Sequence, pp: PitchParams, bp: BallParams,
                           new_figure=Figure) -> Figure:
    """The pitch with the path of every kick in demo_pitch_ball.

    new_figure makes the figure; pass matplotlib.pyplot.figure to show it in a window.
    """
    fig = new_figure(figsize=(10, 7.6), layout='constrained')
    ax = fig.add_subplot()
    draw_pitch(ax, pp)
    for robot in world_init(pp).robots:
        ax.add_patch(Circle(robot.pos, bp.robot_radius, facecolor=team_colour(robot.team),
                            edgecolor='black', zorder=3))
    handles = []
    for r, colour in zip(results, PATH_COLOURS):
        xs = [q[0] for q in r.path]
        ys = [q[1] for q in r.path]
        handles.append(ax.plot(xs, ys, '-', color=colour, linewidth=2, zorder=4)[0])
        ax.plot(xs[0], ys[0], 'o', markersize=7, markerfacecolor='white', markeredgecolor=colour,
                markeredgewidth=1.5, zorder=5)
        if r.event is not None:
            ax.plot(xs[-1], ys[-1], 'x', color=colour, markersize=12, markeredgewidth=2.5, zorder=5)
            ax.plot(*r.restart.pos, 's', markersize=10, markerfacecolor=colour, markeredgecolor='black',
                    zorder=5)
        else:
            ax.plot(xs[-1], ys[-1], 'o', markersize=7, markerfacecolor=colour, markeredgecolor='black',
                    zorder=5)
    fig.legend(handles, [r.name for r in results], loc='outside lower center', ncol=2)
    ax.set_title('Ball model demo: white circle = start, x = rule applied, square = restart position\n'
                 'filled circle = ball stopped; blue = team 1 (attacks +x), red = team 2')
    return fig


def figure_sensor_top_view(records: Sequence, world, sp, new_figure=Figure) -> Figure:
    """Top view: what robot 0 believes about the ball."""
    fig = new_figure(figsize=(8.5, 6.8), layout='constrained')
    ax = fig.add_subplot()
    ax.add_patch(Rectangle((-4.5, -3), 9, 6, fill=False, edgecolor='black'))
    true_line = ax.plot([r.ball[0] for r in records], [r.ball[1] for r in records], '-',
                        color=(0.7, 0.7, 0.7))[0]
    seen = [r.percept.ball_pos for r in records if r.percept.ball_visible]
    kept = [r.percept.ball_pos for r in records
            if not r.percept.ball_visible and is_finite(r.percept.ball_pos)]
    seen_dots = ax.plot([q[0] for q in seen], [q[1] for q in seen], '.', color=BLUE)[0]
    kept_dots = ax.plot([q[0] for q in kept], [q[1] for q in kept], '.', color=AMBER)[0]
    for robot in world.robots:
        ax.plot(*robot.pos, 'o', markersize=10, markerfacecolor=team_colour(robot.team),
                markeredgecolor='black')
    # Field of view of robot 0 at the end of the run
    last = records[-1]
    ax.add_patch(Polygon(view_wedge(world.robots[0].pos, last.heading + last.head_yaw, sp),
                         facecolor=BLUE, alpha=0.12, edgecolor='none'))
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)')
    ax.set_ylabel('y (m)')
    ax.set_title('Robot 0: what it believes about the ball')
    fig.legend([true_line, seen_dots, kept_dots],
               ['true ball path', 'estimate (seen)', 'estimate (remembered)'],
               loc='outside lower center', ncol=3)
    return fig


def figure_sensor_over_time(records: Sequence, new_figure=Figure) -> Figure:
    """Ball error, whether the ball is seen, and the head angle over time."""
    fig = new_figure(figsize=(8.5, 6.8), layout='constrained')
    axes = fig.subplots(3, 1, sharex=True)
    t = [r.t for r in records]
    errors: List[float] = []
    for r in records:
        p = r.percept.ball_pos
        errors.append(norm((p[0] - r.ball[0], p[1] - r.ball[1])) if is_finite(p) else math.nan)
    axes[0].plot(t, errors)
    axes[0].set_ylabel('ball error (m)')
    axes[0].set_title('Error of the ball estimate (gaps = no estimate)')
    axes[1].step(t, [float(r.percept.ball_visible) for r in records], where='post')
    axes[1].set_ylim(-0.1, 1.1)
    axes[1].set_ylabel('seen')
    axes[2].plot(t, [math.degrees(r.head_yaw) for r in records])
    axes[2].set_ylabel('head yaw (deg)')
    axes[2].set_xlabel('time (s)')
    for ax in axes:
        ax.grid(True)
    return fig


def view_wedge(position, gaze: float, sp, n: int = 30):
    """Corners of the camera's field of view, out to the ball detection range."""
    angles = [gaze - sp.fov_h / 2 + sp.fov_h * i / (n - 1) for i in range(n)]
    return [position] + [(position[0] + sp.range_ball * math.cos(a),
                          position[1] + sp.range_ball * math.sin(a)) for a in angles]
