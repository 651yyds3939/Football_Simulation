"""Body-frame ball alignment and hysteresis, independent of the robot SDK."""
import math
from Utils.TeamPolicy import distance, unit, avoid_obstacles
from Utils.DefensivePlan import route, SETTINGS

ATTACK = {'INTERCEPT', 'DRIBBLE', 'SHOOT', 'PASS', 'CLEAR', 'RESTART'}


def angle_to(own, target, yaw):
    angle = math.atan2(target[1]-own[1], target[0]-own[0])-yaw
    return math.degrees((angle+math.pi) % (2*math.pi)-math.pi)


def turn_action(angle):
    # Actual isolated measurements: L20 ~17deg, L40 ~39deg, R20 ~17deg.
    # Legacy R40 is ~16deg and L10 only ~4deg; do not infer performance from names.
    return ('left40' if angle > 32 else 'left20') if angle > 0 else 'right20'


class Navigator:
    def __init__(self):
        self.arrived = False
        self.aligned = False
        self.escape = None
        self.blocked_anchor = None
        self.blocked_calls = 0

    def choose(self, decision, own, yaw, ball, robots=()):
        action, stage = self._choose(decision, own, yaw, ball, robots)
        if not SETTINGS['blocked_escape']:
            return action, stage
        if self.escape is not None:
            origin, primitive = self.escape
            if distance(own, origin) < SETTINGS['escape_metres']:
                return primitive, 'MAKE_ROOM_BEFORE_ALIGNMENT'
            self.escape = None
        if action not in ('step_left', 'step_right', 'back'):
            self.blocked_anchor = None
            self.blocked_calls = 0
            return action, stage
        c, s = math.cos(yaw), math.sin(yaw)
        vectors = {'walk': (c, s, .08525), 'back': (-c, -s, .03415),
                   'step_left': (-s, c, .01271), 'step_right': (s, -c, .02230)}
        vx, vy, _ = vectors[action]
        blockers = [p for p in robots if distance(own, p) < .34 and
                    (p[0]-own[0])*vx+(p[1]-own[1])*vy > .025]
        if not blockers:
            self.blocked_anchor = None
            self.blocked_calls = 0
            return action, stage
        if self.blocked_anchor is None or distance(own, self.blocked_anchor[0]) > .008 or distance(ball, self.blocked_anchor[1]) > .025:
            self.blocked_anchor = (tuple(own[:2]), tuple(ball[:2]))
            self.blocked_calls = 0
        self.blocked_calls += 1
        # This planar backend calls navigation once per fixed 40 ms tick.
        if self.blocked_calls*.04 < SETTINGS['blocked_seconds']:
            return action, stage
        self.blocked_anchor = None
        self.blocked_calls = 0
        other = min(blockers, key=lambda p: distance(own, p))
        away = (own[0]-other[0], own[1]-other[1])
        safe = [(k, v) for k,v in vectors.items() if
                abs(own[0]+v[0]*SETTINGS['escape_metres']) < 4.35 and
                abs(own[1]+v[1]*SETTINGS['escape_metres']) < 2.85 and
                all((own[0]-p[0])*v[0]+(own[1]-p[1])*v[1] >= 0 for p in robots if distance(own,p)<.38)]
        if not safe:
            return action, stage
        primitive, _ = max(safe, key=lambda kv: (away[0]*kv[1][0]+away[1]*kv[1][1])*kv[1][2])
        self.escape = (tuple(own[:2]), primitive)
        return primitive, 'MAKE_ROOM_BEFORE_ALIGNMENT'

    def _choose(self, decision, own, yaw, ball, robots=()):
        if decision.behaviour == 'DEFENSIVE_INTERCEPT':
            self.arrived = self.aligned = False
            _, action, _ = route(own, yaw, decision.target)
            if action == 'stand':
                angle = angle_to(own, ball if SETTINGS['face_real_ball'] else decision.face, yaw)
                return (turn_action(angle), 'INTERCEPT_FACE_INCOMING') if abs(angle) > 20 else ('stand', 'INTERCEPT_HOLD_LANE')
            return action, 'INTERCEPT_MOVE_EARLY'
        if decision.behaviour == 'CHALLENGE':
            self.arrived = False
            dx, dy = ball[0]-own[0], ball[1]-own[1]
            front = dx*math.cos(yaw)+dy*math.sin(yaw)
            lateral = -dx*math.sin(yaw)+dy*math.cos(yaw)
            if .08 < front < .30 and abs(lateral) < .12:
                # The ball is already reachable by the forward foot. Do not
                # lose the tackle window turning towards a point under the body.
                return 'walk', 'CHALLENGE_POKE_BALL'
            if distance(own, ball) < .75 and front > .08:
                # Keep the blocking heading at close range. Rotating to chase
                # a changing bearing opened a lane beside the defender's feet.
                if abs(lateral) >= SETTINGS['challenge_side']:
                    return ('step_left' if lateral > 0 else 'step_right'), 'CHALLENGE_SHADOW_LANE'
                return 'walk', 'CHALLENGE_CLOSE_LANE'
            angle = angle_to(own, ball, yaw)
            if abs(angle) > (25 if self.aligned else 12):
                self.aligned = False
                return turn_action(angle), 'CHALLENGE_FACE_BALL'
            self.aligned = True
            if front < .10:
                return 'back', 'CHALLENGE_CREATE_SPACE'
            return 'walk', 'CHALLENGE_EXPOSED_BALL'
        if decision.behaviour == 'RECOVER_DEFENCE':
            self.arrived = self.aligned = False
            _, action, _ = route(own, yaw, decision.target, tolerance=.10)
            stage = ('RECOVERY_BACKTRACK' if action == 'back' else 'RECOVERY_ADVANCE' if action == 'walk'
                     else 'RECOVERY_HOLD_LANE' if action == 'stand'
                     else 'RECOVERY_SIDE_COVER' if action.startswith('step_') else 'RECOVERY_CHANGE_HEADING')
            return action, stage
        if decision.behaviour == 'DUEL_ESCAPE':
            self.arrived = self.aligned = False
            dx, dy = decision.target[0]-own[0], decision.target[1]-own[1]
            lateral = -dx*math.sin(yaw)+dy*math.cos(yaw)
            if abs(lateral) < .025:
                return 'stand', 'DUEL_SPACE_CREATED'
            return ('step_left' if lateral > 0 else 'step_right'), 'DUEL_STEP_ASIDE'
        if decision.behaviour in ATTACK:
            self.arrived = False
            forward = unit(ball, decision.face)
            own_ahead = (own[0]-ball[0])*forward[0]+(own[1]-ball[1])*forward[1]
            separation = distance(own, ball)
            # Approach the ball from behind the intended kick direction.
            # An approach from the goal side goes around, rather than through it.
            if separation > .70 or (own_ahead > -.02 and separation > .32):
                target = decision.target
                if own_ahead > -.02:
                    lateral = (own[1]-ball[1])*forward[0]-(own[0]-ball[0])*forward[1]
                    side = 1 if lateral >= 0 else -1
                    target = (ball[0]-.36*forward[0]-.45*side*forward[1],
                              ball[1]-.36*forward[1]+.45*side*forward[0])
                self.aligned = False
                return self.travel(own, yaw, target, robots, 'APPROACH_BEHIND_BALL')
            # Face the intended ball trajectory, not a centimetre-scale target
            # underneath the torso. This is the old source of 180-degree oscillations.
            facing = (own[0]+forward[0], own[1]+forward[1])
            angle = angle_to(own, facing, yaw)
            limit = 20 if decision.kick else 25
            if abs(angle) > (limit if self.aligned else 12):
                self.aligned = False
                return turn_action(angle), 'FACE_KICK_DIRECTION'
            self.aligned = True
            dx, dy = ball[0]-own[0], ball[1]-own[1]
            front = dx*math.cos(yaw)+dy*math.sin(yaw)
            left = -dx*math.sin(yaw)+dy*math.cos(yaw)
            lateral_target = .05 if decision.kick else 0
            lateral_limit = .055 if decision.kick else .10
            if abs(left-lateral_target) > lateral_limit:
                return ('step_left' if left > lateral_target else 'step_right'), 'ALIGN_FOOT_LATERALLY'
            if front < .12:
                return 'back', 'MAKE_FOOT_SPACE'
            if front > (.24 if decision.kick else .30):
                return 'walk', 'CLOSE_BALL_DISTANCE'
            return (decision.kick if decision.kick else 'walk'), ('EXECUTE_KICK' if decision.kick else 'DRIBBLE_TOWARD_GOAL')
        self.aligned = False
        separation = distance(own, decision.target)
        if separation < .15:
            self.arrived = True
        elif separation > .30:
            self.arrived = False
        if self.arrived:
            angle = angle_to(own, decision.face, yaw)
            return (turn_action(angle), 'WATCH_BALL') if abs(angle) > 25 else ('stand', 'HOLD_POSITION')
        return self.travel(own, yaw, decision.target, robots, 'MOVE_TO_ROLE_POSITION')

    def travel(self, own, yaw, target, robots, stage):
        target = avoid_obstacles(own, target, robots)
        angle = angle_to(own, target, yaw)
        return (turn_action(angle), stage) if abs(angle) > 25 else ('walk', stage)
