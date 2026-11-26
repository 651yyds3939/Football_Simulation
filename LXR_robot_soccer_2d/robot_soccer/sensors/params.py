"""Parameters of the NAO6 sensor representation.

Sources, baseline assumptions and design choices are listed in docs/sensor_design.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorParams:
    # 'perfect' = behaviours read the true state (baseline for experiments)
    # 'realistic' = limited view, noise, delay
    mode: str = 'realistic'

    # Camera and head (only the NAO6 top head camera is modelled)
    fov_h: float = 56.3 * math.pi / 180         # rad, NAO V6 CameraTop horizontal FOV (NAOqi 2.8)
    head_yaw_max: float = 119.5 * math.pi / 180 # rad, NAO V6 HeadYaw limit (NAOqi 2.8)
    head_speed: float = 180 * math.pi / 180    # rad/s, simulated command cap; actual rate unmeasured
    scan_amp: float = 90 * math.pi / 180        # rad, head sweep when ball lost (design choice)
    scan_period: float = 4.0                    # s, one full sweep (design choice)
    track_time: float = 1.0                     # s, keep looking at a recent ball (design choice)

    # Detection range (depends on the vision software, not only the camera)
    range_ball: float = 4.0     # m, baseline assumption for the ball detector
    range_robot: float = 6.0    # m, baseline assumption for the player detector
    min_range: float = 0.10     # m, design choice for the missing near-field view, used for all targets

    # Measurement noise
    sig_range_rel: float = 0.05             # baseline assumption: distance-dependent part of range noise
    sig_range_abs: float = 0.03             # m, baseline assumption: constant part of range noise
    sig_bearing: float = 2 * math.pi / 180  # rad, baseline assumption: bearing noise std
    p_miss: float = 0.05                    # baseline assumption: per-frame miss probability in view

    # Timing
    update_period: float = 0.1  # s, assumed nominal vision update interval; not raw camera frame rate
    latency: float = 0.1        # s, assumed delay from capture to result

    # Self-localisation (the robot's estimate of its own pose)
    sig_loc_pos: float = 0.10                   # m, assumed position error std per axis
    sig_loc_heading: float = 5 * math.pi / 180  # rad, assumed heading error std
    loc_tau: float = 2.0  # s, assumed drift time constant; 0 = independent errors per image

    # Occlusion and memory
    occlusion: bool = True      # other robots can hide the ball (design choice)
    robot_radius: float = 0.155 # m, half of the larger body dimension: 311 mm,
                                #    which the NAO6 datasheet calls depth (width is 275 mm)
    ball_memory: float = 3.0    # s, keep the last ball estimate this long (design choice)
