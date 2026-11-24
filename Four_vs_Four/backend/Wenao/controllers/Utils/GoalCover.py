"""Use the existing movement primitives to cover the goal before contact."""

import math

from Utils.CourseSpecs import BALL_RADIUS, GOAL_WIDTH, PITCH_LENGTH
from Utils.DefensivePlan import route, wrap
from Utils.Navigation import turn_action
from Utils.Passing import frame
from Utils.TeamPolicy import Decision, distance

GOALKEEPER_DEPTH = 4.14
GOALKEEPER_SPAN = 1.10
TRACKING_RANGE = 2.65
POSITION_TOLERANCE = .065
BODY_LIMIT_X = 4.4


def clamp(value, low, high):
    return max(low, min(high, value))


def rolling_crossing(ball, velocity, plane, deceleration):
    """Return the crossing y coordinate and time if the ball can reach x=plane."""
    vx, vy = velocity
    if abs(vx) < 1e-6:
        return None
    speed = math.hypot(vx, vy)
    fraction = (plane - ball[0]) / vx
    residual = speed * speed - 2 * deceleration * speed * fraction
    if fraction < 0 or residual < 0:
        return None
    return ball[1] + fraction * vy, (speed - math.sqrt(residual)) / deceleration


def translations(yaw, model):
    c, s = math.cos(yaw), math.sin(yaw)
    return (
        ('walk', model.walk_speed * c, model.walk_speed * s),
        ('back', -model.back_speed * c, -model.back_speed * s),
        ('step_left', -model.left_speed * s, model.left_speed * c),
        ('step_right', model.right_speed * s, -model.right_speed * c),
    )


def reachable_shot_point(own, yaw, ball, velocity, deadline, model):
    """Rank available moves by the first body contact along the rolling path."""
    vx, vy = velocity
    speed = math.hypot(vx, vy)
    radius = model.robot_radius + BALL_RADIUS
    moves = [(0., 0.), *((dx, dy) for _, dx, dy in translations(yaw, model))]
    samples = []
    for sample in range(1, 10):
        t = deadline * sample / 9
        fraction = t * (1 - .5 * model.rolling_deceleration * t / speed)
        samples.append((t, ball[0] + vx * fraction, ball[1] + vy * fraction))
    best = None
    for dx, dy in moves:
        for t, x, y in samples:
            own_x = clamp(own[0] + dx * t, -BODY_LIMIT_X, BODY_LIMIT_X)
            own_y = own[1] + dy * t
            gap = math.hypot(own_x - x, own_y - y)
            cost = (0, t, gap) if gap < radius else (1, gap, t)
            candidate = (cost, (own_x, own_y))
            if best is None or candidate < best:
                best = candidate
    point = best[1]
    gap = distance(own, point)
    if gap < .001:
        return tuple(own[:2])
    # Represent the selected primitive as a nearby body target in the replay.
    scale = .12 / gap
    return (clamp(own[0] + scale * (point[0] - own[0]), -BODY_LIMIT_X, BODY_LIMIT_X),
            own[1] + scale * (point[1] - own[1]))


