"""What a robot can work out about a rolling ball."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..environment.ball import BallParams
from ..geometry import Vec2, norm
from ..robot.motion import RobotParams
from ..sensors.percept import Percept


def ball_path(pos: Vec2, vel: Vec2, times: Sequence[float], bp: BallParams):
    """Predict a rolling ball with the ball model's rolling resistance.

    Returns (positions, speeds, t_stop, d_stop): one position and speed per
    time, when the ball stops (s) and how far it rolls (m). The ball keeps its
    direction and slows down at roll_decel + drag * speed, the same law as
    ball_step. Bounces are not predicted.
    """
    v0 = norm(vel)
    c, b = bp.roll_decel, bp.drag
    if v0 < 1e-12:
        return [pos for _ in times], [0.0 for _ in times], 0.0, 0.0
    ux, uy = vel[0] / v0, vel[1] / v0
    if b > 0:
        t_stop = math.log(1 + b * v0 / c) / b

        def dist(t):
            return (v0 + c / b) * (1 - math.exp(-b * t)) / b - c / b * t

        def speed_at(t):
            return max(0.0, (v0 + c / b) * math.exp(-b * t) - c / b)
    else:
        t_stop = v0 / c

        def dist(t):
            return v0 * t - c * t * t / 2

        def speed_at(t):
            return max(0.0, v0 - c * t)

    clipped = [min(t, t_stop) for t in times]
    positions = [(pos[0] + dist(t) * ux, pos[1] + dist(t) * uy) for t in clipped]
    return positions, [speed_at(t) for t in clipped], t_stop, dist(t_stop)


@dataclass
class BallTracker:
    """Recent sightings of the ball."""
    t: List[float] = field(default_factory=list)
    pos: List[Vec2] = field(default_factory=list)


def track_ball(p: Percept, tr: Optional[BallTracker], bp: BallParams) -> Tuple[Vec2, BallTracker]:
    """Estimate the ball's velocity from the robot's recent images.

    Returns (velocity, tracker); velocity is (nan, nan) with fewer than 3
    recent sightings. A straight line is fitted to the positions of the last
    0.8 s; its slope is the velocity at the middle of that window, and the
    rolling resistance then slows it down to the time of the latest sighting.
    Right after a kick the estimate takes a few images to catch up.
    """
    window = 0.8    # s (design choice) longer = smoother, but slower to notice a kick

    tr = tr if tr is not None else BallTracker()
    if p.ball_visible and (not tr.t or p.t_measured > tr.t[-1]):
        tr.t.append(p.t_measured)
        tr.pos.append(p.ball_pos)
    keep = [i for i, t in enumerate(tr.t) if t >= p.t_measured - window]
    tr.t = [tr.t[i] for i in keep]
    tr.pos = [tr.pos[i] for i in keep]

    no_estimate = (math.nan, math.nan)
    n = len(tr.t)
    if n < 3:
        return no_estimate, tr
    tc = sum(tr.t) / n
    dts = [t - tc for t in tr.t]
    s2 = sum(d * d for d in dts)
    if s2 < 1e-9:
        return no_estimate, tr
    mx = sum(q[0] for q in tr.pos) / n
    my = sum(q[1] for q in tr.pos) / n
    v_mid = (sum(d * (q[0] - mx) for d, q in zip(dts, tr.pos)) / s2,
             sum(d * (q[1] - my) for d, q in zip(dts, tr.pos)) / s2)    # least-squares slope
    speed_mid = norm(v_mid)
    if speed_mid <= 1e-12:
        return (0.0, 0.0), tr
    _, speeds, _, _ = ball_path((0.0, 0.0), v_mid, [tr.t[-1] - tc], bp)
    return (v_mid[0] / speed_mid * speeds[0], v_mid[1] / speed_mid * speeds[0]), tr


def intercept_point(ball_pos: Vec2, ball_vel: Vec2, robot_pos: Vec2, rp: RobotParams,
                    bp: BallParams) -> Tuple[Vec2, float]:
    """The first point on a rolling ball's path that the robot can reach in time.

    Returns (target, t_meet). The robot's time to reach a point is its distance
    at full forward speed plus a margin for turning and speeding up. If it
    cannot get to any point before the ball, target is where the ball stops.
    """
    margin = 0.3    # s (design choice) for turning and accelerating
    step = 0.05     # s between checked points on the path

    _, _, t_stop, _ = ball_path(ball_pos, ball_vel, [0.0], bp)
    n = int(math.floor((t_stop + step) / step + 1e-10)) + 1
    times = [i * step for i in range(n)]
    points, _, _, _ = ball_path(ball_pos, ball_vel, times, bp)
    for t, q in zip(times, points):
        if norm((q[0] - robot_pos[0], q[1] - robot_pos[1])) / rp.v_forward + margin <= t:
            return q, min(t, t_stop)
    return points[-1], min(times[-1], t_stop)    # cannot get there first: go where it stops


def pass_speed(dist: float, bp: BallParams) -> Tuple[float, bool]:
    """Kick speed that makes the ball roll a given distance and stop.

    Returns (speed, reachable); reachable is False if even the fastest kick
    stops short of dist, and the speed is then kick_speed_max.
    """
    def rolled(speed):
        return ball_path((0.0, 0.0), (speed, 0.0), [0.0], bp)[3]

    if dist > rolled(bp.kick_speed_max):
        return bp.kick_speed_max, False
    lo, hi = 0.0, bp.kick_speed_max
    for _ in range(50):                  # bisection: rolling distance grows with speed
        mid = (lo + hi) / 2
        if rolled(mid) < dist:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2, True
