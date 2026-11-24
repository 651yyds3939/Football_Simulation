"""Select short passes that a teammate can receive facing the attack."""
import math

from Utils.CourseSpecs import PITCH_LENGTH, PITCH_WIDTH, BALL_RADIUS
from Utils.DefensivePlan import route, wrap
from Utils.TeamPolicy import Decision, distance, lane_clear
from Utils.TeamTactics import TacticalPolicy

SETTINGS = {
    'lead_pass': True,
    'open_support': True,
    'defender_carry': True,
    'defender_carry_x': -1.2,
    'defender_pressure': .65,
    'discard_unreachable': True,
    'receive_eta': 11.,
    'receiver_radius': .95,
    'pressure': .65,
    'sender_angles': [-24, -12, 0, 12, 24],
    'face_options': [-55, -30, 0, 30, 55],
    'interception_buffer': .28,
    'allow_backwards_pass': True,
}


def bearing(origin, target):
    return math.atan2(target[1] - origin[1], target[0] - origin[0])


def offset(origin, heading, amount):
    return origin[0] + amount * math.cos(heading), origin[1] + amount * math.sin(heading)


def frame(origin, point, heading):
    dx, dy = point[0] - origin[0], point[1] - origin[1]
    c, s = math.cos(heading), math.sin(heading)
    return dx * c + dy * s, -dx * s + dy * c


def foot_can_push(origin, point, yaw):
    forward, side = frame(origin, point, yaw)
    return .08 < forward < .275 and abs(side) < .11


