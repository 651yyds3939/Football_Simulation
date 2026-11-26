"""Animations: played in a window, or saved as a GIF."""
from __future__ import annotations

import math
import time
from typing import List, Optional, Sequence

import matplotlib

from ..environment.pitch import PitchParams
from ..geometry import is_finite
from .pitch_view import AMBER, BLUE, GREY, RED, draw_pitch, team_colour
from .plots import view_wedge

GIF_FRAME_SECONDS = 0.1    # simulated seconds per GIF frame
SCREEN_FPS = 25


def _pyplot(on_screen: bool):
    """pyplot with a window on screen, or without any window when only saving."""
    if not on_screen:
        matplotlib.use('Agg', force=True)
    import matplotlib.pyplot as plt
    return plt


def _gif_writer(fig, path: str, speed: float):
    from matplotlib.animation import PillowWriter
    writer = PillowWriter(fps=speed / GIF_FRAME_SECONDS)
    writer.setup(fig, path, dpi=100)
    return writer


def _freeze_layout(fig) -> None:
    """Fix the layout after the first draw, so that every frame draws quickly."""
    fig.canvas.draw()
    fig.set_layout_engine('none')


def animate_sensor(records: Sequence, world, sp, speed: float = 1.0, save: Optional[str] = None,
                   hold: bool = True, pp: Optional[PitchParams] = None) -> int:
    """Animate what robot 0 sees and believes; returns the number of frames shown.

    Filled circles are the truth; the other markers are robot 0's percept. The
    wedge is the view of the image behind the current percept (an image arrives
    sp.latency seconds after it is taken): blue if the ball is in it, grey if not.
    """
    from matplotlib.patches import Circle, Patch, Polygon, Rectangle

    plt = _pyplot(save is None)
    realistic = sp.mode != 'perfect'
    dt = records[1].t - records[0].t
    me = world.robots[0]

    fig = plt.figure('Sensor animation', figsize=(9, 7.6), layout='constrained')
    ax = fig.add_subplot()
    ax.add_patch(Rectangle((-4.5, -3), 9, 6, fill=False, edgecolor='black'))
    ax.plot([0, 0], [-3, 3], 'k-', linewidth=1)
    wedge = Polygon([(0, 0), (0, 0), (0, 0)], facecolor=GREY, alpha=0.15, edgecolor='none', visible=False)
    ax.add_patch(wedge)
    trail, = ax.plot([], [], '-', color=(0.8, 0.8, 0.8))
    for robot in world.robots:
        ax.add_patch(Circle(robot.pos, sp.robot_radius, facecolor=team_colour(robot.team),
                            edgecolor='black', zorder=3))
    body, = ax.plot([], [], 'k-', linewidth=2, zorder=4)
    error, = ax.plot([], [], '--', color=(0.3, 0.3, 0.3), zorder=4)
    ball, = ax.plot([], [], 'o', markersize=9, markerfacecolor='white', markeredgecolor='black',
                    markeredgewidth=1.5, zorder=5)
    seen, = ax.plot([], [], 'o', markersize=7, color=BLUE, zorder=6)
    kept, = ax.plot([], [], 'o', markersize=7, color=AMBER, zorder=6)
    own, = ax.plot([], [], 'o', markersize=8, markerfacecolor='none', markeredgecolor=(0, 0.2, 0.4),
                   markeredgewidth=1.5, zorder=6)
    others, = ax.plot([], [], 'x', markersize=9, markeredgewidth=1.5, color='black', zorder=6)
    team1, = ax.plot([], [], 'o', markersize=9, markerfacecolor=BLUE, markeredgecolor='black')
    team2, = ax.plot([], [], 'o', markersize=9, markerfacecolor=RED, markeredgecolor='black')
    ax.set_xlim(-5.5, 5)
    ax.set_ylim(-4.2, 4.2)
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)')
    ax.set_ylabel('y (m)')
    title = ax.set_title(' \n ')
    view_key = Patch(facecolor=BLUE, alpha=0.3)    # the wedge itself starts hidden
    fig.legend([team1, team2, view_key, trail, ball, seen, kept, error, own, others],
               ['robot, team 1', 'robot, team 2', 'field of view (latest image)', 'true ball path',
                'true ball', 'ball estimate (seen)', 'ball estimate (remembered)', 'estimate error',
                "robot 0's own position estimate", 'robots seen (estimates)'],
               loc='outside lower center', ncol=3)

    def draw(i: int) -> None:
        r = records[i]
        p = r.percept
        body.set_data([me.pos[0], me.pos[0] + 0.35 * math.cos(r.heading)],
                      [me.pos[1], me.pos[1] + 0.35 * math.sin(r.heading)])
        ball.set_data([r.ball[0]], [r.ball[1]])
        trail.set_data([q.ball[0] for q in records[:i + 1]], [q.ball[1] for q in records[:i + 1]])
        if realistic and math.isfinite(p.t_measured):
            image = records[round(p.t_measured / dt)]
            wedge.set_xy(view_wedge(me.pos, image.heading + p.head_yaw, sp))
            wedge.set_facecolor(BLUE if p.ball_visible else GREY)
            wedge.set_alpha(0.15)
            wedge.set_visible(True)
        has_estimate = is_finite(p.ball_pos)
        seen.set_data([p.ball_pos[0]] if p.ball_visible else [], [p.ball_pos[1]] if p.ball_visible else [])
        remembered = has_estimate and not p.ball_visible
        kept.set_data([p.ball_pos[0]] if remembered else [], [p.ball_pos[1]] if remembered else [])
        error.set_data([p.ball_pos[0], r.ball[0]] if has_estimate else [],
                       [p.ball_pos[1], r.ball[1]] if has_estimate else [])
        own.set_data([p.self_pos[0]], [p.self_pos[1]])
        robots_seen = p.mates + p.opponents
        others.set_data([q[0] for q in robots_seen], [q[1] for q in robots_seen])

        err = math.hypot(p.ball_pos[0] - r.ball[0], p.ball_pos[1] - r.ball[1]) if has_estimate else math.nan
        if p.ball_visible:
            status = f'ball seen: error {err:.2f} m, information {r.t - p.t_measured:.2f} s old'
        elif has_estimate:
            status = f'ball remembered: last seen {r.t - p.ball_last_seen:.1f} s ago, error {err:.2f} m'
        else:
            status = 'no ball estimate'
        head = (f'head yaw in latest image {math.degrees(p.head_yaw):+4.0f} deg' if realistic
                else '(sees everything)')
        title.set_text(f't = {r.t:4.1f} s    mode: {sp.mode}    {head}\n{status}')

    _freeze_layout(fig)
    shown = 0
    if save is not None:
        writer = _gif_writer(fig, save, speed)
        for i in range(0, len(records), max(1, round(GIF_FRAME_SECONDS / dt))):
            draw(i)
            writer.grab_frame()
            shown += 1
        writer.finish()
        plt.close(fig)
        return shown

    stride = max(1, round(max(dt, speed / SCREEN_FPS) / dt))
    plt.show(block=False)
    started = time.monotonic()
    for i in range(0, len(records), stride):
        if not plt.fignum_exists(fig.number):
            return shown                      # window closed: stop
        draw(i)
        fig.canvas.draw_idle()
        shown += 1
        plt.pause(max(0.001, records[i].t / speed - (time.monotonic() - started)))
    if hold and plt.fignum_exists(fig.number):
        plt.show()
    return shown


