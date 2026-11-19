"""Repeatable rectangular spawn regions for the planar 1v1 exercise."""
from dataclasses import dataclass, asdict
import math
import random


@dataclass(frozen=True)
class SpawnZones:
    # Bounds are [minimum x, maximum x, minimum y, maximum y], in metres.
    attacker: tuple = (-1., 1., -1.1, 1.1)
    defender: tuple = (1.8, 3.2, -1.25, 1.25)
    goal_side_margin: float = .25

    def __post_init__(self):
        for role in ('attacker', 'defender'):
            bounds = getattr(self, role)
            if len(bounds) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                       or not math.isfinite(v) for v in bounds):
                raise ValueError(role+' bounds must contain four finite numbers')
            x0, x1, y0, y1 = bounds
            if not (-4.25 <= x0 < x1 <= 4.25 and -2.65 <= y0 < y1 <= 2.65):
                raise ValueError(role+' rectangle must be inside the pitch')
            if x1-x0 < .1 or y1-y0 < .1:
                raise ValueError(role+' rectangle must be at least 0.10 m wide and high')
        if (isinstance(self.goal_side_margin, bool) or not isinstance(self.goal_side_margin, (int, float))
                or not math.isfinite(self.goal_side_margin) or not .05 <= self.goal_side_margin <= 1.):
            raise ValueError('Goal-side margin must be between 0.05 and 1.00 m')

    @classmethod
    def parse(cls, value=None):
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict) or set(value)-{'attacker', 'defender', 'goal_side_margin'}:
            raise ValueError('Unknown spawn-zone setting')
        data = dict(value)
        for role in ('attacker', 'defender'):
            if role in data:
                if not isinstance(data[role], (list, tuple)):
                    raise ValueError(role+' rectangle must be a list of four bounds')
                data[role] = tuple(data[role])
        return cls(**data)

    def dictionary(self):
        return asdict(self)

    def sample(self, seed, ball_radius=.07):
        rng = random.Random(seed)
        goal = (4.5, 0.)
        ax0, ax1, ay0, ay1 = self.attacker
        dx0, dx1, dy0, dy1 = self.defender
        for _ in range(1024):
            ax, ay = rng.uniform(ax0, ax1), rng.uniform(ay0, ay1)
            yaw = math.atan2(-ay, 4.8-ax)+rng.uniform(-.06, .06)
            front, lateral = rng.uniform(.27, .31), .025
            ball = [ax+front*math.cos(yaw)-lateral*math.sin(yaw),
                    ay+front*math.sin(yaw)+lateral*math.cos(yaw), ball_radius]
            dx, dy = rng.uniform(dx0, dx1), rng.uniform(dy0, dy1)
            if (abs(ball[0]) > 4.35 or abs(ball[1]) > 2.8
                    or dx < ball[0]+.20 or math.dist((dx, dy), ball[:2]) < .32
                    or math.dist((dx, dy), (ax, ay)) < .34):
                continue
            if math.dist((dx, dy), goal)+self.goal_side_margin > min(
                    math.dist((ax, ay), goal), math.dist(ball[:2], goal)):
                continue
            return {'ball': ball, 'robots': {
                'RedForwardA': {'position': [ax, ay, .334], 'yaw': yaw},
                'BlueDefender': {'position': [dx, dy, .334],
                                 'yaw': math.atan2(ball[1]-dy, ball[0]-dx)}}}
        raise ValueError('These rectangles cannot produce a valid goal-side defender. '
                         'Move the defender region nearer the right goal or reduce lateral separation.')
