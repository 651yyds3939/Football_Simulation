"""Bounded off-ball coordination around the existing carrier and referee logic.

Keep one ordinary ball chaser. A support player searches nearby reachable space
when its team controls the ball; non-carriers yield out of the contest corridor.
All targets use observed state and measured primitive rates, never placements.
"""
import math
from Utils.TeamPolicy import TeamPolicy, Decision, distance, lane_clear

SETTINGS = {
    'handoff_distance': .60,
    'cover_gap': 1.2,
    'support_search': True,
    'search_ring': 1.1,
    'search_eta_weight': .15,
    'search_lane_weight': 1.,
    'search_predict': 4.,
    'search_radius_min': .9,
    'search_attack_only': True,
    'support_hold': 4.,
    'yield_enabled': True,
    'yield_enter': .75,
    'yield_exit': 1.05,
    'navigation': 'route',
}


def clamp(value, low, high):
    return max(low, min(high, value))


class TacticalPolicy(TeamPolicy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.support_plan = None
        self.yield_target = None

    def decide(self, world):
        intent = world.get('pass_intent')
        if intent and intent.get('receiver') in world['robots']:
            receiver = world['robots'][intent['receiver']]['position']
            if distance(receiver, world['ball']['position']) > SETTINGS['handoff_distance']:
                world = dict(world)
                world.pop('pass_intent', None)
        decision = super().decide(world)
        match = world['match']
        if match['phase'] != 'PLAYING' or not match['released']:
            self.support_plan = None
            return decision
        if decision.behaviour == 'DEFEND':
            direction = match['red_direction'] * (1 if self.team == 'RED' else -1)
            ball = world['ball']['position']
            x = direction*clamp(direction*ball[0]-SETTINGS['cover_gap'], -3.65, -1.5)
            return Decision('COVER_GOAL', (x, clamp(ball[1]*.6, -1.65, 1.65)), tuple(ball[:2]))
        if SETTINGS['support_search'] and decision.behaviour=='SUPPORT':
            ball=world['ball']['position'][:2];own=world['robots'][self.name]['position'][:2]
            direction=match['red_direction']*(1 if self.team=='RED' else -1)
            enemies=[r['position'][:2] for n,r in world['robots'].items() if not n.startswith(self.prefix)]
            mates={n:r for n,r in world['robots'].items() if n.startswith(self.prefix) and 'Goalkeeper' not in n}
            carrier=min(mates,key=lambda n:(distance(mates[n]['position'],ball),n))
            own_near=distance(mates[carrier]['position'],ball);enemy_near=min((distance(p,ball) for p in enemies),default=math.inf)
            possessing=match.get('last_touch') in mates and own_near<.8
            if possessing or not SETTINGS['search_attack_only']:
                from Utils.DefensivePlan import route
                velocity=world['ball'].get('velocity',[0.,0.])
                speed=math.hypot(*velocity[:2]);horizon=SETTINGS['search_predict']
                predicted=(ball[0]+velocity[0]*min(horizon,.5/max(speed,.001)),ball[1]+velocity[1]*min(horizon,.5/max(speed,.001)))
                candidates=[]
                for angle in (-120,-85,-50,50,85,120):
                    radians=math.radians(angle)
                    point=(clamp(predicted[0]+direction*SETTINGS['search_ring']*math.cos(radians),-3.8,3.8),clamp(predicted[1]+SETTINGS['search_ring']*math.sin(radians),-2.35,2.35))
                    if distance(point,ball)<SETTINGS['search_radius_min']:continue
                    eta,_,_=route(own,world['robots'][self.name].get('yaw',0.),point)
                    clearance=min((distance(p,point) for p in enemies),default=2.)
                    lane=lane_clear(ball,point,enemies,.28)
                    teammate_gap=min((distance(point,r['position']) for n,r in mates.items() if n!=self.name),default=2.)
                    score=min(clearance,1.5)*.7+int(lane)*SETTINGS['search_lane_weight']+direction*(point[0]-ball[0])*.15-eta*SETTINGS['search_eta_weight']-max(0.,.65-teammate_gap)*2.
                    candidates.append((score,point))
                if candidates:
                    target=max(candidates,key=lambda x:x[0])[1]
                    now=world['time']
                    if self.support_plan is not None and self.support_plan[0]>now and distance(self.support_plan[1],ball)<.45:target=self.support_plan[2]
                    else:self.support_plan=(now+SETTINGS['support_hold'],tuple(ball),target,'FIND_PASS_LANE')
                    return Decision('FIND_PASS_LANE',target,tuple(ball))
        if SETTINGS['yield_enabled'] and decision.behaviour in ('SUPPORT','COVER_GOAL'):
            ball=world['ball']['position'][:2]
            own=world['robots'][self.name]['position'][:2]
            gap=distance(own,ball)
            if gap < SETTINGS['yield_enter']:
                dx,dy=own[0]-ball[0],own[1]-ball[1]
                norm=max(math.hypot(dx,dy),1e-9)
                self.yield_target=(clamp(ball[0]+dx/norm*SETTINGS['yield_exit'],-4.1,4.1),clamp(ball[1]+dy/norm*SETTINGS['yield_exit'],-2.55,2.55))
            elif gap >= SETTINGS['yield_exit'] or (self.yield_target is not None and distance(own,self.yield_target)<.10):
                self.yield_target=None
            if self.yield_target is not None:
                return Decision('YIELD_TO_CARRIER',self.yield_target,tuple(ball))
        return decision
