"""Off-ball routes compare existing turn, forward, backward and side primitives."""
from Utils.Navigation import Navigator, angle_to, turn_action
from Utils.TeamPolicy import distance, avoid_obstacles
from Utils.DefensivePlan import route
from Utils.TeamTactics import TacticalPolicy, SETTINGS
from soccer2d import Simulation

class CooperativeNavigator(Navigator):
    def choose(self, decision, own, yaw, ball, robots=()):
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

class TeamSimulation(Simulation):
    def install_team_navigators(self):
        for name,policy in self.policies.items():
            if isinstance(policy,TacticalPolicy):self.navigators[name]=CooperativeNavigator()
    def _place_formation(self,jitter=False):
        super()._place_formation(jitter=jitter)
        self.install_team_navigators()
