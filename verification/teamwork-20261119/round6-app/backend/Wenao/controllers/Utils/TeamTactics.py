"""Experimental four-player coordination; the movement/contact model is unchanged."""
import math
from Utils.TeamPolicy import TeamPolicy as PreviousPolicy
from Utils.TeamPolicy import Decision, distance, lane_clear

SETTINGS = {
    'support': 'adaptive',       # unchanged, safe, adaptive, close
    'support_radius': 1.0,
    'support_ahead': .65,
    'support_width': .90,
    'support_hold': 2.0,
    'screen_gap': .8,
    'safe_support': True,
    'passing': 'unchanged',      # unchanged, reachable, opportunistic
    'pass_distance': .95,
    'handoff_distance': .60,
    'mark': False,
    'support_search': True,
    'search_ring': 1.1,
    'search_eta_weight': .06,
    'search_lane_weight': 1.,
    'search_predict': 4.,
    'search_radius_min': .9,
    'search_attack_only': True,
    'yield_enabled': True,
    'yield_enter': .75,
    'yield_exit': 1.05,
    'all_field_pass': False,
    'pass_pressure_max': 1.5,
    'pass_progress': .1,
    'receive_prepare': True,
    'navigation': 'route',
}


def clamp(x, low, high):
    return max(low, min(high, x))


class TacticalPolicy(PreviousPolicy):
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
        # Receiver stages while the foot swing is pending, then approaches
        # only after the executor confirms actual ball contact.
        if (SETTINGS['receive_prepare'] and intent and intent.get('receiver')==self.name
                and intent.get('stage')=='preparing' and 'pass_intent' in world):
            own=world['robots'][self.name]['position']
            return Decision('READY_TO_RECEIVE',tuple(own[:2]),tuple(world['ball']['position'][:2]))
        decision = super().decide(world)
        match = world['match']
        if match['phase'] != 'PLAYING' or not match['released']:
            self.support_plan = None
            return decision
        if decision.behaviour == 'DEFEND':
            direction = match['red_direction'] * (1 if self.team == 'RED' else -1)
            ball = world['ball']['position']
            x = direction*clamp(direction*ball[0]-1.2,-3.65,-1.5)
            return Decision('COVER_GOAL',(x,clamp(ball[1]*.6,-1.65,1.65)),tuple(ball[:2]))
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
        if decision.behaviour != 'SUPPORT' or SETTINGS['support'] == 'unchanged':
            return decision
        ball = world['ball']['position'][:2]
        own = world['robots'][self.name]['position'][:2]
        direction = match['red_direction'] * (1 if self.team == 'RED' else -1)
        mates = {n:r for n,r in world['robots'].items() if n.startswith(self.prefix) and 'Goalkeeper' not in n and n not in world.get('penalties',{})}
        opponents = [r['position'][:2] for n,r in world['robots'].items() if not n.startswith(self.prefix)]
        carrier = min(mates, key=lambda n:(distance(mates[n]['position'],ball),n))
        team_near = distance(mates[carrier]['position'],ball)
        other_near = min((distance(p,ball) for p in opponents),default=math.inf)
        owner = match.get('last_touch')
        attacking = (owner in mates and team_near < .8) or team_near + .10 < other_near
        if SETTINGS['support'] == 'safe':
            target = decision.target
            behaviour = 'SPREAD_SUPPORT'
        else:
            side = -1 if self.name.endswith('A') else 1
            # Centre-side support remains inside the pitch when the carrier is wide.
            if abs(ball[1]) > 1.5:
                side = -1 if ball[1] > 0 else 1
            ahead = SETTINGS['support_ahead'] if attacking else -SETTINGS['screen_gap']
            width = SETTINGS['support_width'] if attacking else .65
            target = (clamp(ball[0]+direction*ahead,-3.8,3.8),clamp(ball[1]+side*width,-2.35,2.35))
            behaviour = 'OFFER_PASS' if attacking else 'DEFENSIVE_SCREEN'
            if SETTINGS['support'] == 'close' and attacking:
                target = (clamp(ball[0]+direction*.30,-3.8,3.8),clamp(ball[1]+side*.60,-2.35,2.35))
        if SETTINGS['safe_support'] and distance(target,ball) < SETTINGS['support_radius']:
            dx,dy=target[0]-ball[0],target[1]-ball[1]
            norm=max(math.hypot(dx,dy),1e-9)
            target=(clamp(ball[0]+dx/norm*SETTINGS['support_radius'],-4.1,4.1),clamp(ball[1]+dy/norm*SETTINGS['support_radius'],-2.5,2.5))
        # Do not recompute a moving target for every millimetre of ball sway.
        now=world['time']
        if self.support_plan is not None:
            expiry,anchor,old_target,old_behaviour=self.support_plan
            if now < expiry and distance(anchor,ball)<.35 and behaviour==old_behaviour:
                target=old_target
        self.support_plan=(now+SETTINGS['support_hold'],tuple(ball),tuple(target),behaviour) if self.support_plan is None or target!=self.support_plan[2] else self.support_plan
        return Decision(behaviour,tuple(target),tuple(ball))

    def attack(self, own, ball, direction, teammates, opponents, context=''):
        mode=SETTINGS['passing']
        if mode=='unchanged' or (self.role!='striker' and not SETTINGS['all_field_pass']) or self.role=='goalkeeper' or context=='RESTART':
            return super().attack(own,ball,direction,teammates,opponents,context)
        reachable={n:p for n,p in teammates.items() if n==self.name or distance(p,ball)<=SETTINGS['pass_distance']}
        decision=super().attack(own,ball,direction,reachable,opponents,context)
        if mode=='opportunistic' and decision.behaviour in ('DRIBBLE','EVADE_DRIBBLE','CLEAR') and distance(own,ball)<.45:
            options=[(n,p) for n,p in reachable.items() if n!=self.name and 'Goalkeeper' not in n and direction*(p[0]-ball[0])>SETTINGS['pass_progress'] and distance(p,ball)>.35 and lane_clear(ball,p,opponents,.30)]
            pressure=min((distance(p,ball) for p in opponents),default=math.inf)
            if options and .35<pressure<SETTINGS['pass_pressure_max']:
                receiver,aim=min(options,key=lambda item:distance(item[1],ball))
                return Decision('PASS',decision.target,tuple(aim[:2]),'pass',receiver)
        return decision
