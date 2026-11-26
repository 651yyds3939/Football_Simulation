"""Play a fixed duration 4 v 4 match with two autonomous teams."""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from functools import partial

from ..behaviours.approach import approach_ball, odometry_update, walk_to
from ..behaviours.defender import defender_behaviour
from ..behaviours.goalkeeper import goalkeeper_behaviour
from ..behaviours.navigation import navigate_to
from ..behaviours.striker import striker_behaviour
from ..environment.ball import BallParams, ball_kick
from ..environment.pitch import PitchParams
from ..environment.world import World, world_init, world_step
from ..geometry import Vec2, is_finite, norm, sign
from ..robot.motion import RobotParams, WalkCmd, keep_apart, robot_state_init, robot_step
from ..sensors.params import SensorParams
from ..sensors.percept import Percept
from ..sensors.sensor_layer import sensor_init, sensor_step

DT = 0.02
REPLAY_INTERVAL = 0.1
RESTART_TIMEOUT = 12.0
PLAYERS_PER_TEAM = 4
ROLES = ('GK', 'D1', 'D2', 'ST')


@dataclass(frozen=True)
class MatchFrame:
    time: float
    ball: Vec2
    poses: tuple[tuple[Vec2, float], ...]
    score: tuple[int, int]
    states: tuple[str, ...]


@dataclass
class MatchResult:
    world: World
    kicks: tuple[int, int]
    frames: list[MatchFrame]


def _restart_cmd(percept: Percept, odom, direction: float, rp: RobotParams, bp: BallParams) -> WalkCmd:
    p = odometry_update(percept, odom)
    if not is_finite(p.self_pos) or not is_finite(p.ball_pos):
        return WalkCmd()
    cmd, ready, _ = approach_ball(p, direction, rp, bp)
    if ready:
        cmd.kick = True
        cmd.kick_dir = direction
        cmd.kick_speed = 1.0
    return cmd


def _prepare_restart(world: World, pp: PitchParams, rp: RobotParams, bp: BallParams) -> tuple[int, float]:
    """Make room for the ball and choose a taker for the simplified restart."""
    restart = world.restart
    attack = -sign(pp.own_goal_x(restart.team)) if restart.team else 0
    bx, by = restart.pos
    if restart.type == 'kickoff':
        return restart.team * PLAYERS_PER_TEAM - 1, 0.0 if attack > 0 else math.pi

    if restart.type == 'corner_kick':
        direction = math.atan2(-by, -attack * pp.goal_area_length)
    elif restart.type == 'throw_in':
        direction = math.atan2(-by, attack)
    else:  # goal kick
        direction = math.atan2(-by, attack * pp.half_length)

    # A robot may still overlap the new ball spot, particularly on a touchline.
    # Move it towards the pitch so it cannot immediately push the ball out again.
    clearance = rp.radius + bp.radius + 0.1
    for robot in world.robots:
        x, y = robot.pos
        if norm((x - bx, y - by)) < clearance:
            robot.pos = (bx + clearance * math.cos(direction), by + clearance * math.sin(direction))
        robot.vel = (0.0, 0.0)
    keep_apart(world.robots, pp, rp)

    spot = (bx - clearance * math.cos(direction), by - clearance * math.sin(direction))
    eligible = (k for k, robot in enumerate(world.robots) if restart.team in (0, robot.team))
    kicker = min(eligible, key=lambda k: math.dist(world.robots[k].pos, spot))
    return kicker, direction


