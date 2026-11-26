"""Top-down replay of a 4 v 4 match."""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle

from ..robot.motion import RobotParams
from ..simulations.match import PLAYERS_PER_TEAM, REPLAY_INTERVAL, ROLES, MatchFrame
from .pitch_view import draw_pitch, team_colour


def show_match(frames: list[MatchFrame]) -> None:
    fig, ax = plt.subplots(figsize=(10, 7), layout='constrained')
    draw_pitch(ax)
    heading = ax.set_title('')
    radius = RobotParams().radius
    bodies, directions, labels = [], [], []
    for k, (pos, _) in enumerate(frames[0].poses):
        team = k // PLAYERS_PER_TEAM + 1
        body = Circle(pos, radius, facecolor=team_colour(team), edgecolor='black', zorder=4)
        ax.add_patch(body)
        bodies.append(body)
        directions.append(ax.plot([], [], color='black', lw=1, zorder=5)[0])
        labels.append(ax.text(*pos, ROLES[k % PLAYERS_PER_TEAM], ha='center', va='top', fontsize=8))
    ball, = ax.plot([], [], 'o', ms=6, mfc='white', mec='black', zorder=6)

    def draw(frame: MatchFrame) -> None:
        blue, orange = frame.score
        heading.set_text(f'{frame.time:5.1f} s  |  Blue {blue}–{orange} Orange')
        ball.set_data([frame.ball[0]], [frame.ball[1]])
        for k, ((x, y), angle) in enumerate(frame.poses):
            bodies[k].center = (x, y)
            directions[k].set_data([x, x + 0.24 * math.cos(angle)], [y, y + 0.24 * math.sin(angle)])
            labels[k].set_position((x, y - radius - 0.05))

    replay = FuncAnimation(fig, draw, frames=frames, interval=REPLAY_INTERVAL * 1000,
                           repeat=False, cache_frame_data=False)
    plt.show()
