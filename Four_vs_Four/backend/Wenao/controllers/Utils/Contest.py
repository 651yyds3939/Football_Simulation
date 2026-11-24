"""Coordinate one side approach during a stall and prepare announced passes."""
from dataclasses import dataclass
import math

from Utils.DefensivePlan import route, wrap
from Utils.Passing import bearing, frame, offset
from Utils.TeamPolicy import Decision, distance, lane_clear


SUPPORT = {'OPEN_SUPPORT', 'FIND_PASS_LANE', 'SUPPORT', 'YIELD_TO_CARRIER'}


@dataclass(frozen=True)
class SideRun:
    started: float
    expires: float
    anchor: tuple
    helper: str
    challenger: str
    stance: tuple
    heading: float
    exit_point: tuple


class Contest:
    def __init__(self):
        self.anchor = None
        self.side_run = None
        self.retry_after = 0.

    def adjust(self, world, decisions, enabled):
        match = world['match']
        if match['phase'] != 'PLAYING' or not match['released'] or world.get('pass_intent'):
            self.anchor = self.side_run = None
            self.retry_after = 0.
            return decisions

        ball = tuple(world['ball']['position'][:2])
        now = world['time']
        players = {name: robot for name, robot in world['robots'].items()
                   if robot.get('standing', True) and name not in world.get('penalties', {})}
        pair = self.facing_pair(players, ball)
        slow = math.hypot(*world['ball']['velocity'][:2]) < .045
        if not pair or not slow:
            self.anchor = None
        elif not self.anchor or pair != self.anchor[2] or distance(ball, self.anchor[0]) > .10:
            self.anchor = (ball, now, pair)

        if self.prepare_receiver(players, enabled, decisions, ball):
            return decisions
        if self.side_run is not None:
            run = self.side_run
            ball_movement = distance(run.anchor, ball)
            contact_time = world.get('last_foot_contact_time')
            helper_has_touched = (world.get('last_foot_contact') == run.helper
                                  and contact_time is not None and contact_time >= run.started)
            displacement_limit = .23 if helper_has_touched else .16
            if (now < run.expires and ball_movement <= displacement_limit
                    and run.helper in enabled and run.helper in players and run.challenger in players):
                yield_now = helper_has_touched and ball_movement > .08 and run.challenger in enabled
                self.direct_side_run(run, players, ball, decisions, yield_now)
                return decisions
            self.side_run = None
            self.retry_after = now + 4.

        if self.anchor and now >= self.retry_after and now - self.anchor[1] >= 3.:
            self.side_run = self.plan_side_run(pair, players, enabled, decisions, ball, match, now)
            if self.side_run is not None:
                run = self.side_run
                decisions[run.helper] = Decision('DUEL_RELAY', run.stance, ball)
        return decisions

    @staticmethod
    def prepare_receiver(players, enabled, decisions, ball):
        offers = []
        for name, order in decisions.items():
            if (name not in enabled or name not in players or order.behaviour != 'LEAD_PASS'
                    or not order.receive_stance or order.receiver not in enabled
                    or order.receiver not in players
                    or decisions[order.receiver].behaviour not in SUPPORT | {'COVER_GOAL'}):
                continue
            if distance(players[order.receiver]['position'], order.receive_stance) < 1.0:
                offers.append((distance(players[name]['position'], ball), name, order))
        if not offers:
            return False
        _, _, order = min(offers)
        stance = order.receive_stance
        decisions[order.receiver] = Decision('EARLY_RECEIVE', stance, offset(stance, order.receive_heading, 1.))
        return True

    @staticmethod
    def facing_pair(players, ball):
        pair = []
        for prefix in ('Red', 'Blue'):
            facing = []
            for name, robot in players.items():
                if not name.startswith(prefix) or distance(robot['position'], ball) >= .34:
                    continue
                forward, side = frame(robot['position'], ball, robot['yaw'])
                if .065 < forward < .30 and abs(side) < .13:
                    facing.append((distance(robot['position'], ball), name))
            if not facing:
                return None
            pair.append(min(facing)[1])
        a, b = (players[name]['yaw'] for name in pair)
        return tuple(pair) if math.cos(a - b) < -.5 else None

    @staticmethod
    def plan_side_run(pair, players, enabled, decisions, ball, match, now):
        options = []
        for challenger in pair:
            if challenger not in enabled or challenger.endswith('Goalkeeper'):
                continue
            prefix = challenger[:3]
            direction = match['red_direction'] * (1 if prefix == 'Red' else -1)
            if direction * ball[0] < -2.1:
                continue
            heading = bearing(players[challenger]['position'], ball)
            for helper, robot in players.items():
                if (helper not in enabled or helper == challenger or not helper.startswith(prefix + 'Forward')
                        or decisions[helper].behaviour not in SUPPORT
                        or distance(robot['position'], ball) > 1.55):
                    continue
                obstacles = [r['position'] for n, r in players.items() if n != helper]
                for degrees in (-105, -90, -75, 75, 90, 105):
                    approach = heading + math.radians(degrees)
                    stance = offset(ball, approach, -.28)
                    exit_point = offset(ball, approach, .5)
                    if abs(stance[0]) > 4.2 or abs(stance[1]) > 2.65 or abs(exit_point[1]) > 2.72:
                        continue
                    if (min((distance(p, stance) for p in obstacles), default=2.) < .295
                            or not lane_clear(robot['position'], stance, obstacles, .25)):
                        continue
                    eta, _, arrival_yaw = route(robot['position'], robot['yaw'], stance, tolerance=.045)
                    turn = abs(wrap(approach - arrival_yaw))
                    eta += max(0., turn - math.radians(12)) / .073
                    if eta <= 15.:
                        options.append((eta, helper, challenger, stance, approach, exit_point))
        if not options:
            return None
        _, helper, challenger, stance, heading, exit_point = min(options)
        return SideRun(now, now + 16., ball, helper, challenger, stance, heading, exit_point)

    @staticmethod
    def direct_side_run(run, players, ball, decisions, yield_now):
        robot = players[run.helper]
        front, side = frame(robot['position'], ball, robot['yaw'])
        angle = abs(wrap(run.heading - robot['yaw']))
        if .11 < front < .39 and abs(side) < .10 and angle < math.radians(40):
            decisions[run.helper] = Decision('DUEL_TAKEOVER', ball, run.exit_point)
            if yield_now and front < .275:
                point = tuple(players[run.challenger]['position'][:2])
                decisions[run.challenger] = Decision('DUEL_SCREEN', point, ball)
        else:
            decisions[run.helper] = Decision('DUEL_RELAY', run.stance, ball)
