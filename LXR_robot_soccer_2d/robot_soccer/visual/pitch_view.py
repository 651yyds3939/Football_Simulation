"""The pitch of Table 1, and the colours shared by every figure."""
from __future__ import annotations

from typing import Optional

from matplotlib.patches import Circle, Rectangle

from ..environment.pitch import PitchParams, goal_geometry

GREEN = (0.33, 0.62, 0.33)
BLUE = (0.0, 0.45, 0.74)      # team 1
RED = (0.85, 0.33, 0.10)      # team 2
AMBER = (0.93, 0.69, 0.13)    # remembered ball position
GREY = (0.6, 0.6, 0.6)
NET = (0.85, 0.85, 0.85)
LINE_WIDTH = 1.5


def team_colour(team: int):
    return BLUE if team == 1 else RED


def draw_pitch(ax, pp: Optional[PitchParams] = None) -> None:
    """Draw the carpet, lines, marks and goals into the axes."""
    pp = pp or PitchParams()
    half_l, half_w, border = pp.half_length, pp.half_width, pp.border_width
    line = dict(color='white', linewidth=LINE_WIDTH, zorder=1)
    outline = dict(fill=False, edgecolor='white', linewidth=LINE_WIDTH, zorder=1)

    # Carpet, including the border strip
    ax.add_patch(Rectangle((-half_l - border, -half_w - border), pp.length + 2 * border,
                           pp.width + 2 * border, facecolor=GREEN, edgecolor='none', zorder=0))

    # Touchlines and goal lines, halfway line, centre circle and mark
    ax.add_patch(Rectangle((-half_l, -half_w), pp.length, pp.width, **outline))
    ax.plot([0, 0], [-half_w, half_w], **line)
    ax.add_patch(Circle((0, 0), pp.centre_circle_d / 2, **outline))
    ax.plot([0], [0], marker='+', markersize=8, markeredgewidth=LINE_WIDTH, color='white', zorder=1)

    for s in (-1, 1):
        # Goal area (E x F) and penalty area (J x K), open towards the goal line
        for length, width in ((pp.goal_area_length, pp.goal_area_width),
                              (pp.penalty_area_length, pp.penalty_area_width)):
            ax.plot([s * half_l, s * (half_l - length), s * (half_l - length), s * half_l],
                    [-width / 2, -width / 2, width / 2, width / 2], **line)
        # Penalty mark (G from the goal line)
        ax.plot([s * (half_l - pp.penalty_mark_dist)], [0], marker='+', markersize=8,
                markeredgewidth=LINE_WIDTH, color='white', zorder=1)

    # Goals: nets and posts
    posts, nets = goal_geometry(pp)
    for x1, y1, x2, y2 in nets:
        ax.plot([x1, x2], [y1, y2], color=NET, linewidth=2, zorder=2)
    for post in posts:
        ax.add_patch(Circle(post, pp.post_radius, facecolor='white', edgecolor=(0.3, 0.3, 0.3), zorder=2))

    ax.set_xlim(-half_l - border, half_l + border)
    ax.set_ylim(-half_w - border, half_w + border)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)')
    ax.set_ylabel('y (m)')
