"""The true world state and one simulation step of the ball and rules."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from ..geometry import Vec2, sign
from .ball import Ball, BallParams, ball_step
from .pitch import PitchParams
from .referee import Event, Restart, referee_step


@dataclass
class Robot:
    pos: Vec2
    heading: float
    team: int
    vel: Vec2 = (0.0, 0.0)   # m/s, set by the robot motion model


@dataclass
class World:
    t: float = 0.0
    ball: Ball = field(default_factory=Ball)
    robots: List[Robot] = field(default_factory=list)
    score: List[int] = field(default_factory=lambda: [0, 0])     # [team 1, team 2]
    restart: Restart = field(default_factory=lambda: Restart('kickoff', 1, (0.0, 0.0)))
    events: List[Event] = field(default_factory=list)


def world_init(pp: Optional[PitchParams] = None) -> World:
    """World at kick-off: ball on the centre mark, two teams of four.

    The start positions are only an example formation (design choice):
    a goalkeeper, two defenders and a striker per team, in their own half.
    """
    pp = pp or PitchParams()
    formation = [(-(pp.half_length - 0.3), 0.0),   # goalkeeper
                 (-3.0, -1.0),                     # defender
                 (-3.0, 1.0),                      # defender
                 (-1.0, 0.0)]                      # striker
    robots = []
    for team in (1, 2):
        s = -sign(pp.own_goal_x(team))             # +1 if this team attacks +x
        heading = (1 - s) / 2 * math.pi            # face the opponents' goal
        robots += [Robot((s * x, y), heading, team) for x, y in formation]
    return World(robots=robots)


def world_step(world: World, pp: PitchParams, bp: BallParams, dt: float) -> Optional[Event]:
    """Move the ball and apply the rules for one time step.

    Call this once per step, after the robots have been moved and any kicks
    applied. Returns an event if a goal was scored or the ball went out of play.
    """
    ball_step(world.ball, world.robots, pp, bp, dt)
    world.t += dt
    return referee_step(world, pp, bp)
