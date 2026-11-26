"""Goalkeeper: guard the goal, block shots and clear the ball when it comes close.

States (mem.state):
  home       no ball estimate: stand just in front of the goal centre, facing the pitch
  guard      stand on the line from the goal centre to the ball, 0.5 m out,
             facing the ball: the position that covers most of the goal
  intercept  the ball is rolling towards the goal mouth: step to where its
             path crosses the keeper's line, 0.4 m in front of the goal
  clear      no shot on its way, and the ball is inside the own penalty area
             and within 0.8 m: get behind it and kick it away from the goal

The keeper cannot dive; it blocks shots with its body only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..geometry import is_finite, norm, sign
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept
from .approach import WalkGuidance, approach_ball, odometry_update, walk_to
from .ball_prediction import BallTracker, track_ball


@dataclass
class KeeperMemory:
    state: str = 'home'
    tr: Optional[BallTracker] = None


def goalkeeper_behaviour(p: Percept, mem: Optional[KeeperMemory], team: int, pp: PitchParams,
                         bp: BallParams, rp: RobotParams,
                         odom=None, *, guide: WalkGuidance = walk_to) -> Tuple[WalkCmd, KeeperMemory]:
    """One decision. p is this robot's percept (never the true world); pass mem=None first."""
    mem = mem if mem is not None else KeeperMemory()
    p = odometry_update(p, odom)
    if not is_finite(p.self_pos):
        return WalkCmd(), mem                   # no image processed yet
    goal_x = pp.own_goal_x(team)                # own goal centre is (goal_x, 0)
    s = sign(goal_x)                            # +1 if the own goal is at +x
    ball_vel, mem.tr = track_ball(p, mem.tr, bp)
    y_max = pp.goal_width / 2 - 0.1             # furthest the keeper goes to the side

    if not is_finite(p.ball_pos):
        mem.state = 'home'
        return guide(p, (goal_x - s * 0.35, 0.0), math.pi * (s > 0)), mem   # face the pitch

    b = p.ball_pos
    db = (b[0] - p.self_pos[0], b[1] - p.self_pos[1])
    face = math.atan2(db[1], db[0])             # face the ball

    # Ball rolling towards the goal mouth: step into its path (this comes
    # first: a shot on its way is blocked, not chased)
    shot = False
    x_line = goal_x - s * 0.4                   # the keeper's line
    y_cross = 0.0
    if is_finite(ball_vel) and s * ball_vel[0] > 0.3 and norm(ball_vel) > 0.4:
        y_cross = b[1] + ball_vel[1] * (x_line - b[0]) / ball_vel[0]
        y_goal = b[1] + ball_vel[1] * (goal_x - b[0]) / ball_vel[0]
        shot = s * (x_line - b[0]) > 0 and abs(y_goal) < pp.goal_width / 2 + 0.3

    # Otherwise, a ball close by inside the penalty area is cleared
    depth = s * (goal_x - b[0])                 # ball's distance in front of the goal line
    in_box = -0.2 < depth < pp.penalty_area_length and abs(b[1]) < pp.penalty_area_width / 2
    if not shot and in_box and norm(db) < 0.8:
        mem.state = 'clear'
        side = sign(b[1]) or 1.0
        kick_dir = math.atan2(0.6 * side, -s)   # away from the goal, towards the side
        cmd, ready, _ = approach_ball(p, kick_dir, rp, bp, guide=guide)
        if ready:
            cmd.kick = True
            cmd.kick_dir = kick_dir
            cmd.kick_speed = bp.kick_speed_max
        return cmd, mem

    if shot:
        mem.state = 'intercept'
        target = (x_line, max(-y_max, min(y_max, y_cross)))
    else:
        mem.state = 'guard'
        to_ball = (b[0] - goal_x, b[1])
        length = max(norm(to_ball), 1e-6)
        x = goal_x + 0.5 * to_ball[0] / length
        y = 0.5 * to_ball[1] / length
        x = goal_x - s * max(0.2, s * (goal_x - x))   # stay in front of the goal line
        target = (x, max(-y_max, min(y_max, y)))
    return guide(p, target, face), mem
