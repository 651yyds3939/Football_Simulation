"""Goalkeeper: return home, narrow the angle, intercept, or clear a loose ball."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..geometry import Vec2, is_finite, norm, sign, sign_or_one
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept
from .approach import WalkGuidance, approach_ball, odometry_update, walk_to
from .ball_prediction import BallTracker, ball_path, track_ball


@dataclass(frozen=True)
class KeeperParams:
    gap: float = 0.5              # m, design choice: selected in GK-14
    max_out: float = 1.5          # m, design choice: selected in GK-14
    min_out: float = 0.5          # m, design choice: minimum guard radius
    max_lateral: float = 1.2      # m, design choice: maximum lateral guard offset
    guard_min_depth: float = 0.05  # m, design choice: minimum ball depth for the guard target
    claim_speed: float = 0.5      # m/s, design choice: only challenge a slow ball
    claim_margin: float = 0.5     # s, design choice: lead to start, deficit to abandon
    opponent_memory: float = 2.0  # s, design choice: age limit for opponent sightings
    home_depth: float = 0.35      # m, baseline assumption: MATLAB home position
    clear_side: float = 0.6       # baseline assumption: MATLAB lateral/forward kick ratio

    matlab_baseline: bool = False  # design choice: select the historical policy explicitly
    baseline_guard_radius: float = 0.5      # m, baseline assumption: MATLAB guard radius
    baseline_guard_min_depth: float = 0.2   # m, baseline assumption: MATLAB guard setback
    baseline_intercept_depth: float = 0.4   # m, baseline assumption: fixed intercept line
    baseline_post_margin: float = 0.1       # m, baseline assumption: inset from each post
    baseline_shot_vx: float = 0.3           # m/s, baseline assumption: goalward speed threshold
    baseline_shot_speed: float = 0.4        # m/s, baseline assumption: total speed threshold
    baseline_shot_mouth_slack: float = 0.3  # m, baseline assumption: extra width per side
    baseline_clear_radius: float = 0.8      # m, baseline assumption: close-ball clearance
    baseline_clear_line_slack: float = 0.2  # m, baseline assumption: allowance behind goal line


DEFAULT_KEEPER = KeeperParams()
MATLAB_KEEPER = KeeperParams(matlab_baseline=True)
KEEPER_DESIGNS = {'refined': DEFAULT_KEEPER, 'matlab': MATLAB_KEEPER}


@dataclass
class KeeperMemory:
    state: str = 'home'
    tr: Optional[BallTracker] = None
    opponent_frames: Deque[Tuple[float, Tuple[Vec2, ...]]] = field(default_factory=deque)


def goalkeeper_behaviour(p: Percept, mem: Optional[KeeperMemory], team: int, pp: PitchParams,
                         bp: BallParams, rp: RobotParams,
                         odom=None, *, guide: WalkGuidance = walk_to,
                         params: KeeperParams = DEFAULT_KEEPER) -> Tuple[WalkCmd, KeeperMemory]:
    """One decision. p is this robot's percept (never the true world); pass mem=None first."""
    mem = mem if mem is not None else KeeperMemory()
    p = odometry_update(p, odom)
    if not is_finite(p.self_pos):
        return WalkCmd(), mem                   # no image processed yet
    goal_x = pp.own_goal_x(team)                # own goal centre is (goal_x, 0)
    s = sign(goal_x)                            # +1 if the own goal is at +x
    ball_vel, mem.tr = track_ball(p, mem.tr, bp)
    if not params.matlab_baseline:
        _remember_opponents(p, mem, params.opponent_memory)

    b = p.ball_pos
    ball_depth = s * (goal_x - b[0])
    ball_past_goal = s * b[0] > abs(goal_x) + bp.radius
    if not is_finite(b) or (not params.matlab_baseline and ball_past_goal):
        mem.state = 'home'
        return guide(p, (goal_x - s * params.home_depth, 0.0), math.pi * (s > 0)), mem

    if params.matlab_baseline:
        mem.state, target = _matlab_target(p, ball_vel, goal_x, pp, params)
    else:
        target = _shot_target(b, ball_vel, p.self_pos[0], goal_x, pp, bp)
        if target is not None:
            mem.state = 'intercept'
        elif _can_claim(p, mem, ball_vel, ball_depth, pp, rp, params):
            mem.state = 'clear'
        else:
            mem.state = 'guard'
            guard_ball = b
            if ball_depth < params.guard_min_depth:
                guard_ball = (goal_x - s * params.guard_min_depth, b[1])
            target = _guard_target(guard_ball, goal_x, pp, params)

    if target is None:  # clear
        kick_dir = math.atan2(params.clear_side * sign_or_one(b[1]), -s)
        cmd, ready, _ = approach_ball(p, kick_dir, rp, bp, guide=guide)
        if ready:
            cmd.kick = True
            cmd.kick_dir = kick_dir
            cmd.kick_speed = bp.kick_speed_max
        return cmd, mem

    face = math.atan2(b[1] - p.self_pos[1], b[0] - p.self_pos[0])
    return guide(p, target, face), mem


