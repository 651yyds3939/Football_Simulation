"""The percept: the interface between the sensor layer and the behaviours.

Behaviours must read only these fields, never the true world state. Bearings
are measured from the robot body's forward direction, positive anticlockwise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from ..geometry import Vec2

NAN = math.nan


@dataclass
class Percept:
    t_measured: float = -math.inf     # s, time of the image this percept comes from
    self_pos: Vec2 = (NAN, NAN)       # m, estimated own position (world frame)
    self_heading: float = NAN         # rad, estimated own heading (world frame)
    head_yaw: float = 0.0             # rad, head angle when the image was taken
    # odometry reading (x, y, theta) when the image was taken
    odom: Tuple[float, float, float] = (NAN, NAN, NAN)

    ball_visible: bool = False        # True only if the ball was seen in this image
    ball_range: float = NAN           # m, measured distance (this image only)
    ball_bearing: float = NAN         # rad, measured bearing from body forward
    ball_pos: Vec2 = (NAN, NAN)       # m, estimated position; kept from memory for ball_memory s
    ball_last_seen: float = -math.inf # s, time the ball was last seen

    mates: List[Vec2] = field(default_factory=list)      # estimated team-mate positions
    opponents: List[Vec2] = field(default_factory=list)  # estimated opponent positions