class GoalCover:
    def __init__(self):
        self.defend = set()

    def adjust(self, world, decisions, model, kicking):
        match = world['match']
        if not self.defend or match['phase'] != 'PLAYING' or not match['released']:
            return decisions
        ball = world['ball']['position'][:2]
        velocity = world['ball']['velocity'][:2]
        robots = world['robots']
        for prefix, direction in (('Red', match['red_direction']), ('Blue', -match['red_direction'])):
            name = prefix + 'Goalkeeper'
            if (name not in self.defend or name not in robots or name in kicking
                    or decisions[name].behaviour in ('PENALIZED', 'WAIT')
                    or name in world.get('penalties', {}) or not robots[name].get('standing', True)):
                continue
            opponents = [robot for player, robot in robots.items() if not player.startswith(prefix)]
            if not opponents:
                continue
            opponent = min(opponents, key=lambda robot: distance(robot['position'], ball))
            order = self.choose_keeper(robots[name], ball, velocity, direction, opponent, model)
            if order is not None:
                decisions[name] = order
        return decisions

    @staticmethod
    def choose_keeper(own, ball, velocity, direction, enemy, model):
        position, yaw = own['position'], own['yaw']
        goal = -direction * PITCH_LENGTH / 2
        goal_distance = direction * (ball[0] - goal)
        ball_speed = math.hypot(*velocity)
        goalward_speed = -direction * velocity[0]
        gap = distance(position, ball)
        pressure = distance(enemy['position'], ball)
        facing = (direction, 0.)
        if goalward_speed > .055:
            crossing = rolling_crossing(ball, velocity, goal - direction * BALL_RADIUS,
                                        model.rolling_deceleration)
            if crossing and abs(crossing[0]) + BALL_RADIUS < GOAL_WIDTH / 2:
                target = reachable_shot_point(position, yaw, ball, velocity, crossing[1], model)
                return Decision('KEEPER_SHOT', target, facing)

        front, side = frame(position, ball, yaw)
        upfield = (position[0] + math.cos(yaw), position[1] + math.sin(yaw))
        # An already lined-up keeper can clear a stationary duel with a
        # normal kick. The ball must still be in the foot window at contact.
        if (goal_distance < .85 and pressure < .39 and ball_speed < .055 and gap < .45
                and .12 < front < .26 and -.023 < side < .122 and direction * math.cos(yaw) > .55):
            return Decision('KEEPER_CLEAR', tuple(ball), upfield, 'pass')

        # Give stationary or receding play back to the regular keeper policy.
        # Holding the lane indefinitely can pin the ball between two players.
        if (not .25 < goal_distance < 2.45 or goalward_speed < .01
                or (gap < .60 and goalward_speed < .015)):
            return None
        if (goal_distance < 1.15 and ball_speed < .15 and direction * math.cos(yaw) > .36
                and gap < .34 and .075 < front < .33):
            if .085 < front < .275 and abs(side) < .118:
                if .13 <= front <= .24 and -.015 <= side <= .115 and pressure > .36:
                    return Decision('KEEPER_CLEAR', tuple(ball), upfield, 'pass')
                return Decision('KEEPER_POKE', tuple(ball), upfield)
            if .10 < front < .29 and .102 <= abs(side) < .21:
                return Decision('KEEPER_ALIGN', tuple(ball), upfield)

        plane = -direction * GOALKEEPER_DEPTH
        proximity = clamp(1 - goal_distance / TRACKING_RANGE, 0., 1.)
        y = clamp(ball[1] * (.45 + .55 * proximity), -GOALKEEPER_SPAN, GOALKEEPER_SPAN)
        if pressure < .52 and direction * math.cos(enemy['yaw']) < -.56:
            edge = ball[1] + (plane - ball[0]) * math.tan(enemy['yaw'])
            if abs(edge) <= GOAL_WIDTH / 2 + .15:
                y += (clamp(edge, -GOALKEEPER_SPAN, GOALKEEPER_SPAN) - y) * .58
        if goal_distance < .82 and pressure < .78:
            behaviour = 'KEEPER_HOLD'
        else:
            behaviour = 'KEEPER_STEP' if goal_distance < 1.65 else 'KEEPER_TRACK'
        return Decision(behaviour, (plane, y), facing)


def keeper_motion(order, own, yaw, model):
    if order.behaviour == 'KEEPER_CLEAR':
        return 'pass', 'CLEAR_WHEN_IN_FOOT_WINDOW'
    if order.behaviour == 'KEEPER_ALIGN':
        _, side = frame(own, order.target, yaw)
        return ('step_left' if side > 0 else 'step_right'), 'ALIGN_KEEPER_FOOT'
    if order.behaviour == 'KEEPER_POKE':
        return 'walk', 'CLEAR_FROM_FRONT_FOOT'

    gap = distance(own, order.target)
    if gap < POSITION_TOLERANCE:
        if order.behaviour == 'KEEPER_TRACK':
            angle = wrap(math.atan2(order.face[1], order.face[0]) - yaw)
            if abs(angle) > math.radians(22):
                return turn_action(math.degrees(angle)), 'SET_KEEPER_STANCE'
        return 'stand', 'HOLD_GOAL_LANE'
    if order.behaviour == 'KEEPER_TRACK':
        _, action, _ = route(own, yaw, order.target, tolerance=.055)
        return action, 'MOVE_TO_GOAL_LANE'

    options = []
    for action, dx, dy in translations(yaw, model):
        x = clamp(own[0] + model.dt * dx, -BODY_LIMIT_X, BODY_LIMIT_X)
        y = own[1] + model.dt * dy
        options.append((distance((x, y), order.target), action))
    best, action = min(options)
    if best < gap - .0001:
        return action, 'BLOCK_WITHOUT_TURNING'
    return 'stand', 'HOLD_GOAL_LANE'
