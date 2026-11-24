"""Off-ball routes compare existing turn, forward, backward and side primitives."""
from dataclasses import replace
import math

from Utils.Contest import Contest
from Utils.Flow import Flow
from Utils.GoalCover import GoalCover, keeper_motion
from Utils.Passing import bearing, foot_can_push, frame
from Utils.Navigation import Navigator, angle_to, turn_action
from Utils.TeamPolicy import distance, avoid_obstacles
from Utils.DefensivePlan import route, wrap
from Utils.PlanarMotion import PlanarMotion
from Utils.TeamTactics import TacticalPolicy, SETTINGS
from soccer2d import Simulation

class CooperativeNavigator(Navigator):
    def __init__(self, model=None):
        super().__init__()
        self.model = model

    def choose(self, decision, own, yaw, ball, robots=()):
        if decision.behaviour.startswith('KEEPER_'):
            return keeper_motion(decision, own, yaw, self.model)
        if decision.behaviour == 'DUEL_RELAY':
            if distance(own, ball) < .425:
                angle = angle_to(own, ball, yaw)
                if abs(angle) > 13:
                    return turn_action(angle), 'FACE_BALL_FROM_SIDE'
                front, side = frame(own, ball, yaw)
                if .105 < front < .38 and abs(side) < .095:
                    return 'walk', 'APPROACH_BALL_FROM_SIDE'
            _, action, _ = route(own, yaw, decision.target, tolerance=.055)
            return action, 'MOVE_TO_SIDE_OF_CONTEST'
        if decision.behaviour == 'DUEL_SCREEN':
            return 'stand', 'YIELD_AFTER_TEAMMATE_CONTACT'
        if decision.behaviour == 'DUEL_TAKEOVER':
            return 'walk', 'TAKE_BALL_FROM_SIDE'
        if decision.behaviour == 'ADVANCE_FROM_PASS':
            return 'walk', 'ADVANCE_FROM_PASS'
        if decision.behaviour in ('OPEN_SUPPORT', 'PREPARE_FORWARD', 'RECEIVE_FORWARD', 'EARLY_RECEIVE'):
            return self.receive_or_support(decision, own, yaw, ball, robots)
        if decision.behaviour in ('COORDINATED_PASS', 'LEAD_PASS'):
            from Utils.TeamPolicy import Decision
            decision=Decision('PASS',decision.target,decision.face,decision.kick,decision.receiver)
        if SETTINGS['navigation']!='route' or decision.behaviour not in ('YIELD_TO_CARRIER','FIND_PASS_LANE'):
            return super().choose(decision,own,yaw,ball,robots)
        gap=distance(own,decision.target)
        if gap<.15:self.arrived=True
        elif gap>.30:self.arrived=False
        if self.arrived:
            angle=angle_to(own,decision.face,yaw)
            return (turn_action(angle),'TEAM_FACE_PLAY') if abs(angle)>25 else ('stand','TEAM_HOLD_LANE')
        target=avoid_obstacles(own,decision.target,robots)
        _,action,_=route(own,yaw,target,tolerance=.10)
        return action,'TEAM_REPOSITION'

    def receive_or_support(self, decision, own, yaw, ball, robots):
        receiving = decision.behaviour == 'RECEIVE_FORWARD'
        if receiving and foot_can_push(own, ball, yaw):
            return 'walk', 'RECEIVE_WITH_FORWARD_FOOT'
        tolerance = .035 if receiving else .075
        if receiving and distance(own, decision.target) < .16:
            desired = math.atan2(decision.face[1] - decision.target[1],
                                 decision.face[0] - decision.target[0])
            error = math.degrees((desired - yaw + math.pi) % (2 * math.pi) - math.pi)
            if abs(error) <= 20:
                front, side = frame(own, ball, yaw)
                if .27 <= front < .43 and abs(side) <= .11:
                    return 'walk', 'CLOSE_TO_RECEIVE'
                if .035 <= front < .31 and .11 < abs(side) < .22:
                    action = 'step_left' if side > 0 else 'step_right'
                    return action, 'ALIGN_RECEIVING_FOOT'
        if distance(own, decision.target) > tolerance:
            target = avoid_obstacles(own, decision.target, robots, margin=.35 if receiving else .5)
            _, action, _ = route(own, yaw, target, tolerance=tolerance*.85)
            return action, 'MOVE_TO_RECEIVING_POSITION'
        desired = math.atan2(decision.face[1] - decision.target[1],
                             decision.face[0] - decision.target[0])
        error = math.degrees((desired - yaw + math.pi) % (2*math.pi) - math.pi)
        if abs(error) > 12:
            return turn_action(error), 'FACE_ATTACKING_GOAL'
        return 'stand', 'HOLD_RECEIVING_POSITION'


