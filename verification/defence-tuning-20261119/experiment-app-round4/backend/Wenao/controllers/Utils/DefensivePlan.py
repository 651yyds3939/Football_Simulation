"""Reachability estimates for interception, shared by 2D and Webots policy.

Rates are existing isolated-motion averages, not a new gait or a hardware
calibration. Paths use successive translations/turns; no simultaneous steering.
"""
import math

WALK = .08525241087733532
BACK = .034151821846239855
LEFT = .012710006709112306
RIGHT = .02229703610271777
TURN = math.radians(16.873355846361836)/4
SETTINGS = {'face_weight': .55, 'plan_seconds': 1., 'buffer': .22,
            'horizon': 40., 'prediction': 'arrival', 'lead': 1.,
            'tackle': 'poke', 'tackle_wait': 1., 'lane_width': 0., 'axis_priority': 'lateral',
            'reserve': -.5, 'selection': 'earliest', 'guard_line': 4.3}


def wrap(angle):
    return (angle+math.pi) % (2*math.pi)-math.pi


def route(own, yaw, target, tolerance=.08, face=None):
    """Return estimated seconds, first primitive, and arrival body heading.

    Compare body-frame translation with turn-then-walk and turn-then-back.
    Slow sideways motion can therefore be selected immediately for small lane
    corrections, while larger offsets justify turning early, before contact.
    """
    dx, dy = target[0]-own[0], target[1]-own[1]
    length = math.hypot(dx, dy)
    if length <= tolerance:
        return 0., 'stand', yaw
    front = dx*math.cos(yaw)+dy*math.sin(yaw)
    side = -dx*math.sin(yaw)+dy*math.cos(yaw)
    lateral_time = max(0, abs(side)-tolerance)/(LEFT if side > 0 else RIGHT)
    forward_time = max(0, abs(front)-tolerance)/(WALK if front >= 0 else BACK)
    translation = 'step_left' if side > 0 else 'step_right'
    if (abs(side) <= tolerance or
            (SETTINGS['axis_priority'] == 'time' and forward_time > lateral_time)):
        translation = 'walk' if front >= 0 else 'back'
    final_yaw = math.atan2(face[1]-target[1], face[0]-target[0]) if face else None
    def final_turn(heading):
        return (SETTINGS['face_weight']*max(0., abs(wrap(final_yaw-heading))-math.radians(12))/TURN
                if final_yaw is not None else 0.)
    candidates = [(forward_time+lateral_time+final_turn(yaw), translation, yaw)]
    bearing = math.atan2(dy, dx)
    for reverse, speed in ((False, WALK), (True, BACK)):
        heading = wrap(bearing+(math.pi if reverse else 0))
        angle = wrap(heading-yaw)
        turning = max(0, abs(angle)-math.radians(8))/TURN
        action = 'left40' if angle > math.radians(32) else 'left20' if angle > 0 else 'right20'
        if abs(angle) <= math.radians(10):
            action = 'back' if reverse else 'walk'
        candidates.append((turning+max(0, length-tolerance)/speed+final_turn(heading), action, heading))
    return min(candidates, key=lambda item: item[0])


def interception(own, yaw, ball, velocity, direction, carrier_yaw=None):
    """Choose the earliest reachable point on a goalward threat trajectory.

    An approaching carrier is modelled at the measured walk average when the
    ball is nearly stationary. A moving ball supplies its observed direction;
    horizon is bounded at the goal line. Forecasts are refreshed by the policy.
    """
    goal = (-direction*4.5, 0.)
    gx, gy = goal[0]-ball[0], goal[1]-ball[1]
    goal_distance = max(math.hypot(gx, gy), 1e-9)
    ux, uy = gx/goal_distance, gy/goal_distance
    speed = math.hypot(*velocity[:2])
    if speed > .025 and velocity[0]*(-direction) > .01:
        vx, vy = velocity[0]/speed, velocity[1]/speed
        # Keep prediction bounded: a brief kick impulse is not a sustained
        # sprint, and its rolling deceleration is handled by the executor.
        speed = min(speed, WALK*1.35)
    else:
        vx, vy, speed = ux, uy, WALK
        if carrier_yaw is not None and -direction*math.cos(carrier_yaw) > .2:
            vx, vy = math.cos(carrier_yaw), math.sin(carrier_yaw)
    horizon = min(SETTINGS['horizon'], max(0., (-direction*SETTINGS['guard_line']-ball[0])/(vx*speed))
                  if abs(vx) > .01 else SETTINGS['horizon'])
    def blocking_point(predicted):
        side = (own[0]-predicted[0])*(-uy)+(own[1]-predicted[1])*ux
        side = max(-SETTINGS['lane_width'], min(SETTINGS['lane_width'], side))
        return (max(-4.3, min(4.3, predicted[0]+ux*SETTINGS['buffer']-uy*side)),
                max(-2.6, min(2.6, predicted[1]+uy*SETTINGS['buffer']+ux*side)))
    if SETTINGS['prediction'] != 'arrival':
        gap = math.hypot(own[0]-ball[0], own[1]-ball[1])
        if SETTINGS['prediction'] == 'pursuit':
            t = min(horizon, SETTINGS['lead']*gap/(2*WALK))
        elif SETTINGS['prediction'] == 'lane':
            t = min(horizon, max(0., (own[0]-ball[0])/(vx*speed))) if abs(vx) > .01 else 0.
        else:
            t = 0.
        predicted = (ball[0]+vx*speed*t, ball[1]+vy*speed*t)
        target = blocking_point(predicted)
        eta, _, _ = route(own, yaw, target, face=predicted)
        return target, predicted, t, eta <= t+.5
    best = None
    feasible = []
    samples = max(1, math.ceil(horizon/.75))
    for index in range(samples+1):
        t = horizon*index/samples
        predicted = (ball[0]+vx*speed*t, ball[1]+vy*speed*t)
        target = blocking_point(predicted)
        eta, action, arrival_yaw = route(own, yaw, target, face=predicted)
        # Arrival means covering the lane with the body, not completing a
        # tackle. Facing and foot alignment are still separate later actions.
        candidate = (eta-t, t, target, predicted)
        if best is None or candidate[0] < best[0]:
            best = candidate
        if eta <= t-SETTINGS['reserve']:
            if SETTINGS['selection'] == 'earliest':
                return target, predicted, t, True
            feasible.append((eta-t, target, predicted, t))
    if feasible:
        _, target, predicted, t = min(feasible)
        return target, predicted, t, True
    return best[2], best[3], best[1], False
