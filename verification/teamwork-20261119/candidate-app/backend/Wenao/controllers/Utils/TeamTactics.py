"""Experimental four-player coordination; the movement/contact model is unchanged."""
import math
from Utils.PreviousTactics import TacticalPolicy as PreviousPolicy
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
}


def clamp(x, low, high):
    return max(low, min(high, x))


class TacticalPolicy(PreviousPolicy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.support_plan = None

    def decide(self, world):
        # A reachable handoff stays a local receiver task, never a ball teleport.
        intent = world.get('pass_intent')
        if intent and intent.get('receiver') in world['robots']:
            receiver = world['robots'][intent['receiver']]['position']
            if distance(receiver, world['ball']['position']) <= SETTINGS['handoff_distance']:
                # Bypass only the previous .60m filter; preserve its cover change.
                from Utils.PreviousTactics import SETTINGS as previous_settings
                old = previous_settings['handoff_range']
                previous_settings['handoff_range'] = SETTINGS['handoff_distance']
                try:
                    decision = super().decide(world)
                finally:
                    previous_settings['handoff_range'] = old
            else:
                decision = super().decide(world)
        else:
            decision = super().decide(world)
        match = world['match']
        if match['phase'] != 'PLAYING' or not match['released']:
            self.support_plan = None
            return decision
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
        if mode=='unchanged' or self.role!='striker' or context=='RESTART':
            return super().attack(own,ball,direction,teammates,opponents,context)
        reachable={n:p for n,p in teammates.items() if n==self.name or distance(p,ball)<=SETTINGS['pass_distance']}
        decision=super().attack(own,ball,direction,reachable,opponents,context)
        if mode=='opportunistic' and decision.behaviour in ('DRIBBLE','EVADE_DRIBBLE') and distance(own,ball)<.45:
            options=[(n,p) for n,p in reachable.items() if n!=self.name and 'Forward' in n and direction*(p[0]-ball[0])>.10 and distance(p,ball)>.35 and lane_clear(ball,p,opponents,.30)]
            pressure=min((distance(p,ball) for p in opponents),default=math.inf)
            if options and .40<pressure<1.1:
                receiver,aim=min(options,key=lambda item:distance(item[1],ball))
                return Decision('PASS',decision.target,tuple(aim[:2]),'pass',receiver)
        return decision
