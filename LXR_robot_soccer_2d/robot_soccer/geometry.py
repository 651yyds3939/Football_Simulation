"""Vector and angle helpers shared by every module.

Vectors are (x, y) tuples. World frame: origin at the pitch centre, x along
the pitch length, y to the left; metres and radians, anticlockwise positive.
"""
from __future__ import annotations

import math
from typing import Iterable, Tuple

Vec2 = Tuple[float, float]


def wrap_angle(a: float) -> float:
    """Wrap an angle to the interval [-pi, pi)."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def add(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def scale(a: Vec2, k: float) -> Vec2:
    return (a[0] * k, a[1] * k)


def dot(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def norm(a: Vec2) -> float:
    return math.hypot(a[0], a[1])


def sign(x: float) -> float:
    """-1, 0 or +1."""
    return float((x > 0) - (x < 0))


def sign_or_one(x: float) -> float:
    """Like sign, but 0 counts as +1."""
    return sign(x) or 1.0


def is_finite(values: Iterable[float]) -> bool:
    return all(math.isfinite(v) for v in values)


def to_body(v_world: Vec2, heading: float) -> Vec2:
    """Turn a world-frame vector into the robot's own frame (x forward, y left)."""
    c = math.cos(heading)
    s = math.sin(heading)
    return (c * v_world[0] + s * v_world[1], -s * v_world[0] + c * v_world[1])
