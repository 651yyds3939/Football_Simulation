"""Coordinate passing, runs and goal-side coverage in planar 4v4."""

from dataclasses import dataclass
import math

from Utils.CourseSpecs import BALL_RADIUS, GOAL_WIDTH, PITCH_LENGTH, PITCH_WIDTH
from Utils.DefensivePlan import route, wrap
from Utils.GoalCover import rolling_crossing, reachable_shot_point
from Utils.Passing import bearing, frame, offset
from Utils.TeamPolicy import Decision, distance, lane_clear

HALF_FIELD = PITCH_LENGTH / 2
HALF_WIDTH = PITCH_WIDTH / 2


def clamp(value, lo, hi):
    return max(lo, min(value, hi))


def inside(point, x=4.28, y=2.62):
    return clamp(point[0], -x, x), clamp(point[1], -y, y)


def pose_for_contact(ball, heading, lateral=0.05):
    return offset(offset(ball, heading, -0.17), heading - math.pi / 2, lateral)


def goal_side(ball, direction, gap=0.43):
    return inside((ball[0] - direction * gap, ball[1] * 0.86))


def partial_lane_clear(start, end, obstacles, radius, start_margin=0.0):
    yaw = bearing(start, end)
    if start_margin > 0:
        start = offset(start, yaw, min(start_margin, distance(start, end) * 0.4))
    return lane_clear(start, end, obstacles, radius)


