"""Ball model: rolling, collisions and kicks.

Values marked [CHECK] are placeholders: measure them or find a source, and
write the source next to each one.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional, Sequence

from ..geometry import Vec2, dot, norm, wrap_angle
from .pitch import PitchParams, goal_geometry


@dataclass(frozen=True)
class BallParams:
    # Size (Project Specification: like a FIFA size 1 ball, circumference 45 cm)
    radius: float = 0.45 / (2 * math.pi)  # m, about 0.0716 (diameter about 14 cm)

    # Rolling on the carpet: deceleration = roll_decel + drag * speed
    roll_decel: float = 0.6       # m/s^2 [CHECK] constant rolling resistance
    drag: float = 0.2             # 1/s   [CHECK] part that grows with speed
    v_stop: float = 0.01          # m/s, slower than this counts as stopped (numerical)

    # Collisions: coefficient of restitution (0 = stops dead, 1 = no energy lost)
    e_robot: float = 0.3          # [CHECK] ball against a robot's legs and feet
    e_post: float = 0.6           # [CHECK] ball against a goal post
    e_net: float = 0.1            # [CHECK] ball against the goal net

    # Robots are circles for ball contact: half of the larger body dimension,
    # 311 mm, which the NAO6 datasheet calls depth (width is 275 mm)
    robot_radius: float = 0.155   # m

    # Kick
    kick_reach: float = 0.10                  # m [CHECK] foot reach beyond the body circle
    kick_cone: float = 90 * math.pi / 180     # rad [CHECK] ball within +-45 deg of the heading
    kick_dir_max: float = 45 * math.pi / 180  # rad [CHECK] widest kick direction from the heading
    kick_speed_max: float = 2.0               # m/s [CHECK] fastest NAO6 kick
    kick_sig_dir: float = 5 * math.pi / 180   # rad [CHECK] kick direction noise (std)
    kick_sig_speed: float = 0.10              # [CHECK] kick speed noise, fraction of speed (std)


@dataclass
class Ball:
    pos: Vec2 = (0.0, 0.0)
    vel: Vec2 = (0.0, 0.0)
    last_touch_team: int = 0                  # 0 = nobody since the last restart
    last_touch_robot: Optional[int] = None    # index into world.robots


def ball_step(ball: Ball, robots: Sequence, pp: PitchParams, bp: BallParams, dt: float) -> None:
    """Move the ball for one time step.

    The ball rolls on the ground (2D) and slows down from rolling resistance.
    It bounces off robots, goal posts and goal nets; a walking robot pushes it
    along (dribbling). Whether it has crossed a line is decided by referee_step.
    """
    # Sub-steps short enough (half a ball radius) that the ball cannot jump
    # through a post or a net in one step.
    n_sub = max(1, math.ceil(norm(ball.vel) * dt / (0.5 * bp.radius)))
    h = dt / n_sub
    posts, nets = goal_geometry(pp)

    for _ in range(n_sub):
        # Rolling resistance: slows the ball down, never reverses it
        speed = norm(ball.vel)
        if speed > 0:
            dv = (bp.roll_decel + bp.drag * speed) * h
            if dv >= speed or speed < bp.v_stop:
                ball.vel = (0.0, 0.0)
            else:
                factor = 1 - dv / speed
                ball.vel = (ball.vel[0] * factor, ball.vel[1] * factor)
        ball.pos = (ball.pos[0] + ball.vel[0] * h, ball.pos[1] + ball.vel[1] * h)

        # Robots: circles that may be moving
        for k, robot in enumerate(robots):
            if _hit_circle(ball, robot.pos, bp.robot_radius + bp.radius, robot.vel, bp.e_robot):
                ball.last_touch_team = robot.team
                ball.last_touch_robot = k

        # Goal posts: fixed circles
        for post in posts:
            _hit_circle(ball, post, pp.post_radius + bp.radius, (0.0, 0.0), bp.e_post)

        # Goal nets: fixed line segments, solid from both sides
        for x1, y1, x2, y2 in nets:
            _hit_segment(ball, (x1, y1), (x2, y2), bp.radius, bp.e_net)


def _hit_circle(ball: Ball, c: Vec2, radius: float, v_obj: Vec2, e: float) -> bool:
    """Ball against a circle centred at c; radius includes the ball's radius."""
    dx, dy = ball.pos[0] - c[0], ball.pos[1] - c[1]
    dist = math.hypot(dx, dy)
    if dist >= radius:
        return False
    if dist > 1e-12:
        n = (dx / dist, dy / dist)                 # contact normal, pointing at the ball
    elif norm(v_obj) > 0:
        n = (v_obj[0] / norm(v_obj), v_obj[1] / norm(v_obj))
    else:
        n = (1.0, 0.0)
    ball.pos = (c[0] + n[0] * radius, c[1] + n[1] * radius)    # move out of the overlap
    vn = (ball.vel[0] - v_obj[0]) * n[0] + (ball.vel[1] - v_obj[1]) * n[1]
    if vn < 0:
        ball.vel = (ball.vel[0] - (1 + e) * vn * n[0], ball.vel[1] - (1 + e) * vn * n[1])
    return True


def _hit_segment(ball: Ball, a: Vec2, b: Vec2, r: float, e: float) -> None:
    """Ball (radius r) against a fixed line segment from a to b."""
    ab = (b[0] - a[0], b[1] - a[1])
    s = dot((ball.pos[0] - a[0], ball.pos[1] - a[1]), ab) / dot(ab, ab)
    s = max(0.0, min(1.0, s))
    q = (a[0] + s * ab[0], a[1] + s * ab[1])       # closest point of the segment
    d = (ball.pos[0] - q[0], ball.pos[1] - q[1])
    dist = norm(d)
    if dist >= r or dist < 1e-12:
        return
    n = (d[0] / dist, d[1] / dist)
    ball.pos = (q[0] + n[0] * r, q[1] + n[1] * r)
    vn = dot(ball.vel, n)
    if vn < 0:
        ball.vel = (ball.vel[0] - (1 + e) * vn * n[0], ball.vel[1] - (1 + e) * vn * n[1])


def ball_kick(ball: Ball, robot, k: int, direction: float, speed: float, bp: BallParams,
              rng=random) -> bool:
    """Robot k tries to kick the ball; returns True if the kick happened.

    The kick only happens when the ball is within reach and in front of the
    robot; otherwise the ball is unchanged. The speed is limited to
    kick_speed_max and the direction to kick_dir_max either side of the
    robot's heading; then noise is added.
    """
    d = (ball.pos[0] - robot.pos[0], ball.pos[1] - robot.pos[1])
    bearing = wrap_angle(math.atan2(d[1], d[0]) - robot.heading)
    if norm(d) > bp.robot_radius + bp.radius + bp.kick_reach or abs(bearing) > bp.kick_cone / 2:
        return False

    rel = wrap_angle(direction - robot.heading)
    rel = max(-bp.kick_dir_max, min(bp.kick_dir_max, rel))
    direction = robot.heading + rel + bp.kick_sig_dir * rng.gauss(0, 1)

    speed = min(max(speed, 0.0), bp.kick_speed_max)
    speed = min(bp.kick_speed_max, max(0.0, speed * (1 + bp.kick_sig_speed * rng.gauss(0, 1))))

    ball.vel = (speed * math.cos(direction), speed * math.sin(direction))
    ball.last_touch_team = robot.team
    ball.last_touch_robot = k
    return True
