"""Attackers try to score past a goalkeeper, over repeated attempts.

Run from the code/python folder:
  python3 -m robot_soccer.simulations.striker_keeper_drill
  python3 -m robot_soccer.simulations.striker_keeper_drill --attempts 50 --attackers 2
  python3 -m robot_soccer.simulations.striker_keeper_drill --sensors perfect --keeper-sensors realistic
  .venv/bin/python -m robot_soccer.simulations.striker_keeper_drill --animate --speed 3
  .venv/bin/python -m robot_soccer.simulations.striker_keeper_drill --attempts 2 --save drill.gif

Each attempt: the ball lies still at a random spot in the attacking half; the
first attacker (team 1) starts at a random spot behind the halfway line, a
second attacker at a random spot in the attacking half; they attack the goal
at +x. The goalkeeper (team 2) starts in front of its goal. Every behaviour
uses only its own percept. The starting spots depend only on the seed, not on
the sensor settings or the number of attackers, so runs can be compared
attempt by attempt.

An attempt ends with:
  goal     the ball goes into the goal
  saved    the keeper kicks the ball away, or touched it last before it went out
  missed   the ball goes out, last touched by an attacker
  timeout  none of these within 60 s
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Union

from ..behaviours.goalkeeper import goalkeeper_behaviour
from ..behaviours.striker import striker_behaviour
from ..environment.ball import Ball, BallParams, ball_kick
from ..environment.pitch import PitchParams
from ..environment.world import Robot, World, world_step
from ..geometry import Vec2, norm, sign_or_one
from ..robot.motion import RobotParams, WalkCmd, keep_apart, robot_state_init, robot_step
from ..sensors.params import SensorParams
from ..sensors.sensor_layer import sensor_init, sensor_step

Setting = Union[str, SensorParams]
DT = 0.02
T_MAX = 60.0


@dataclass
class Attempt:
    outcome: str
    time: float
    striker_start: Vec2
    ball_start: Vec2
    support_start: Optional[Vec2]    # None with one attacker
    passes: int                      # passes kicked
    passes_received: int             # reached the other attacker before anyone else


@dataclass
class DrillFrame:
    """What a viewer gets after every simulation step."""
    trial: int                       # attempt number, from 1
    n_trials: int
    t: float
    dt: float
    robots: List[Robot]
    ball_pos: Vec2                   # where a rule applied, if one just did
    percepts: list
    history: list                    # true (x, y, heading) of every robot at every step so far
    labels: List[str]                # what each robot is doing
    counts: Dict[str, int]           # results of the finished attempts
    passes: int
    received: int
    done: bool                       # this attempt has just ended
    outcome: str


def sensor_setting(setting: Setting) -> SensorParams:
    """'realistic' or 'perfect' give the default parameters; a SensorParams is used as it is."""
    sp = SensorParams(mode=setting) if isinstance(setting, str) else setting
    if sp.mode not in ('realistic', 'perfect'):
        raise ValueError(f"sensor mode must be 'realistic' or 'perfect', not '{sp.mode}'")
    return sp


def striker_keeper_drill(n_trials: int = 5,
                         sensors: Union[Setting, Tuple[Setting, Setting]] = 'realistic',
                         seed: int = 1, use_odometry: bool = True, n_attackers: int = 1,
                         verbose: bool = True,
                         on_step: Optional[Callable[[DrillFrame], bool]] = None) -> List[Attempt]:
    """Run the drill and return one Attempt per attempt.

    sensors is one setting for every robot, or (attackers, keeper). on_step, if
    given, is called after every step with a DrillFrame; returning False stops
    the drill (the unfinished attempt is left out of the results).
    """
    if n_attackers not in (1, 2):
        raise ValueError('n_attackers must be 1 or 2')
    na = n_attackers
    n = na + 1                                   # robots: attackers, then the keeper
    if not isinstance(sensors, tuple):
        sensors = (sensors, sensors)
    sps = [sensor_setting(sensors[0])] * na + [sensor_setting(sensors[1])]

    # Starting spots first, so they do not depend on the settings
    rng = random.Random(seed)
    striker_y = [3 * rng.random() - 1.5 for _ in range(n_trials)]
    ball_x = [2.5 * rng.random() for _ in range(n_trials)]
    ball_y = [4 * rng.random() - 2 for _ in range(n_trials)]
    support_x = [1.0 + 1.5 * rng.random() for _ in range(n_trials)]
    support_y = [4 * rng.random() - 2 for _ in range(n_trials)]

    pp = PitchParams()
    bp = BallParams()
    rp = RobotParams()
    n_steps = round(T_MAX / DT)
    counts = {'goal': 0, 'saved': 0, 'missed': 0, 'timeout': 0}
    total_passes = total_received = 0
    results: List[Attempt] = []
    names = ['striker'] if na == 1 else [f'A{k + 1}' for k in range(na)]
    names.append('keeper')
    stopped = False

    if verbose:
        print(f'\nStriker v goalkeeper: {na} attacker(s) {_describe(sensors[0])}, '
              f'keeper {_describe(sensors[1])}')

    for trial in range(n_trials):
        # ---- Start of an attempt ----
        ball_start = (ball_x[trial], ball_y[trial])
        support = (support_x[trial], support_y[trial])
        if norm((support[0] - ball_start[0], support[1] - ball_start[1])) < 0.6:   # not on the ball
            support = (support[0], ball_start[1] - sign_or_one(ball_start[1]) * 1.2)
        robots = [Robot((-1.5, striker_y[trial]), 0.0, 1)]
        if na == 2:
            robots.append(Robot(support, 0.0, 1))
        robots.append(Robot((pp.own_goal_x(2) - 0.35, 0.0), 3.141592653589793, 2))
        w = World(ball=Ball(pos=ball_start), robots=robots)
        striker_start = robots[0].pos

        ss = sensor_init(n)
        rs = robot_state_init(n)
        mem = [None] * n
        outcome = 'timeout'
        n_pass = n_recv = 0
        pass_from = None                         # attacker whose pass is on its way
        pass_kick = [False] * n                  # kick in progress is a pass
        history: list = []                       # true poses, to draw each robot's view

        for step in range(n_steps):
            if on_step is not None:
                history.append([(r.pos[0], r.pos[1], r.heading) for r in w.robots])

            # Sense, decide, act
            percepts = [sensor_step(w, k, ss[k], sps[k], DT, rs[k].odom, rng) for k in range(n)]
            cmds: List[WalkCmd] = []
            for k in range(n):
                odo = rs[k].odom if use_odometry else None
                if k < na:
                    cmd, mem[k] = striker_behaviour(percepts[k], mem[k], 1, pp, bp, rp, odo, rng)
                else:
                    cmd, mem[k] = goalkeeper_behaviour(percepts[k], mem[k], 2, pp, bp, rp, odo)
                cmds.append(cmd)

            done = False
            for k in range(n):
                if k < na and cmds[k].kick and rs[k].kick_t is None and mem[k].state == 'pass':
                    pass_kick[k] = True
                if robot_step(w.robots[k], rs[k], cmds[k], rp, DT, rng):
                    kicked = ball_kick(w.ball, w.robots[k], k, rs[k].kick_dir, rs[k].kick_speed,
                                       bp, rng)
                    if kicked and k == n - 1:
                        outcome = 'saved'        # the keeper cleared the ball
                        done = True
                    if pass_kick[k] and kicked:
                        n_pass += 1
                        pass_from = k
                    pass_kick[k] = False
            keep_apart(w.robots, pp, rp)

            # Ball and rules
            event = world_step(w, pp, bp, DT)
            if pass_from is not None:
                touch = w.ball.last_touch_robot
                if touch is not None and touch < na and touch != pass_from:
                    n_recv += 1                  # the other attacker reached it first
                    pass_from = None
                elif touch == n - 1 or event is not None:
                    pass_from = None             # the keeper got it, or the ball went out
            if event is not None and not done:
                if event.type == 'goal' and event.team == 1:
                    outcome = 'goal'
                elif event.team == 1:
                    outcome = 'saved'            # out of play, last touched by the keeper
                else:
                    outcome = 'missed'
                done = True

            if on_step is not None:
                labels = [f'{names[k]}: ' + ('kicking' if rs[k].kick_t is not None else mem[k].state)
                          for k in range(n)]
                frame = DrillFrame(trial + 1, n_trials, w.t, DT, w.robots,
                                   event.pos if event is not None else w.ball.pos, percepts, history,
                                   labels, dict(counts), total_passes + n_pass, total_received + n_recv,
                                   done or step == n_steps - 1, outcome)
                if on_step(frame) is False:
                    stopped = True
                    break
            if done:
                break

        if stopped:
            break
        counts[outcome] += 1
        total_passes += n_pass
        total_received += n_recv
        results.append(Attempt(outcome, w.t, striker_start, ball_start,
                               support if na == 2 else None, n_pass, n_recv))
        if verbose:
            extra = f'   passes {n_pass}, received {n_recv}' if na > 1 else ''
            print(f'  attempt {trial + 1:2d}: {outcome:<8s} after {w.t:4.1f} s{extra}')

    if verbose:
        print(f"\n  goals {counts['goal']}, saved {counts['saved']}, missed {counts['missed']}, "
              f"timeout {counts['timeout']}  ({len(results)} attempts)")
        if na > 1:
            print(f'  passes {total_passes}, received by the other attacker {total_received}')
        print()
    return results


def _describe(setting: Setting) -> str:
    return setting if isinstance(setting, str) else f'{setting.mode} (own parameters)'


def main() -> None:
    parser = argparse.ArgumentParser(description='Attackers v goalkeeper, repeated attempts.')
    parser.add_argument('--attempts', type=int, default=5)
    parser.add_argument('--sensors', default='realistic', help="attackers: realistic or perfect")
    parser.add_argument('--keeper-sensors', default=None, help='keeper (default: same as attackers)')
    parser.add_argument('--attackers', type=int, default=1, choices=(1, 2))
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--no-odometry', action='store_true', help='behaviours ignore odometry')
    parser.add_argument('--animate', action='store_true', help='show the drill in a window')
    parser.add_argument('--speed', type=float, default=1.0, help='playback speed (default 1 = real time)')
    parser.add_argument('--save', metavar='FILE.gif', help='save the animation as a GIF')
    parser.add_argument('--no-hold', action='store_true', help='close the window at the end')
    args = parser.parse_args()
    sensors = (args.sensors, args.keeper_sensors or args.sensors)
    viewer = None
    if args.animate or args.save:
        from ..visual.animation import DrillViewer
        settings = [sensor_setting(sensors[0])] * args.attackers + [sensor_setting(sensors[1])]
        viewer = DrillViewer(args.attackers, settings, RobotParams(), speed=args.speed, save=args.save)
    striker_keeper_drill(args.attempts, sensors, args.seed, not args.no_odometry, args.attackers,
                         on_step=viewer)
    if viewer is not None:
        viewer.finish(hold=not args.no_hold)
        if args.save:
            print(f'saved {args.save} ({viewer.frames} frames)')


if __name__ == '__main__':
    main()
