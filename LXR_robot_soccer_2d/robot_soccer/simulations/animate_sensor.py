"""Animate, in 2D, what robot 0 sees and believes.

Run from the code/python folder:
  .venv/bin/python -m robot_soccer.simulations.animate_sensor
  .venv/bin/python -m robot_soccer.simulations.animate_sensor --speed 2
  .venv/bin/python -m robot_soccer.simulations.animate_sensor --mode perfect
  .venv/bin/python -m robot_soccer.simulations.animate_sensor --save sensor.gif

The same scenario and random seed as demo_sensor. Close the window to stop.
"""
from __future__ import annotations

import argparse

from .demo_sensor import run_sensor_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description='Animation of the sensor model.')
    parser.add_argument('--speed', type=float, default=1.0, help='playback speed (default 1 = real time)')
    parser.add_argument('--mode', default='realistic', choices=('realistic', 'perfect'))
    parser.add_argument('--save', metavar='FILE.gif', help='save a GIF instead of opening a window')
    parser.add_argument('--no-hold', action='store_true', help='close the window at the end')
    args = parser.parse_args()

    from ..visual.animation import animate_sensor
    world, sp, records = run_sensor_scenario(mode=args.mode)
    frames = animate_sensor(records, world, sp, args.speed, args.save, hold=not args.no_hold)
    if args.save:
        print(f'saved {args.save} ({frames} frames)')


if __name__ == '__main__':
    main()
