"""4v4 team coordination around the unchanged planar movement executor.

The same observation produces one designated chaser for a team. Support and
cover stay out of its immediate foot contest. No messages or rates are faked.
"""
import math
from Utils.TeamPolicy import TeamPolicy,Decision,distance,unit,lane_clear
from Utils.DefensivePlan import WALK,TURN,interception,route

SETTINGS={'switch_margin':.35,'heading_weight':.25,'support_width':1.05,
          'support_advance':.65,'cover_gap':1.0,'yield_distance':.65,
          'keep_owner':True,'short_pass_only':True,'pass_distance':.38,
          'coordinate':True,'keeper_reach':.60,'evade':True, 'defender_intercept':True,
          'recovering_not_chaser':True, 'forward_chase_only':False, 'minimal':True, 'assignment':False,
          'support_change':True,'cover_change':True,'yield_enabled':True, 'restart_assignment':True, 'support_defensive_only':False,
          'cover_max_x':-1.5,'handoff_enabled':True,'handoff_range':.60}

def clamp(x,lo,hi):return max(lo,min(hi,x))

class TacticalPolicy(TeamPolicy):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.team_chaser=None
        self.restart_taker=None
        self.restart_key=None

    def assign_chaser(self,world,direction):
        ball=world['ball']['position'];robots=world['robots'];penalties=world.get('penalties',{})
        own={n:r for n,r in robots.items() if n.startswith(self.prefix) and n not in penalties and r.get('standing',True)}
        eligible={n:r for n,r in own.items() if 'Goalkeeper' not in n and
                  ('Defender' not in n or direction*ball[0]<.5 or distance(r['position'],ball)<.4)}
        if SETTINGS['forward_chase_only']:
            eligible={n:r for n,r in eligible.items() if 'Forward' in n}
        if SETTINGS['recovering_not_chaser']:
            threatening=min((distance(r['position'],ball) for n,r in robots.items() if not n.startswith(self.prefix)),default=math.inf)<.45 or direction*world['ball'].get('velocity',[0,0])[0]<-.02
            eligible={n:r for n,r in eligible.items() if 'Defender' not in n or not threatening or direction*(r['position'][0]-ball[0])<=.10}
        keeper=next((n for n in own if 'Goalkeeper' in n),None)
        if keeper and direction*ball[0]<-3.4 and distance(own[keeper]['position'],ball)<SETTINGS['keeper_reach']:
            near=min((distance(r['position'],ball) for r in eligible.values()),default=math.inf)
            if distance(own[keeper]['position'],ball)+.12<near:eligible={keeper:own[keeper]}
        if not eligible:eligible=own
        costs={}
        for name,robot in eligible.items():
            point=robot['position'];bearing=math.atan2(ball[1]-point[1],ball[0]-point[0]);yaw=robot.get('yaw',0.)
            error=abs((bearing-yaw+math.pi)%(2*math.pi)-math.pi)
            costs[name]=distance(point,ball)+SETTINGS['heading_weight']*error/TURN*WALK
        chosen=min(costs,key=lambda n:(costs[n],n),default=self.name)
        if self.team_chaser in costs and costs[self.team_chaser]<=costs[chosen]+SETTINGS['switch_margin']:
            chosen=self.team_chaser
        owner=world['match'].get('last_touch')
        if SETTINGS['keep_owner'] and owner in eligible:
            point=eligible[owner]['position'];yaw=eligible[owner].get('yaw',0.);dx,dy=ball[0]-point[0],ball[1]-point[1]
            front=dx*math.cos(yaw)+dy*math.sin(yaw);side=-dx*math.sin(yaw)+dy*math.cos(yaw)
            if .08<front<.35 and abs(side)<.15:chosen=owner
        self.team_chaser=chosen
        return chosen

    def chase_assignment(self,world,eligible,own,ball,direction):
        if not SETTINGS['assignment']:
            return super().chase_assignment(world,eligible,own,ball,direction)
        chosen=self.assign_chaser(world,direction)
        # Keep the parent's legal restart/keeper eligibility constraints.
        if chosen not in eligible:chosen=min(eligible,key=lambda n:(distance(eligible[n],ball),n),default=self.name)
        return eligible,chosen

    def minimal_decide(self,world):
        result=super().decide(world)
        result=self.restart_decision(world,result) if SETTINGS['restart_assignment'] else result
        if world['match']['phase']!='PLAYING' or not world['match']['released']:
            self.team_chaser=None
            return result
        if result.behaviour not in ('SUPPORT','DEFEND'):
            return result
        own=world['robots'][self.name]['position'];ball=world['ball']['position'][:2]
        direction=world['match']['red_direction']*(1 if self.team=='RED' else -1)
        teammates=[r['position'] for n,r in world['robots'].items() if n.startswith(self.prefix)]
        opponents=[r['position'] for n,r in world['robots'].items() if not n.startswith(self.prefix)]
        if result.behaviour=='DEFEND':
            if not SETTINGS['cover_change']:return result
            target=(direction*clamp(direction*ball[0]-SETTINGS['cover_gap'],-3.65,SETTINGS['cover_max_x']),clamp(ball[1]*.6,-1.65,1.65));behaviour='COVER_GOAL'
        else:
            if not SETTINGS['support_change']:return result
            defending=min((distance(p,ball) for p in opponents),default=math.inf)+.12<min((distance(p,ball) for p in teammates),default=math.inf)
            if SETTINGS['support_defensive_only'] and not defending:return result
            side=-1 if self.name.endswith('A') else 1
            x=clamp(direction*ball[0]+(-.7 if defending else SETTINGS['support_advance']),-3.3,3.7)
            target=(direction*x,clamp(ball[1]+side*SETTINGS['support_width'],-2.25,2.25));behaviour='RECOVERY_SUPPORT' if defending else 'WIDE_SUPPORT'
        if SETTINGS['yield_enabled'] and distance(own,ball)<SETTINGS['yield_distance']:
            away=unit(ball,target);target=(clamp(ball[0]+away[0]*.85,-4.2,4.2),clamp(ball[1]+away[1]*.85,-2.6,2.6));behaviour='YIELD_TO_CHASER'
        return Decision(behaviour,target,tuple(ball))

    def restart_decision(self,world,result):
        match=world['match'];phase=match['phase']
        if phase=='PLAYING' and match['released']:
            self.restart_key=self.restart_taker=None
            return result
        if match['restart']!='KICKOFF' or match['restart_team']!=self.team or phase not in ('READY','PLAYING'):
            return result
        key=(match['half'],tuple(match['restart_point']),match['restart_team'])
        if self.restart_key!=key or self.restart_taker is None:
            point=match['restart_point'];robots=world['robots'];eligible={n:r for n,r in robots.items() if n.startswith(self.prefix) and 'Goalkeeper' not in n and n not in world.get('penalties',{})}
            self.restart_taker=min(eligible,key=lambda n:(route(eligible[n]['position'],eligible[n].get('yaw',0.),point,tolerance=.20)[0],n),default=self.name)
            self.restart_key=key
        own=world['robots'][self.name]['position'];ball=world['ball']['position'][:2]
        direction=match['red_direction']*(1 if self.team=='RED' else -1)
        if phase=='READY':
            point=match['restart_point']
            home=(point[0]-direction*.27,point[1]) if self.name==self.restart_taker else self.home(direction)
            return Decision('FORMATION',tuple(home),tuple(ball))
        if self.name==self.restart_taker:
            teammates={n:r['position'] for n,r in world['robots'].items() if n.startswith(self.prefix)}
            opponents=[r['position'] for n,r in world['robots'].items() if not n.startswith(self.prefix)]
            return self.attack(own,ball,direction,teammates,opponents,'RESTART')
        if distance(own,ball)<.85:
            ux,uy=unit(ball,own);return Decision('KEEP_DISTANCE',(ball[0]+ux*.95,ball[1]+uy*.95),tuple(ball))
        return Decision('FORMATION',self.home(direction),tuple(ball))

    def carry_around(self,*args,**kwargs):
        if not SETTINGS['evade']:return args[2]
        return super().carry_around(*args,**kwargs)

    def decide(self,world):
        intent=world.get('pass_intent')
        if SETTINGS['handoff_enabled'] and intent and intent['receiver'] in world['robots']:
            receiver=world['robots'][intent['receiver']]['position']
            if distance(receiver,world['ball']['position'])>SETTINGS['handoff_range']:
                # A short local kick must not freeze the sender for a distant
                # receiver. Ignore that handoff and retain ordinary ball pursuit.
                world=dict(world);world.pop('pass_intent',None)
        if SETTINGS['minimal']:return self.minimal_decide(world)
        if not SETTINGS['coordinate']:return super().decide(world)
        match=world['match'];phase=match['phase'];own=world['robots'][self.name]['position'];ball=world['ball']['position'][:2]
        self.own_yaw=world['robots'][self.name].get('yaw',0.)
        direction=match['red_direction']*(1 if self.team=='RED' else -1)
        if phase!='PLAYING' or not match['released'] or self.name in world.get('penalties',{}):
            self.team_chaser=None
            return super().decide(world)
        chaser=self.assign_chaser(world,direction)
        teammates={n:r['position'] for n,r in world['robots'].items() if n.startswith(self.prefix)}
        opponents=[r['position'] for n,r in world['robots'].items() if not n.startswith(self.prefix)]
        velocity=world['ball'].get('velocity',[0,0])
        intent=world.get('pass_intent')
        if intent and intent['expires']>world['time'] and intent['receiver'] in teammates:
            chaser=intent['receiver']
        if self.name==chaser:
            # Preserve the existing predictive tackle and recovery for defenders.
            if self.role=='defender':
                recovery=self.defensive_recovery(own,ball,velocity,direction,opponents)
                if recovery is not None:return recovery
            press=self.counterpress(world,own,ball,velocity,direction,opponents)
            if press is not None:
                self.carry_plan=None
                return press
            if self.role=='defender' and SETTINGS['defender_intercept']:
                threatening=min((distance(p,ball) for p in opponents),default=math.inf)<.65
                if threatening and distance(own,ball)>.40:
                    carriers=[r for n,r in world['robots'].items() if not n.startswith(self.prefix)]
                    carrier=min(carriers,key=lambda r:distance(r['position'],ball),default={})
                    if self.intercept_plan is None or world['time']-self.intercept_plan[0]>=.6 or distance(ball,self.intercept_plan[1])>.18:
                        target,predicted,_,_=interception(own,self.own_yaw,ball,velocity,direction,carrier.get('yaw'))
                        self.intercept_plan=(world['time'],tuple(ball),target,predicted)
                    return Decision('DEFENSIVE_INTERCEPT',self.intercept_plan[2],self.intercept_plan[3])
                if threatening and -direction*(own[0]-ball[0])>-.05 and distance(own,ball)<1.6:
                    escape=self.unblock_duel(world,own,ball,opponents)
                    return escape if escape is not None else Decision('CHALLENGE',tuple(ball),tuple(ball))
            escape=self.unblock_duel(world,own,ball,opponents)
            if escape is not None:return escape
            return self.attack(own,ball,direction,teammates,opponents)
        self.duel_anchor=self.duel_escape=None
        self.counterpressing=False;self.carry_plan=None
        if self.role=='goalkeeper':
            x=-direction*4.12;v=velocity;t=(x-ball[0])/v[0] if abs(v[0])>.02 else -1
            y=ball[1]+v[1]*t if 0<t<4 else ball[1]*.4
            return Decision('GUARD_INTERCEPT' if 0<t<4 else 'GUARD',(x,clamp(y,-1.05,1.05)),tuple(ball))
        near_team=min((distance(p,ball) for p in teammates.values()),default=math.inf)
        near_other=min((distance(p,ball) for p in opponents),default=math.inf)
        defending=near_other+.12<near_team
        if self.role=='defender':
            x=direction*clamp(direction*ball[0]-SETTINGS['cover_gap'],-3.65,SETTINGS['cover_max_x'])
            target=(x,clamp(ball[1]*.60,-1.65,1.65));behaviour='COVER_GOAL'
        else:
            # The spare forward offers width in possession; retreats into a
            # separate recovery lane when opponents are nearer the ball.
            side=-1 if self.name.endswith('A') else 1
            x=clamp(direction*ball[0]+(-.7 if defending else SETTINGS['support_advance']),-3.3,3.7)
            target=(direction*x,clamp(ball[1]+side*SETTINGS['support_width'],-2.25,2.25))
            behaviour='RECOVERY_SUPPORT' if defending else 'WIDE_SUPPORT'
        if distance(own,ball)<SETTINGS['yield_distance']:
            away=unit(ball,target)
            target=(clamp(ball[0]+away[0]*.85,-4.2,4.2),clamp(ball[1]+away[1]*.85,-2.6,2.6));behaviour='YIELD_TO_CHASER'
        return Decision(behaviour,target,tuple(ball))

    def attack(self,own,ball,direction,teammates,opponents,context=''):
        if SETTINGS['minimal']:
            legal={n:p for n,p in teammates.items() if n==self.name or distance(p,ball)<=SETTINGS['pass_distance']} if SETTINGS['short_pass_only'] and not context else teammates
            return super().attack(own,ball,direction,legal,opponents,context)
        if context or self.role=='goalkeeper' or (self.role=='defender' and direction*ball[0]<-1.2):
            return super().attack(own,ball,direction,teammates,opponents,context)
        nearest_y=clamp(ball[1],-.9,.9);goal=(direction*(4.5+self.goal_depth),0.)
        for y in (nearest_y,0.,-.9,.9):
            point=(goal[0],y)
            if lane_clear(ball,point,opponents):goal=point;break
        limit=SETTINGS['pass_distance'] if SETTINGS['short_pass_only'] else 3.5
        receivers=[(n,p) for n,p in teammates.items() if n!=self.name and 'Goalkeeper' not in n and
                   direction*(p[0]-ball[0])>.12 and distance(ball,p)<=limit and lane_clear(ball,p,opponents)]
        behaviour='DRIBBLE';kick='';receiver='';aim=goal
        if distance(ball,(direction*4.5,goal[1]))<.50 and lane_clear(ball,goal,opponents):
            behaviour='SHOOT';kick='shoot'
        elif receivers and not lane_clear(ball,goal,opponents):
            receiver,aim=max(receivers,key=lambda x:direction*x[1][0]);behaviour='PASS';kick='pass'
        elif SETTINGS['evade']:
            aim=self.carry_around(own,ball,goal,direction,opponents)
            if self.carry_plan is not None:behaviour='EVADE_DRIBBLE'
        ux,uy=unit(ball,aim);back,lateral=(.17,.05) if kick else (.19,0.)
        target=(ball[0]-back*ux+lateral*uy,ball[1]-back*uy-lateral*ux)
        if distance(own,ball)>.6:behaviour='INTERCEPT'
        return Decision(behaviour,target,tuple(aim),kick,receiver)
