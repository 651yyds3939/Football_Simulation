"""Clip planar robot moves at first body contact."""

import math


def stop_conflicting_moves(names, players, proposed, diameter):
    """Keep actual displacement on each player's own commanded segment.

    An idle robot has a zero-length segment. An active robot can move away
    or along a tangent, including when it starts in contact.
    """
    vectors = {}
    for name in names:
        x, y = players[name]["position"][:2]
        vectors[name] = proposed[name][0] - x, proposed[name][1] - y
    nearby = []
    for i, a in enumerate(names):
        ax, ay = players[a]["position"][:2]
        for b in names[i + 1 :]:
            bx, by = players[b]["position"][:2]
            dx, dy = ax - bx, ay - by
            limit = diameter + math.hypot(*vectors[a]) + math.hypot(*vectors[b])
            if dx * dx + dy * dy <= limit * limit:
                nearby.append((a, b, dx, dy))

    fractions = dict.fromkeys(names, 1.0)
    blocked = set()
    for _ in range(5):
        updates = fractions.copy()
        for a, b, dx, dy in nearby:
            fa, fb = fractions[a], fractions[b]
            adx, ady = vectors[a][0] * fa, vectors[a][1] * fa
            bdx, bdy = vectors[b][0] * fb, vectors[b][1] * fb
            vx, vy = adx - bdx, ady - bdy
            hit = collision_time(dx, dy, vx, vy, diameter)
            if hit is None:
                continue
            nx, ny = dx + vx * hit, dy + vy * hit
            if nx * adx + ny * ady < -1e-12:
                updates[a] = min(updates[a], fa * hit)
                blocked.add(a)
            if nx * bdx + ny * bdy > 1e-12:
                updates[b] = min(updates[b], fb * hit)
                blocked.add(b)
        if updates == fractions:
            break
        fractions = updates

    # Shortening a move elsewhere can remove a gap that a second mover
    # expected. Recheck the resulting segments and stop any remaining
    # inward moves instead of displacing the other robot.
    for _ in names:
        offenders = set()
        for a, b, dx, dy in nearby:
            adx, ady = (v * fractions[a] for v in vectors[a])
            bdx, bdy = (v * fractions[b] for v in vectors[b])
            vx, vy = adx - bdx, ady - bdy
            hit = collision_time(dx, dy, vx, vy, diameter)
            if hit is None:
                continue
            nx, ny = dx + vx * hit, dy + vy * hit
            if nx * adx + ny * ady < -1e-12:
                offenders.add(a)
            if nx * bdx + ny * bdy > 1e-12:
                offenders.add(b)
        if not offenders:
            break
        for name in offenders:
            fractions[name] = 0.0
        blocked.update(offenders)

    for name in blocked:
        x, y = players[name]["position"][:2]
        dx, dy = vectors[name]
        fraction = fractions[name]
        proposed[name][:2] = x + fraction * dx, y + fraction * dy
    return blocked


def collision_time(dx, dy, vx, vy, diameter):
    """First inward crossing of the body boundary on a relative move."""
    approach = dx * vx + dy * vy
    delta = vx * vx + vy * vy
    if approach >= -1e-12 or delta <= 1e-18:
        return None
    clearance = dx * dx + dy * dy - diameter * diameter
    if clearance <= 1e-12:
        return 0.0
    root = approach * approach - delta * clearance
    if root <= 1e-15:
        return None
    hit = clearance / (-approach + math.sqrt(root))
    return hit if hit < 1 - 1e-8 else None


def foot_entry(origin, movement, position, yaw):
    """Find the first point of the rolling segment in the forward foot window."""
    c, s = math.cos(yaw), math.sin(yaw)
    dx, dy = origin[0] - position[0], origin[1] - position[1]
    vx, vy = movement
    projections = (
        (dx * c + dy * s, vx * c + vy * s, 0.09, 0.295),
        (-dx * s + dy * c, -vx * s + vy * c, -0.112, 0.112),
    )
    enter, leave = 0.0, 1.0
    for loc, step, low, high in projections:
        if abs(step) < 1e-12:
            if not low <= loc <= high:
                return None
            continue
        near, far = sorted(((low - loc) / step, (high - loc) / step))
        enter, leave = max(enter, near), min(leave, far)
        if enter > leave:
            return None
    return enter
