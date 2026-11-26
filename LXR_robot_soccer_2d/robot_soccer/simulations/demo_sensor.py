"""Watch one robot's sensor model while the ball moves.

Run from the code/python folder:
  python3 -m robot_soccer.simulations.demo_sensor              summary only
  .venv/bin/python -m robot_soccer.simulations.demo_sensor --plot
  .venv/bin/python -m robot_soccer.simulations.demo_sensor --save sensor_demo

Robot 0 (team 1) stands at (-2, 0) and turns slowly; the ball moves on an
ellipse; one team-mate and two opponents stand still.
"""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..environment.ball import Ball
from ..environment.world import Robot, World
from ..geometry import Vec2, is_finite, norm
from ..sensors.params import SensorParams
from ..sensors.percept import Percept
from ..sensors.sensor_layer import sensor_init, sensor_step


@dataclass
class SensorRecord:
    """One time step of the scenario."""
    t: float
    ball: Vec2         # true ball position
    heading: float     # robot 0's true heading
    head_yaw: float
    percept: Percept


def run_sensor_scenario(seed: int = 1, mode: str = 'realistic') -> Tuple[World, SensorParams, List[SensorRecord]]:
    """Run the 30 s scenario and record every time step."""
    rng = random.Random(seed)
    sp = SensorParams(mode=mode)
    dt = 0.02
    w = World(ball=Ball(), robots=[Robot((-2.0, 0.0), 0.0, 1), Robot((1.0, 1.5), 0.0, 1),
                                   Robot((0.8, -0.4), math.pi, 2), Robot((3.0, 1.0), math.pi, 2)])
    ss = sensor_init(len(w.robots))
    records = []
    for i in range(round(30 / dt)):
        t = i * dt
        w.t = t
        w.ball.pos = (0.5 + 2.0 * math.cos(0.35 * t), 1.8 * math.sin(0.35 * t))
        w.robots[0].heading = 0.4 * math.sin(0.15 * t)
        p = sensor_step(w, 0, ss[0], sp, dt, rng=rng)
        records.append(SensorRecord(t, w.ball.pos, w.robots[0].heading, ss[0].head_yaw, p))
    return w, sp, records


def demo_sensor(seed: int = 1, verbose: bool = True) -> Dict[str, float]:
    """Run the scenario and return (and print) a summary."""
    _, sp, records = run_sensor_scenario(seed)
    n = len(records)
    seen = [r for r in records if r.percept.ball_visible]
    errors = [norm((r.percept.ball_pos[0] - r.ball[0], r.percept.ball_pos[1] - r.ball[1])) for r in seen]
    ages = [r.t - r.percept.t_measured for r in records if math.isfinite(r.percept.t_measured)]
    summary = {'frac_seen': len(seen) / n,
               'frac_with_estimate': sum(is_finite(r.percept.ball_pos) for r in records) / n,
               'mean_err_seen': sum(errors) / len(errors),
               'mean_age': sum(ages) / len(ages)}
    if verbose:
        print(f'\nDemo summary (mode = {sp.mode})')
        print(f"  ball seen in the latest image   : {100 * summary['frac_seen']:5.1f} % of the time")
        print(f"  any ball estimate (incl. memory): {100 * summary['frac_with_estimate']:5.1f} % of the time")
        print(f"  mean error when seen            : {summary['mean_err_seen']:5.2f} m (includes the delay)")
        print(f"  mean age of the information     : {summary['mean_age']:5.2f} s\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Sensor model demo.')
    parser.add_argument('--plot', action='store_true', help='show the two figures')
    parser.add_argument('--save', metavar='PREFIX', help='save PREFIX_top_view.png and PREFIX_over_time.png')
    args = parser.parse_args()
    demo_sensor()
    if args.plot or args.save:
        import matplotlib
        if not args.plot:
            matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ..visual.plots import figure_sensor_over_time, figure_sensor_top_view
        world, sp, records = run_sensor_scenario()
        figures = {'top_view': figure_sensor_top_view(records, world, sp, plt.figure),
                   'over_time': figure_sensor_over_time(records, plt.figure)}
        if args.save:
            for name, fig in figures.items():
                fig.savefig(f'{args.save}_{name}.png', dpi=130)
                print(f'saved {args.save}_{name}.png')
        if args.plot:
            plt.show()


if __name__ == '__main__':
    main()
