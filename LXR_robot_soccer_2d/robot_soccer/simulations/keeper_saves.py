"""Reproducible one-shot goalkeeper trials. Run as a module with --help."""
from __future__ import annotations

import argparse
import hashlib
import math
import random
from collections import Counter
from dataclasses import dataclass
from functools import partial
from statistics import quantiles
from typing import Optional, Sequence

from ..behaviours.goalkeeper import MATLAB_KEEPER, KeeperParams, goalkeeper_behaviour
from ..environment.ball import Ball, BallParams, ball_kick, ball_step, rolling_range
from ..environment.pitch import PitchParams
from ..environment.referee import referee_step
from ..environment.world import Robot, World
from ..geometry import Vec2, norm, sign_or_one
from ..robot.motion import RobotParams, RobotState, WalkCmd, keep_apart, robot_step
from ..sensors.params import SensorParams
from ..sensors.sensor_layer import SensorState, sensor_step
from .striker_keeper_drill import DT, Setting, sensor_setting

PITCH = PitchParams()
BALL = BallParams()
MOTION = RobotParams()
SETUP_SECONDS = 8
SHOT_SECONDS = 12
SHOOTER_GAP = 0.30
KEEPER = 1  # index; the keeper is on team 2
OUTCOMES = ('goal', 'saved', 'wide', 'short', 'cleared_early')
SCORABLE = {'goal', 'saved'}
DESIGNS = {
    'stationary': None,
    'baseline': partial(goalkeeper_behaviour, params=MATLAB_KEEPER),
    'updated': goalkeeper_behaviour,
}


@dataclass(frozen=True)
class Shot:
    distance: float
    angle: float  # signed radians from the line straight out from the goal centre
    ball_pos: Vec2
    shooter_pos: Vec2
    target_y: float
    heading: float
    nominal_speed: float
    velocity: Vec2
    keeper_seed: int


@dataclass(frozen=True)
class Attempt:
    shot: Shot
    outcome: str
    shooter_seen: bool  # at least one released image during setup


@dataclass(frozen=True)
class PairedResult:
    n: int
    first_only_eligible: int
    second_only_eligible: int
    first_only_saved: int
    second_only_saved: int
    change: Optional[float]  # second minus first, as a fraction
    interval: Optional[tuple[float, float]]
    p_value: Optional[float]


def generate_shots(attempts: int, seed: int, aim: str) -> list[Shot]:
    """Fix the setup and noisy kick before either keeper runs."""
    if attempts < 1:
        raise ValueError('attempts must be positive')
    if aim not in ('uniform', 'corner'):
        raise ValueError("aim must be 'uniform' or 'corner'")
    rng = random.Random(seed)
    goal_x = PITCH.own_goal_x(2)
    clear_half_width = PITCH.goal_width / 2 - BALL.radius
    max_range = rolling_range(BALL.kick_speed_max, BALL, DT)
    shots = []
    for _ in range(attempts):
        if aim == 'uniform':
            # Keep this target when resampling the start so targets remain uniform.
            target_y = rng.uniform(-clear_half_width, clear_half_width)
        while True:
            distance = rng.uniform(1.0, 2.3)
            angle = rng.uniform(-math.pi / 3, math.pi / 3)
            x = goal_x - distance * math.cos(angle)
            y = distance * math.sin(angle)
            if aim == 'corner':
                # The nominal guard position is on the goal-centre-to-ball ray.
                target_y = -sign_or_one(y) * (PITCH.goal_width / 2 - 0.35)
            heading = math.atan2(target_y - y, goal_x - x)
            direction = (math.cos(heading), math.sin(heading))
            # Referee requires the trailing edge of the ball past the line.
            required_range = (goal_x + BALL.radius + 1e-8 - x) / direction[0]
            if required_range <= max_range:
                break

        low, high = 0.0, BALL.kick_speed_max
        for _ in range(16):
            mid = (low + high) / 2
            if rolling_range(mid, BALL, DT) >= required_range:
                high = mid
            else:
                low = mid
        speed = rng.uniform(high, BALL.kick_speed_max)
        shooter_pos = (x - SHOOTER_GAP * direction[0], y - SHOOTER_GAP * direction[1])
        shooter = Robot(shooter_pos, heading, 1)
        ball = Ball(pos=(x, y))
        if not ball_kick(ball, shooter, 0, heading, speed, BALL, rng):
            raise RuntimeError('placed shooter could not contact the ball')
        shots.append(Shot(distance, angle, ball.pos, shooter_pos, target_y, heading,
                          speed, ball.vel, rng.getrandbits(64)))
    return shots


