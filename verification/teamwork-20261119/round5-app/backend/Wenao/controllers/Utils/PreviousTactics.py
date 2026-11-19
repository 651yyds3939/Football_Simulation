"""Small, measured 4v4 coordination changes around the existing role policy.

Keep the carrier, goalkeeper, finishing and movement logic. Reject a distant
handoff that would freeze local pursuit; retain a deeper defensive cover line.
"""
import math
from Utils.TeamPolicy import TeamPolicy,Decision,distance

SETTINGS={'handoff_enabled':True,'handoff_range':.60,'cover_change':True,'cover_gap':1.2}

class TacticalPolicy(TeamPolicy):
    def decide(self,world):
        intent=world.get('pass_intent')
        if SETTINGS['handoff_enabled'] and intent and intent['receiver'] in world['robots']:
            receiver=world['robots'][intent['receiver']]['position']
            if distance(receiver,world['ball']['position'])>SETTINGS['handoff_range']:
                # The declared pass rolls about 0.305m. Beyond its range plus
                # a local foot window, retain ordinary nearest-player pursuit.
                # Do not mutate the shared observation or invent a completion.
                world=dict(world)
                world.pop('pass_intent',None)
        decision=super().decide(world)
        match=world['match']
        if (not SETTINGS['cover_change'] or decision.behaviour!='DEFEND'
                or match['phase']!='PLAYING' or not match['released']):
            return decision
        direction=match['red_direction']*(1 if self.team=='RED' else -1)
        ball=world['ball']['position']
        # Cover stays goal-side; it does not become a second ball chaser.
        x=direction*max(-3.65,min(-1.5,direction*ball[0]-SETTINGS['cover_gap']))
        y=max(-1.65,min(1.65,ball[1]*.6))
        return Decision('COVER_GOAL',(x,y),tuple(ball[:2]))
