"""Materialize the selected strategy without unused experimental branches."""
from pathlib import Path
import shutil,json,argparse
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--width',type=float,default=.65);p.add_argument('--ballside-threshold',type=float);a=p.parse_args()
APP=H/'production-app';shutil.copytree(H/'baseline-app',APP,dirs_exist_ok=True)
u=APP/'backend/Wenao/controllers/Utils'
p=u/'DefensivePlan.py';t=p.read_text().replace("'defender_space': True}","'defender_space': True,\n            # Carrying/duel policy assumptions; motion rates remain unchanged.\n            'evade_enabled': True, 'evade_distance': 1.8, 'evade_min_distance': .65,\n            'evade_width': "+repr(a.width)+", 'evade_ahead': .35,\n            'evade_angle':10., 'evade_enter_angle':4.}");p.write_text(t)
p=u/'TeamPolicy.py';t=p.read_text();t=t.replace('self.counterpressing = False\n\n    def home','self.counterpressing = False\n        self.carry_plan = None\n        self.own_yaw = 0.\n\n    def home')
t=t.replace('        match = world["match"]','        self.own_yaw = world["robots"][self.name].get("yaw",0.)\n        match = world["match"]',1)
t=t.replace('            self.intercept_plan = None\n            self.counterpressing = False','            self.intercept_plan = None\n            self.counterpressing = False\n            self.carry_plan = None',1)
t=t.replace('            if pressure is not None:\n                return pressure','            if pressure is not None:\n                self.carry_plan = None\n                return pressure',1)
t=t.replace("        if now-self.duel_anchor[1] < (8 if self.role == 'defender' else 3):",'''        wait=8 if self.role=='defender' else 3
        if self.role=='striker':
            yaw=world['robots'][self.name].get('yaw',0.)
            dx,dy=ball[0]-own[0],ball[1]-own[1]
            front=dx*math.cos(yaw)+dy*math.sin(yaw)
            lateral=-dx*math.sin(yaw)+dy*math.cos(yaw)
            # Match the existing defender's hold only while the ball really
            # remains in our forward foot window. Else realign promptly.
            if .08<front<.30 and abs(lateral)<.12:
                wait=SETTINGS['duel_hold_seconds']
        if now-self.duel_anchor[1] < wait:''')
if a.ballside_threshold is not None:
 t=t.replace("        if self.role == 'defender':\n            ball_lateral", "        if self.role == 'defender' or self.role=='striker':\n            ball_lateral")
 t=t.replace("            if abs(ball_lateral) > .02:","            if abs(ball_lateral) > (.02 if self.role=='defender' else "+repr(a.ballside_threshold)+"):")
t=t.replace('        ux, uy = unit(ball, aim)\n        # Shoot', '''        if behaviour=='DRIBBLE' and SETTINGS['evade_enabled']:
            aim=self.carry_around(own,ball,aim,direction,opponents)
            if self.carry_plan is not None:
                behaviour='EVADE_DRIBBLE'
        ux, uy = unit(ball, aim)
        # Shoot''')