def _run_shot(shot: Shot, sp: SensorParams, behaviour) -> Attempt:
    goal_x = PITCH.own_goal_x(2)
    shooter = Robot(shot.shooter_pos, shot.heading, 1)
    keeper = Robot((goal_x - 0.35, 0.0), math.pi, 2)
    world = World(ball=Ball(pos=shot.ball_pos), robots=[shooter, keeper])
    state, camera = RobotState(), SensorState()
    mem = None
    rng = random.Random(shot.keeper_seed)
    sensor_rng, motion_rng, kick_rng = [random.Random(rng.getrandbits(64)) for _ in range(3)]
    shooter_seen = keeper_touched = False

    def record_contact(robot_index: int) -> None:
        nonlocal keeper_touched
        if robot_index == KEEPER:
            keeper_touched = True

    setup_steps = round(SETUP_SECONDS / DT)
    for step in range(setup_steps + round(SHOT_SECONDS / DT)):
        if step == setup_steps:
            world.ball.vel = shot.velocity
            world.ball.last_touch_team = shooter.team
            world.ball.last_touch_robot = 0

        percept = sensor_step(world, KEEPER, camera, sp, DT, state.odom, sensor_rng)
        if step < setup_steps:
            shooter_seen |= bool(percept.opponents)

        cmd = WalkCmd()
        if behaviour is not None:
            cmd, mem = behaviour(percept, mem, 2, PITCH, BALL, MOTION, state.odom)
        previous_pos = keeper.pos
        foot_contact = robot_step(keeper, state, cmd, MOTION, DT, motion_rng)
        # The shooter is fixed in this drill. Only the keeper can be blocked.
        if math.dist(keeper.pos, shooter.pos) < 2 * MOTION.radius:
            keeper.pos = previous_pos
            keeper.vel = (0.0, 0.0)
            state.v_body = (0.0, 0.0, state.v_body[2])
        keep_apart([keeper], PITCH, MOTION)
        if foot_contact and ball_kick(world.ball, keeper, KEEPER, state.kick_dir,
                                     state.kick_speed, BALL, kick_rng):
            keeper_touched = True

        ball_step(world.ball, world.robots, PITCH, BALL, DT, on_robot_contact=record_contact)
        world.t = (step + 1) * DT
        if step < setup_steps:
            if keeper_touched:
                return Attempt(shot, 'cleared_early', shooter_seen)
            continue

        event = referee_step(world, PITCH, BALL)
        if event is not None and event.type == 'goal' and event.team == 1:
            return Attempt(shot, 'goal', shooter_seen)
        if event is not None or world.ball.vel == (0.0, 0.0):
            outcome = 'saved' if keeper_touched else 'wide' if event is not None else 'short'
            return Attempt(shot, outcome, shooter_seen)

    raise RuntimeError(f'shot did not resolve within {SHOT_SECONDS} s of the kick')


def run_shots(shots: Sequence[Shot], sensors: Setting, keeper_design: str | KeeperParams) -> list[Attempt]:
    """Replay an existing shot list under one keeper and sensor configuration."""
    sp = sensor_setting(sensors)
    if isinstance(keeper_design, KeeperParams):
        behaviour = partial(goalkeeper_behaviour, params=keeper_design)
    else:
        if keeper_design not in DESIGNS:
            raise ValueError(f'unknown keeper design: {keeper_design}')
        behaviour = DESIGNS[keeper_design]
    return [_run_shot(shot, sp, behaviour) for shot in shots]


def compare_paired(first: Sequence[Attempt], second: Sequence[Attempt]) -> PairedResult:
    """Compare save flags over the shots scorable in both runs."""
    if len(first) != len(second) or any(a.shot != b.shot for a, b in zip(first, second)):
        raise ValueError('paired comparison requires the same shots in the same order')

    changes = []
    first_only_eligible = second_only_eligible = 0
    for a, b in zip(first, second):
        eligible_a, eligible_b = a.outcome in SCORABLE, b.outcome in SCORABLE
        if eligible_a and eligible_b:
            changes.append(int(b.outcome == 'saved') - int(a.outcome == 'saved'))
        elif eligible_a:
            first_only_eligible += 1
        elif eligible_b:
            second_only_eligible += 1

    n = len(changes)
    losses, gains = changes.count(-1), changes.count(1)
    change, interval, p_value = paired_binary_change(changes)
    return PairedResult(n, first_only_eligible, second_only_eligible, losses, gains,
                        change, interval, p_value)


