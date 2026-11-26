"""Send the ball off in seven situations and show what happens.

Run from the code/python folder:
  python3 -m robot_soccer.simulations.demo_pitch_ball             results only
  .venv/bin/python -m robot_soccer.simulations.demo_pitch_ball --plot
  .venv/bin/python -m robot_soccer.simulations.demo_pitch_ball --save pitch_ball.png

The robots stand still in the example formation from world_init. Each
situation starts with the ball moving, as if just kicked, and runs until the
ball stops or a rule applies (goal or ball out of play).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..environment.ball import BallParams
from ..environment.pitch import PitchParams
from ..environment.referee import Event, Restart
from ..environment.world import world_init, world_step
from ..geometry import Vec2, norm

# name, start, aimed at, speed (m/s), last touched by team
SCENARIOS = (
    ('shot into the goal', (2.0, 0.5), (4.5, 1.0), 3.0, 1),
    ('shot blocked by the goalkeeper', (2.0, -0.3), (4.5, 0.0), 3.0, 1),
    ('shot against the post', (3.4, -0.2), (4.5, -1.35), 2.5, 1),
    ('pass out over the touchline', (-1.0, 1.5), (0.5, 3.5), 3.0, 1),
    ('long pass that stops', (-3.5, -2.2), (0.0, -2.2), 2.5, 1),
    ('attacker sends it over the goal line', (-2.5, 2.0), (-4.5, 2.6), 2.5, 2),
    ('defender clears it over own goal line', (-3.5, 1.8), (-4.6, 2.2), 2.5, 1),
)


@dataclass
class DemoResult:
    name: str
    path: List[Vec2]
    event: Optional[Event]
    restart: Optional[Restart]
    outcome: str


def demo_pitch_ball(verbose: bool = True) -> List[DemoResult]:
    pp = PitchParams()
    bp = BallParams()
    dt = 0.02
    results = []
    for name, start, aim, speed, last_team in SCENARIOS:
        w = world_init(pp)
        d = (aim[0] - start[0], aim[1] - start[1])
        w.ball.pos = start
        w.ball.vel = (speed * d[0] / norm(d), speed * d[1] / norm(d))
        w.ball.last_touch_team = last_team
        path = [w.ball.pos]
        event = None
        for _ in range(round(10 / dt)):
            event = world_step(w, pp, bp, dt)
            if event is not None:
                path.append(event.pos)
                break
            path.append(w.ball.pos)
            if w.ball.vel == (0.0, 0.0):
                break
        if event is None:
            outcome = f'stopped at ({w.ball.pos[0]:.2f}, {w.ball.pos[1]:.2f}) after {w.t:.1f} s'
            restart = None
        else:
            restart = w.restart
            outcome = (f'{event.type} at {event.t:.1f} s -> {restart.type} for team {restart.team} '
                       f'at ({restart.pos[0]:.2f}, {restart.pos[1]:.2f})')
        results.append(DemoResult(name, path, event, restart, outcome))
    if verbose:
        print('\nBall model demo')
        for r in results:
            print(f'  {r.name:<40s} {r.outcome}')
        print()
    return results


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Ball model demo.')
    parser.add_argument('--plot', action='store_true', help='show the figure')
    parser.add_argument('--save', metavar='FILE.png', help='save the figure')
    args = parser.parse_args()
    results = demo_pitch_ball()
    if args.plot or args.save:
        import matplotlib
        if not args.plot:
            matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ..visual.plots import figure_pitch_ball_demo
        fig = figure_pitch_ball_demo(results, PitchParams(), BallParams(), plt.figure)
        if args.save:
            fig.savefig(args.save, dpi=130)
            print(f'saved {args.save}')
        if args.plot:
            plt.show()


if __name__ == '__main__':
    main()
