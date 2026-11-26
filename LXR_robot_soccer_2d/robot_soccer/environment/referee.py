"""Match rules applied after the ball has moved.

Lines marked [RULE] are a simplified reading of the RoboCup Humanoid KidSize
rules. Check each one against RC-HL-2025 and write the result in the team's
adopted rules list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..geometry import Vec2, sign
from .ball import BallParams
from .pitch import PitchParams


@dataclass
class Event:
    t: float
    type: str    # 'goal', 'out_goal_line' or 'out_touchline'
    team: int    # the team that scores or is given the restart (0 = undecided)
    pos: Vec2    # where the ball was when the rule applied


@dataclass
class Restart:
    type: str    # 'kickoff', 'corner_kick', 'goal_kick' or 'throw_in'
    team: int
    pos: Vec2
    t: float = 0.0


def referee_step(world, pp: PitchParams, bp: BallParams) -> Optional[Event]:
    """Check whether the whole ball has crossed a goal line or a touchline.

    If it has, record the event, update the score, place the ball for the
    restart and stop it. Returns None while play continues.
    """
    x, y = world.ball.pos
    r = bp.radius
    half_l = pp.half_length
    half_w = pp.half_width
    last = world.ball.last_touch_team

    if abs(x) > half_l + r:
        side = sign(x)                                      # which goal line
        defending = 1 if sign(pp.own_goal_x(1)) == side else 2
        attacking = 3 - defending
        if abs(y) < pp.goal_width / 2:
            # [RULE] Goal: the whole ball is over the goal line between the posts.
            # The team that conceded kicks off from the centre mark.
            world.score[attacking - 1] += 1
            event = Event(world.t, 'goal', attacking, (x, y))
            restart = Restart('kickoff', defending, (0.0, 0.0))
        elif last == defending:
            # [RULE] Corner kick: a defender touched it last. Ball to the
            # corner on the side where it went out.
            event = Event(world.t, 'out_goal_line', attacking, (x, y))
            restart = Restart('corner_kick', attacking, (side * half_l, sign(y) * half_w))
        else:
            # [RULE] Goal kick: an attacker (or nobody) touched it last. Ball to
            # the corner of the goal area on the side where it went out.
            event = Event(world.t, 'out_goal_line', defending, (x, y))
            restart = Restart('goal_kick', defending,
                              (side * (half_l - pp.goal_area_length),
                               sign(y) * pp.goal_area_width / 2))
    elif abs(y) > half_w + r:
        # [RULE] Throw-in: the other team restarts, with the ball on the
        # touchline where it went out.
        team = 0 if last == 0 else 3 - last
        event = Event(world.t, 'out_touchline', team, (x, y))
        restart = Restart('throw_in', team, (max(-half_l, min(half_l, x)), sign(y) * half_w))
    else:
        return None                                         # ball in play

    restart.t = world.t
    world.restart = restart
    world.ball.pos = restart.pos
    world.ball.vel = (0.0, 0.0)
    world.ball.last_touch_team = 0
    world.ball.last_touch_robot = None
    world.events.append(event)
    return event
