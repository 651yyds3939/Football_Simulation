"""Turns the true world into what one robot could know from its head camera."""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

from ..geometry import Vec2, is_finite, norm, wrap_angle
from .params import SensorParams
from .percept import Percept


@dataclass
class SensorState:
    """Internal sensor state of one robot."""
    next_sample: float = 0.0                         # s, time of the next image
    queue: Deque[Tuple[float, Percept]] = field(default_factory=deque)  # (release time, image)
    percept: Percept = field(default_factory=Percept)                   # latest released percept
    head_yaw: float = 0.0                            # rad, current head angle
    loc_err: Optional[Tuple[float, float, float]] = None   # self-localisation error (dx, dy, dth)
    last_sample_time: Optional[float] = None         # s, time of the last capture, before latency


def sensor_init(n_robots: int) -> List[SensorState]:
    """Create the sensor state of every robot."""
    return [SensorState() for _ in range(n_robots)]


def sensor_step(world, k: int, ss: SensorState, sp: SensorParams, dt: float,
                odom: Optional[Tuple[float, float, float]] = None, rng=random) -> Percept:
    """Update robot k's sensors for one simulation step; returns its percept.

    In 'realistic' mode a new image is taken every update_period seconds and
    its result only becomes available latency seconds later. Between updates
    the behaviour keeps using the last result. The self-localisation error
    drifts slowly (time constant loc_tau) instead of being new in every image.
    odom is the robot's odometry reading now; it is stored with each image.
    """
    t = world.t
    if sp.mode == 'perfect':
        ss.percept = perfect_percept(world, k)
        return ss.percept

    # 1) Move the head (rate limited, within the joint limits)
    ss.head_yaw = head_control(ss, sp, t, dt)

    # 2) Take an image at the vision update rate
    if t >= ss.next_sample - 1e-9:
        # Each new error keeps a share a of the old one; its spread stays sig_loc.
        sig = (sp.sig_loc_pos, sp.sig_loc_pos, sp.sig_loc_heading)
        fresh = [s * rng.gauss(0, 1) for s in sig]
        if ss.loc_err is None or ss.last_sample_time is None:
            ss.loc_err = tuple(fresh)
        else:
            elapsed = t - ss.last_sample_time
            a = math.exp(-elapsed / sp.loc_tau) if sp.loc_tau > 0 else 0.0
            ss.loc_err = tuple(a * e + math.sqrt(1 - a * a) * f
                               for e, f in zip(ss.loc_err, fresh))
        m = sense_once(world, k, ss.head_yaw, sp, ss.loc_err, rng)
        if odom is not None:
            m.odom = tuple(odom)
        ss.queue.append((t + sp.latency, m))
        ss.last_sample_time = t
        ss.next_sample += sp.update_period
        if ss.next_sample <= t:          # in case dt is larger than the period
            ss.next_sample = t + sp.update_period

    # 3) Release results whose latency has passed, oldest first
    while ss.queue and ss.queue[0][0] <= t + 1e-9:
        _, m = ss.queue.popleft()
        ss.percept = update_percept(ss.percept, m, sp)
    return ss.percept


def sense_once(world, k: int, head_yaw: float, sp: SensorParams,
               loc_err: Optional[Tuple[float, float, float]] = None, rng=random) -> Percept:
    """One camera image of robot k, turned into measurements.

    Applies the field of view, detection range, occlusion, missed detections
    and noise. Without loc_err a new random localisation error is drawn.
    """
    me = world.robots[k]
    m = Percept(t_measured=world.t, head_yaw=head_yaw)

    # Self-localisation: the robot's own pose estimate is off by loc_err
    if loc_err is None:
        loc_err = (sp.sig_loc_pos * rng.gauss(0, 1), sp.sig_loc_pos * rng.gauss(0, 1),
                   sp.sig_loc_heading * rng.gauss(0, 1))
    m.self_pos = (me.pos[0] + loc_err[0], me.pos[1] + loc_err[1])
    m.self_heading = wrap_angle(me.heading + loc_err[2])

    gaze = me.heading + head_yaw         # true direction of the camera axis

    # Ball
    vis, r, b = _detect(world.ball.pos, me.pos, gaze, sp.range_ball, sp, rng)
    if vis and sp.occlusion:
        vis = not _is_occluded(world, k, world.ball.pos, sp)
    if vis:
        r_m, b_m = _add_noise(r, b, sp, rng)
        m.ball_visible = True
        m.ball_range = r_m
        m.ball_bearing = wrap_angle(b_m + head_yaw)   # camera -> body frame
        m.ball_pos = _to_world(m.self_pos, m.self_heading, r_m, m.ball_bearing)
        m.ball_last_seen = world.t

    # Other robots (occlusion between robots is ignored)
    for j, other in enumerate(world.robots):
        if j == k:
            continue
        vis, r, b = _detect(other.pos, me.pos, gaze, sp.range_robot, sp, rng)
        if not vis:
            continue
        r_m, b_m = _add_noise(r, b, sp, rng)
        estimate = _to_world(m.self_pos, m.self_heading, r_m, wrap_angle(b_m + head_yaw))
        (m.mates if other.team == me.team else m.opponents).append(estimate)
    return m


