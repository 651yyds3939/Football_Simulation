"""Explicit combined 2D translations used by the tactical simulator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanarMotion:
    label: str
    forward: float
    lateral: float
    angular: float
