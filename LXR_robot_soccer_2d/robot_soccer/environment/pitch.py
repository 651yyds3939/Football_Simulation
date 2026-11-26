"""Pitch and goal dimensions.

Letters A-K are the codes in Table 1 of the Project Specification. Values
marked [CHECK] are not in Table 1: confirm them from the RoboCup Humanoid
KidSize rules (RC-HL-2025) and write the source next to each one.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple


@dataclass(frozen=True)
class PitchParams:
    # Table 1, Project Specification
    length: float = 9.0               # m, A  field length (goal line to goal line)
    width: float = 6.0                # m, B  field width (touchline to touchline)
    goal_depth: float = 0.6           # m, C
    goal_width: float = 2.6           # m, D  gap between the posts' inner edges (Figure 3)
    goal_height: float = 1.2          # m, (no code) unused in 2D, kept for a future 3D ball
    goal_area_length: float = 1.0     # m, E
    goal_area_width: float = 3.0      # m, F
    penalty_mark_dist: float = 1.5    # m, G  from the goal line
    centre_circle_d: float = 1.5      # m, H
    border_width: float = 1.0         # m, I  carpet outside the lines
    penalty_area_length: float = 2.0  # m, J
    penalty_area_width: float = 5.0   # m, K

    # Not in Table 1
    post_diameter: float = 0.10       # m [CHECK] goal post diameter

    # Derived values
    @property
    def half_length(self) -> float:
        return self.length / 2

    @property
    def half_width(self) -> float:
        return self.width / 2

    @property
    def post_radius(self) -> float:
        return self.post_diameter / 2

    @property
    def post_y(self) -> float:
        """Post centres, so that the gap between the posts is goal_width."""
        return self.goal_width / 2 + self.post_radius

    def own_goal_x(self, team: int) -> float:
        """x of a team's own goal line (design choice).

        Team 1 defends x = -length/2 and attacks +x; team 2 the opposite.
        Changing ends at half time is not modelled.
        """
        return (-1 if team == 1 else 1) * self.length / 2


Post = Tuple[float, float]
Net = Tuple[float, float, float, float]


@lru_cache(maxsize=8)
def goal_geometry(pp: PitchParams) -> Tuple[Tuple[Post, ...], Tuple[Net, ...]]:
    """Goal posts and nets of both goals.

    Returns (posts, nets): post centres (x, y), and net segments
    (x1, y1, x2, y2) for the back and the two sides of each goal. The posts
    stand on the goal line and the net runs back from them by the goal depth.
    2D only: the crossbar and the ball's height are ignored.
    """
    half = pp.half_length
    yp = pp.post_y
    xb = half + pp.goal_depth
    posts: List[Post] = []
    nets: List[Net] = []
    for s in (-1, 1):
        posts += [(s * half, -yp), (s * half, yp)]
        nets += [(s * xb, -yp, s * xb, yp),       # back
                 (s * half, -yp, s * xb, -yp),    # side
                 (s * half, yp, s * xb, yp)]      # side
    return tuple(posts), tuple(nets)