class FlowNavigator(CooperativeNavigator):
    def __init__(self, model, flow):
        super().__init__(model)
        self.flow = flow

    def choose(self, decision, own, yaw, ball, robots=()):
        behaviour = decision.behaviour
        if not self.flow.steer:
            if behaviour == "SWEEP_NEAR_POST":
                return keeper_motion(
                    replace(decision, behaviour="KEEPER_TRACK"), own, yaw, self.model
                )
            if behaviour.startswith("KEEPER_") and behaviour != "KEEPER_TAP":
                return super().choose(decision, own, yaw, ball, robots)
        if behaviour in ("SWEEP_NEAR_POST", "KEEPER_STEP", "KEEPER_HOLD", "KEEPER_SHOT"):
            facing = math.atan2(decision.face[1], decision.face[0])
            turn = behaviour == "SWEEP_NEAR_POST"
            command = self.translate(
                own, yaw, decision.target, facing if turn else yaw, 0.050, keeper=True
            )
            return command, "KEEPER_COVER_LANE" if turn else "KEEPER_BLOCK_LANE"
        if behaviour in ("DUEL_TAP", "KEEPER_TAP", "CARRY_TAP", "TOUCH_PASS", "SNAP_SHOT"):
            return "tap", "PLAY_BALL_SIDEWAYS"
        if behaviour == "KEEPER_ALIGN" and self.flow.steer:
            _, side = frame(own, ball, yaw)
            lateral = math.copysign(self.model.planar_side_speed * 0.66, side)
            return (
                PlanarMotion("step_left" if side > 0 else "step_right", 0.0, lateral, 0.0),
                "ALIGN_KEEPER_FOOT",
            )
        if behaviour in ("OUTLET_PASS", "FINISH_OPEN", "RESTART") and decision.kick:
            desired = bearing(ball, decision.face)
            error = wrap(desired - yaw)
            front, lateral = frame(own, ball, yaw)
            if abs(error) <= math.radians(7 if behaviour == "FINISH_OPEN" else 9) and (
                -0.02 < lateral < 0.118 and 0.112 < front < 0.264
            ):
                return decision.kick, "STRIKE_BALL"
            command = self.ball_stance(own, yaw, ball, decision.target, desired, robots)
            return command, "ALIGN_KICK_FOOT"
        if behaviour in ("BEAT_MARKER", "CARRY_LANE", "CUT_AROUND"):
            desired = bearing(ball, decision.face)
            if behaviour == "CUT_AROUND" and distance(own, decision.target) > 0.095:
                return self.follow(decision.target, own, yaw, robots, "ARC_AROUND_CONTEST")
            front, lateral = frame(own, ball, yaw)
            error = wrap(desired - yaw)
            if 0.082 < front < 0.34 and abs(lateral) < 0.103 and abs(error) < math.radians(20):
                command = self.motion(self.model.walk_speed, 0.0, self.turn(error))
                return command, "CARRY_AROUND" if behaviour != "CARRY_LANE" else "CARRY_IN_LANE"
            return (
                self.ball_stance(own, yaw, ball, decision.target, desired, robots),
                "ALIGN_CARRY_FOOT",
            )
        if behaviour == "EDGE_RECOVERY":
            desired = bearing(decision.target, decision.face)
            return (
                self.ball_stance(own, yaw, ball, decision.target, desired, robots),
                "MOVE_AROUND_BOUNDARY_BALL",
            )
        if behaviour == "DUEL_WITHDRAW":
            return "back", "GIVE_SIDE_RUN_SPACE"
        if behaviour in (
            "PRESS_LANE",
            "FLANK_PRESS",
            "DOUBLE_COVER",
            "COVER_CUTBACK",
            "OFFER_OUTLET",
            "RECOVER_DEFENCE",
        ):
            return self.follow(decision.target, own, yaw, robots, "MOVE_TO_LANE", face=decision.face)
        if behaviour == "PURSUE_BALL":
            return self.follow(decision.target, own, yaw, robots, "PURSUE_ROLLING_BALL")
        if behaviour in ("INTERCEPT", "COUNTERPRESS", "CHALLENGE") and self.flow.steer:
            gap = distance(own, ball)
            if gap >= 0.35:
                return self.follow(
                    ball[:2] if gap < 0.8 else decision.target, own, yaw, robots, "CLOSE_BALL"
                )
            heading = bearing(own, ball)
            front, side = frame(own, ball, yaw)
            if 0.085 < front < 0.30 and abs(side) < 0.113:
                return (
                    self.motion(self.model.walk_speed, 0.0, self.turn(wrap(heading - yaw))),
                    "CONTEST_FOOT",
                )
            target = own[:2] if abs(wrap(heading - yaw)) > math.radians(62) else decision.target
            return self.translate(own, yaw, target, heading, 0.09), "PREPARE_TO_CONTEST"
        if (
            behaviour in ("FLOW_RECEIVE", "RECEIVE_FORWARD", "PREPARE_FORWARD", "EARLY_RECEIVE")
            and self.flow.steer
        ):
            desired = bearing(decision.target, decision.face)
            front, side = frame(own, ball, yaw)
            if (
                behaviour in ("FLOW_RECEIVE", "RECEIVE_FORWARD")
                and 0.075 < front < 0.39
                and abs(side) < 0.113
            ):
                return (
                    self.motion(self.model.walk_speed, 0.0, self.turn(wrap(desired - yaw))),
                    "RECEIVE_WITH_FORWARD_FOOT",
                )
            return self.follow(
                decision.target,
                own,
                yaw,
                robots,
                "MOVE_TO_RECEIVING_POSITION",
                heading=desired,
                tolerance=0.035,
            )
        return super().choose(decision, own, yaw, ball, robots)

    def ball_stance(self, own, yaw, ball, stance, facing, robots):
        gap = distance(own, ball)
        if gap > 0.55:
            return self.follow(stance, own, yaw, robots, "GET_SIDE_OF_BALL", heading=facing)[0]
        angle = bearing(ball, own)
        desired = bearing(ball, stance)
        arc = wrap(desired - angle)
        # Close diagonal motion can hit the side of the ball, leaving neither
        # a legal kick stance nor a clear body path. Circle outside its disc.
        if abs(arc) > math.radians(24) and self.flow.arc_approach:
            delta = max(-0.36, min(0.36, arc))
            radius = max(0.285, min(0.34, gap))
            waypoint = (
                ball[0] + radius * math.cos(angle + delta),
                ball[1] + radius * math.sin(angle + delta),
            )
            alternatives = [waypoint]
            if abs(arc) > math.pi * 0.72:
                alternatives.append(
                    (
                        ball[0] + radius * math.cos(angle - delta),
                        ball[1] + radius * math.sin(angle - delta),
                    )
                )
            target = max(
                alternatives, key=lambda q: min((distance(q, r) for r in robots), default=2.0)
            )
            target = (max(-4.39, min(4.39, target[0])), max(-2.88, min(2.88, target[1])))
            if distance(own, target) > 0.018:
                stance = target
        return self.translate(own, yaw, stance, facing, 0.02)

    def turn(self, error):
        max_rate = self.model.planar_turn_rate * self.flow.turn_scale
        return max(-max_rate, min(max_rate, error * 2.4))

    @staticmethod
    def motion(forward, lateral, angular):
        if abs(forward) + abs(lateral) < 0.001:
            if abs(angular) < 0.015:
                return "stand"
            label = "left20" if angular > 0 else "right20"
        elif abs(lateral) > abs(forward) * 1.4:
            label = "step_left" if lateral > 0 else "step_right"
        elif abs(angular) > 0.02:
            label = "steer"
        else:
            label = "walk" if forward > 0 else "back"
        return PlanarMotion(label, forward, lateral, angular)

    def translate(self, own, yaw, target, heading, tolerance=0.066, keeper=False):
        error = wrap(heading - yaw)
        if not self.flow.steer:
            if abs(error) > math.radians(14):
                return turn_action(math.degrees(error))
            return route(own, yaw, target, tolerance=tolerance)[1]
        dx, dy = frame(own, target, yaw)
        side = self.model.planar_side_speed * self.flow.side_scale
        if keeper:
            side *= self.flow.keeper_side_scale
        if math.hypot(dx, dy) < tolerance:
            dx = dy = 0.0
        front_speed = self.model.walk_speed if dx >= 0 else self.model.back_speed
        front = max(-front_speed, min(front_speed, dx * 2.0))
        lateral = max(-side, min(side, dy * 2.0))
        scale = max(1.0, math.hypot(front / front_speed, lateral / side))
        return self.motion(front / scale, lateral / scale, self.turn(error))

    def follow(self, target, own, yaw, robots, stage, face=None, heading=None, tolerance=0.085):
        gap = distance(own, target)
        if gap <= tolerance:
            if heading is None:
                heading = yaw if face is None else bearing(own, face)
            return self.translate(own, yaw, own, heading, tolerance), stage
        local = avoid_obstacles(own, target, robots, margin=0.54)
        if heading is None or gap > 0.30:
            heading = bearing(own, local)
            if abs(wrap(heading - yaw)) > math.radians(105) and gap < 0.45:
                heading = wrap(heading + math.pi)
        return self.translate(own, yaw, local, heading, tolerance * 0.65), stage


class TeamSimulation(Simulation):
    def __init__(self, *args, **kwargs):
        self.contest = Contest()
        self.goal_cover = GoalCover()
        self.contest_players = set()
        self.flow = None
        super().__init__(*args, **kwargs)
        self.flow = Flow(self.model)

    def decide_all(self, world):
        decisions = super().decide_all(world)
        if self.contest_players:
            decisions = self.contest.adjust(
                world, decisions, self.contest_players - self.kicking.keys()
            )
        decisions = self.goal_cover.adjust(world, decisions, self.model, self.kicking)
        return self.flow.adjust(world, decisions, self.kicking)

    def install_team_navigators(self):
        for name, policy in self.policies.items():
            if self.flow is not None and policy.team.title() in self.flow.enabled:
                self.navigators[name] = FlowNavigator(self.model, self.flow)
            elif isinstance(policy, TacticalPolicy):
                self.navigators[name] = CooperativeNavigator(self.model)

    def _place_formation(self, jitter=False):
        super()._place_formation(jitter=jitter)
        self.install_team_navigators()