class PassingPolicy(TacticalPolicy):
    def __init__(self, name, *, model, **kwargs):
        super().__init__(name, **kwargs)
        self.model = model
        self.receive_until = -1.
        self.prepared_pass = None

    def attack(self, own, ball, direction, teammates, opponents, context=""):
        if SETTINGS['discard_unreachable'] and not context:
            limit = self.model.pass_range + .15
            teammates = {name: pose for name, pose in teammates.items()
                         if name == self.name or distance(pose, ball) <= limit}
        result = super().attack(own, ball, direction, teammates, opponents, context)
        if (SETTINGS['defender_carry'] and result.behaviour == 'CLEAR' and self.role == 'defender'
                and direction * ball[0] > SETTINGS['defender_carry_x']
                and min((distance(ball, p) for p in opponents), default=2.) > SETTINGS['defender_pressure']):
            goal = (direction * (PITCH_LENGTH / 2 + self.goal_depth), 0.)
            return Decision('DRIBBLE', offset(ball, bearing(ball, goal), -.19), goal)
        return result

    def decide(self, world):
        normal = super().decide(world)
        match = world['match']
        if match['phase'] != 'PLAYING' or not match['released'] or normal.behaviour == 'PENALIZED':
            self.receive_until = -1.
            self.prepared_pass = None
            return normal

        robots = world['robots']
        own = robots[self.name]
        point = own['position']
        ball = world['ball']['position'][:2]
        direction = match['red_direction'] * (1 if self.team == 'RED' else -1)
        goal = (direction * PITCH_LENGTH / 2, 0.)
        intent = world.get('pass_intent')
        if intent and intent['expires'] > world['time'] and intent['sender'].startswith(self.prefix):
            if intent['receiver'] == self.name and intent.get('stance') and distance(point, ball) < 1.2:
                return self.receive(world, intent, ball)
            return normal
        if (world['time'] < self.receive_until and match.get('last_touch') == self.name
                and world.get('last_foot_contact') == self.name):
            error = abs(wrap(own['yaw'] - bearing(ball, goal)))
            if error <= math.radians(60) and foot_can_push(point, ball, own['yaw']):
                return Decision('ADVANCE_FROM_PASS', tuple(ball), offset(ball, own['yaw'], 1.))
        if SETTINGS['open_support'] and normal.behaviour == 'FIND_PASS_LANE':
            return Decision('OPEN_SUPPORT', normal.target, offset(normal.target, bearing(ball, goal), 1.))
        if (not SETTINGS['lead_pass'] or normal.behaviour not in (
                'DRIBBLE', 'EVADE_DRIBBLE', 'CLEAR', 'CHALLENGE', 'PASS', 'COORDINATED_PASS')
                or distance(point, ball) >= .34 or math.hypot(*world['ball']['velocity'][:2]) > .11):
            self.prepared_pass = None
            return normal

        opponents = [robot['position'] for name, robot in robots.items() if not name.startswith(self.prefix)]
        pressure = min((distance(ball, p) for p in opponents), default=2.)
        if pressure < SETTINGS['pressure']:
            self.prepared_pass = None
            return normal
        if self.prepared_pass is not None:
            previous, anchor, expires = self.prepared_pass
            receiver = robots[previous.receiver]
            if (world['time'] < expires and distance(ball, anchor) < .05
                    and distance(receiver['position'], previous.receive_stance) < .48
                    and lane_clear(ball, previous.face, opponents, SETTINGS['interception_buffer'])):
                return previous
            self.prepared_pass = None
        plan = self.choose_pass(world, own, ball, opponents, goal, direction)
        if plan is None:
            return normal
        self.prepared_pass = (plan, tuple(ball), world['time'] + 3.5)
        return plan

    def receive(self, world, intent, ball):
        target = intent['stance']
        heading = intent['heading']
        released = intent['stage'] == 'released'
        if released:
            vx, vy = world['ball']['velocity'][:2]
            factor = math.hypot(vx, vy) / (2 * self.model.rolling_deceleration)
            predicted = (ball[0] + vx*factor, ball[1] + vy*factor)
            correction = min(1., .13 / max(distance(predicted, intent['landing']), 1e-9))
            target = tuple(target[i] + correction*(predicted[i]-intent['landing'][i]) for i in range(2))
            self.receive_until = world['time'] + 5.
        return Decision('RECEIVE_FORWARD' if released else 'PREPARE_FORWARD', target, offset(target, heading, 1.))

    def choose_pass(self, world, own, ball, opponents, goal, direction):
        players = world['robots']
        circle = self.model.robot_radius + BALL_RADIUS
        turn_rate = min(self.model.left_turn, self.model.right_turn)
        choices = []
        for name, robot in players.items():
            point = robot['position']
            if (name == self.name or not name.startswith(self.prefix) or 'Goalkeeper' in name
                    or name in world.get('penalties', {}) or not robot.get('standing', True)
                    or not .28 <= distance(ball, point) <= SETTINGS['receiver_radius']):
                continue
            for angle in SETTINGS['sender_angles']:
                heading = own['yaw'] + math.radians(angle)
                landing = offset(ball, heading, self.model.pass_range)
                gain = direction * (landing[0] - ball[0])
                if (gain < (-.20 if SETTINGS['allow_backwards_pass'] else .03)
                        or abs(landing[0]) > PITCH_LENGTH/2-.12 or abs(landing[1]) > PITCH_WIDTH/2-.24):
                    continue
                if not lane_clear(ball, landing, opponents, SETTINGS['interception_buffer']):
                    continue
                obstacles = [p['position'] for n, p in players.items()
                             if n.startswith(self.prefix) and n != self.name]
                if not lane_clear(ball, landing, obstacles, circle):
                    continue
                sender = offset(offset(ball, heading, -.17), heading-math.pi/2, .05)
                sender_time, _, _ = route(own['position'], own['yaw'], sender, tolerance=.055)
                sender_time += abs(math.radians(angle)) / turn_rate
                goal_heading = bearing(landing, goal)
                for rotation in SETTINGS['face_options']:
                    receive_heading = goal_heading + math.radians(rotation)
                    stance = offset(landing, receive_heading, -.245)
                    if (abs(stance[0]) > PITCH_LENGTH / 2 - .10
                            or abs(stance[1]) > PITCH_WIDTH / 2 - .10
                            or distance(stance, sender) < 2 * self.model.robot_radius
                            or not lane_clear(ball, landing, [stance], circle)):
                        continue
                    travel, _, arrive = route(point, robot['yaw'], stance, tolerance=.075)
                    turning = max(0, abs(wrap(receive_heading-arrive))-math.radians(12)) / turn_rate
                    eta = travel + turning
                    if eta > SETTINGS['receive_eta']:
                        continue
                    ahead = offset(landing, receive_heading, .60)
                    clear = lane_clear(landing, ahead, opponents, .36)
                    if not clear:
                        continue
                    margin = min((distance(landing,p) for p in opponents), default=2.)
                    minimum_time = max(sender_time+self.model.pass_seconds, eta)
                    if margin < .40 + self.model.walk_speed * min(minimum_time, 6.):
                        continue
                    score = min(margin,1.25) + gain - .09*eta - .07*sender_time - .002*abs(rotation)
                    choices.append((score, name, sender, landing, stance, receive_heading))
        if not choices:
            return None
        _, name, sender, landing, stance, receive_heading = max(choices)
        return Decision('LEAD_PASS', sender, landing, 'pass', name, stance, receive_heading)
