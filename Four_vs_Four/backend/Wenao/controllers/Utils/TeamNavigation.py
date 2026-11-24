"""Off-ball routes compare existing turn, forward, backward and side primitives."""
import math

from Utils.Contest import Contest
from Utils.GoalCover import GoalCover, keeper_motion
from Utils.Passing import foot_can_push, frame
from Utils.Navigation import Navigator, angle_to, turn_action
from Utils.TeamPolicy import distance, avoid_obstacles
from Utils.DefensivePlan import route
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


class TeamSimulation(Simulation):
    def __init__(self, *args, **kwargs):
        self.contest = Contest()
        self.goal_cover = GoalCover()
        self.contest_players = set()
        super().__init__(*args, **kwargs)

    def decide_all(self, world):
        decisions = super().decide_all(world)
        if self.contest_players:
            decisions = self.contest.adjust(world, decisions, self.contest_players - self.kicking.keys())
        return self.goal_cover.adjust(world, decisions, self.model, self.kicking)


    def install_team_navigators(self):
        for name,policy in self.policies.items():
            if isinstance(policy,TacticalPolicy):self.navigators[name]=CooperativeNavigator(self.model)
    def _place_formation(self,jitter=False):
        super()._place_formation(jitter=jitter)
        self.install_team_navigators()
