"""Tune GK-14 or run the GK-15 paired evaluation. Results are written as JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from itertools import product

from ..behaviours.goalkeeper import DEFAULT_KEEPER, MATLAB_KEEPER, KeeperParams
from .keeper_saves import PITCH, SCORABLE, Shot, compare_paired, generate_shots, paired_binary_change, run_shots
from .striker_keeper_drill import striker_keeper_drill

GAPS = (0.5, 0.6, 0.8)
MAX_OUTS = (1.0, 1.5, 1.8)
TUNING_REFERENCE = replace(DEFAULT_KEEPER, gap=0.6, max_out=1.5)


@dataclass(frozen=True)
class Run:
    attempts: int
    seed: int
    params: KeeperParams
    sensors: str = 'realistic'
    shots: list[Shot] | None = None


def _simulate(run: Run):
    if run.shots is not None:
        return run_shots(run.shots, run.sensors, run.params)
    return striker_keeper_drill(run.attempts, run.sensors, run.seed, verbose=False,
                                keeper_design=run.params, per_trial_rng=True)


def _run_all(runs: list[Run], workers: int):
    if workers == 1:
        return [_simulate(run) for run in runs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_simulate, runs))


def _shot_save_rate(counts: Counter) -> float | None:
    eligible = counts['saved'] + counts['goal']
    return counts['saved'] / eligible if eligible else None


def _rates(shots, drill) -> dict:
    shots_counts = Counter(attempt.outcome for attempt in shots)
    drill_counts = Counter(attempt.outcome for attempt in drill)
    return {
        'shots': dict(shots_counts),
        'shot_save_rate': _shot_save_rate(shots_counts),
        'shot_goal_rate': shots_counts['goal'] / len(shots),
        'drill': dict(drill_counts),
        'drill_goal_rate': drill_counts['goal'] / len(drill),
    }


def tune(attempts: int, seed: int, workers: int) -> dict:
    shots = generate_shots(attempts, seed, 'corner')
    candidates = [replace(TUNING_REFERENCE, gap=gap, max_out=max_out)
                  for gap, max_out in product(GAPS, MAX_OUTS)]
    runs = [run for params in [*candidates, MATLAB_KEEPER]
            for run in (Run(attempts, seed, params, shots=shots), Run(attempts, seed, params))]
    results = _run_all(runs, workers)
    _validate_drill_pairs(results[1::2])
    rows = []
    for params, shot_run, drill_run in zip(candidates, results[::2], results[1::2]):
        rows.append({'gap': params.gap, 'max_out': params.max_out, **_rates(shot_run, drill_run)})

    reference = rows[candidates.index(TUNING_REFERENCE)]
    # Screen on both all-attempt goal rates plus the post-shot save rate.
    # Among qualifying settings, favour the largest gain in the less improved scenario.
    eligible = []
    if reference['shot_save_rate'] is not None:
        for row in rows:
            shot_gain = reference['shot_goal_rate'] - row['shot_goal_rate']
            drill_gain = reference['drill_goal_rate'] - row['drill_goal_rate']
            save_rate = row['shot_save_rate']
            if (shot_gain >= 0 and drill_gain >= 0 and save_rate is not None
                    and save_rate >= reference['shot_save_rate']):
                key = (min(shot_gain, drill_gain), shot_gain + drill_gain,
                       save_rate - reference['shot_save_rate'], row is reference,
                       -row['max_out'], -row['gap'])
                eligible.append((key, row))
    selected = max(eligible, key=lambda result: result[0])[1] if eligible else None
    return {'stage': 'tune', 'attempts': attempts, 'seed': seed, 'reference': reference,
            'candidates': rows, 'matlab': _rates(results[-2], results[-1]), 'selected': selected}


def _drill_starts(attempts) -> list:
    return [(attempt.striker_start, attempt.ball_start, attempt.support_start) for attempt in attempts]


def _validate_drill_pairs(runs) -> None:
    first = _drill_starts(runs[0])
    if any(_drill_starts(run) != first for run in runs[1:]):
        raise RuntimeError('drill runs must have identical indexed starting positions')


def _compare_groups(first, second, distances: list[float], edges: tuple[float, ...],
                    is_shot: bool) -> list[dict]:
    if len(first) != len(second) or len(first) != len(distances):
        raise RuntimeError('paired runs must contain the same number of attempts')
    pairs = list(zip(first, second))
    bands = [('all', pairs)]
    for low, high in zip(edges, edges[1:]):
        band = [pair for distance, pair in zip(distances, pairs)
                if low <= distance < high or (high == edges[-1] and distance == high)]
        bands.append((f'{low:g}–{high:g}', band))
    if sum(len(band) for _, band in bands[1:]) != len(pairs):
        raise RuntimeError('distance bands must cover the entire run')

    rows = []
    for label, band in bands:
        baseline = Counter(a.outcome for a, _ in band)
        refined = Counter(b.outcome for _, b in band)
        changes = [int(b.outcome == 'goal') - int(a.outcome == 'goal') for a, b in band]
        delta, ci, p_value = paired_binary_change(changes)
        row = {'distance': label, 'n': len(band), 'baseline': dict(baseline), 'refined': dict(refined),
               'goals': {'change': delta, 'ci95': ci, 'p': p_value,
                         'baseline_only': changes.count(-1), 'refined_only': changes.count(1)}}
        if is_shot:
            saves = compare_paired([a for a, _ in band], [b for _, b in band])
            eligible = [(a, b) for a, b in band if a.outcome in SCORABLE and b.outcome in SCORABLE]
            row['saves'] = {'n': saves.n, 'change': saves.change, 'ci95': saves.interval,
                            'baseline_saved': sum(a.outcome == 'saved' for a, _ in eligible),
                            'refined_saved': sum(b.outcome == 'saved' for _, b in eligible),
                            'p': saves.p_value, 'baseline_only': saves.first_only_saved,
                            'refined_only': saves.second_only_saved,
                            'baseline_only_eligible': saves.first_only_eligible,
                            'refined_only_eligible': saves.second_only_eligible}
        rows.append(row)
    return rows


def evaluate(attempts: int, seed: int, workers: int, params: KeeperParams) -> dict:
    aims = ('uniform', 'corner')
    conditions = list(product(aims, ('perfect', 'realistic')))
    shots = {aim: generate_shots(attempts, seed, aim) for aim in aims}
    policies = (MATLAB_KEEPER, params)
    runs = [Run(attempts, seed, policy) for policy in policies]
    runs.extend(Run(attempts, seed, policy, sensors, shots[aim])
                for aim, sensors in conditions for policy in policies)
    results = _run_all(runs, workers)
    output = []
    for (aim, sensors), first, second in zip(conditions, results[2::2], results[3::2]):
        cases = shots[aim]
        rows = _compare_groups(first, second, [shot.distance for shot in cases],
                               (1.0, 1.5, 2.0, 2.3), is_shot=True)
        output.append({'aim': aim, 'sensors': sensors, 'rows': rows,
                       'setup_sha256': hashlib.sha256(repr(cases).encode()).hexdigest()})

    first, second = results[:2]
    _validate_drill_pairs((first, second))
    goal = (PITCH.own_goal_x(2), 0.0)
    distances = [math.dist(a.ball_start, goal) for a in first]
    rows = _compare_groups(first, second, distances, (2.0, 3.0, 4.0, 5.0), is_shot=False)
    drill = {'sensors': 'realistic', 'rows': rows,
             'setup_sha256': hashlib.sha256(repr(_drill_starts(first)).encode()).hexdigest()}
    return {'stage': 'final', 'attempts': attempts, 'seed': seed, 'gap': params.gap,
            'max_out': params.max_out, 'shots': output, 'drill': drill}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('tune', 'final'))
    parser.add_argument('--attempts', type=int, help='attempts per configuration')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--gap', type=float, choices=GAPS, default=DEFAULT_KEEPER.gap)
    parser.add_argument('--max-out', type=float, choices=MAX_OUTS, default=DEFAULT_KEEPER.max_out)
    args = parser.parse_args()
    attempts = args.attempts if args.attempts is not None else (500 if args.stage == 'tune' else 2000)
    seed = args.seed if args.seed is not None else (2501 if args.stage == 'tune' else 2503)
    if attempts < 1 or args.workers < 1:
        parser.error('--attempts and --workers must be positive')
    if args.stage == 'tune':
        result = tune(attempts, seed, args.workers)
    else:
        params = replace(DEFAULT_KEEPER, gap=args.gap, max_out=args.max_out)
        result = evaluate(attempts, seed, args.workers, params)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