method='''
    def carry_around(self, own, ball, goal, direction, opponents):
        """Commit to one carrying lane around a defender blocking the goal.

        The waypoint is an intended ball path, not a ball placement. Every
        turn, foot alignment and push still uses the ordinary executor.
        """
        if self.carry_plan is not None:
            anchor,waypoint=self.carry_plan
            passed=direction*(ball[0]-anchor[0])>.30
            if passed or distance(ball,waypoint)<.25 or distance(own,ball)>.65:
                self.carry_plan=None
            else:
                return waypoint
        if distance(own,ball)>.50 or lane_clear(ball,goal,opponents,clearance=.50):
            return goal
        # Starting a large turn in an already close tackle exposes the ball.
        ahead=[p for p in opponents if direction*(p[0]-ball[0])>.20
               and SETTINGS['evade_min_distance']<distance(p,ball)<SETTINGS['evade_distance']
               and abs(p[1]-ball[1])<.80]
        if not ahead:
            return goal
        other=min(ahead,key=lambda p:distance(p,ball))
        options=[]
        for side in (-1,1):
            waypoint=(max(-4.15,min(4.15,other[0]+direction*SETTINGS['evade_ahead'])),
                      max(-2.35,min(2.35,other[1]+side*SETTINGS['evade_width'])))
            bearing=math.atan2(waypoint[1]-ball[1],waypoint[0]-ball[0])
            error=abs((bearing-self.own_yaw+math.pi)%(2*math.pi)-math.pi)
            blocked=not lane_clear(ball,waypoint,opponents,clearance=.30)
            cost=distance(ball,waypoint)+error*1.2+int(blocked)*2.+max(0,abs(waypoint[1])-1.9)
            options.append((cost,waypoint))
        waypoint=min(options,key=lambda item:item[0])[1]
        self.carry_plan=(tuple(other[:2]),waypoint)
        return waypoint
'''
t=t.replace('\n\ndef avoid_obstacles(', '\n'+method+'\n\ndef avoid_obstacles(');p.write_text(t)
p=u/'Navigation.py';t=p.read_text().replace("'DRIBBLE', 'SHOOT'","'DRIBBLE', 'EVADE_DRIBBLE', 'SHOOT'")
t=t.replace("            limit = 20 if decision.kick else 25\n            if abs(angle) > (limit if self.aligned else 12):", "            evading=decision.behaviour=='EVADE_DRIBBLE'\n            limit=SETTINGS['evade_angle'] if evading else 20 if decision.kick else 25\n            entry=SETTINGS['evade_enter_angle'] if evading else 12\n            if abs(angle) > (limit if self.aligned else entry):")
t=t.replace("return turn_action(angle), 'FACE_KICK_DIRECTION'", "return turn_action(angle), ('EVADE_FACE_LANE' if evading else 'FACE_KICK_DIRECTION')")
t=t.replace("return ('step_left' if left > lateral_target else 'step_right'), 'ALIGN_FOOT_LATERALLY'", "return ('step_left' if left > lateral_target else 'step_right'), ('EVADE_ALIGN_FOOT' if evading else 'ALIGN_FOOT_LATERALLY')")
t=t.replace("('EXECUTE_KICK' if decision.kick else 'DRIBBLE_TOWARD_GOAL')", "('EXECUTE_KICK' if decision.kick else 'EVADE_CARRY_LANE' if evading else 'DRIBBLE_TOWARD_GOAL')")
p.write_text(t)
# Expose intended ball lane for visual review; never fed back into decisions.
p=APP/'server.py';t=p.read_text().replace("'action': self.last_actions.get(name, 'stand'),", "'ballTarget': dict(zip(('x','y'),decision.face)) if decision and decision.behaviour=='EVADE_DRIBBLE' else None,\n                             'action': self.last_actions.get(name, 'stand'),")
t=t.replace("target={'x':player['x'], 'y':player['y']})", "target={'x':player['x'], 'y':player['y']}, ballTarget=None)");p.write_text(t)
p=APP/'viewer.html';t=p.read_text();en={'EVADE_DRIBBLE':'Carry around defender','EVADE_FACE_LANE':'Turn towards the chosen side lane','EVADE_ALIGN_FOOT':'Keep the ball in the carrying foot window','EVADE_CARRY_LANE':'Carry along the committed side lane','evadeNotice':'Red is carrying towards a side lane around the defender.'};zh={'EVADE_DRIBBLE':'绕行带球','EVADE_FACE_LANE':'转向已选定的侧路','EVADE_ALIGN_FOOT':'对齐脚位，保持足球可控','EVADE_CARRY_LANE':'沿选定侧路带球推进','evadeNotice':'红方正在沿选定侧路带球，尝试绕过防守。'}
t=t.replace("function update(){", "Object.assign(translations.en,"+json.dumps(en,ensure_ascii=False)+");\nObject.assign(translations.zh,"+json.dumps(zh,ensure_ascii=False)+");\nfunction update(){")
t=t.replace(" else if(counterpressing)$('status').textContent=tr('pressNotice');", " else if(counterpressing)$('status').textContent=tr('pressNotice');\n else if(!sim.outcome&&sim.attacker.state==='EVADE_DRIBBLE')$('status').textContent=tr('evadeNotice');")
needle=" if($('targets').checked)for(const player of [sim.attacker,sim.defender])"
t=t.replace(needle," if($('targets').checked&&sim.attacker.ballTarget){const target=sim.attacker.ballTarget;line(sim.ball.x,sim.ball.y,target.x,target.y,'#ffd58a',2,[6,5]);circle(target.x,target.y,.07,'#ffd58a');}\n"+needle)
p.write_text(t)
print(APP)