def _guard_target(ball: Vec2, goal_x: float, pp: PitchParams, params: KeeperParams) -> Vec2:
    """Apply all guard bounds to the radius, preserving the goal-to-ball ray."""
    dx, dy = ball[0] - goal_x, ball[1]
    distance = math.hypot(dx, dy)
    ux, uy = dx / distance, dy / distance
    lateral_limit = min(params.max_lateral, pp.penalty_area_width / 2)
    radius_limit = min(params.max_out, pp.penalty_area_length / abs(ux))
    if uy:
        radius_limit = min(radius_limit, lateral_limit / abs(uy))
    radius = min(radius_limit, max(params.min_out, distance - params.gap))
    return goal_x + radius * ux, radius * uy


def _shot_target(ball: Vec2, velocity: Vec2, keeper_x: float, goal_x: float,
                 pp: PitchParams, bp: BallParams) -> Optional[Vec2]:
    """Intersect the rolling trajectory with the keeper's current depth."""
    if not is_finite(velocity) or sign(goal_x) * velocity[0] <= 0:
        return None
    speed = norm(velocity)
    if speed < bp.v_stop:
        return None
    dx, dy = velocity[0] / speed, velocity[1] / speed
    at_keeper = (keeper_x - ball[0]) / dx
    at_goal = (goal_x - ball[0]) / dx
    if not 0 <= at_keeper <= at_goal or abs(ball[1] + at_goal * dy) >= pp.goal_width / 2:
        return None
    _, _, _, stop_distance = ball_path(ball, velocity, (), bp)
    if at_goal > stop_distance:
        return None
    return keeper_x, ball[1] + at_keeper * dy


def _remember_opponents(p: Percept, mem: KeeperMemory, max_age: float) -> None:
    frames = mem.opponent_frames
    while frames and p.t_measured - frames[0][0] > max_age:
        frames.popleft()
    if (p.opponents and math.isfinite(p.t_measured)
            and (not frames or p.t_measured > frames[-1][0])):
        frames.append((p.t_measured, tuple(p.opponents)))


def _can_claim(p: Percept, mem: KeeperMemory, velocity: Vec2, depth: float,
               pp: PitchParams, rp: RobotParams, params: KeeperParams) -> bool:
    if (not 0 <= depth <= pp.penalty_area_length or abs(p.ball_pos[1]) > pp.penalty_area_width / 2
            or not is_finite(velocity) or norm(velocity) >= params.claim_speed):
        return False
    ball = p.ball_pos
    closest = min((math.dist(ball, opponent)
                   for _, opponents in mem.opponent_frames for opponent in opponents),
                  default=math.inf)
    # Also accept current observations from a caller without a measurement timestamp.
    closest = min(closest, min((math.dist(ball, q) for q in p.opponents), default=math.inf))
    # Both travel times use v_forward, so the distance lead needed to start
    # against a recent opponent is claim_margin * v_forward (0.125 m by default).
    lead = (closest - math.dist(ball, p.self_pos)) / rp.v_forward
    required_lead = -params.claim_margin if mem.state == 'clear' else params.claim_margin
    return lead >= required_lead


def _matlab_target(p: Percept, velocity: Vec2, goal_x: float,
                   pp: PitchParams, params: KeeperParams) -> Tuple[str, Optional[Vec2]]:
    """The historical decisions and limits used by the MATLAB trace comparison."""
    b = p.ball_pos
    s = sign(goal_x)
    y_max = pp.goal_width / 2 - params.baseline_post_margin
    x_line = goal_x - s * params.baseline_intercept_depth
    if (is_finite(velocity) and s * velocity[0] > params.baseline_shot_vx
            and norm(velocity) > params.baseline_shot_speed):
        y_cross = b[1] + velocity[1] * (x_line - b[0]) / velocity[0]
        y_goal = b[1] + velocity[1] * (goal_x - b[0]) / velocity[0]
        if s * (x_line - b[0]) > 0 and abs(y_goal) < pp.goal_width / 2 + params.baseline_shot_mouth_slack:
            return 'intercept', (x_line, max(-y_max, min(y_max, y_cross)))

    depth = s * (goal_x - b[0])
    in_box = (-params.baseline_clear_line_slack < depth < pp.penalty_area_length
              and abs(b[1]) < pp.penalty_area_width / 2)
    if in_box and norm((b[0] - p.self_pos[0], b[1] - p.self_pos[1])) < params.baseline_clear_radius:
        return 'clear', None

    to_ball = (b[0] - goal_x, b[1])
    length = max(norm(to_ball), 1e-6)
    x = goal_x + params.baseline_guard_radius * to_ball[0] / length
    y = params.baseline_guard_radius * to_ball[1] / length
    x = goal_x - s * max(params.baseline_guard_min_depth, s * (goal_x - x))
    return 'guard', (x, max(-y_max, min(y_max, y)))
