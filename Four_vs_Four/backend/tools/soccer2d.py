"""Small kinematic experiment adapter around the *existing* football policy.

This adapter separates fast behaviour experiments from 3D execution and
does not simulate balance, legs, cameras, flight of the ball or physical fouls.
"""
from dataclasses import dataclass, asdict
from collections import Counter
import math
from pathlib import Path

from contact_motion import foot_entry, stop_conflicting_moves
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Wenao/controllers"))
from Utils.CourseSpecs import BALL_RADIUS
from Utils.MatchEngine import MatchConfig, MatchEngine
from Utils.Navigation import Navigator
from Utils.PlanarMotion import PlanarMotion
from Utils.ProcessSupervisor import ROBOT_NAMES
from Utils.TeamPolicy import TeamPolicy, distance


@dataclass(frozen=True)
class Model:
    dt: float = .2
    half_seconds: float = 300
    ready_seconds: float = 10
    # Recorded isolated movement averages, not hardware calibration.
    walk_speed: float = .08525241087733532
    back_speed: float = .034151821846239855
    left_speed: float = .012710006709112306
    right_speed: float = .02229703610271777
    left_turn: float = math.radians(16.873355846361836)/4
    right_turn: float = math.radians(17.348436344702577)/4
    # The following are explicit model assumptions, shared by both teams.
    robot_radius: float = .15
    rolling_deceleration: float = .35
    shot_range: float = .406003256198733
    pass_range: float = .3051396105104535
    shot_seconds: float = 4.8
    pass_seconds: float = 3.299
    kick_noise_radians: float = .04
    planar_pass_range: float = 1.65
    planar_shot_range: float = 2.47
    planar_turn_rate: float = .23
    planar_side_speed: float = .049
    planar_tap_seconds: float = .44
    planar_tap_range: float = .48
    planar_touch_pass_range: float = 1.48
    planar_shot_seconds: float = 1.55
    planar_pass_seconds: float = 1.45
    planar_snap_range: float = 1.89
    planar_snap_seconds: float = .68

    def __post_init__(self):
        values = asdict(self)
        if not all(math.isfinite(v) and v > 0 for v in values.values()):
            raise ValueError("Model values must be finite and positive")
        if self.half_seconds <= self.ready_seconds+1:
            raise ValueError("A half must include time after READY/SET")
        if self.dt > .2:
            raise ValueError("Use dt <= 0.2 seconds for contact/boundary sampling")


def wrap(angle):
    return (angle+math.pi) % (2*math.pi)-math.pi


