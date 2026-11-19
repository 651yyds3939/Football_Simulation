"""Pure role decisions. Coordinates in metres; no simulator/ground-truth API."""
from dataclasses import dataclass
import math
from Utils.DefensivePlan import interception, SETTINGS


def distance(a, b):
    return math.dist(a[:2], b[:2])


def unit(a, b):
    length = max(distance(a, b), 1e-9)
    return ((b[0]-a[0])/length, (b[1]-a[1])/length)


def lane_clear(a, b, obstacles, clearance=.38):
    dx, dy = b[0]-a[0], b[1]-a[1]
    squared = dx*dx+dy*dy
    if squared < 1e-9:
        return False
    for p in obstacles:
        t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/squared))
        if distance(p, (a[0]+t*dx, a[1]+t*dy)) < clearance:
            return False
    return True


@dataclass(frozen=True)
class Decision:
    behaviour: str
    target: tuple
    face: tuple
    kick: str = ""
    receiver: str = ""


class TeamPolicy:
    def __init__(self, name, goal_depth=0, finishing_nearest=False, support_mode="baseline"):
        if support_mode not in ("baseline", "possession"):
            raise ValueError("support_mode must be baseline or possession")
        self.name = name
        self.team = "RED" if name.startswith("Red") else "BLUE"
        self.prefix = "Red" if self.team == "RED" else "Blue"
        self.role = "goalkeeper" if "Goalkeeper" in name else "defender" if "Defender" in name else "striker"
        self.active_chaser = None
        self.goal_depth = goal_depth
        self.finishing_nearest = finishing_nearest
        self.support_mode = support_mode
        self.duel_anchor = None
        self.duel_escape = None
        self.recovering_defence = False
        self.intercept_plan = None
        self.counterpressing = False
        self.carry_plan = None
        self.own_yaw = 0.

    def home(self, direction):
        x = -4.15 if self.role == "goalkeeper" else -2.1 if self.role == "defender" else -.8
        y = 0 if self.role != "striker" else (-1.5 if self.name.endswith("A") else 1.5)
        return (direction*x, direction*y)

    def decide(self, world):
        own = world["robots"][self.name]["position"]
        self.own_yaw = world["robots"][self.name].get("yaw",0.)
        match = world["match"]
        direction = match["red_direction"] * (1 if self.team == "RED" else -1)
        home = self.home(direction)
        ball = world["ball"]["position"][:2]
        velocity = world["ball"].get("velocity", [0, 0])
        phase = match["phase"]
        if phase != 'PLAYING' or self.name in world.get('penalties', {}):
            self.intercept_plan = None
            self.counterpressing = False
            self.carry_plan = None
        if self.name in world.get("penalties", {}):
            self.duel_anchor = self.duel_escape = None
            self.recovering_defence = False
            return Decision("PENALIZED", tuple(own[:2]), tuple(ball))
        if phase in ("INITIAL", "SET", "STOPPED", "HALFTIME", "FINISHED"):
            self.duel_anchor = self.duel_escape = None
            self.recovering_defence = False
            return Decision("WAIT", tuple(own[:2]), tuple(ball))
        teammates = {n: r["position"] for n, r in world["robots"].items()
                     if n.startswith(self.prefix) and n not in world.get("penalties", {}) and r.get("standing", True)}
        opponents = [r["position"] for n, r in world["robots"].items() if not n.startswith(self.prefix)]
        eligible = {n: p for n, p in teammates.items() if "Goalkeeper" not in n}
        if direction*ball[0] < -3.5 and abs(ball[1]) < 1.5:
            eligible = teammates
        eligible,chaser = self.chase_assignment(world,eligible,own,ball,direction)
        owner = match.get('last_touch')
        if (owner in eligible and distance(eligible[owner], ball) < .70
                and distance(eligible[owner], ball) <= distance(eligible.get(chaser, own), ball)+.30):
            # Shared contact evidence holds one carrier through torso sway;
            # relinquish possession when another teammate is substantially nearer.
            chaser = owner
        # Identical observations produce one chaser across all four controllers.
        if phase == "READY":
            self.duel_anchor = self.duel_escape = None
            self.recovering_defence = False
            if match["restart"] == "KICKOFF" and match["restart_team"] == self.team and self.name.endswith("ForwardA"):
                home = (-direction*.3, 0)
            return Decision("FORMATION", home, tuple(ball))
        if phase == "PREPARE" or not match["released"]:
            self.duel_anchor = self.duel_escape = None
            self.recovering_defence = False
            point = match["restart_point"][:2]
            taker = min(eligible, key=lambda n: (distance(eligible[n], point), n), default=self.name)
            if match["restart_team"] == self.team and self.name == taker:
                return self.attack(own, ball, direction, teammates, opponents, "RESTART") if phase == "PLAYING" else Decision(
                    "PREPARE_RESTART", (ball[0]-direction*.28, ball[1]), (ball[0]+direction, 0))
            if distance(own, ball) < .85:
                ux, uy = unit(ball, own)
                return Decision("KEEP_DISTANCE", (ball[0]+ux*.95, ball[1]+uy*.95), tuple(ball))
            return Decision("FORMATION", home, tuple(ball))
        recovery = self.defensive_recovery(own, ball, velocity, direction, opponents)
        if recovery is not None:
            self.duel_anchor = self.duel_escape = None
            return recovery
        intent = world.get("pass_intent")
        if intent and intent["expires"] > world["time"] and intent["receiver"] in teammates:
            if self.name == intent["receiver"]:
                if distance(own, ball) < .20:
                    return self.attack(own, ball, direction, teammates, opponents)
                return Decision("RECEIVE_PASS", tuple(ball), tuple(ball))
            if self.name == intent["sender"]:
                return Decision("SUPPORT_PASS", (own[0], own[1]), tuple(ball))
            chaser = intent["receiver"]
        if self.name == chaser:
            pressure = self.counterpress(world, own, ball, velocity, direction, opponents)
            if pressure is not None:
                self.carry_plan = None
                return pressure
            # Begin positioning while there is still time to cover a lane.
            # Close foot contests keep their existing tackle/escape behaviour.
            threatening = min((distance(p, ball) for p in opponents), default=math.inf) < .65
            yaw = world['robots'][self.name].get('yaw', 0)
            if self.role == 'defender' and threatening and distance(own, ball) > .40:
                now = world['time']
                if (self.intercept_plan is None or now < self.intercept_plan[0]
                        or now-self.intercept_plan[0] >= SETTINGS['plan_seconds']
                        or distance(ball, self.intercept_plan[1]) > .18):
                    carriers = [r for n, r in world['robots'].items() if not n.startswith(self.prefix)]
                    carrier = min(carriers, key=lambda r: distance(r['position'], ball), default={})
                    target, predicted, horizon, reachable = interception(own, yaw, ball, velocity, direction, carrier.get('yaw'))
                    self.intercept_plan = (now, tuple(ball), target, predicted)
                return Decision('DEFENSIVE_INTERCEPT', self.intercept_plan[2], self.intercept_plan[3])
            self.intercept_plan = None
            challenge = (self.role == "defender" and -direction*(own[0]-ball[0]) > -.05
                         and distance(own, ball) < 1.6
                         and min((distance(p, ball) for p in opponents), default=math.inf) < .65)
            if challenge:
                yaw = world['robots'][self.name].get('yaw', 0)
                dx, dy = ball[0]-own[0], ball[1]-own[1]
                front = dx*math.cos(yaw)+dy*math.sin(yaw)
                lateral = -dx*math.sin(yaw)+dy*math.cos(yaw)
                if .08 < front < .30 and abs(lateral) < .12:
                    now = world['time']
                    if self.duel_anchor is None or distance(ball, self.duel_anchor[0]) > .06 or now < self.duel_anchor[1]:
                        self.duel_anchor = (tuple(ball), now)
                    # Keep a genuine foot challenge through a brief contest,
                    # but do not let two defenders press forever without progress.
                    if self.duel_escape is None and now-self.duel_anchor[1] < SETTINGS['duel_hold_seconds']:
                        return Decision("CHALLENGE", tuple(ball), tuple(ball))
            escape = self.unblock_duel(world, own, ball, opponents)
            if escape is not None:
                return escape
            if challenge:
                return Decision("CHALLENGE", tuple(ball), tuple(ball))
            predicted = ball
            if distance(own, ball) > .6:
                speed = math.hypot(*velocity[:2])
                horizon = min(.8, .4/max(speed, .01))
                predicted = [ball[0]+velocity[0]*horizon, ball[1]+velocity[1]*horizon]
            return self.attack(own, predicted, direction, teammates, opponents)
        self.duel_anchor = self.duel_escape = None
        if self.role == "goalkeeper":
            x = -direction*4.12
            t = (x-ball[0])/velocity[0] if abs(velocity[0]) > .02 else -1
            predicted_y = ball[1]+velocity[1]*t if 0 < t < 4 else ball[1]*.35
            target = (x, max(-1.05, min(1.05, predicted_y)))
            return Decision("GUARD_INTERCEPT" if 0 < t < 4 else "GUARD", target, tuple(ball))
        if self.role == "defender":
            x = direction*max(-3.6, min(-1.5, direction*ball[0]-.8))
            return Decision("DEFEND", (x, max(-1.9, min(1.9, ball[1]*.65))), tuple(ball))
        side = -1 if self.name.endswith("A") else 1
        support_x = max(-.5, min(3.5, direction*ball[0]+1))
        if self.support_mode == "possession":
            # Possession-dependent support line.
            # A distance advantage is only a proxy, not measured possession.
            near_team = min((distance(p, ball) for p in teammates.values()), default=math.inf)
            near_opponent = min((distance(p, ball) for p in opponents), default=math.inf)
            if near_opponent + .20 < near_team:
                # Cover behind the ball instead of always running ahead of it.
                support_x = max(-3.5, min(2.8, direction*ball[0]-.8))
        target = (direction*support_x, max(-2.4, min(2.4, ball[1]+side*1.1)))
        return Decision("SUPPORT", target, tuple(ball))

    def chase_assignment(self,world,eligible,own,ball,direction):
        return eligible,min(eligible,key=lambda n:(distance(eligible[n],ball),n),default=self.name)

    def counterpress(self, world, own, ball, velocity, direction, opponents):
        """Recover a lost ball before resuming goal-facing attacking alignment."""
        if self.role != 'striker' or not SETTINGS['press_enabled']:
            return None
        owner = world['match'].get('last_touch')
        opponent_distance = min((distance(p,ball) for p in opponents), default=math.inf)
        own_distance = distance(own,ball)
        yaw = world['robots'][self.name].get('yaw',0)
        front = (ball[0]-own[0])*math.cos(yaw)+(ball[1]-own[1])*math.sin(yaw)
        side = -(ball[0]-own[0])*math.sin(yaw)+(ball[1]-own[1])*math.cos(yaw)
        regained = (owner == self.name and .08 < front < .30 and abs(side)<.12)
        if regained:
            self.counterpressing = False
        opponent_owner = owner and not owner.startswith(self.prefix)
        if (opponent_owner and opponent_distance < .70 and not regained
                and opponent_distance+SETTINGS['press_loss_margin']<own_distance):
            self.counterpressing = True
        if not self.counterpressing:
            return None
        # Clear stale ownership when the ball has become safely recoverable.
        if opponent_distance > 1.2 and own_distance < .35 and direction*(ball[0]-own[0])>.05:
            self.counterpressing = False
            return None
        escape = self.unblock_duel(world,own,ball,opponents)
        if escape is not None:
            return escape
        # A bounded lead follows the observed ball path. Close contests use
        # the current ball, so the chaser does not turn towards the attack goal.
        horizon = SETTINGS['press_lead_seconds'] if own_distance > SETTINGS['press_near'] else 0.
        horizon = min(horizon,.4/max(math.hypot(*velocity[:2]),.01))
        target = (max(-4.3,min(4.3,ball[0]+velocity[0]*horizon)),
                  max(-2.65,min(2.65,ball[1]+velocity[1]*horizon)))
        return Decision('COUNTERPRESS',tuple(target),tuple(ball))

    def defensive_recovery(self, own, ball, velocity, direction, opponents):
        """Get goal-side after being beaten, before attempting a clearance."""
        if self.role != "defender":
            return None
        goal_side = -direction*(own[0]-ball[0])
        threatened = (min((distance(p, ball) for p in opponents), default=math.inf) < .45
                      or direction*velocity[0] < -.02)
        if goal_side > .30 or not threatened:
            self.recovering_defence = False
        elif goal_side < -.10:
            self.recovering_defence = True
        if not self.recovering_defence:
            return None
        predicted = (ball[0]+velocity[0]*.8, ball[1]+velocity[1]*.8)
        # Recover towards the goal corridor, rather than forever pursuing a
        # point just beyond a carrier that is faster than backward walking.
        goal_x = -direction*4.18
        target = (goal_x, max(-1.05, min(1.05, predicted[1]*.55)))
        return Decision("RECOVER_DEFENCE", target, tuple(ball))

    def unblock_duel(self, world, own, ball, opponents):
        """Briefly step aside after a genuinely stationary, crowded duel.

        Thresholds are policy assumptions, measured in simulation seconds and
        metres. They do not change robot speed, reset the ball or award a result.
        """
        now = world["time"]
        if self.duel_anchor is not None and now < self.duel_anchor[1]:
            self.duel_anchor = self.duel_escape = None
        crowded = (distance(own, ball) < .45 and any(
            distance(p, ball) < .45 and distance(p, own) < .42 for p in opponents))
        if self.duel_escape is not None:
            until, target = self.duel_escape
            if crowded and now < until and distance(own, target) > .025:
                return Decision("DUEL_ESCAPE", target, tuple(ball))
            self.duel_escape = None
            self.duel_anchor = (tuple(ball), now)
        if not crowded:
            self.duel_anchor = None
            return None
        if self.duel_anchor is None or distance(ball, self.duel_anchor[0]) > .06 or now < self.duel_anchor[1]:
            self.duel_anchor = (tuple(ball), now)
            return None
        wait=8 if self.role=='defender' else 3
        if self.role=='striker':
            yaw=world['robots'][self.name].get('yaw',0.)
            dx,dy=ball[0]-own[0],ball[1]-own[1]
            front=dx*math.cos(yaw)+dy*math.sin(yaw)
            lateral=-dx*math.sin(yaw)+dy*math.cos(yaw)
            # Match the existing defender's hold only while the ball really
            # remains in our forward foot window. Else realign promptly.
            if .08<front<.30 and abs(lateral)<.12:
                wait=SETTINGS['duel_hold_seconds']
        if now-self.duel_anchor[1] < wait:
            return None
        other = min(opponents, key=lambda p: distance(p, own))
        yaw = world["robots"][self.name].get("yaw", 0)
        lateral = -(other[0]-own[0])*math.sin(yaw)+(other[1]-own[1])*math.cos(yaw)
        side = -1 if lateral > .02 else 1
        step = .12
        if self.role == 'defender':
            ball_lateral = -(ball[0]-own[0])*math.sin(yaw)+(ball[1]-own[1])*math.cos(yaw)
            if abs(ball_lateral) > .02:
                side = 1 if ball_lateral > 0 else -1
                step = min(step, abs(ball_lateral))
        target = (own[0]-step*side*math.sin(yaw), own[1]+step*side*math.cos(yaw))
        if abs(target[0]) > 4.35 or abs(target[1]) > 2.85:
            target = (own[0]+step*side*math.sin(yaw), own[1]-step*side*math.cos(yaw))
        target = (max(-4.35, min(4.35, target[0])), max(-2.85, min(2.85, target[1])))
        self.duel_escape = (now+8, target)
        return Decision("DUEL_ESCAPE", target, tuple(ball))

    def attack(self, own, ball, direction, teammates, opponents, context=""):
        # Prefer the nearest safe aperture point, especially when close to goal.
        nearest_y = max(-.9, min(.9, ball[1]))
        # Opt-in experiment: a closing defender can block every candidate.
        # Keep the near-goal fallback aim at the nearest aperture; blocked shots
        # remain forbidden. Multiplayer stability did not improve, so this
        # candidate is disabled by default.
        finishing = distance(ball, (direction*4.5, nearest_y)) < .50
        goal = (direction*(4.5+self.goal_depth), nearest_y if self.finishing_nearest and finishing else 0)
        for goal_y in (nearest_y, 0, -.9, .9):
            candidate_goal = (direction*(4.5+self.goal_depth), goal_y)
            if lane_clear(ball, candidate_goal, opponents):
                goal = candidate_goal
                break
        receiver = ""
        kick = ""
        if context == "RESTART":
            aim, behaviour, kick = (ball[0]+direction*1, ball[1]*.5), "RESTART", "pass"
        elif self.role == "goalkeeper" or self.role == "defender":
            aim, behaviour, kick = (ball[0]+direction*2, ball[1]*.5), "CLEAR", "pass"
        else:
            candidates = [(n, p) for n, p in teammates.items() if n != self.name and "Forward" in n
                          and direction*(p[0]-ball[0]) > .4 and distance(ball, p) < 3.5
                          and lane_clear(ball, p, opponents)]
            if candidates and not lane_clear(ball, goal, opponents):
                receiver, aim = max(candidates, key=lambda item: direction*item[1][0])
                behaviour, kick = "PASS", "pass"
            # The bundled shot moved ~0.4 m in the physical fixture. A midfield
            # shot wastes setup time; carry into a close finishing range first.
            elif distance(ball, (direction*4.5, goal[1])) < .50 and lane_clear(ball, goal, opponents):
                aim, behaviour, kick = goal, "SHOOT", "shoot"
            else:
                aim, behaviour = goal, "DRIBBLE"
        if behaviour=='DRIBBLE' and SETTINGS['evade_enabled']:
            aim=self.carry_around(own,ball,aim,direction,opponents)
            if self.carry_plan is not None:
                behaviour='EVADE_DRIBBLE'
        ux, uy = unit(ball, aim)
        # Shoot/LongPass swing the left foot; align the ball with that foot.
        back, lateral = (.17, .05) if kick else (.19, 0)
        target = (ball[0]-back*ux+lateral*uy, ball[1]-back*uy-lateral*ux)
        if distance(own, ball) > .6 and not context:
            # Lead a moving ball with a bounded horizon, not an unlimited extrapolation.
            behaviour = "INTERCEPT"
        return Decision(behaviour, target, tuple(aim), kick, receiver)


    def carry_around(self, own, ball, goal, direction, opponents):
        """Commit to one carrying lane around a defender blocking the goal.

        The waypoint is an intended ball path, not a ball placement. Every
        turn, foot alignment and push still uses the ordinary executor.
        """
        if self.carry_plan is not None:
            anchor,waypoint=self.carry_plan
            passed=direction*(ball[0]-anchor[0])>.30
            if passed or distance(ball,waypoint)<.25 or distance(own,ball)>.65:
                self.carry_plan=None
            else:
                return waypoint
        if distance(own,ball)>.50 or lane_clear(ball,goal,opponents,clearance=.50):
            return goal
        # Starting a large turn in an already close tackle exposes the ball.
        ahead=[p for p in opponents if direction*(p[0]-ball[0])>.20
               and SETTINGS['evade_min_distance']<distance(p,ball)<SETTINGS['evade_distance']
               and abs(p[1]-ball[1])<.80]
        if not ahead:
            return goal
        other=min(ahead,key=lambda p:distance(p,ball))
        options=[]
        for side in (-1,1):
            waypoint=(max(-4.15,min(4.15,other[0]+direction*SETTINGS['evade_ahead'])),
                      max(-2.35,min(2.35,other[1]+side*SETTINGS['evade_width'])))
            bearing=math.atan2(waypoint[1]-ball[1],waypoint[0]-ball[0])
            error=abs((bearing-self.own_yaw+math.pi)%(2*math.pi)-math.pi)
            blocked=not lane_clear(ball,waypoint,opponents,clearance=.30)
            cost=distance(ball,waypoint)+error*1.2+int(blocked)*2.+max(0,abs(waypoint[1])-1.9)
            options.append((cost,waypoint))
        waypoint=min(options,key=lambda item:item[0])[1]
        self.carry_plan=(tuple(other[:2]),waypoint)
        return waypoint


def avoid_obstacles(own, target, robots, margin=.5):
    """Bounded local waypoint deflection; target itself remains inside the pitch."""
    ux, uy = unit(own, target)
    step = min(.6, distance(own, target))
    x, y = own[0]+ux*step, own[1]+uy*step
    for other in robots:
        d = distance(own, other)
        if .01 < d < margin and (other[0]-own[0])*ux+(other[1]-own[1])*uy > 0:
            side = 1 if (other[0]-own[0])*uy-(other[1]-own[1])*ux >= 0 else -1
            x += -uy*side*.3
            y += ux*side*.3
    return (max(-4.35, min(4.35, x)), max(-2.85, min(2.85, y)))