def update_percept(prev: Percept, m: Percept, sp: SensorParams) -> Percept:
    """Combine a new measurement with the previous percept.

    If the ball is not seen in this image, the last ball estimate is kept for
    ball_memory seconds (ball_visible stays False, so the behaviour knows it
    is a remembered position, not a new observation).
    """
    if not m.ball_visible and (m.t_measured - prev.ball_last_seen) <= sp.ball_memory:
        m.ball_pos = prev.ball_pos
        m.ball_last_seen = prev.ball_last_seen
    return m


def perfect_percept(world, k: int) -> Percept:
    """Percept with the true state: the baseline for experiments."""
    me = world.robots[k]
    d = (world.ball.pos[0] - me.pos[0], world.ball.pos[1] - me.pos[1])
    p = Percept(t_measured=world.t, self_pos=me.pos, self_heading=me.heading,
                ball_visible=True, ball_range=norm(d),
                ball_bearing=wrap_angle(math.atan2(d[1], d[0]) - me.heading),
                ball_pos=world.ball.pos, ball_last_seen=world.t)
    for j, other in enumerate(world.robots):
        if j != k:
            (p.mates if other.team == me.team else p.opponents).append(other.pos)
    return p


def head_control(ss: SensorState, sp: SensorParams, t: float, dt: float) -> float:
    """Simple default head motion.

    If the ball was seen in the last track_time seconds, turn the head towards
    its estimated position; otherwise sweep left and right. The head turns at
    most head_speed and stays within the joint limit.
    """
    p = ss.percept
    if (t - p.ball_last_seen) <= sp.track_time and is_finite(p.ball_pos):
        d = (p.ball_pos[0] - p.self_pos[0], p.ball_pos[1] - p.self_pos[1])
        target = wrap_angle(math.atan2(d[1], d[0]) - p.self_heading)
    else:
        target = sp.scan_amp * math.sin(2 * math.pi * t / sp.scan_period)
    target = max(-sp.head_yaw_max, min(sp.head_yaw_max, target))
    step = max(-sp.head_speed * dt, min(sp.head_speed * dt, target - ss.head_yaw))
    return ss.head_yaw + step


def _detect(target: Vec2, pos: Vec2, gaze: float, max_range: float, sp: SensorParams, rng):
    """Is the target in view? Returns (visible, true distance, bearing from the camera axis)."""
    d = (target[0] - pos[0], target[1] - pos[1])
    r = norm(d)
    b = wrap_angle(math.atan2(d[1], d[0]) - gaze)
    visible = (sp.min_range <= r <= max_range and abs(b) <= sp.fov_h / 2
               and rng.random() >= sp.p_miss)
    return visible, r, b


def _add_noise(r: float, b: float, sp: SensorParams, rng):
    """Range noise grows with distance; bearing noise is constant."""
    r_m = max(0.0, r + (sp.sig_range_rel * r + sp.sig_range_abs) * rng.gauss(0, 1))
    return r_m, b + sp.sig_bearing * rng.gauss(0, 1)


def _to_world(self_pos: Vec2, self_heading: float, r: float, bearing_body: float) -> Vec2:
    """Body-frame (range, bearing) to world frame, using the noisy own pose."""
    a = self_heading + bearing_body
    return (self_pos[0] + r * math.cos(a), self_pos[1] + r * math.sin(a))


def _is_occluded(world, k: int, target: Vec2, sp: SensorParams) -> bool:
    """True if another robot stands on the line from robot k to the target."""
    p0 = world.robots[k].pos
    v = (target[0] - p0[0], target[1] - p0[1])
    length2 = v[0] * v[0] + v[1] * v[1]
    if length2 == 0:
        return False
    for j, other in enumerate(world.robots):
        if j == k:
            continue
        c = other.pos
        s = ((c[0] - p0[0]) * v[0] + (c[1] - p0[1]) * v[1]) / length2   # position along the line
        if 0 < s < 1 and norm((p0[0] + s * v[0] - c[0], p0[1] + s * v[1] - c[1])) < sp.robot_radius:
            return True
    return False
