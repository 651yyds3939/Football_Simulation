"""Striker v goalkeeper, changing one robot's sensors at a time.

Run from the code/python folder:
  python3 -m robot_soccer.simulations.compare_sensor_settings --attempts 500 --seed 1

Runs the drill four times with the same starting spots: both perfect (the
baseline), only the striker realistic, only the keeper realistic, both
realistic. Comparing each single change with the baseline shows how much the
sensor model affects each robot on its own.
"""
from __future__ import annotations

import argparse
from typing import Dict, List

from .striker_keeper_drill import striker_keeper_drill

SETTINGS = (('both perfect', ('perfect', 'perfect')),
            ('striker realistic', ('realistic', 'perfect')),
            ('keeper realistic', ('perfect', 'realistic')),
            ('both realistic', ('realistic', 'realistic')))


def compare_sensor_settings(n_trials: int = 50, seed: int = 1, verbose: bool = True) -> List[Dict]:
    """Returns one row per setting: counts, goal rate and mean time to a goal (s)."""
    rows = []
    for name, sensors in SETTINGS:
        results = striker_keeper_drill(n_trials, sensors, seed, verbose=False)
        goal_times = [r.time for r in results if r.outcome == 'goal']
        count = lambda outcome: sum(r.outcome == outcome for r in results)
        rows.append({'setting': name, 'goals': count('goal'), 'saved': count('saved'),
                     'missed': count('missed'), 'timeout': count('timeout'),
                     'goal_rate': count('goal') / n_trials,
                     'time_to_goal': sum(goal_times) / len(goal_times) if goal_times else float('nan')})
    if verbose:
        print(f'\nStriker v goalkeeper: {n_trials} attempts per setting, seed {seed}\n')
        print(f"  {'setting':<18s} {'goals':>6s} {'saved':>6s} {'missed':>7s} {'timeout':>8s} "
              f"{'goal rate':>10s} {'time to goal':>14s}")
        for r in rows:
            print(f"  {r['setting']:<18s} {r['goals']:6d} {r['saved']:6d} {r['missed']:7d} "
                  f"{r['timeout']:8d} {100 * r['goal_rate']:9.0f}% {r['time_to_goal']:12.1f} s")
        print()
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--attempts', type=int, default=50)
    parser.add_argument('--seed', type=int, default=1)
    args = parser.parse_args()
    compare_sensor_settings(args.attempts, args.seed)