def play_match(duration: float = 120.0, sensors: str = 'realistic', seed: int = 1,
               kickoff_team: int = 1, record: bool = False, *, control_design: bool = False) -> MatchResult:
    """Run both teams with the same controllers. Record sampled poses for optional replay.

    A goal resets the formation and starts a new kickoff for the team that
    conceded. For each restart, only the designated taker can move until it
    contacts the ball or the restart window expires.
    """
    if not math.isfinite(duration) or duration < DT:
        raise ValueError(f'duration must be at least {DT} seconds and finite')
    if sensors not in ('realistic', 'perfect'):
        raise ValueError('sensors must be realistic or perfect')
    if kickoff_team not in (1, 2):
        raise ValueError('kickoff team must be 1 or 2')

    rng = random.Random(seed)
    pp, bp = PitchParams(), BallParams()
    rp = RobotParams()
    guide = partial(navigate_to, pp=pp, rp=rp) if control_design else walk_to
    sp = SensorParams(mode=sensors)
    world = world_init(pp)
    world.restart.team = kickoff_team
    n = len(world.robots)
    ss, rs = sensor_init(n), robot_state_init(n)
    memory = [None] * n
    kicker, restart_direction = _prepare_restart(world, pp, rp, bp)
    kicks = [0, 0]
    frames: list[MatchFrame] = []
    states = ['ready'] * n
    if record:
        frames.append(_frame(world, states))

    n_steps = math.ceil(duration / DT - 1e-9)
    stride = round(REPLAY_INTERVAL / DT)
    for step in range(1, n_steps + 1):
        dt = duration - (step - 1) * DT if step == n_steps else DT
        if kicker is not None and world.t - world.restart.t >= RESTART_TIMEOUT:
            kicker = None

        # Sample all robots before any of them moves.
        percepts = [sensor_step(world, k, ss[k], sp, dt, rs[k].odom, rng) for k in range(n)]
        commands = []
        for k, (robot, p) in enumerate(zip(world.robots, percepts)):
            role = k % PLAYERS_PER_TEAM
            odom = rs[k].odom
            if kicker is not None:
                cmd = _restart_cmd(p, odom, restart_direction, rp, bp) if k == kicker else WalkCmd()
                states[k] = world.restart.type if k == kicker else 'wait for restart'
            elif role == 0:
                cmd, memory[k] = goalkeeper_behaviour(p, memory[k], robot.team, pp, bp, rp, odom,
                                                       guide=guide)
                states[k] = memory[k].state
            elif role == PLAYERS_PER_TEAM - 1:
                # There is one striker per team. The other players remain visible
                # for navigation but cannot take the striker's attacking role.
                cmd, memory[k] = striker_behaviour(p, memory[k], robot.team, pp, bp, rp, odom, rng,
                                                    guide=guide, coordinate_attack=False)
                states[k] = memory[k].state
            else:
                lane = -1 if role == 1 else 1
                cmd, states[k] = defender_behaviour(p, robot.team, lane, pp, bp, rp, odom, guide=guide)
            commands.append(cmd)

        for k, (robot, cmd) in enumerate(zip(world.robots, commands)):
            if robot_step(robot, rs[k], cmd, rp, dt, rng):
                if ball_kick(world.ball, robot, k, rs[k].kick_dir, rs[k].kick_speed, bp, rng):
                    kicks[robot.team - 1] += 1
        keep_apart(world.robots, pp, rp)
        event = world_step(world, pp, bp, dt)
        if event is not None:
            if event.type == 'goal':
                world.robots = world_init(pp).robots
            ss, rs = sensor_init(n), robot_state_init(n)
            memory = [None] * n
            kicker, restart_direction = _prepare_restart(world, pp, rp, bp)
            states = ['ready'] * n
        elif kicker is not None and world.ball.last_touch_robot == kicker:
            kicker = None

        if record and (step % stride == 0 or step == n_steps):
            frames.append(_frame(world, states))

    return MatchResult(world, (kicks[0], kicks[1]), frames)


def _frame(world: World, states: list[str]) -> MatchFrame:
    return MatchFrame(world.t, world.ball.pos, tuple((r.pos, r.heading) for r in world.robots),
                      (world.score[0], world.score[1]), tuple(states))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=120.0, help='match duration in simulated seconds')
    parser.add_argument('--sensors', choices=('realistic', 'perfect'), default='realistic')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--kickoff-team', type=int, choices=(1, 2), default=1)
    parser.add_argument('--animate', action='store_true', help='show a replay in a window')
    parser.add_argument('--control-design', action='store_true',
                        help='use perception-based routing (combined walking limits always apply)')
    args = parser.parse_args()
    try:
        result = play_match(args.seconds, args.sensors, args.seed, args.kickoff_team, args.animate,
                            control_design=args.control_design)
    except ValueError as error:
        parser.error(str(error))

    w = result.world
    print(f'4 v 4 | {w.t:.2f} s | sensors: {args.sensors} | seed: {args.seed} | kickoff: team {args.kickoff_team}')
    if args.control_design:
        print('Navigation: perception-based routing')
    for event in w.events:
        print(f'{event.t:6.2f} s  {event.type:15s} team {event.team or "undecided"}')
    print(f'Score (blue vs orange): {w.score[0]}–{w.score[1]} | successful kicks: {result.kicks[0]}–{result.kicks[1]}')
    if args.animate:
        from ..visual.match_replay import show_match
        show_match(result.frames)


if __name__ == '__main__':
    main()
