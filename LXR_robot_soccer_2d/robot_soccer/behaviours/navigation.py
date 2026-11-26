"""Local waypoint navigation using players seen by this robot."""
from __future__ import annotations

import math
from heapq import heappop, heappush

from ..environment.pitch import PitchParams
from ..geometry import Vec2, add, dot, is_finite, norm, scale, sub
from ..robot.motion import RobotParams, WalkCmd
from ..sensors.percept import Percept
from .approach import walk_to

CLEARANCE_MARGIN = 0.10  # m beyond the two robot radii, design assumption
GEOMETRY_TOLERANCE = 1e-9
RING_DIRECTIONS = tuple((math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i in range(8))


def _segment_distance(point: Vec2, start: Vec2, end: Vec2) -> float:
    segment = sub(end, start)
    length2 = dot(segment, segment)
    if length2 == 0:
        return norm(sub(point, start))
    along = max(0.0, min(1.0, dot(sub(point, start), segment) / length2))
    return norm(sub(point, add(start, scale(segment, along))))


def _clear_leg(start: Vec2, end: Vec2, obstacle: Vec2, clearance: float) -> bool:
    offset = sub(start, obstacle)
    if norm(offset) < clearance - GEOMETRY_TOLERANCE:
        # If already threatened, moving away or tangentially must be possible.
        # A non-negative initial derivative means distance never decreases
        # along this straight segment, including when the estimate overlaps us.
        return dot(offset, sub(end, start)) >= -GEOMETRY_TOLERANCE
    return _segment_distance(obstacle, start, end) >= clearance - GEOMETRY_TOLERANCE


def _local_step(start: Vec2, target: Vec2, obstacles: list[Vec2], clearance: float,
                max_x: float, max_y: float) -> Vec2:
    """Make safe local progress when no single waypoint can connect to the target."""
    dx, dy = sub(target, start)
    heading = math.atan2(dy, dx)
    direct_distance = norm((dx, dy))
    nearby = [obstacle for obstacle in obstacles if math.dist(start, obstacle) < clearance - GEOMETRY_TOLERANCE]
    candidates = []
    for length in (0.30, 0.12, 0.04):
        for offset in (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90,
                       105, -105, 120, -120, 135, -135, 150, -150, 165, -165, 180):
            angle = heading + math.radians(offset)
            point = add(start, (length * math.cos(angle), length * math.sin(angle)))
            if abs(point[0]) > max_x or abs(point[1]) > max_y:
                continue
            if not all(_clear_leg(start, point, obstacle, clearance) for obstacle in obstacles):
                continue
            remaining = math.dist(target, point)
            # When starting too close, a retreat may be necessary before a
            # forward path opens. Otherwise require progress to avoid wandering
            # around a blocked destination.
            if nearby or remaining < direct_distance - GEOMETRY_TOLERANCE:
                candidates.append(point)
    if nearby and candidates:
        return max(candidates, key=lambda point: (min(math.dist(point, pos) for pos in nearby),
                                                  -math.dist(target, point)))
    return min(candidates, key=lambda point: math.dist(target, point), default=start)


def _detour(start: Vec2, target: Vec2, obstacles: list[Vec2], clearance: float,
            max_x: float, max_y: float) -> Vec2 | None:
    """Find the first waypoint of a short route around one or more players."""
    nodes = [start, target]
    # Adjacent ring points can be joined without cutting into the clearance
    # circle. Extra room allows for replanning while the robot is moving.
    for obstacle in obstacles:
        for direction in RING_DIRECTIONS:
            point = add(obstacle, scale(direction, 1.17 * clearance))
            if (abs(point[0]) <= max_x and abs(point[1]) <= max_y
                    and all(math.dist(point, other) >= clearance for other in obstacles)):
                nodes.append(point)

    queue = [(math.dist(start, target), 0.0, 0, 0)]
    best = {0: 0.0}
    while queue:
        _, travelled, index, first = heappop(queue)
        if travelled > best[index]:
            continue
        if index == 1:
            return nodes[first]
        current = nodes[index]
        for next_index in range(1, len(nodes)):
            point = nodes[next_index]
            distance = math.dist(current, point)
            new_total = travelled + distance
            if distance < GEOMETRY_TOLERANCE or new_total >= best.get(next_index, math.inf):
                continue
            if all(_clear_leg(current, point, obstacle, clearance) for obstacle in obstacles):
                best[next_index] = new_total
                heappush(queue, (new_total + math.dist(point, target), new_total,
                                 next_index, first if index else next_index))
    return None


def navigate_to(p: Percept, target: Vec2, face: float, *, pp: PitchParams, rp: RobotParams) -> WalkCmd:
    """Go straight when clear; otherwise look for a waypoint beside the blocker."""
    if not is_finite((*p.self_pos, p.self_heading, *target, face)):
        return WalkCmd()
    start = p.self_pos
    max_x = pp.half_length - rp.radius
    max_y = pp.half_width - rp.radius
    target = (max(-max_x, min(max_x, target[0])), max(-max_y, min(max_y, target[1])))
    obstacles = [pos for pos in (*p.mates, *p.opponents) if is_finite(pos)]
    clearance = 2 * rp.radius + CLEARANCE_MARGIN
    blockers = [pos for pos in obstacles if not _clear_leg(start, target, pos, clearance)]
    if not blockers:
        return walk_to(p, target, face)

    direction = sub(target, start)
    distance = norm(direction)
    if distance == 0:
        return walk_to(p, start, face)
    side = scale((-direction[1], direction[0]), 1 / distance)
    blocker = min(blockers, key=lambda pos: norm(sub(pos, start)))

    waypoints = []
    for width in (1.5, 2.0, 3.0):
        for sign in (1, -1):
            point = add(blocker, scale(side, sign * width * clearance))
            if abs(point[0]) > max_x or abs(point[1]) > max_y:
                continue
            if all(_clear_leg(start, point, pos, clearance)
                   and _clear_leg(point, target, pos, clearance) for pos in obstacles):
                waypoints.append(point)

    if not waypoints:
        if all(math.dist(target, pos) >= clearance for pos in obstacles):
            detour = _detour(start, target, obstacles, clearance, max_x, max_y)
            if detour is not None:
                return walk_to(p, detour, face)
        return walk_to(p, _local_step(start, target, obstacles, clearance, max_x, max_y), face)
    waypoint = min(waypoints, key=lambda point: math.dist(start, point) + math.dist(point, target))
    return walk_to(p, waypoint, face)
