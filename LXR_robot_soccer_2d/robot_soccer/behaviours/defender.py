"""Guard one side of the defensive half and clear a nearby ball."""
from __future__ import annotations

import math

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..geometry import is_finite, norm, sign
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept
from .approach import WalkGuidance, approach_ball, odometry_update, walk_to


def defender_behaviour(p: Percept, team: int, lane: int, pp: PitchParams,
                       bp: BallParams, rp: RobotParams, odom=None, *,
                       guide: WalkGuidance = walk_to) -> tuple[WalkCmd, str]:
    """Use local vision and odometry. Lane is -1 for y < 0 and +1 otherwise."""
    p = odometry_update(p, odom)
    if not is_finite(p.self_pos):
        return WalkCmd(), 'waiting for vision'

    goal_x = pp.own_goal_x(team)
    attack = -sign(goal_x)
    home = (goal_x + attack * 1.5, lane * pp.half_width / 3)
    if not is_finite(p.ball_pos):
        return guide(p, home, 0.0 if attack > 0 else math.pi), 'hold lane'

    bx, by = p.ball_pos
    dx, dy = (bx - p.self_pos[0], by - p.self_pos[1])
    ball_lane = -1 if by < 0 else 1
    goal_depth = attack * (bx - goal_x)
    keeper_zone = goal_depth < 1.0 and abs(by) < pp.goal_width / 2
    if ball_lane == lane and 0 < goal_depth < pp.half_length * 0.75 and not keeper_zone:
        if norm((dx, dy)) < 1.0:
            # Clear upfield, angling towards the centre when near the touchline.
            direction = math.atan2(-0.3 * by, attack)
            cmd, ready, _ = approach_ball(p, direction, rp, bp, guide=guide)
            if ready:
                cmd.kick = True
                cmd.kick_dir = direction
                cmd.kick_speed = bp.kick_speed_max
            return cmd, 'clear ball'

    # Shift towards the ball within the assigned lane and stay goal side.
    y = lane * min(pp.half_width * 0.75, max(0.55, lane * by))
    depth = max(0.9, min(pp.half_length * 0.65, goal_depth - 0.45))
    face = math.atan2(dy, dx)
    return guide(p, (goal_x + attack * depth, y), face), 'guard lane'