def rolling_lane(start, target, positions, radius):
    dx, dy = target[0] - start[0], target[1] - start[1]
    length = dx * dx + dy * dy
    if length < 1e-9:
        return False
    for point in positions:
        ahead = (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
        if ahead <= 0:
            continue
        t = min(1.0, ahead / length)
        if distance(point, (start[0] + dx * t, start[1] + dy * t)) < radius:
            return False
    return True


@dataclass
class CarryRoute:
    name: str
    marker: str
    target: tuple
    started: float


@dataclass
class DuelRoute:
    name: str
    helper: str
    anchor: tuple
    target: tuple
    expires: float


class Flow:
    def __init__(self, model):
        self.model = model
        self.enabled = set()
        self.carry = {}
        self.duel = {}
        self.anchor = None
        self.crowd_snapshot = None
        self.crowd_exit = {}
        self.pass_hold = {}
        self.support_plan = {}
        self.last_pass = {}
        self.keeper_attempt = {}
        self.use_wider_pass = True
        self.finish_range = True
        self.defend_enabled = True
        self.evade_enabled = True
        self.support_enabled = True
        self.duel_enabled = True
        self.press_enabled = True
        self.no_keeper_turn = 1.8
        self.preferred_pass = 0.9
        self.pass_pressure = 0.38
        self.pass_eta = 6.4
        self.avoid_min = 0.45
        self.avoid_max = 2.17
        self.outlet_space = 0.76
        self.duel_wait = 1.8
        self.stuck_cut = 2.4
        self.steer = True
        self.turn_scale = 1.0
        self.side_scale = 1.0
        self.keeper_side_scale = 1.38
        self.tap_enabled = True
        self.allow_trap = True
        self.arc_approach = True
        self.crowd_radius = 0.42
        self.allow_duel_flare = True
        self.touch_pass = True
        self.touch_pass_threshold = 0.51
        self.touch_pass_cooldown = 3.6
        self.escape_delay = 1.65
        self.lock_roles = True
        self.chaser = {}
        self.break_margin = 0.08
        self.long_shot = True
        self.quick_outlet = True
        self.attack_x_limit = 3.95
        self.keeper_loose = True
        self.keeper_near_depth = 1.30
        self.press_start = 0.56
        self.wide_layer = True
        self.snap_enabled = True
        self.flank_defence = False
        self.flank_gap = 0.26
        self.press_duel = 0.42
        self.counter_layer = True
        self.finish_movement = True
        self.finish_move_x = 2.50
        self.finish_lateral = 0.53
        self.finish_commit = {}
        self.finish_decision = {}
        self.attack_layer = True
        self.tap_path_exact = False
        self.duel_flank_time = 2.9
        self.helper_path = True
        self.helper_limit = 1.70
        self.free_runner_body = 0.25
        self.last_escape = {}
        self.escape_retry = True
        self.duel_break_gap = 6.2
        self.arc_commit = 5.95
        self.dogleg = True
        self.evade_clearance = 0.30
        self.diagonal_save = True
        self.edge_min_stall = 3.8
        self.escape = {}
        self.tap_wait = 1.7
        self.tap_range = 0.35
        self.press_gap = 0.33
        self.dribble_width = 0.55
        self.tap_attempt = {}
        self.pass_hold_seconds = 7.0
        self.support_hold_seconds = 5.0

    def reset(self):
        self.crowd_snapshot = None
        self.crowd_exit.clear()
        self.carry.clear()
        self.duel.clear()
        self.anchor = None
        self.pass_hold.clear()
        self.support_plan.clear()
        self.last_pass.clear()
        self.keeper_attempt.clear()
        self.tap_attempt.clear()
        self.escape.clear()
        self.chaser.clear()
        self.finish_commit.clear()
        self.finish_decision.clear()
        self.last_escape.clear()

    def adjust(self, world, orders, kicking):
        match = world["match"]
        if not self.enabled:
            return orders
        if match["phase"] != "PLAYING" or not match["released"]:
            self.reset()
            return orders
        players = {
            name: state
            for name, state in world["robots"].items()
            if name not in world.get("penalties", {}) and state.get("standing", True)
        }
        ball = tuple(world["ball"]["position"][:2])
        velocity = tuple(world["ball"]["velocity"][:2])
        speed = math.hypot(*velocity)
        now = world["time"]
        pair = self.crowd_pair(players, ball)
        if not pair or speed > 0.065:
            self.anchor = None
        elif self.anchor is None or exceeds_anchor(self.anchor, pair, ball):
            self.anchor = ball, now, pair
        for team in ("Red", "Blue"):
            if team not in self.enabled:
                continue
            one = {n: p for n, p in players.items() if n.startswith(team)}
            other = {n: p for n, p in players.items() if not n.startswith(team)}
            direction = match["red_direction"] * (1 if team == "Red" else -1)
            self.order_team(team, one, other, ball, velocity, now, direction, world, orders, kicking)
        self.open_crowded_lane(players, ball, speed, now, orders, kicking, world.get("pass_intent"))
        return orders

    def open_crowded_lane(self, players, ball, speed, now, orders, kicking, intent):
        """Move off-ball players out when their commands produce no movement."""
        if intent or speed > 0.035:
            self.crowd_snapshot = None
            self.crowd_exit.clear()
            return
        nearby = {
            name: tuple(player["position"][:2])
            for name, player in players.items()
            if not name.endswith("Goalkeeper") and distance(player["position"], ball) < 0.83
        }
        teams = {
            team: sorted((distance(point, ball), name) for name, point in nearby.items()
                         if name.startswith(team))
            for team in ("Red", "Blue")
        }
        if any(not members or members[0][0] > 0.55 for members in teams.values()):
            self.crowd_snapshot = None
            self.crowd_exit.clear()
            return
        if self.crowd_exit:
            started, anchor, _ = self.crowd_snapshot
            if now - started < 5.0 and distance(ball, anchor) < 0.12:
                for name, target in self.crowd_exit.items():
                    if name in players and name not in kicking:
                        orders[name] = Decision("MAKE_SPACE", target, ball)
                return
            self.crowd_exit.clear()
            self.crowd_snapshot = None
        if len(nearby) < 3:
            self.crowd_snapshot = None
            return
        if self.crowd_snapshot:
            started, anchor, poses = self.crowd_snapshot
            unchanged = (
                distance(ball, anchor) < 0.065 and poses.keys() == nearby.keys()
                and all(distance(point, poses[name]) < 0.10 for name, point in nearby.items())
            )
            if unchanged and now - started < 4.0:
                return
            if unchanged:
                for team, members in teams.items():
                    if team not in self.enabled:
                        continue
                    for _, name in members[1:]:
                        point = nearby[name]
                        yaw = bearing(ball, point)
                        options = [
                            inside(offset(point, yaw + angle, 0.43))
                            for angle in (0.0, -0.65, 0.65)
                        ]
                        obstacles = [r["position"] for n, r in players.items() if n != name]
                        target = max(
                            options, key=lambda q: (
                                lane_clear(point, q, obstacles, 0.285),
                                min(distance(q, p) for p in obstacles),
                            )
                        )
                        if distance(target, ball) > distance(point, ball) + 0.16:
                            self.crowd_exit[name] = target
                            if name not in kicking:
                                orders[name] = Decision("MAKE_SPACE", target, ball)
        self.crowd_snapshot = now, ball, nearby

    def order_team(self, team, one, other, ball, velocity, now, direction, world, orders, kicking):
        field = {n: p for n, p in one.items() if not n.endswith("Goalkeeper")}
        if not field or not other:
            return
        keeper = team + "Goalkeeper"
        positions = [r["position"] for r in other.values()]
        enemy = min(other, key=lambda n: (distance(ball, other[n]["position"]), n))
        enemy_gap = distance(ball, other[enemy]["position"])
        near = min(field, key=lambda n: (distance(ball, field[n]["position"]), n))
        owner = world.get("last_foot_contact")
        touch_time = world.get("last_foot_contact_time")
        my_control = (
            owner in field
            and touch_time is not None
            and now - touch_time < 1.3
            and distance(field[owner]["position"], ball) < 0.45
        )
        their_control = (
            (
                owner in other
                and touch_time is not None
                and now - touch_time < 1.5
                and distance(other[owner]["position"], ball) < 0.60
            )
            or enemy_gap < 0.32
            and distance(field[near]["position"], ball) > 0.47
        )
        carrier = owner if my_control else near
        if self.lock_roles and not my_control:
            carrier = self.pick_chaser(team, field, ball, velocity)
        else:
            self.chaser[team] = carrier
        intent = world.get("pass_intent")
        if (
            intent
            and intent.get("sender") in one
            and intent.get("receiver") in field
            and intent.get("stance")
        ):
            if intent["receiver"] not in kicking:
                self.receive(intent, field[intent["receiver"]], ball, velocity, orders)
            if intent["sender"] not in kicking:
                point = tuple(one[intent["sender"]]["position"][:2])
                orders[intent["sender"]] = Decision("SUPPORT_PASS", point, ball)
            self.offer_width(
                field, intent["receiver"], ball, direction, orders, kicking, intent["sender"]
            )
        elif self.free_boundary_ball(field, other, ball, velocity, direction, now, orders, kicking):
            self.pass_hold.pop(team, None)
        elif self.snap_enabled and self.try_snap(
            team, carrier, field, other, ball, velocity, direction, now, orders, kicking
        ):
            self.pass_hold.pop(team, None)
        elif self.try_finish_from_space(
            team, carrier, field, other, ball, velocity, direction, now, orders, kicking
        ):
            self.pass_hold.pop(team, None)
        elif self.touch_pass and self.try_touch_pass(
            team, carrier, field, other, ball, velocity, direction, now, orders, kicking
        ):
            self.pass_hold.pop(team, None)
        elif self.tap_enabled and self.tap_contest(
            team, field, other, ball, velocity, now, direction, orders, kicking
        ):
            self.pass_hold.pop(team, None)
        elif self.duel_enabled and self.resolve_duel(
            team, field, other, ball, direction, now, orders, kicking
        ):
            self.pass_hold.pop(team, None)
        elif their_control and not my_control and self.press_enabled:
            self.pass_hold.pop(team, None)
            self.carry.pop(team, None)
            self.defend(field, ball, velocity, direction, orders, kicking)
        else:
            attack = field[carrier]
            if distance(attack["position"], ball) <= 0.52 and carrier not in kicking:
                receiver = self.attack(
                    team,
                    carrier,
                    attack,
                    field,
                    other,
                    ball,
                    velocity,
                    direction,
                    now,
                    orders,
                    kicking,
                )
                if self.support_enabled and not receiver:
                    self.place_support(
                        team, field, carrier, ball, direction, positions, now, orders, kicking
                    )
            else:
                if self.lock_roles and carrier not in kicking:
                    speed = math.hypot(*velocity)
                    horizon = min(2.8, 0.64 / max(speed, 0.015))
                    objective = inside(
                        (ball[0] + velocity[0] * horizon, ball[1] + velocity[1] * horizon)
                    )
                    orders[carrier] = Decision("PURSUE_BALL", objective, ball)
                if self.support_enabled:
                    self.offer_width(field, carrier, ball, direction, orders, kicking)
        if keeper in one and keeper not in kicking and self.defend_enabled:
            pick = self.keep_goal(team, one[keeper], other, ball, velocity, now, direction)
            if pick:
                orders[keeper] = pick

    def pick_chaser(self, team, field, ball, velocity):
        speed = math.hypot(*velocity)
        time = min(2.1, 0.48 / max(speed, 0.015))
        forecast = (ball[0] + velocity[0] * time, ball[1] + velocity[1] * time)
        current = self.chaser.get(team)
        scores = []
        for name, p in field.items():
            point = p["position"]
            gap = distance(point, forecast)
            error = abs(wrap(bearing(point, forecast) - p["yaw"]))
            travel = gap + min(0.36, error * 0.12)
            if name == current:
                travel -= self.break_margin
            scores.append((travel, name))
        user = min(scores)[1]
        self.chaser[team] = user
        return user

    def receive(self, intent, own, ball, velocity, orders):
        receiver = intent["receiver"]
        heading = intent["heading"]
        target = intent["stance"]
        if intent["stage"] == "released":
            settle = math.hypot(*velocity) / (2 * self.model.rolling_deceleration)
            predicted = (ball[0] + velocity[0] * settle, ball[1] + velocity[1] * settle)
            if math.hypot(*velocity) < 0.05 and distance(own["position"], ball) > 0.30:
                target = pose_for_contact(ball, heading, 0.0)
            else:
                target = inside(offset(predicted, heading, -0.23))
            orders[receiver] = Decision(
                "FLOW_RECEIVE" if self.allow_trap else "RECEIVE_FORWARD",
                target,
                offset(target, heading, 1.0),
            )
        else:
            orders[receiver] = Decision("PREPARE_FORWARD", target, offset(target, heading, 1.0))

    def attack(self, team, name, own, field, other, ball, velocity, direction, now, orders, kicking):
        opponents = [p["position"] for p in other.values()]
        front, side = frame(own["position"], ball, own["yaw"])
        in_control = 0.07 < front < 0.35 and abs(side) < 0.16
        if math.hypot(*velocity) > 0.17:
            return None
        if self.finish_range and in_control:
            shot = self.find_shot(own, ball, field, other, direction, name)
            if shot:
                self.pass_hold.pop(team, None)
                self.carry.pop(team, None)
                orders[name] = shot
                return None
        pass_plan = self.pass_hold.get(team)
        if pass_plan:
            anchor, expires, sender, order = pass_plan
            if (
                sender != name
                or now > expires
                or distance(anchor, ball) > 0.09
                or order.receiver in kicking
                or order.receiver not in field
                or not lane_clear(ball, order.face, opponents, 0.25)
            ):
                self.pass_hold.pop(team, None)
                self.last_pass[team] = now
                pass_plan = None
        pressure = min(distance(ball, p) for p in opponents)
        if (
            self.quick_outlet
            and pass_plan is None
            and in_control
            and pressure > self.pass_pressure
            and now - self.last_pass.get(team, -100.0) > 1.4
        ):
            order = self.find_pass(name, own, field, other, ball, direction, kicking)
            if order:
                pass_plan = self.pass_hold[team] = (ball, now + self.pass_hold_seconds, name, order)
        if pass_plan:
            order = pass_plan[3]
            orders[name] = order
            stance = order.receive_stance
            orders[order.receiver] = Decision(
                "EARLY_RECEIVE", stance, offset(stance, order.receive_heading, 1.0)
            )
            return order.receiver
        if self.evade_enabled:
            cut = self.find_finishing_lane(team, name, own, other, ball, direction, now)
            if cut is None:
                cut = self.choose_carry(team, name, own, other, ball, direction, now)
            if cut is not None:
                aim = bearing(ball, cut)
                if (
                    self.tap_enabled
                    and in_control
                    and pressure < 0.82
                    and abs(wrap(aim - own["yaw"])) > math.radians(19)
                    and self.safe_pass_path(
                        ball, offset(ball, aim, 0.22), opponents, self.model.planar_tap_seconds
                    )
                    and self.set_tap(name, own, ball, cut, now, orders, "CARRY_TAP", 0.22)
                ):
                    return None
                orders[name] = Decision("BEAT_MARKER", pose_for_contact(ball, aim, 0.0), cut)
                return None
        if (
            self.steer
            and distance(own["position"], ball) < 0.57
            and (orders[name].behaviour not in ("PASS", "LEAD_PASS") or pressure >= 0.82)
        ):
            aim = (direction * (HALF_FIELD + 0.1), clamp(ball[1] * 0.52, -0.96, 0.96))
            orders[name] = Decision(
                "CARRY_LANE", pose_for_contact(ball, bearing(ball, aim), 0.0), aim
            )
        return None

    def try_finish_from_space(
        self, team, name, field, other, ball, velocity, direction, now, orders, kicking
    ):
        if (
            not self.long_shot
            or name in kicking
            or direction * ball[0] < 2.36
            or math.hypot(*velocity) > 0.18
        ):
            return False
        own = field[name]
        if distance(own["position"], ball) > 0.35:
            return False
        front, side = frame(own["position"], ball, own["yaw"])
        if front < 0.079 or abs(side) > 0.158:
            return False
        order = self.finish_decision.get(team)
        enemies = [r["position"] for r in other.values()]
        if order:
            sender, anchor, expires, planned = order
            if (
                name == sender
                and now < expires
                and distance(ball, anchor) < 0.079
                and rolling_lane(ball, planned.face, enemies, 0.25)
            ):
                orders[name] = planned
                return True
        selection = self.find_shot(own, ball, field, other, direction, name)
        if selection is None:
            self.finish_decision.pop(team, None)
            return False
        self.finish_decision[team] = (name, ball, now + 4.8, selection)
        orders[name] = selection
        return True

    def try_snap(self, team, name, field, other, ball, velocity, direction, now, orders, kicking):
        if (
            name in kicking
            or not self.use_wider_pass
            or direction * ball[0] < HALF_FIELD - self.model.planar_snap_range + 0.13
            or math.hypot(*velocity) > 0.17
        ):
            return False
        own = field[name]
        front, side = frame(own["position"], ball, own["yaw"])
        if not 0.082 < front < 0.31 or abs(side) > 0.14:
            return False
        opponents = [r["position"] for r in other.values()]
        options = []
        for y in (-1.05, -0.78, -0.42, 0.0, 0.42, 0.78, 1.05):
            target = (direction * (HALF_FIELD + BALL_RADIUS + 0.025), y)
            travel = distance(ball, target)
            heading = bearing(ball, target)
            if (
                travel > self.model.planar_snap_range * 0.94
                or abs(wrap(heading - own["yaw"])) > math.radians(85)
                or not rolling_lane(ball, target, opponents, 0.285)
            ):
                continue
            if abs(ball[1] - y) < 0.10 and abs(y) > 1.02:
                continue
            options.append((travel + 0.21 * abs(y), target))
        if not options:
            return False
        _, target = min(options)
        return self.set_tap(
            name, own, ball, target, now, orders, "SNAP_SHOT", self.model.planar_snap_range
        )

    def find_shot(self, own, ball, field, other, direction, name):
        candidates = []
        swing = (
            self.model.planar_shot_range
            if self.use_wider_pass and self.long_shot
            else self.model.shot_range
        )
        robots = [p["position"] for n, p in {**field, **other}.items() if n != name]
        span = GOAL_WIDTH / 2 - BALL_RADIUS - 0.19
        for y in (ball[1] * 0.66, 0.0, -0.99, 0.99, -0.55, 0.55, -0.29, 0.29):
            target = (direction * (HALF_FIELD + BALL_RADIUS + 0.04), clamp(y, -span, span))
            gap = distance(ball, target)
            if gap > swing * 0.95 or direction * (target[0] - ball[0]) < 0.04:
                continue
            yaw = bearing(ball, target)
            error = abs(wrap(yaw - own["yaw"]))
            if error < 0.72 and rolling_lane(ball, target, robots, 0.27):
                candidates.append((error + gap * 0.22, target, yaw))
        if not candidates:
            return None
        _, target, yaw = min(candidates)
        return Decision(
            "FINISH_OPEN", pose_for_contact(ball, yaw), target, "shoot", kick_distance=swing
        )

    def safe_pass_path(self, ball, target, rivals, windup, roll_distance=None):
        """Reject passes that an opponent could reach before the rolling ball."""
        length = distance(ball, target)
        travel = length if roll_distance is None else roll_distance
        if length < 0.05 or travel <= 0.0:
            return False
        deceleration = self.model.rolling_deceleration
        speed = math.sqrt(2 * deceleration * travel)
        contact_radius = self.model.robot_radius + BALL_RADIUS
        if not rolling_lane(ball, target, rivals, contact_radius):
            return False
        for fraction in (0.25, 0.50, 0.75, 1.0):
            elapsed = (speed - math.sqrt(max(0.0, speed**2 * (1 - fraction)))) / deceleration
            point = tuple(a + fraction * (b - a) for a, b in zip(ball, target))
            margin = contact_radius + 0.04 * fraction * length
            reach = margin + self.model.walk_speed * max(0.0, windup + elapsed - 0.24)
            if any(distance(point, rival) < reach for rival in rivals):
                return False
        return True

    def pass_can_release(self, name, decision, players, ball, heading, roll_distance):
        receiver = players.get(decision.receiver)
        if not receiver or not receiver.get("standing", True):
            return False
        predicted = offset(ball, heading, roll_distance)
        if distance(receiver["position"], predicted) > 0.36 + self.model.walk_speed * math.sqrt(
            2 * roll_distance / self.model.rolling_deceleration
        ):
            return False
        prefix = "Red" if name.startswith("Red") else "Blue"
        rivals = [p["position"] for n, p in players.items() if not n.startswith(prefix)]
        return self.safe_pass_path(ball, predicted, rivals, 0.0, roll_distance)

    def try_touch_pass(
        self, team, name, field, other, ball, velocity, direction, now, orders, kicking
    ):
        if name in kicking or now - self.last_pass.get(team, -100.0) < self.touch_pass_cooldown:
            return False
        own = field[name]
        point, yaw = own["position"], own["yaw"]
        front, side = frame(point, ball, yaw)
        if not 0.08 < front < 0.309 or abs(side) > 0.139 or math.hypot(*velocity) > 0.135:
            return False
        if direction * math.cos(yaw) < -0.52 and direction * ball[0] > -2.6:
            return False
        rivals = [p["position"] for p in other.values()]
        pressure = min(distance(ball, p) for p in rivals)
        risk = pressure < 0.80 or not rolling_lane(ball, offset(ball, yaw, 1.05), rivals, 0.35)
        if not risk:
            return False
        options = []
        wide = self.model.planar_touch_pass_range if self.use_wider_pass else self.model.pass_range
        upstream = 0.0 if direction > 0 else math.pi
        own_positions = [p["position"] for n, p in field.items() if n != name]
        for mate, robot in field.items():
            p = robot["position"]
            if mate == name or mate in kicking or not 0.30 < distance(p, ball) < wide + 0.38:
                continue
            face = bearing(p, ball)
            headings = (robot["yaw"], face, upstream, upstream + 0.82, upstream - 0.82)
            for heading in headings:
                stance = tuple(p[:2])
                target = offset(stance, heading, 0.235)
                length = distance(ball, target)
                if not 0.32 < length < wide or abs(target[0]) > 4.32 or abs(target[1]) > 2.78:
                    continue
                forward = direction * (target[0] - ball[0])
                if forward < (-0.6 if abs(ball[0]) > 2.75 else -0.24):
                    continue
                launch = bearing(ball, target)
                if abs(wrap(launch - yaw)) > math.radians(98):
                    continue
                if not rolling_lane(ball, target, rivals, 0.224):
                    continue
                if not rolling_lane(ball, target, own_positions + [point], 0.216):
                    continue
                turn = abs(wrap(heading - robot["yaw"]))
                flight = math.sqrt(2 * length / self.model.rolling_deceleration)
                turn_budget = (
                    self.model.planar_turn_rate * self.turn_scale
                    if self.steer
                    else self.model.left_turn
                )
                if turn > turn_budget * (flight + self.model.planar_tap_seconds) + 0.32:
                    continue
                clear = min(distance(target, e) for e in rivals)
                forward_path = rolling_lane(target, offset(target, upstream, 0.64), rivals, 0.33)
                if clear < 0.32 or clear < pressure - 0.15 and forward < 0.12:
                    continue
                cost = min(clear, 1.05) + 0.63 * forward + 0.37 * forward_path - 0.34 * turn
                if cost >= self.touch_pass_threshold and self.safe_pass_path(
                    ball, target, rivals, self.model.planar_tap_seconds
                ):
                    options.append((cost, mate, target, heading, stance, length))
        if not options:
            return False
        _, mate, target, heading, stance, length = max(options)
        self.last_pass[team] = now
        orders[name] = Decision(
            "TOUCH_PASS", tuple(point[:2]), target, "tap", mate, stance, heading, length
        )
        orders[mate] = Decision("EARLY_RECEIVE", stance, offset(stance, heading, 1.0))
        return True

    def find_pass(self, name, own, field, other, ball, direction, kicking):
        width = self.model.planar_pass_range if self.use_wider_pass else self.model.pass_range
        turn_rate = (
            self.model.planar_turn_rate * self.turn_scale
            if self.steer
            else min(self.model.left_turn, self.model.right_turn)
        )
        options = []
        rivals = [p["position"] for p in other.values()]
        occupied = [p["position"] for n, p in field.items() if n != name]
        own_yaw = own["yaw"]
        immediate = min(distance(ball, e) for e in rivals)
        for mate, player in field.items():
            if mate == name or mate in kicking:
                continue
            p, yaw = player["position"], player["yaw"]
            if not 0.43 <= distance(ball, p) <= width + 0.60:
                continue
            # A teammate presents either foot by changing stance, never by
            # teleporting or being credited for a body collision.
            upfield = 0.0 if direction > 0 else math.pi
            towards_source = bearing(p, ball)
            headings = (yaw, upfield, upfield - 0.80, upfield + 0.80, towards_source)
            for receive_yaw in headings:
                for step in (0.0, 0.15, -0.14):
                    stance = inside(offset(p, receive_yaw, step))
                    landing = offset(stance, receive_yaw, 0.23)
                    travel = distance(ball, landing)
                    if travel > width or travel < 0.34 and self.use_wider_pass:
                        continue
                    if direction * (landing[0] - ball[0]) < (-0.7 if abs(ball[0]) > 3.1 else -0.32):
                        continue
                    heading = bearing(ball, landing)
                    error = abs(wrap(heading - own_yaw))
                    if error > (0.94 if immediate > 0.83 else 0.60):
                        continue
                    pass_forward_to_receiver = math.cos(heading - receive_yaw)
                    if pass_forward_to_receiver > 0.15:
                        # Land just beside the receive foot, rather than
                        # approaching from behind into the receiver disc.
                        protection = self.model.robot_radius + BALL_RADIUS
                        if not lane_clear(ball, landing, [stance], protection - 0.016):
                            continue
                    bounds = self.model.robot_radius + BALL_RADIUS
                    if not lane_clear(ball, landing, rivals, 0.26) or not lane_clear(
                        ball, landing, [q for q in occupied if q is not p], bounds
                    ):
                        continue
                    receive_time, _, arrival = route(p, yaw, stance, tolerance=0.06)
                    receive_time += max(0.0, abs(wrap(receive_yaw - arrival)) - 0.17) / turn_rate
                    clearance = min(distance(landing, e) for e in rivals)
                    eta_budget = self.model.planar_pass_seconds + math.sqrt(
                        2 * travel / self.model.rolling_deceleration
                    )
                    if receive_time > min(self.pass_eta, eta_budget + 1.6) or clearance < 0.33:
                        continue
                    open_run = lane_clear(landing, offset(landing, receive_yaw, 0.64), rivals, 0.34)
                    gain = direction * (landing[0] - ball[0])
                    if not open_run and clearance < immediate * 0.80:
                        continue
                    preference = (
                        min(clearance, 1.1)
                        + 0.50 * gain
                        + 0.38 * open_run
                        - error * 0.8
                        - 0.11 * receive_time
                    )
                    if preference < self.preferred_pass or not self.safe_pass_path(
                        ball, landing, rivals, self.model.planar_pass_seconds
                    ):
                        continue
                    options.append((preference, mate, landing, stance, receive_yaw, heading, travel))
        if not options:
            return None
        _, mate, landing, stance, receive_yaw, heading, travel = max(options)
        return Decision(
            "OUTLET_PASS",
            pose_for_contact(ball, heading),
            landing,
            "pass",
            mate,
            stance,
            receive_yaw,
            travel,
        )

    def place_support(self, team, field, carrier, ball, direction, opponents, now, orders, kicking):
        source = field[carrier]
        choice = self.support_plan.get(team)
        if not choice or choice[0] != carrier or now > choice[3] or distance(ball, choice[2]) > 0.60:
            candidates = []
            yaw = source["yaw"]
            for mate, p in field.items():
                if mate == carrier or mate in kicking:
                    continue
                for shift in (-self.outlet_space, -0.58, 0.58, self.outlet_space):
                    landing = inside(offset(offset(ball, yaw, 0.86), yaw + math.pi / 2, shift))
                    if direction * (landing[0] - ball[0]) < -0.32:
                        continue
                    if not lane_clear(ball, landing, opponents, 0.28):
                        continue
                    heading = bearing(landing, (direction * HALF_FIELD, 0.0))
                    stance = inside(offset(landing, heading, -0.24))
                    if distance(stance, ball) < 0.58:
                        continue
                    length = distance(stance, p["position"])
                    clear = min(distance(stance, q) for q in opponents)
                    score = min(clear, 1.3) - length * 0.70 - abs(shift) * 0.15
                    candidates.append((score, mate, stance, heading))
            if candidates:
                _, mate, stance, heading = max(candidates)
                choice = carrier, mate, ball, now + self.support_hold_seconds, stance, heading
                self.support_plan[team] = choice
        if choice and choice[1] in field and choice[1] not in kicking:
            _, mate, _, _, stance, heading = choice
            orders[mate] = Decision("OFFER_OUTLET", stance, offset(stance, heading, 1.0))
            self.offer_width(field, carrier, ball, direction, orders, kicking, mate)

    def offer_width(self, field, main, ball, direction, orders, kicking, excluded=None):
        for name, state in field.items():
            if name in (main, excluded) or name in kicking:
                continue
            x, y = state["position"][:2]
            if orders[name].behaviour in ("RECEIVE_FORWARD", "PREPARE_FORWARD", "EARLY_RECEIVE"):
                continue
            if name.endswith("Defender"):
                if direction * (x - ball[0]) > -0.70 or distance((x, y), ball) < 0.60:
                    target = inside((ball[0] - direction * 1.15, ball[1] * 0.56))
                    orders[name] = Decision("COVER_CUTBACK", target, ball)
            elif self.wide_layer or distance((x, y), ball) < 0.83:
                if self.attack_layer and excluded in orders:
                    sign = -1 if orders[excluded].target[1] >= ball[1] else 1
                else:
                    sign = 1 if y >= ball[1] else -1
                forward_step = 0.67 if excluded is None else 1.26
                lateral_step = (1.05 if excluded is None else 1.27) * sign
                target = inside(
                    (ball[0] + direction * forward_step, ball[1] + lateral_step),
                    self.attack_x_limit,
                    2.60,
                )
                orders[name] = Decision("OFFER_OUTLET", target, ball)

    def find_finishing_lane(self, team, name, own, other, ball, direction, now):
        if not self.finish_movement or direction * ball[0] < self.finish_move_x:
            return None
        rivals = [p["position"] for p in other.values()]
        previous = self.finish_commit.get(team)
        if previous:
            carrier, anchor, expires, target = previous
            if (
                name == carrier
                and now < expires
                and distance(ball, target) > 0.19
                and rolling_lane(ball, target, rivals, 0.285)
            ):
                return target
            self.finish_commit.pop(team, None)
        choices = []
        swing = self.model.planar_shot_range
        for dx in (0.20, 0.42, 0.64):
            for dy in (-0.75, -self.finish_lateral, 0.0, self.finish_lateral, 0.75):
                target = inside((ball[0] + direction * dx, ball[1] + dy), 4.17, 1.56)
                if distance(ball, target) < 0.22 or direction * (target[0] - ball[0]) < -0.04:
                    continue
                heading = bearing(ball, target)
                angle = abs(wrap(heading - own["yaw"]))
                if angle > math.radians(79) or not rolling_lane(ball, target, rivals, 0.30):
                    continue
                best = None
                for y in (-1.05, -0.63, 0.0, 0.63, 1.05):
                    goal = (direction * (HALF_FIELD + BALL_RADIUS + 0.04), y)
                    if not rolling_lane(target, goal, rivals, 0.295):
                        continue
                    gap = distance(target, goal)
                    if gap < swing * 0.95:
                        quality = swing - gap - 0.12 * abs(y)
                        best = quality if best is None else max(best, quality)
                if best is not None:
                    choices.append((best - 0.35 * angle - 0.14 * abs(target[1]), target))
        if not choices:
            return None
        _, target = max(choices)
        self.finish_commit[team] = (name, ball, now + 8.5, target)
        return target

    def choose_carry(self, team, name, own, others, ball, direction, now):
        current = self.carry.get(team)
        if current:
            marker = others.get(current.marker)
            if (
                current.name == name
                and marker
                and now - current.started < 28
                and direction * (ball[0] - marker["position"][0]) < 0.32
                and distance(ball, current.target) > 0.23
                and distance(ball, own["position"]) < 0.50
                and partial_lane_clear(ball, current.target, [marker["position"]], 0.27, 0.10)
            ):
                return current.target
            self.carry.pop(team, None)
        direct = (direction * HALF_FIELD, clamp(ball[1] * 0.55, -0.93, 0.93))
        rivals = [
            (n, r["position"])
            for n, r in others.items()
            if direction * (r["position"][0] - ball[0]) > 0.08
            and self.avoid_min < distance(ball, r["position"]) < self.avoid_max
        ]
        blocker = [
            (distance(ball, pos), n, pos)
            for n, pos in rivals
            if not lane_clear(ball, direct, [pos], 0.47)
        ]
        if not blocker:
            return None
        _, marker, point = min(blocker)
        options = []
        obstacles = [r["position"] for r in others.values()]
        for side in (-1, 1):
            direct = inside(
                (point[0] + direction * 0.38, point[1] + side * self.dribble_width),
                HALF_FIELD - 0.17,
                2.62,
            )
            candidates = [(0.0, direct)]
            if self.dogleg:
                past_ball = max(0.28, direction * (point[0] - ball[0]) - 0.34)
                bend = inside(
                    (ball[0] + direction * past_ball, point[1] + side * (self.dribble_width + 0.06)),
                    HALF_FIELD - 0.17,
                    2.62,
                )
                candidates.append((0.23, bend))
            for delay, cut in candidates:
                if not partial_lane_clear(ball, cut, obstacles, self.evade_clearance, 0.09):
                    continue
                error = abs(wrap(bearing(ball, cut) - own["yaw"]))
                if direction * (cut[0] - ball[0]) > 0.12 and error < 1.20:
                    options.append(
                        (delay + error + abs(cut[1]) * 0.15 + distance(ball, cut) * 0.12, cut)
                    )
        if not options:
            return None
        target = min(options)[1]
        self.carry[team] = CarryRoute(name, marker, target, now)
        return target

    def set_tap(self, name, own, ball, target, now, orders, behaviour, kick_distance):
        front, side = frame(own["position"], ball, own["yaw"])
        if (
            now - self.tap_attempt.get(name, -100.0) < self.tap_wait
            or not 0.078 < front < 0.31
            or abs(side) > 0.142
            or abs(wrap(bearing(ball, target) - own["yaw"])) > math.radians(100)
        ):
            return False
        self.tap_attempt[name] = now
        orders[name] = Decision(behaviour, ball, target, "tap", kick_distance=kick_distance)
        return True

    def crowd_pair(self, players, ball):
        pair = []
        for prefix in ("Red", "Blue"):
            choices = [
                (distance(robot["position"], ball), n)
                for n, robot in players.items()
                if n.startswith(prefix)
            ]
            if not choices:
                return None
            gap, name = min(choices)
            if gap > self.crowd_radius:
                return None
            pair.append(name)
        return tuple(pair)

    def tap_contest(self, team, field, other, ball, velocity, now, direction, orders, kicking):
        if (
            not self.anchor
            or now - self.anchor[1] < self.duel_wait * 0.50
            or math.hypot(*velocity) > 0.085
        ):
            return False
        name = next((n for n in self.anchor[2] if n in field and n not in kicking), None)
        if not name:
            return False
        own = field[name]
        targets = []
        rivals = [p["position"] for p in other.values()]
        bodies = rivals + [p["position"] for p in field.values()]
        for sign in (-1, 1):
            for angle in (47, 59, 72, 84, 95, 100):
                yaw = own["yaw"] + math.radians(sign * angle)
                target = offset(ball, yaw, self.tap_range)
                if abs(target[0]) > 4.45 or abs(target[1]) > 2.81:
                    continue
                clearance = max(0.0, min(distance(target, p) for p in rivals) - 0.18)
                ahead = direction * (target[0] - ball[0])
                if self.tap_path_exact:
                    clear = rolling_lane(
                        ball, target, bodies, self.model.robot_radius + BALL_RADIUS - 0.004
                    )
                else:
                    clear = partial_lane_clear(ball, target, rivals, 0.208, 0.12)
                if not clear:
                    continue
                support = min(
                    (distance(target, p["position"]) for n, p in field.items() if n != name),
                    default=1.5,
                )
                score = clearance + ahead * 0.85 - abs(target[1]) * 0.30 - min(support, 1.8) * 0.33
                targets.append((score, target))
        if targets and self.set_tap(
            name, own, ball, max(targets)[1], now, orders, "DUEL_TAP", self.tap_range
        ):
            self.escape.pop(team, None)
            return True
        if (
            not self.allow_duel_flare
            or now - self.anchor[1] < self.escape_delay
            or direction * ball[0] < -3.28
            or self.helper_path
            and team in self.duel
            or self.helper_path
            and self.duel_flank_time < now - self.anchor[1] < self.duel_flank_time + 1.5
        ):
            return False
        route = self.escape.get(team)
        if route and (
            route.name != name or distance(ball, route.anchor) > 0.14 or now > route.expires
        ):
            if route.name == name and distance(ball, route.anchor) < 0.12:
                self.last_escape[team] = route.target
            route = None
            self.escape.pop(team, None)
        if route is None:
            callbacks = []
            previous = self.last_escape.get(team)
            for sign in (-1, 1):
                yaw = (0 if direction > 0 else math.pi) + sign * 0.74
                aim = offset(ball, yaw, 0.68)
                stance = pose_for_contact(ball, yaw, 0.0)
                if abs(aim[1]) > 2.85 or abs(stance[0]) > 4.39:
                    continue
                clear = min(distance(aim, p) for p in rivals)
                score = clear - 0.18 * abs(wrap(yaw - own["yaw"])) - 0.17 * abs(aim[1])
                if self.escape_retry and previous is not None and distance(previous, aim) < 0.40:
                    score -= 0.72
                callbacks.append((score, aim))
            if not callbacks:
                return False
            _, target = max(callbacks)
            route = self.escape[team] = DuelRoute(name, name, ball, target, now + self.arc_commit)
        elif (
            self.escape_retry
            and distance(ball, route.anchor) < 0.027
            and now + 1.1 > route.expires
            and now - self.anchor[1] > self.duel_break_gap
        ):
            point = tuple(own["position"][:2])
            target = inside(offset(point, own["yaw"], -0.16))
            orders[name] = Decision("DUEL_WITHDRAW", target, ball)
            return True
        aim = route.target
        stance = pose_for_contact(ball, bearing(ball, aim), 0.0)
        orders[name] = Decision("BEAT_MARKER", stance, aim)
        return True

    def resolve_duel(self, team, field, other, ball, direction, now, orders, kicking):
        active = self.duel.get(team)
        if active and (
            now > active.expires
            or distance(ball, active.anchor) > 0.24
            or active.name not in field
            or active.helper not in field
        ):
            self.duel.pop(team, None)
            active = None
        if active is None and self.anchor and now - self.anchor[1] >= self.duel_wait:
            left, right = self.anchor[2]
            name, enemy = (left, right) if team == "Red" else (right, left)
            if name not in field or enemy not in other:
                return False
            position = field[name]["position"]
            yaw = field[name]["yaw"]
            candidates = []
            opponents = [r["position"] for n, r in other.items() if n != enemy]
            # Step out of the straight contest with another player arriving
            # at an angle, even if the projected contact is still undecided.
            for helper, p in field.items():
                if (
                    helper == name
                    or helper in kicking
                    or distance(p["position"], ball) > self.helper_limit
                ):
                    continue
                for angle in (-104, -90, -68, 68, 90, 104):
                    heading = yaw + math.radians(angle)
                    stance = inside(offset(ball, heading, -0.32))
                    blockers = opponents + [other[enemy]["position"], position]
                    if not lane_clear(p["position"], stance, blockers, self.free_runner_body):
                        continue
                    travel, _, arrive = route(p["position"], p["yaw"], stance, tolerance=0.065)
                    rate = (
                        self.model.planar_turn_rate
                        if self.steer
                        else min(self.model.left_turn, self.model.right_turn)
                    )
                    eta = travel + abs(wrap(heading - arrive)) * 0.65 / rate
                    if eta < (17.0 if self.helper_path else 14.0):
                        candidates.append((eta, helper, stance))
            if candidates:
                _, helper, stance = min(candidates)
                active = self.duel[team] = DuelRoute(name, helper, ball, stance, now + 14.0)
        if active:
            name, helper = active.name, active.helper
            if helper not in kicking:
                orders[helper] = Decision("DUEL_RELAY", active.target, ball)
                close = distance(field[helper]["position"], ball) < 0.54
                if close and name not in kicking:
                    point = field[name]["position"]
                    target = inside(offset(point, field[name]["yaw"], -0.16))
                    orders[name] = Decision("DUEL_WITHDRAW", target, ball)
            return True
        if self.anchor and now - self.anchor[1] >= self.stuck_cut:
            name = next((n for n in self.anchor[2] if n in field and n not in kicking), None)
            if name and direction * ball[0] > -3.25:
                own = field[name]
                point = own["position"]
                axis = bearing(point, ball)
                options = []
                for side in (-1, 1):
                    approach = axis + side * math.radians(46)
                    stance = inside(offset(ball, approach, -0.34))
                    if lane_clear(point, stance, [p["position"] for p in other.values()], 0.31):
                        options.append((abs(stance[1]), stance, approach))
                if options:
                    _, target, yaw = min(options)
                    orders[name] = Decision("CUT_AROUND", target, offset(ball, yaw, 0.72))
                    return True
        return False

    def defend(self, field, ball, velocity, direction, orders, kicking):
        if direction * velocity[0] < -0.03:
            target = goal_side(
                (ball[0] + velocity[0] * 1.5, ball[1] + velocity[1] * 1.5), direction, self.press_gap
            )
        else:
            target = goal_side(ball, direction, self.press_gap)
        choices = []
        for name, p in field.items():
            if name in kicking:
                continue
            point = p["position"]
            behind = direction * (point[0] - ball[0])
            eta, _, _ = route(point, p["yaw"], target, tolerance=0.09)
            choices.append((eta + max(0.0, behind + 0.18) * 8, name))
        if not choices:
            return
        press = min(choices)[1]
        gap = distance(field[press]["position"], ball)
        # Goal-side player closes the exposed foot. If beaten, keep a position
        # between ball and net, leaving the other field players staggered.
        if self.flank_defence and 0.25 < gap < 1.06 and abs(ball[1]) < 2.63:
            own = field[press]
            sign = (
                math.copysign(1.0, own["position"][1] - ball[1])
                if abs(own["position"][1] - ball[1]) > 0.068
                else math.copysign(1.0, -ball[1])
            )
            direct = direction * (own["position"][0] - ball[0])
            front, side = frame(own["position"], ball, own["yaw"])
            if (
                (0.09 < front < 0.32 and abs(side) < 0.13)
                or gap < self.press_duel
                and direct < -0.06
            ):
                orders[press] = Decision("CHALLENGE", ball, ball)
            else:
                approach = inside((ball[0] - direction * 0.27, ball[1] + sign * self.flank_gap))
                orders[press] = Decision("FLANK_PRESS", approach, ball)
        elif gap < self.press_start and direction * (field[press]["position"][0] - ball[0]) < -0.06:
            orders[press] = Decision("CHALLENGE", ball, ball)
        else:
            orders[press] = Decision("PRESS_LANE", target, ball)
        second = next((n for _, n in sorted(choices) if n != press), None)
        if second:
            px = clamp(direction * ball[0] - 1.04, -3.62, 3.1)
            py = clamp(ball[1] * 0.53, -1.26, 1.26)
            orders[second] = Decision("DOUBLE_COVER", (direction * px, py), ball)
        for name in field:
            if name in (press, second) or name in kicking:
                continue
            bx = clamp(direction * ball[0] + (0.12 if self.counter_layer else -0.62), -3.1, 3.45)
            by = clamp(ball[1] + math.copysign(1.18, -ball[1]), -2.30, 2.30)
            orders[name] = Decision("COVER_CUTBACK", (direction * bx, by), ball)

    def free_boundary_ball(self, field, other, ball, velocity, direction, now, orders, kicking):
        if (
            abs(ball[0]) < 4.31
            and abs(ball[1]) < 2.77
            or not self.anchor
            or now - self.anchor[1] < self.edge_min_stall
            or math.hypot(*velocity) > 0.05
        ):
            return False
        eligible = [(distance(p["position"], ball), n) for n, p in field.items() if n not in kicking]
        if not eligible:
            return False
        gap, name = min(eligible)
        rivals = [p["position"] for p in other.values()]
        if gap > 0.51 or gap > min(distance(p, ball) for p in rivals) + 0.11:
            return False
        pose = field[name]
        point = pose["position"]
        front, side = frame(point, ball, pose["yaw"])
        bodies = rivals + [q["position"] for n, q in field.items() if n != name]
        moves = []
        for heading_deg in range(-178, 180, 22):
            heading = math.radians(heading_deg)
            stance = offset(ball, heading, -0.252)
            if abs(stance[0]) > 4.387 or abs(stance[1]) > 2.875:
                continue
            for tangent in (-92, -76, -54, 54, 76, 92):
                strike = heading + math.radians(tangent)
                target = offset(ball, strike, 0.43)
                progress = (
                    (abs(ball[0]) - abs(target[0]))
                    if abs(ball[0]) > 4.31
                    else (abs(ball[1]) - abs(target[1]))
                )
                if progress < 0.095 or abs(target[0]) > 4.39 or abs(target[1]) > 2.77:
                    continue
                if not rolling_lane(ball, target, bodies, 0.22):
                    continue
                score = (
                    progress
                    + 0.22 * direction * (target[0] - ball[0])
                    - 0.9 * distance(point, stance)
                )
                moves.append((score, stance, heading, target))
                if (
                    0.082 < front < 0.311
                    and abs(side) < 0.14
                    and abs(wrap(strike - pose["yaw"])) < 1.65
                ):
                    if self.set_tap(name, pose, ball, target, now, orders, "DUEL_TAP", 0.43):
                        return True
        if not moves:
            return False
        _, stance, heading, _ = max(moves)
        orders[name] = Decision("EDGE_RECOVERY", stance, offset(stance, heading, 1.0))
        return True

    def shot_reach(self, own, yaw, ball, velocity, time, side_speed):
        speed = math.hypot(*velocity)
        stop = self.model.rolling_deceleration
        c, s = math.cos(yaw), math.sin(yaw)
        circle = self.model.robot_radius + BALL_RADIUS
        ranking = []
        for sample in range(1, 13):
            elapsed = time * sample / 12
            term = elapsed * (1 - 0.5 * stop * elapsed / speed)
            path = (ball[0] + velocity[0] * term, ball[1] + velocity[1] * term)
            forward, side = frame(own, path, yaw)
            linear = self.model.walk_speed if forward > 0 else self.model.back_speed
            factor = min(1.0, elapsed / max(1e-9, math.hypot(forward / linear, side / side_speed)))
            qx, qy = (forward * c - side * s) * factor, (forward * s + side * c) * factor
            point = inside((own[0] + qx, own[1] + qy), 4.40, 2.9)
            if distance(own, path) < circle - 0.006:
                ranking.append(((0, elapsed, 0.0), tuple(own[:2])))
            else:
                gap = distance(path, point)
                key = (0, elapsed, distance(own, point)) if gap < circle else (1, gap, elapsed)
                ranking.append((key, point))
        _, target = min(ranking)
        length = distance(own, target)
        if length < 0.002:
            return tuple(own[:2])
        scale = 0.16 / length
        return inside(
            (own[0] + scale * (target[0] - own[0]), own[1] + scale * (target[1] - own[1])), 4.4, 2.9
        )

    def keep_goal(self, team, own, opponents, ball, velocity, now, direction):
        position, yaw = own["position"], own["yaw"]
        depth = HALF_FIELD + direction * ball[0]
        incoming = -direction * velocity[0]
        goal_line = -direction * (HALF_FIELD + BALL_RADIUS)
        if incoming > 0.043:
            shot = rolling_crossing(ball, velocity, goal_line, self.model.rolling_deceleration)
            if shot and abs(shot[0]) + BALL_RADIUS < GOAL_WIDTH / 2:
                if self.diagonal_save and self.steer:
                    side_speed = (
                        self.model.planar_side_speed * self.side_scale * self.keeper_side_scale
                    )
                    target = self.shot_reach(position, yaw, ball, velocity, shot[1], side_speed)
                else:
                    target = reachable_shot_point(position, yaw, ball, velocity, shot[1], self.model)
                return Decision("KEEPER_SHOT", target, (direction, 0.0))
        nearest = min(opponents.values(), key=lambda p: distance(p["position"], ball))
        pressure = distance(nearest["position"], ball)
        front, side = frame(position, ball, yaw)
        if (
            self.keeper_loose
            and depth < self.keeper_near_depth
            and 0.13 < pressure < 0.55
            and math.hypot(*velocity) < 0.10
            and 0.082 < front < 0.31
            and abs(side) < 0.14
        ):
            targets = []
            for sign in (-1, 1):
                for angle in (60, 80, 95):
                    aimed = yaw + math.radians(sign * angle)
                    target = offset(ball, aimed, self.tap_range)
                    if direction * (target[0] - ball[0]) < -0.075 or abs(target[1]) > 2.72:
                        continue
                    obstacles = [p["position"] for p in opponents.values()]
                    if rolling_lane(ball, target, obstacles, 0.23):
                        targets.append(
                            (
                                min(distance(target, e) for e in obstacles) + abs(target[1]) * 0.16,
                                target,
                            )
                        )
            if targets and now - self.tap_attempt.get(team, -100.0) > self.tap_wait:
                self.tap_attempt[team] = now
                return Decision(
                    "KEEPER_TAP", ball, max(targets)[1], "tap", kick_distance=self.tap_range
                )
        if depth < 1.1 and math.hypot(*velocity) < 0.18 and 0.09 < front < 0.29:
            if direction * math.cos(yaw) > 0.36 and -0.02 < side < 0.121 and pressure > 0.28:
                previous = self.keeper_attempt.get(team, -100.0)
                if now - previous > self.model.pass_seconds + 3.0:
                    self.keeper_attempt[team] = now
                    face = offset(position, yaw, 1.0)
                    return Decision("KEEPER_CLEAR", ball, face, "pass", kick_distance=0.92)
            if abs(side) < 0.108 and direction * math.cos(yaw) > 0.42:
                if pressure < 0.30:
                    return Decision("KEEPER_HOLD", tuple(position[:2]), (direction, 0.0))
                return Decision("KEEPER_POKE", ball, offset(position, yaw, 1.0))
            if 0.11 < abs(side) < 0.24 and direction * math.cos(yaw) > 0.45 and pressure > 0.38:
                return Decision("KEEPER_ALIGN", ball, offset(position, yaw, 1.0))
        lane = ball[1] * clamp(1.03 - depth * 0.21, 0.28, 0.98)
        keeper_x = -direction * (4.16 if depth > 0.48 else 4.31)
        if depth < 3.1 and pressure < 0.53 and direction * math.cos(nearest["yaw"]) < -0.65:
            slope = math.tan(nearest["yaw"])
            aim = ball[1] + (keeper_x - ball[0]) * slope
            if abs(aim) < GOAL_WIDTH / 2 + 0.15:
                lane = 0.52 * lane + 0.48 * aim
        limit = GOAL_WIDTH / 2 - 0.16
        target = keeper_x, clamp(lane, -limit, limit)
        name = "KEEPER_STEP" if depth < self.no_keeper_turn else "SWEEP_NEAR_POST"
        return Decision(name, target, (direction, 0.0))


def exceeds_anchor(anchor, pair, ball):
    return anchor[2] != pair or distance(anchor[0], ball) > 0.095