class Simulation:
    def __init__(self, seed=27, candidate_team="RED", candidate="possession", model=None,
                 active_names=None, policy_profile=None):
        if candidate_team not in ("RED", "BLUE") or candidate not in ("baseline", "possession"):
            raise ValueError("Invalid candidate team or policy")
        self.model = model or Model()
        self.names = tuple(ROBOT_NAMES if active_names is None else active_names)
        if not self.names or len(set(self.names)) != len(self.names) or not set(self.names) <= set(ROBOT_NAMES):
            raise ValueError('Invalid active player roster')
        self.policy_profile = policy_profile
        self.seed, self.candidate_team, self.candidate = seed, candidate_team, candidate
        self.rng = random.Random(seed)
        # One indexed random stream per robot: changes on one team do not consume
        # another player's kick-noise draws. Opponent state can still diverge.
        self.noise = {n: random.Random(f"{seed}:{n}") for n in ROBOT_NAMES}
        self.engine = MatchEngine(MatchConfig(
            half_seconds=self.model.half_seconds, startup_seconds=0,
            ready_seconds=self.model.ready_seconds, set_seconds=1, halftime_seconds=1,
            interruption_seconds=1, preparation_seconds=5, stuck_seconds=120, seed=seed))
        self.time = 0
        self.ball = [0., 0., BALL_RADIUS]
        self.velocity = [0., 0., 0.]
        self.players, self.policies, self.navigators = {}, {}, {}
        for name in self.names:
            team = "RED" if name.startswith("Red") else "BLUE"
            self.policies[name] = TeamPolicy(name, goal_depth=.30,
                support_mode=candidate if team == candidate_team else "baseline")
            self.navigators[name] = Navigator()
            if policy_profile is not None:
                self.policies[name], self.navigators[name] = policy_profile.create(name)
            self.players[name] = {"position": [0., 0., .334], "yaw": 0., "standing": True}
        self.kicking = {}
        self.touch = None
        self.pass_intent = None
        self.pending_pass = None
        self.events = []
        self.stats = {t: Counter() for t in ("RED", "BLUE")}
        self.last_actions = {}
        self.last_decisions = {}
        self.current_decisions = {}
        self.navigation_stages = {}
        self.previous_contact = None
        self.previous_foot_contact = None
        self.previous_foot_contact_time = None
        self.prepared = set()
        self.reset_on_goal = False
        self.clip_body_contacts = False
        self.active_receiver = None
        self._place_formation(jitter=True)

    def _place_formation(self, jitter=False):
        for name, player in self.players.items():
            policy = self.policies[name]
            direction = self.engine.direction(policy.team)
            x, y = policy.home(direction)
            if name.endswith("ForwardA") and policy.team == self.engine.restart_team:
                x, y = -direction*.3, 0
            if jitter:
                x += self.rng.uniform(-.06, .06)
                y += self.rng.uniform(-.06, .06)
            player.update(position=[x, y, .334], yaw=0 if direction == 1 else math.pi)
            self.navigators[name] = Navigator()
        self.kicking.clear()

    def _reset_after_goal(self):
        self._place_formation()
        self.ball = list(self.engine.restart_point)
        self.velocity = [0., 0., 0.]
        self.touch = self.previous_contact = None
        self.previous_foot_contact = self.previous_foot_contact_time = None
        self.pass_intent = self.pending_pass = None
        self._event("goal_formation", team=self.engine.restart_team)
        self._event("place_ball", point=list(self.ball))

    def observation(self):
        world = {"version": 2, "time": self.time, "match": self.engine.snapshot(),
                 "ball": {"position": list(self.ball), "velocity": list(self.velocity)},
                 "robots": self.players, "penalties": {}, "last_foot_contact": self.previous_foot_contact,
                 "last_foot_contact_time": self.previous_foot_contact_time}
        if self.pass_intent and self.pass_intent["expires"] > self.time:
            world["pass_intent"] = self.pass_intent
        return world

    def _event(self, kind, **fields):
        self.events.append({"event": kind, "time": round(self.time, 6), **fields})

    def _contact(self, name, source='body'):
        self.touch = name
        if source != 'body':
            self.previous_foot_contact_time = self.time
            if name != self.previous_foot_contact:
                self._event('foot_control_change', robot=name, source=source, point=list(self.ball[:2]))
                self.previous_foot_contact = name
        if name != self.previous_contact:
            self.stats[self.policies[name].team]["contact_transitions"] += 1
            self._event("contact", robot=name)
            self.previous_contact = name
        if self.pending_pass and name != self.pending_pass["sender"]:
            sender = self.pending_pass["sender"]
            completed = name == self.pending_pass["receiver"]
            same_team = self.policies[name].team == self.policies[sender].team
            outcome = "completed_passes" if completed else "misdirected_passes" if same_team else "intercepted_passes"
            self.stats[self.policies[sender].team][outcome] += 1
            self._event("pass_result", sender=sender, receiver=name, completed=completed,
                        intended_receiver=self.pending_pass["receiver"],
                        contact_source=source, point=list(self.ball[:2]))
            self.pending_pass = None
            self.pass_intent = None

    def _pass_can_release(self, name, decision, heading, roll_distance):
        return True

    def _finish_kick(self, name, decision):
        player = self.players[name]
        dx = self.ball[0]-player["position"][0]
        dy = self.ball[1]-player["position"][1]
        front = dx*math.cos(player["yaw"])+dy*math.sin(player["yaw"])
        lateral = -dx*math.sin(player["yaw"])+dy*math.cos(player["yaw"])
        team = self.policies[name].team
        tap = decision.kick == "tap"
        on_foot = (.075 <= front <= .32 and abs(lateral) <= .148 if tap
                   else .10 <= front <= .30 and abs(lateral-.05) <= .08)
        # A modelled foot contact must still exist at completion; do not kick a
        # ball that an opponent has already moved away during the wind-up.
        if not on_foot:
            self.stats[team]["kick_misses"] += 1
            if (decision.behaviour in ("COORDINATED_PASS", "LEAD_PASS", "OUTLET_PASS", "TOUCH_PASS") and self.pass_intent
                    and self.pass_intent.get("sender") == name):
                self.pass_intent = None
                self._event("pass_cancelled", robot=name, reason="lost_foot_contact")
            return
        heading = player["yaw"]
        if tap:
            aim = math.atan2(decision.face[1]-self.ball[1],decision.face[0]-self.ball[0])
            change = wrap(aim - heading)
            if abs(change) > math.radians(107):
                self.stats[team]["kick_misses"] += 1
                return
            heading += change
            if decision.receiver:
                maximum = self.model.planar_touch_pass_range
            elif decision.behaviour == "SNAP_SHOT":
                maximum = self.model.planar_snap_range
            else:
                maximum = self.model.planar_tap_range
            desired_range = min(decision.kick_distance, maximum) or maximum
        elif decision.kick == "shoot":
            desired_range = min(decision.kick_distance, self.model.planar_shot_range) or self.model.shot_range
        else:
            desired_range = min(decision.kick_distance, self.model.planar_pass_range) or self.model.pass_range
        if decision.receiver and not self._pass_can_release(name, decision, heading, desired_range):
            if self.pass_intent and self.pass_intent.get("sender") == name and self.pass_intent.get("stage") == "preparing":
                self.pass_intent = None
            self._event("pass_cancelled", robot=name, reason="interception_risk")
            return
        speed = math.sqrt(2*self.model.rolling_deceleration*desired_range)
        angle = heading+self.noise[name].gauss(0, self.model.kick_noise_radians)
        self.velocity = [speed*math.cos(angle), speed*math.sin(angle), 0.]
        self._contact(name, 'kick')
        self.stats[team]["kick_contacts"] += 1
        kick_event = {"technique": decision.behaviour} if tap else {}
        self._event("kick_contact", robot=name, action=decision.kick, **kick_event)
        if decision.receiver:
            self.pending_pass = {"sender": name, "receiver": decision.receiver, "expires": self.time+24}
            self.pass_intent = {**self.pending_pass, "kind": "pass_intent", "coordinated": decision.behaviour in ("COORDINATED_PASS", "LEAD_PASS", "OUTLET_PASS", "TOUCH_PASS"), "stage": "released"}
            if decision.receive_stance:
                self.pending_pass["expires"] = self.time + 8.
                self.pass_intent.update(expires=self.pending_pass["expires"], landing=decision.face,
                                        stance=decision.receive_stance, heading=decision.receive_heading)

    def _ball_body_penetration(self, position, yaw):
        """Depth into the body proxy, excluding its declared forward foot space."""
        dx, dy = self.ball[0]-position[0], self.ball[1]-position[1]
        circle_depth = max(0., self.model.robot_radius+BALL_RADIUS-math.hypot(dx, dy))
        front = dx*math.cos(yaw)+dy*math.sin(yaw)
        lateral = -dx*math.sin(yaw)+dy*math.cos(yaw)
        foot_depth = math.hypot(max(0., .08-front), max(0., abs(lateral)-.12))
        return min(circle_depth, foot_depth)

    def _body_clear_of_ball(self, position, yaw):
        return self._ball_body_penetration(position, yaw) <= 1e-12

    def _limit_body_motion_at_ball(self, previous, proposed, yaw):
        # Checking only ball rays misses a moving body crossing a nearly still
        # ball. Clip that translation at first contact, for either team. Keep
        # the declared front foot space; do not attach or teleport the ball.
        toward = sum((self.ball[i]-previous[i])*(proposed[i]-previous[i]) for i in range(2))
        if toward <= 0 or self._body_clear_of_ball(proposed, yaw):
            return proposed
        old_depth = self._ball_body_penetration(previous, yaw)
        if old_depth > 1e-12:
            return proposed if self._ball_body_penetration(proposed, yaw) < old_depth else list(previous)
        lo, hi = 0., 1.
        for _ in range(20):
            mid = (lo+hi)*.5
            point = [previous[i]+mid*(proposed[i]-previous[i]) for i in range(2)]
            if self._body_clear_of_ball(point, yaw):
                lo = mid
            else:
                hi = mid
        return [previous[i]+lo*(proposed[i]-previous[i]) for i in range(2)]+[.334]

    def _roll_ball(self):
        """Rolling friction and bounded swept rebounds from standing body discs."""
        speed = math.hypot(*self.velocity[:2])
        if not speed:
            return
        dt = self.model.dt
        remaining = max(0, speed-self.model.rolling_deceleration*dt)
        travel = (speed+remaining)*.5*min(dt, speed/self.model.rolling_deceleration)
        dx, dy = self.velocity[0]/speed*travel, self.velocity[1]/speed*travel
        radius = self.model.robot_radius+BALL_RADIUS
        self.velocity[0] *= remaining/speed
        self.velocity[1] *= remaining/speed
        # Consume the remaining travel after a rebound. Previously a fraction-0
        # contact reflected velocity but discarded all displacement; repeated
        # opposing kicks could therefore pin the ball to one exact coordinate.
        for _ in range(6):
            squared = dx*dx+dy*dy
            if squared < 1e-18:
                break
            hits = []
            for name, player in self.players.items():
                ox = self.ball[0]-player["position"][0]
                oy = self.ball[1]-player["position"][1]
                # An outgoing foot impulse may start inside the body proxy.
                if ox*dx+oy*dy >= 0:
                    continue
                b = 2*(ox*dx+oy*dy)
                c = ox*ox+oy*oy-radius*radius
                discriminant = b*b-4*squared*c
                if discriminant < 0:
                    continue
                fraction = 0 if c < 0 else (-b-math.sqrt(discriminant))/(2*squared)
                if 0 <= fraction <= 1:
                    hits.append((fraction, name))
            fraction, name = min(hits) if hits else (1, None)
            receiver = self.active_receiver
            if self.pending_pass and receiver == self.pending_pass["receiver"]:
                player = self.players[receiver]
                entry = foot_entry(self.ball, (dx, dy), player["position"], player["yaw"])
                if entry is not None and entry <= fraction:
                    self.ball[0] += dx * entry
                    self.ball[1] += dy * entry
                    self.velocity = [0., 0., 0.]
                    self._contact(receiver, 'foot_trap')
                    break
            self.ball[0] += dx*fraction
            self.ball[1] += dy*fraction
            if name is None:
                break
            player = self.players[name]
            nx, ny = self.ball[0]-player["position"][0], self.ball[1]-player["position"][1]
            length = max(math.hypot(nx, ny), 1e-9)
            nx, ny = nx/length, ny/length
            inward = self.velocity[0]*nx+self.velocity[1]*ny
            # Assumed inelastic reflection, not calibrated NAO/body contact.
            self.velocity[0] = .35*(self.velocity[0]-2*inward*nx)
            self.velocity[1] = .35*(self.velocity[1]-2*inward*ny)
            decision = self.current_decisions.get(name)
            fresh_block = (self.clip_body_contacts and name != self.previous_contact and decision
                           and decision.behaviour == "KEEPER_SHOT")
            self._contact(name)
            if fresh_block:
                self._event("goalkeeper_block", robot=name)
            inward_travel = dx*nx+dy*ny
            dx, dy = (.35*(1-fraction)*(dx-2*inward_travel*nx),
                      .35*(1-fraction)*(dy-2*inward_travel*ny))

    def _stop_after_referee(self, events):
        """Adapters can end an attempt before issuing post-result commands."""
        return False

    def decide_all(self, world):
        return {name: policy.decide(world) for name, policy in self.policies.items()}

    def step(self):
        dt = self.model.dt
        self.time += dt
        referee_events = self.engine.step(self.time, self.ball, self.touch)
        for event in referee_events:
            self.events.append(dict(event))
            if event["event"] == "place_ball":
                self.ball = list(event["point"])
                self.velocity = [0., 0., 0.]
                self.touch = self.previous_contact = None
                self.previous_foot_contact = self.previous_foot_contact_time = None
                self.pass_intent = self.pending_pass = None
                self.kicking.clear()
        if self.reset_on_goal and any(event["event"] == "goal" for event in referee_events):
            self._reset_after_goal()
        if self._stop_after_referee(referee_events):
            return False
        if self.engine.phase == "READY" and self.engine.half not in self.prepared:
            if self.engine.half == 2:
                self._place_formation(jitter=True)
            self.prepared.add(self.engine.half)
            self._event("fixture_formation", half=self.engine.half)
        if self.pending_pass and self.pending_pass["expires"] <= self.time:
            self.stats[self.policies[self.pending_pass["sender"]].team]["expired_passes"] += 1
            self.pending_pass = self.pass_intent = None
        world = self.observation()
        decisions = self.decide_all(world)
        self.current_decisions = decisions
        self.active_receiver = None
        if self.pending_pass:
            receiver = self.pending_pass["receiver"]
            if receiver in decisions and decisions[receiver].behaviour == "FLOW_RECEIVE":
                self.active_receiver = receiver
        proposed = {}
        pushing = set()
        for name, player in self.players.items():
            decision = decisions[name]
            drive = None
            team = self.policies[name].team
            if self.engine.phase == "PLAYING":
                self.stats[team]["playing_player_seconds"] += dt
                direction = self.engine.direction(team)
                if direction*self.ball[0] < -2.5:
                    self.stats[team]["danger_ball_player_seconds"] += dt
                if decision.behaviour == "SUPPORT":
                    self.stats[team]["support_seconds"] += dt
                    behind = direction*player["position"][0] < direction*self.ball[0]
                    if behind:
                        self.stats[team]["support_behind_ball_seconds"] += dt
                    own_distance = min(distance(p["position"], self.ball) for n, p in self.players.items()
                                       if self.policies[n].team == team)
                    other_distance = min(distance(p["position"], self.ball) for n, p in self.players.items()
                                         if self.policies[n].team != team)
                    if other_distance+.20 < own_distance:
                        self.stats[team]["defending_support_seconds"] += dt
                        if behind:
                            self.stats[team]["defending_support_behind_seconds"] += dt
                        if direction*decision.target[0] < direction*self.ball[0]:
                            self.stats[team]["defending_target_behind_seconds"] += dt
            if self.last_decisions.get(name) != decision.behaviour:
                self.stats[team]["decision_transitions"] += 1
                self.last_decisions[name] = decision.behaviour
            if name in self.kicking:
                self.navigation_stages[name] = 'EXECUTING_MOTION'
                finish, held = self.kicking[name]
                if self.engine.phase != "PLAYING":
                    del self.kicking[name]
                elif self.time >= finish:
                    self._finish_kick(name, held)
                    del self.kicking[name]
                action = "stand"
            elif decision.behaviour in ("WAIT", "PENALIZED"):
                action = "stand"
            else:
                command, stage = self.navigators[name].choose(decision, player["position"], player["yaw"],
                    self.ball, [p["position"] for n, p in self.players.items() if n != name])
                self.navigation_stages[name] = stage
                drive = command if isinstance(command, PlanarMotion) else None
                action = drive.label if drive else command
                if action in ("shoot", "pass", "tap"):
                    durations = {"shoot": self.model.shot_seconds, "pass": self.model.pass_seconds,
                                 "tap": self.model.planar_tap_seconds}
                    if decision.behaviour == "FINISH_OPEN":
                        seconds = self.model.planar_shot_seconds
                    elif decision.behaviour == "SNAP_SHOT":
                        seconds = self.model.planar_snap_seconds
                    elif decision.behaviour == "OUTLET_PASS":
                        seconds = self.model.planar_pass_seconds
                    else:
                        seconds = durations[action]
                    self.kicking[name] = (self.time+seconds, decision)
                    counter = {"shoot": "shot_attempts", "pass": "pass_attempts", "tap": "tap_attempts"}
                    category = "shot_attempts" if decision.behaviour == "SNAP_SHOT" else counter[action]
                    self.stats[team][category] += 1
                    kick_event = {"technique": decision.behaviour} if action == "tap" else {}
                    self._event("kick_start", robot=name, action=action, receiver=decision.receiver, **kick_event)
                    if decision.receiver:
                        self.pass_intent = {"kind": "pass_intent", "sender": name,
                                            "receiver": decision.receiver, "expires": self.time+24, "coordinated": decision.behaviour in ("COORDINATED_PASS", "LEAD_PASS", "OUTLET_PASS", "TOUCH_PASS"), "stage": "preparing"}
                        if decision.receive_stance:
                            self.pass_intent.update(landing=decision.face, stance=decision.receive_stance,
                                                    heading=decision.receive_heading)
                    action = "stand"
            if action != self.last_actions.get(name):
                self.stats[team]["action_transitions"] += 1
                self.last_actions[name] = action
            if action.startswith(("left", "right")):
                rate = self.model.left_turn if action.startswith("left") else -self.model.right_turn
                player["yaw"] = wrap(player["yaw"]+rate*dt)
            forward = self.model.walk_speed if action == "walk" else -self.model.back_speed if action == "back" else 0
            left = self.model.left_speed if action == "step_left" else -self.model.right_speed if action == "step_right" else 0
            if drive:
                player["yaw"] = wrap(player["yaw"] + drive.angular * dt)
                forward = drive.forward
                left = drive.lateral
            if forward >= self.model.walk_speed * .60:
                pushing.add(name)
            c, s = math.cos(player["yaw"]), math.sin(player["yaw"])
            x, y = player["position"][:2]
            proposed[name] = [max(-4.4, min(4.4, x+(forward*c-left*s)*dt)),
                              max(-2.9, min(2.9, y+(forward*s+left*c)*dt)), .334]
        if self.clip_body_contacts:
            if self.engine.phase == "PLAYING":
                for name, point in proposed.items():
                    player = self.players[name]
                    proposed[name] = self._limit_body_motion_at_ball(player["position"], point, player["yaw"])
            blocked = stop_conflicting_moves(self.names, self.players, proposed, 2 * self.model.robot_radius)
            if self.engine.phase == "PLAYING":
                for name in blocked:
                    self.stats[self.policies[name].team]["body_blocked_seconds"] += dt
        else:
            # Simultaneous, symmetric disc exclusion; no stochastic 'fall success'
            # is invented, and neither player's motion has loop-order priority.
            for _ in range(3):
                offsets = {n: [0., 0.] for n in proposed}
                for i, a in enumerate(self.names):
                    for b in self.names[i+1:]:
                        sep = distance(proposed[a], proposed[b])
                        overlap = 2*self.model.robot_radius-sep
                        if overlap > 0:
                            if self.engine.phase == "PLAYING" and _ == 0:
                                self.stats[self.policies[a].team]["disc_overlap_player_seconds"] += dt
                                self.stats[self.policies[b].team]["disc_overlap_player_seconds"] += dt
                            ux, uy = ((proposed[a][0]-proposed[b][0])/sep,
                                      (proposed[a][1]-proposed[b][1])/sep) if sep > 1e-9 else (1., 0.)
                            for n, sign in ((a, 1), (b, -1)):
                                offsets[n][0] += sign*ux*overlap*.5
                                offsets[n][1] += sign*uy*overlap*.5
                for n in proposed:
                    proposed[n][0] = max(-4.4, min(4.4, proposed[n][0]+offsets[n][0]))
                    proposed[n][1] = max(-2.9, min(2.9, proposed[n][1]+offsets[n][1]))
                    if self.engine.phase == "PLAYING":
                        proposed[n] = self._limit_body_motion_at_ball(
                            self.players[n]["position"], proposed[n], self.players[n]["yaw"])
        for name, point in proposed.items():
            self.players[name]["position"] = point
        if self.engine.phase == "PLAYING":
            # Ball pushing is a local contact impulse, not a ball attached to
            # a player or a teleport to the requested destination.
            contacts = []
            for n, p in self.players.items():
                dx, dy = self.ball[0]-p["position"][0], self.ball[1]-p["position"][1]
                front = dx*math.cos(p["yaw"])+dy*math.sin(p["yaw"])
                left = -dx*math.sin(p["yaw"])+dy*math.cos(p["yaw"])
                if .08 < front < .28 and abs(left) < .12 and n in pushing:
                    contacts.append(n)
            if contacts and math.hypot(*self.velocity[:2]) < self.model.walk_speed*1.5:
                speed = self.model.walk_speed+self.model.rolling_deceleration*dt*.5
                # Simultaneous eligible feet contribute together. Selecting
                # one closest robot (and its name on a tie) gave a tiny pose
                # advantage control of the entire impulse on every timestep.
                self.velocity = [speed*sum(math.cos(self.players[n]['yaw']) for n in contacts)/len(contacts),
                                 speed*sum(math.sin(self.players[n]['yaw']) for n in contacts)/len(contacts), 0]
                if len(contacts) == 1:
                    self._contact(contacts[0], 'push')
                else:
                    self.touch = None  # Same-step opposing feet have no unique last toucher.
            self._roll_ball()
        else:
            self.velocity = [0., 0., 0.]
        return self.engine.phase != "FINISHED"

    def run(self, trace=None, observer=None):
        """Run the model; an optional observer records states without choosing actions."""
        steps = 0
        if observer:
            observer(self)
        while self.step():
            steps += 1
            if observer:
                observer(self)
            if trace and steps % max(1, round(1/self.model.dt)) == 0:
                import json
                trace.write(json.dumps(self.observation())+"\n")
            if self.time > 2*self.model.half_seconds+5:
                raise RuntimeError("2D match exceeded its configured clock")
        if observer:
            observer(self)
        score = self.engine.score
        candidate_index = 0 if self.candidate_team == "RED" else 1
        return {"seed": self.seed, "candidate_team": self.candidate_team,
                "candidate": self.candidate, "score_red_blue": list(score),
                "candidate_goal_difference": score[candidate_index]-score[1-candidate_index],
                "simulated_seconds": self.time, "phase": self.engine.phase,
                "team_stats": {t: dict(v) for t, v in self.stats.items()},
                "model": asdict(self.model), "physics_or_hardware_validated": False,
                "limitations": ["Kinematic discs and contact impulses; no NAO balance or joint dynamics.",
                    "Perfect ground-truth state; no independent camera localisation.",
                    "Ball friction, noise and contact are uncalibrated model assumptions.",
                    "Kickoff formation placement is a 2D replay convention.",
                    "Uses current referee geometry, but not complete physical-foul rules.",
                    "An abstract pass completion is not a validated Webots pass."]}