class DrillViewer:
    """Shows the striker v goalkeeper drill; pass it to the drill as on_step.

    Returns False from a step when the window has been closed, which stops the drill.
    """

    def __init__(self, n_attackers: int, sensors: Sequence, rp, pp: Optional[PitchParams] = None,
                 speed: float = 1.0, save: Optional[str] = None):
        from matplotlib.patches import Circle, Patch, Polygon

        self.speed = speed
        self.saving = save is not None
        self.plt = _pyplot(not self.saving)
        self.sensors = sensors
        self.rp = rp
        self.n_attackers = n_attackers
        self.frame_dt = GIF_FRAME_SECONDS if self.saving else max(0.02, speed / SCREEN_FPS)
        self.trial = 0
        self.next_frame = 0.0
        self.started = time.monotonic()
        self.frames = 0

        n = n_attackers + 1
        colours = [BLUE] * n_attackers + [RED]
        self.fig = self.plt.figure('Striker v goalkeeper', figsize=(10, 7.6), layout='constrained')
        ax = self.fig.add_subplot()
        draw_pitch(ax, pp or PitchParams())
        self.wedges: List = []
        self.bodies: List = []
        self.dirs: List = []
        self.estimates: List = []
        for colour in colours:
            wedge = Polygon([(0, 0), (0, 0), (0, 0)], facecolor=colour, alpha=0.15, edgecolor='none',
                            visible=False, zorder=2.5)
            ax.add_patch(wedge)
            self.wedges.append(wedge)
            body = Circle((0, 0), rp.radius, facecolor=colour, edgecolor='black', zorder=4)
            ax.add_patch(body)
            self.bodies.append(body)
            self.dirs.append(ax.plot([], [], 'k-', linewidth=2, zorder=5)[0])
            self.estimates.append(ax.plot([], [], 'o', markersize=6, markerfacecolor=colour,
                                          markeredgecolor='white', zorder=7)[0])
        self.ball, = ax.plot([], [], 'o', markersize=9, markerfacecolor='white', markeredgecolor='black',
                             markeredgewidth=1.5, zorder=6)
        self.title = ax.set_title(' \n ')
        who = 'the striker' if n_attackers == 1 else 'each attacker'
        self.fig.legend([self.ball, self.estimates[0], self.estimates[-1],
                         Patch(facecolor=BLUE, alpha=0.3), Patch(facecolor=RED, alpha=0.3)],
                        ['ball', f'where {who} thinks the ball is', 'where the keeper thinks the ball is',
                         "attacker's view (latest image)", "keeper's view (latest image)"],
                        loc='outside lower center', ncol=3)
        _freeze_layout(self.fig)
        self.writer = _gif_writer(self.fig, save, speed) if self.saving else None
        if not self.saving:
            self.plt.show(block=False)

    def __call__(self, frame) -> bool:
        if not self.saving and not self.plt.fignum_exists(self.fig.number):
            return False
        if frame.trial != self.trial:
            self.trial = frame.trial
            self.next_frame = 0.0
            self.started = time.monotonic()
        if frame.t < self.next_frame - 1e-9 and not frame.done:
            return True
        self.next_frame += self.frame_dt
        self._draw(frame)
        self.frames += 1
        if self.saving:
            for _ in range(int(1 / GIF_FRAME_SECONDS * self.speed) if frame.done else 1):
                self.writer.grab_frame()         # show the result for a moment
        else:
            self.fig.canvas.draw_idle()
            wait = frame.t / self.speed - (time.monotonic() - self.started)
            self.plt.pause(1.0 if frame.done else max(0.001, wait))
        return True

    def _draw(self, frame) -> None:
        for k, robot in enumerate(frame.robots):
            self.bodies[k].center = robot.pos
            self.dirs[k].set_data([robot.pos[0], robot.pos[0] + 0.3 * math.cos(robot.heading)],
                                  [robot.pos[1], robot.pos[1] + 0.3 * math.sin(robot.heading)])
            p = frame.percepts[k]
            self.wedges[k].set_visible(False)
            if self.sensors[k].mode != 'perfect' and math.isfinite(p.t_measured):
                index = round(p.t_measured / frame.dt)
                if index < len(frame.history):
                    x, y, heading = frame.history[index][k]
                    self.wedges[k].set_xy(view_wedge((x, y), heading + p.head_yaw, self.sensors[k], 20))
                    self.wedges[k].set_visible(True)
            has_estimate = is_finite(p.ball_pos)
            self.estimates[k].set_data([p.ball_pos[0]] if has_estimate else [],
                                       [p.ball_pos[1]] if has_estimate else [])
        self.ball.set_data([frame.ball_pos[0]], [frame.ball_pos[1]])

        c = frame.counts
        line1 = (f"Attempt {frame.trial} of {frame.n_trials}    t = {frame.t:4.1f} s    goals {c['goal']}   "
                 f"saved {c['saved']}   missed {c['missed']}   timeout {c['timeout']}")
        if self.n_attackers > 1:
            line1 += f'    passes {frame.passes} (received {frame.received})'
        line2 = f'Result: {frame.outcome.upper()}' if frame.done else '      '.join(frame.labels)
        self.title.set_text(f'{line1}\n{line2}')

    def finish(self, hold: bool = True) -> None:
        """Finish the GIF, or keep the window open until the user closes it."""
        if self.saving:
            self.writer.finish()
            self.plt.close(self.fig)
        elif hold and self.plt.fignum_exists(self.fig.number):
            self.plt.show()
