"""Simple NAO6 motion model.

Walking, kicking and odometry values are assumptions from the MATLAB reference
in code/robot/robot_params.m. See docs/control_design.md for their provenance.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..environment.pitch import PitchParams
from ..geometry import norm, wrap_angle


@dataclass(frozen=True)
class RobotParams:
    radius: float = 0.155      # m, baseline disc proxy for half the datasheet depth (311 mm)
    # Walking (omnidirectional: forward, sideways and turning at once)
    v_forward: float = 0.25    # m/s, MATLAB baseline assumption
    v_backward: float = 0.10   # m/s, MATLAB baseline assumption
    v_side: float = 0.12       # m/s in either direction, MATLAB baseline assumption
    turn_rate: float = math.pi / 3  # rad/s, MATLAB baseline assumption (60 deg/s)
    accel: float = 0.5         # m/s^2 for translation, MATLAB baseline assumption
    # Kicking (the robot stands still for the whole kick motion)
    kick_time: float = 1.0     # s for the whole kick, MATLAB baseline assumption
    kick_contact: float = 0.5  # s to foot contact, MATLAB baseline assumption
    # Odometry (each robot gets its own fixed scale error)
    odo_sig_trans: float = 0.05  # fractional scale error (std), MATLAB baseline assumption
    odo_sig_rot: float = 0.05    # fractional scale error (std), MATLAB baseline assumption
    strict_walk_limit: bool = True  # False is only for comparison with historical MATLAB traces


@dataclass
class WalkCmd:
    """A command from a behaviour to the motion model.

    vx, vy are the wanted velocity in the robot's own frame (x forward, y left)
    and omega the wanted turn rate. A behaviour that wants to kick sets kick,
    kick_dir (rad, world frame) and kick_speed (m/s).
    """
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0
    kick: bool = False
    kick_dir: float = 0.0
    kick_speed: float = 0.0


@dataclass
class RobotState:
    """Motion state of one robot (current walk, kick in progress, odometry)."""
    v_body: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # current vx, vy, omega
    kick_t: Optional[float] = None    # s since the kick started; None = not kicking
    kick_dir: float = 0.0             # rad, world frame, of the kick in progress
    kick_speed: float = 0.0           # m/s, of the kick in progress
    odom: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # own pose by dead reckoning
    odo_scale: Optional[Tuple[float, float]] = None     # scale errors, drawn at the first step


def robot_state_init(n_robots: int) -> List[RobotState]:
    return [RobotState() for _ in range(n_robots)]


def robot_step(robot, rs: RobotState, cmd: WalkCmd, rp: RobotParams, dt: float, rng=random) -> bool:
    """Move one robot for one time step; True in the step the foot meets the ball.

    The walk is limited in speed (forward, backward, sideways and turning
    share one limit) and in acceleration. A kick lasts kick_time; the robot
    stands still and ignores commands until it ends. When this returns True
    the caller applies ball_kick with rs.kick_dir and rs.kick_speed.
    """
    kick_now = False
    if rs.kick_t is None and cmd.kick:
        rs.kick_t = 0.0                                  # start a kick
        rs.kick_dir = cmd.kick_dir
        rs.kick_speed = cmd.kick_speed

    if rs.kick_t is not None:
        # Kicking: stand still; the foot meets the ball at kick_contact
        before = rs.kick_t
        rs.kick_t += dt
        kick_now = before < rp.kick_contact - 1e-9 and rs.kick_t >= rp.kick_contact - 1e-9
        if rs.kick_t >= rp.kick_time - 1e-9:
            rs.kick_t = None
        rs.v_body = (0.0, 0.0, 0.0)
    else:
        target = _limit_walk(cmd.vx, cmd.vy, cmd.omega, rp)
        dv = (target[0] - rs.v_body[0], target[1] - rs.v_body[1])   # acceleration limit
        max_dv = rp.accel * dt
        if norm(dv) > max_dv:
            k = max_dv / norm(dv)
            dv = (dv[0] * k, dv[1] * k)
        vx, vy = rs.v_body[0] + dv[0], rs.v_body[1] + dv[1]
        omega = target[2]
        if rp.strict_walk_limit:
            # Translation is already acceleration limited. Give rotation only the
            # remaining budget rather than rescaling and abruptly braking the walk.
            rotation_budget = rp.turn_rate * math.sqrt(max(0.0, 1.0 - _translation_load(vx, vy, rp)))
            omega = max(-rotation_budget, min(rotation_budget, omega))
        rs.v_body = (vx, vy, omega)

    # Move the true pose
    vx, vy, omega = rs.v_body
    c, s = math.cos(robot.heading), math.sin(robot.heading)
    v_world = (c * vx - s * vy, s * vx + c * vy)
    robot.pos = (robot.pos[0] + v_world[0] * dt, robot.pos[1] + v_world[1] * dt)
    robot.heading = wrap_angle(robot.heading + omega * dt)
    robot.vel = v_world

    # Odometry: the same movement as the robot measures it. Each robot has its
    # own fixed scale error (e.g. its feet slip a little), drawn once.
    if rs.odo_scale is None:
        rs.odo_scale = (1 + rp.odo_sig_trans * rng.gauss(0, 1),
                        1 + rp.odo_sig_rot * rng.gauss(0, 1))
    dx, dy = rs.odo_scale[0] * vx * dt, rs.odo_scale[0] * vy * dt
    dth = rs.odo_scale[1] * omega * dt
    c, s = math.cos(rs.odom[2]), math.sin(rs.odom[2])
    rs.odom = (rs.odom[0] + c * dx - s * dy, rs.odom[1] + s * dx + c * dy,
               wrap_angle(rs.odom[2] + dth))
    return kick_now


def _translation_load(vx: float, vy: float, rp: RobotParams) -> float:
    vx_max = rp.v_backward if vx < 0 else rp.v_forward
    return (vx / vx_max) ** 2 + (vy / rp.v_side) ** 2


def _limit_walk(vx: float, vy: float, omega: float, rp: RobotParams):
    """Scale the command down so walking and turning together stay within limits."""
    f = math.sqrt(_translation_load(vx, vy, rp) + (omega / rp.turn_rate) ** 2)
    return (vx / f, vy / f, omega / f) if f > 1 else (vx, vy, omega)


def keep_apart(robots: Sequence, pp: PitchParams, rp: RobotParams) -> None:
    """Stop robots overlapping each other or leaving the carpet.

    Two robots that overlap are pushed apart equally along the line between
    them. Falls and pushing fouls are not modelled.
    """
    n = len(robots)
    for i in range(n):
        for j in range(i + 1, n):
            d = (robots[j].pos[0] - robots[i].pos[0], robots[j].pos[1] - robots[i].pos[1])
            dist = norm(d)
            gap = 2 * rp.radius - dist
            if gap > 0:
                u = (d[0] / dist, d[1] / dist) if dist > 1e-12 else (1.0, 0.0)
                robots[i].pos = (robots[i].pos[0] - u[0] * gap / 2, robots[i].pos[1] - u[1] * gap / 2)
                robots[j].pos = (robots[j].pos[0] + u[0] * gap / 2, robots[j].pos[1] + u[1] * gap / 2)

    x_max = pp.half_length + pp.border_width - rp.radius
    y_max = pp.half_width + pp.border_width - rp.radius
    for robot in robots:
        robot.pos = (max(-x_max, min(x_max, robot.pos[0])), max(-y_max, min(y_max, robot.pos[1])))