def paired_binary_change(changes: Sequence[int]) -> tuple[
        Optional[float], Optional[tuple[float, float]], Optional[float]]:
    """Mean of second-minus-first binary results, paired 95% CI and exact p."""
    n = len(changes)
    if n == 0:
        return None, None, None
    losses, gains = changes.count(-1), changes.count(1)
    discordant = losses + gains
    # Exact, two-sided McNemar test (binomial on discordant pairs).
    tail = sum(math.comb(discordant, i) for i in range(min(losses, gains) + 1))
    p_value = min(1.0, (2 * tail) / (2 ** discordant))

    interval = None
    if n >= 2:
        # Sample complete pairs by resampling their within-pair differences.
        rng = random.Random(0)
        n_bootstrap = 5000
        means = [sum(rng.choices(changes, k=n)) / n for _ in range(n_bootstrap)]
        percentiles = quantiles(means, n=40, method='inclusive')
        interval = (percentiles[0], percentiles[-1])
    return sum(changes) / n, interval, p_value


def _print_counts(label: str, attempts: Sequence[Attempt]) -> None:
    counts = Counter(attempt.outcome for attempt in attempts)
    n_scorable = counts['goal'] + counts['saved']
    rate = f"{counts['saved'] / n_scorable:.1%}" if n_scorable else 'n/a'
    breakdown = '  '.join(f'{name}={counts[name]}' for name in OUTCOMES)
    print(f'  {label:<18} n={len(attempts):>4}  save rate={rate:>6}  {breakdown}')


def _print_run(design: str, results: list[Attempt]) -> None:
    print(f'\n{design} | shooter detected during setup: '
          f'{sum(result.shooter_seen for result in results)}/{len(results)}')
    _print_counts('all shots', results)

    groups = (
        ('distance', (1.0, 1.5, 2.0, 2.3), 'm', [r.shot.distance for r in results]),
        ('abs. start angle', (0, 20, 40, 60), 'deg', [abs(math.degrees(r.shot.angle)) for r in results]),
        ('launch speed', (0, 1.6, 1.8, 2.0), 'm/s', [norm(r.shot.velocity) for r in results]),
    )
    for name, edges, unit, values in groups:
        print(f'  {name}:')
        for index, (low, high) in enumerate(zip(edges, edges[1:])):
            last = index == len(edges) - 2
            rows = [result for result, value in zip(results, values)
                    if low <= value < high or (last and math.isclose(value, high, abs_tol=1e-12))]
            _print_counts(f'{low:g}-{high:g} {unit}', rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=500)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--sensors', choices=('realistic', 'perfect'), default='realistic')
    parser.add_argument('--aim', choices=('uniform', 'corner'), default='uniform')
    parser.add_argument('--keeper-design', choices=tuple(DESIGNS), nargs='+',
                        default=['stationary', 'baseline'],
                        help='one design, or two designs to compare in the order given')
    args = parser.parse_args()
    if args.attempts < 1:
        parser.error('--attempts must be positive')
    if len(args.keeper_design) > 2:
        parser.error('--keeper-design accepts at most two designs')

    shots = generate_shots(args.attempts, args.seed, args.aim)
    digest = hashlib.sha256(repr(shots).encode()).hexdigest()
    print(f'{args.attempts} shots | seed={args.seed} | aim={args.aim} | sensors={args.sensors}')
    print(f'Shot SHA-256: {digest}')
    runs = []
    for design in args.keeper_design:
        results = run_shots(shots, args.sensors, design)
        runs.append(results)
        _print_run(design, results)

    if len(runs) == 2:
        paired = compare_paired(*runs)
        first, second = args.keeper_design
        print(f'\nPaired comparison ({second} minus {first}): '
              f'{paired.n}/{len(shots)} eligible in both')
        print(f'  Eligible only in {first}: {paired.first_only_eligible} | '
              f'only in {second}: {paired.second_only_eligible}')
        if paired.change is None:
            print('  Save rate change, 95% CI and p-value: n/a')
        else:
            print(f'  Saves only in {first}: {paired.first_only_saved} | '
                  f'only in {second}: {paired.second_only_saved}')
            ci = ('n/a' if paired.interval is None else
                  f'[{paired.interval[0] * 100:+.2f}, {paired.interval[1] * 100:+.2f}] pp')
            print(f'  Save rate change: {paired.change * 100:+.2f} pp | 95% CI: {ci} | '
                  f'exact McNemar p={paired.p_value:.4g}')


if __name__ == '__main__':
    main()
