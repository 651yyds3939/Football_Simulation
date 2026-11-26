"""Walking helpers shared by the behaviours, and the odometry update."""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable, Optional, Tuple

from ..environment.ball import BallParams
from ..geometry import Vec2, dot, is_finite, norm, to_body, wrap_angle
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept

WalkGuidance = Callable[[Percept, Vec2, float], WalkCmd]
POSITION_GAIN = 1.5  # s^-1
HEADING_GAIN = 2.5   # s^-1


def walk_to(p: Percept, target: Vec2, face: float, *, position_gain: float = POSITION_GAIN,
            heading_gain: float = HEADING_GAIN) -> WalkCmd:
    """Walk towards a world-frame point while turning to face the angle face."""
    d = to_body((target[0] - p.self_pos[0], target[1] - p.self_pos[1]), p.self_heading)
    return WalkCmd(position_gain * d[0], position_gain * d[1],
                   heading_gain * wrap_angle(face - p.self_heading))


def approach_ball(p: Percept, kick_dir: float, rp: RobotParams, bp: BallParams,
                  dribble: bool = False, *, guide: Optional[WalkGuidance] = None) -> Tuple[WalkCmd, bool, bool]:
    """Walk to the spot behind the ball, lined up to kick it in kick_dir.

    Returns (cmd, ready, going_round). ready is True when the robot stands
    behind the ball, lined up, with the ball in the latest image. going_round
    is True while it walks round a ball it is on the wrong side of. With
    dribble, once lined up it walks on through the ball, pushing it along.

    Works in the robot's own frame: close up, the measured range and bearing
    are more accurate than the world estimate, which also carries the
    self-localisation error.
    """
    h = p.self_heading
    if p.ball_visible:
        b = (p.ball_range * math.cos(p.ball_bearing), p.ball_range * math.sin(p.ball_bearing))
    else:
        b = to_body((p.ball_pos[0] - p.self_pos[0], p.ball_pos[1] - p.self_pos[1]), h)
    kd = wrap_angle(kick_dir - h)                  # kick direction, robot frame
    k = (math.cos(kd), math.sin(kd))
    behind = rp.radius + bp.radius + 0.02          # robot centre to ball centre for the kick
    spot = (b[0] - behind * k[0], b[1] - behind * k[1])   # where the robot should stand

    # Not behind the ball (level with it or on the goal side): walk to a point
    # beside and behind it first
    going_round = dot((-b[0], -b[1]), k) > -0.05
    if going_round:
        cross = k[0] * (-b[1]) - k[1] * (-b[0])    # which side of the ball the robot is on
        side = -1.0 if cross < 0 else 1.0
        target = (b[0] + 0.45 * side * (-k[1]) - 0.30 * k[0],
                  b[1] + 0.45 * side * k[0] - 0.30 * k[1])
    else:
        target = spot

    # Far away: face where it walks (forward is fastest). Close: face the kick direction.
    face = math.atan2(target[1], target[0]) if norm(target) > 0.4 else kd
    cmd = WalkCmd(POSITION_GAIN * target[0], POSITION_GAIN * target[1], HEADING_GAIN * wrap_angle(face))
    if guide is not None and guide is not walk_to and norm(target) > 0.4:
        # Use the same local navigation as the other travel behaviours. Leave
        # the close range foot alignment below in the robot's own frame.
        c, s = math.cos(h), math.sin(h)
        point = (p.self_pos[0] + c * target[0] - s * target[1],
                 p.self_pos[1] + s * target[0] + c * target[1])
        cmd = guide(p, point, h + face)

    ready = (not going_round and p.ball_visible and norm(spot) < 0.06
             and abs(kd) < 10 * math.pi / 180)

    # Dribbling: once roughly lined up, walk forward through the ball and
    # correct any sideways error, so the ball is pushed along kick_dir
    if dribble and not going_round and norm(spot) < 0.10 and abs(kd) < 15 * math.pi / 180:
        along = dot(spot, k)
        side_err = (spot[0] - along * k[0], spot[1] - along * k[1])
        cmd = WalkCmd(rp.v_forward * k[0] + POSITION_GAIN * side_err[0],
                      rp.v_forward * k[1] + POSITION_GAIN * side_err[1], HEADING_GAIN * kd)
    return cmd, ready, going_round


def odometry_update(p: Percept, odom: Optional[Tuple[float, float, float]]) -> Percept:
    """Bring a percept up to now with the robot's own odometry.

    p.odom is the reading when its image was taken (0.1-0.2 s ago) and odom
    the reading now. The robot's pose and the measured ball range and bearing
    are moved on by the walking and turning done since. The ball is assumed
    not to have moved. If either reading is missing, p is returned unchanged.
    """
    if odom is None or not is_finite(odom) or not is_finite(p.odom) or not is_finite(p.self_pos):
        return p

    # Movement since the image, in the robot's frame at the time of the image
    d = to_body((odom[0] - p.odom[0], odom[1] - p.odom[1]), p.odom[2])
    dth = wrap_angle(odom[2] - p.odom[2])

    c, s = math.cos(p.self_heading), math.sin(p.self_heading)
    q = replace(p, self_pos=(p.self_pos[0] + c * d[0] - s * d[1],
                             p.self_pos[1] + s * d[0] + c * d[1]),
                self_heading=wrap_angle(p.self_heading + dth))

    # Ball relative to the robot now: shift by the walk, then turn
    if p.ball_visible:
        b = (p.ball_range * math.cos(p.ball_bearing), p.ball_range * math.sin(p.ball_bearing))
        b_now = to_body((b[0] - d[0], b[1] - d[1]), dth)
        q.ball_range = norm(b_now)
        q.ball_bearing = math.atan2(b_now[1], b_now[0])
    return q
