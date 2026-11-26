"""Striker: get to the ball, pass or dribble it forward, and shoot.

States (mem.state):
  search         no ball estimate: walk towards the opponents' half while the
                 head sweeps, then turn on the spot
  support        a team-mate is closer to the ball (or this robot has just
                 passed): wait ahead of the ball, on the other side, facing it
  intercept      the ball is rolling: go to the first point on its path that
                 this robot can reach in time
  go to ball     more than 0.6 m from the ball: walk to the spot behind it
  go round       on the wrong side of the ball: walk round it
  line up pass, pass   a team-mate is better placed: pass to it
  dribble        ball further than SHOOT_RANGE from the aim point: push it
                 towards the goal by walking
  approach       within SHOOT_RANGE: walk to the spot behind the ball
  kick           lined up: start a full-speed shot

With two attackers each runs this same behaviour; the one closer to the ball
goes for it and the other supports. Team-mates are known only from the percept
(seen in the last 5 s); there is no team communication.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..geometry import Vec2, dot, is_finite, norm, sign, sign_or_one
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept
from .approach import WalkGuidance, approach_ball, odometry_update, walk_to
from .ball_prediction import BallTracker, ball_path, intercept_point, pass_speed, track_ball

SHOOT_RANGE = 1.8    # m (design choice) a full-speed kick rolls about 2.3 m
PASS_MIN = 0.8       # m (design choice) shortest pass
PASS_GAIN = 1.0      # m (design choice) receiver must be this much nearer the goal
PASS_CLEAR = 0.5     # m (design choice) no opponent this close to the pass line
SUPPORT_TIME = 3.0   # s (design choice) after a pass, leave the ball to the receiver
STUCK_TIME = 4.0     # s (design choice) on the ball this long without progress...
STUCK_GAIN = 0.3     # m (design choice) ...towards the goal counts as stuck


@dataclass
class StrikerMemory:
    state: str = 'search'
    aim_y: float = 0.0
    keeper_y: float = math.nan
    keeper_t: float = -math.inf
    tr: Optional[BallTracker] = None
    mate_pos: Vec2 = (math.nan, math.nan)
    mate_t: float = -math.inf
    role: str = 'chase'
    support_until: float = -math.inf
    pass_to: Vec2 = (math.nan, math.nan)
    pass_until: float = -math.inf
    prog_x: float = -math.inf
    prog_t: float = -math.inf


def striker_behaviour(p: Percept, mem: Optional[StrikerMemory], team: int, pp: PitchParams,
                      bp: BallParams, rp: RobotParams, odom=None,
                      rng=random, *, guide: WalkGuidance = walk_to,
                      coordinate_attack: bool = True) -> Tuple[WalkCmd, StrikerMemory]:
    """One decision. p is this robot's percept (never the true world); pass mem=None first."""
    mem = mem if mem is not None else StrikerMemory()
    p = odometry_update(p, odom)
    if not is_finite(p.self_pos):
        return WalkCmd(), mem                   # no image processed yet
    t = p.t_measured
    goal_x = pp.own_goal_x(3 - team)            # the opponents' goal line
    sx = sign(goal_x)                           # +1 if attacking +x

    # ---- What this robot remembers ----
    # the opposing goalkeeper (nearest opponent to their goal)
    if p.opponents:
        nearest = min(p.opponents, key=lambda q: math.hypot(q[0] - goal_x, q[1]))
        if math.hypot(nearest[0] - goal_x, nearest[1]) < 1.5:
            mem.keeper_y = nearest[1]
            mem.keeper_t = t
    # the nearest team-mate
    if coordinate_attack and p.mates:
        mem.mate_pos = min(p.mates, key=lambda q: math.hypot(q[0] - p.self_pos[0],
                                                             q[1] - p.self_pos[1]))
        mem.mate_t = t
    has_mate = coordinate_attack and t - mem.mate_t < 5
    # the ball's velocity
    ball_vel, mem.tr = track_ball(p, mem.tr, bp)

    # Aim away from the keeper; switch sides only when the keeper is clearly
    # on the side being aimed at
    corner = pp.goal_width / 2 - 0.35
    if t - mem.keeper_t < 5:
        if mem.aim_y == 0:
            mem.aim_y = -sign_or_one(mem.keeper_y) * corner
        elif sign(mem.aim_y) == sign(mem.keeper_y) and abs(mem.keeper_y) > 0.15:
            mem.aim_y = -mem.aim_y

    # ---- No ball estimate: search ----
    if not is_finite(p.ball_pos):
        mem.state = 'search'
        target = (0.4 * goal_x, 0.0)
        d = (target[0] - p.self_pos[0], target[1] - p.self_pos[1])
        if norm(d) > 0.3:
            return guide(p, target, math.atan2(d[1], d[0])), mem
        return WalkCmd(0.0, 0.0, 0.5 * rp.turn_rate), mem

    ball = p.ball_pos
    to_ball = (ball[0] - p.self_pos[0], ball[1] - p.self_pos[1])
    my_d = norm(to_ball)
    face_ball = math.atan2(to_ball[1], to_ball[0])

    # ---- Chase the ball or support the team-mate ----
    if t < mem.support_until:
        mem.role = 'support'
    elif not has_mate:
        mem.role = 'chase'
    else:
        mate_d = norm((ball[0] - mem.mate_pos[0], ball[1] - mem.mate_pos[1]))
        if mem.role == 'chase' and mate_d < my_d - 0.5:
            mem.role = 'support'                # the team-mate is clearly closer
        elif mem.role == 'support' and my_d < mate_d - 0.2:
            mem.role = 'chase'

    # Stuck: on the ball without moving it towards the goal while a team-mate
    # is also at the ball (they block each other). Give way for a random 2-4 s,
    # so the two do not keep giving way and coming back together. Side by side
    # they often cannot see each other, so this does not catch every case.
    if mem.role == 'chase' and my_d < 0.6:
        if sx * ball[0] > mem.prog_x + STUCK_GAIN:
            mem.prog_x = sx * ball[0]
            mem.prog_t = t
        elif (t - mem.prog_t > STUCK_TIME and has_mate
              and norm((ball[0] - mem.mate_pos[0], ball[1] - mem.mate_pos[1])) < 1.0):
            mem.role = 'support'
            mem.support_until = t + 2 + 2 * rng.random()
            mem.prog_t = t + 5
    else:
        mem.prog_x = sx * ball[0]
        mem.prog_t = max(mem.prog_t, t)

    if mem.role == 'support':
        mem.state = 'support'
        spot_x = sx * min(sx * (ball[0] + sx * 1.5), sx * goal_x - 1.2)   # not too near the goal line
        return guide(p, (spot_x, -sign_or_one(ball[1]) * 1.0), face_ball), mem

    # ---- The ball is rolling towards somewhere else: intercept it ----
    if is_finite(ball_vel) and norm(ball_vel) > 0.4 and my_d > 0.6:
        target, _ = intercept_point(ball, ball_vel, p.self_pos, rp, bp)
        if norm((target[0] - p.self_pos[0], target[1] - p.self_pos[1])) > 0.3:
            mem.state = 'intercept'
            return guide(p, target, face_ball), mem

    # ---- Pass if a team-mate is better placed ----
    d_aim = (goal_x - ball[0], mem.aim_y - ball[1])
    far = norm(d_aim) > SHOOT_RANGE
    if t >= mem.pass_until and has_mate and far:
        pass_max = ball_path((0.0, 0.0), (bp.kick_speed_max, 0.0), [0.0], bp)[3]
        to_mate = (mem.mate_pos[0] - ball[0], mem.mate_pos[1] - ball[1])
        opponents = list(p.opponents)
        if t - mem.keeper_t < 5:
            opponents.append((goal_x - sx * 0.35, mem.keeper_y))
        if (sx * to_mate[0] >= PASS_GAIN and norm(to_mate) >= PASS_MIN
                and norm(to_mate) + 0.3 <= pass_max
                and _line_clear(ball, mem.mate_pos, opponents, PASS_CLEAR)):
            mem.pass_to = mem.mate_pos
            mem.pass_until = t + 2              # stick with this pass for 2 s
    if t < mem.pass_until:
        to_mate = (mem.pass_to[0] - ball[0], mem.pass_to[1] - ball[1])
        kick_dir = math.atan2(to_mate[1], to_mate[0])
        cmd, ready, going_round = approach_ball(p, kick_dir, rp, bp, guide=guide)
        if ready:
            mem.state = 'pass'
            cmd.kick = True
            cmd.kick_dir = kick_dir
            cmd.kick_speed = pass_speed(norm(to_mate) + 0.3, bp)[0]
            mem.pass_until = -math.inf
            mem.support_until = t + SUPPORT_TIME
        elif going_round:
            mem.state = 'go round'
        else:
            mem.state = 'line up pass'
        return cmd, mem

    # ---- Far from the goal: dribble towards it. Within range: shoot ----
    kick_dir = math.atan2(d_aim[1], d_aim[0])
    cmd, ready, going_round = approach_ball(p, kick_dir, rp, bp, far, guide=guide)
    if my_d > 0.6:
        mem.state = 'go to ball'
    elif going_round:
        mem.state = 'go round'
    elif far:
        mem.state = 'dribble'
    elif ready:
        mem.state = 'kick'
        cmd.kick = True
        cmd.kick_dir = kick_dir
        cmd.kick_speed = bp.kick_speed_max
    else:
        mem.state = 'approach'
    return cmd, mem


def _line_clear(a: Vec2, b: Vec2, points: Sequence[Vec2], clearance: float) -> bool:
    """True if no point lies within clearance of the segment a-b."""
    ab = (b[0] - a[0], b[1] - a[1])
    for q in points:
        s = max(0.0, min(1.0, dot((q[0] - a[0], q[1] - a[1]), ab) / dot(ab, ab)))
        if norm((a[0] + s * ab[0] - q[0], a[1] + s * ab[1] - q[1])) < clearance:
            return False
    return True
