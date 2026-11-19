"""Body-frame ball alignment and hysteresis, independent of the robot SDK."""
import math
from Utils.TeamPolicy import distance, unit, avoid_obstacles
from Utils.DefensivePlan import route

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

    def choose(self, decision, own, yaw, ball, robots=()):
        if decision.behaviour == 'DEFENSIVE_INTERCEPT':
            self.arrived = self.aligned = False
            _, action, _ = route(own, yaw, decision.target)
            if action == 'stand':
                angle = angle_to(own, decision.face, yaw)
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
                if abs(lateral) >= .12:
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
            target = avoid_obstacles(own, decision.target, robots)
            angle = angle_to(own, target, yaw)
            if abs(angle) <= 60:
                return 'walk', 'RECOVERY_ADVANCE'
            if abs(angle) >= 120:
                return 'back', 'RECOVERY_BACKTRACK'
            # Align the nearer translation axis, rather than always turning
            # through 180 degrees to walk forwards after being overtaken.
            reverse_angle = angle-math.copysign(180, angle)
            return turn_action(angle if abs(angle) <= 90 else reverse_angle), 'RECOVERY_CHANGE_HEADING'
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
