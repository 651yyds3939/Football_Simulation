from pathlib import Path
import sys,json,math
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'round3-app/backend/tools'))
from soccer2d import Simulation,Model
from Utils.TeamTactics import TacticalPolicy,SETTINGS
s=Simulation(110003,'BLUE','baseline',Model());SETTINGS.update({'assignment':True,'heading_weight':0.,'switch_margin':.15})
for n in s.names:
 if s.policies[n].team=='BLUE':s.policies[n]=TacticalPolicy(n,goal_depth=.3)
frames=[];idle=0
while s.step():
 if s.engine.phase!='PLAYING':continue
 near=min(math.dist(p['position'][:2],s.ball[:2]) for p in s.players.values())
 idle=idle+s.model.dt if near>.65 else 0
 if idle>5 and round(idle/s.model.dt)%25==0:
  frames.append({'time':s.time,'ball':s.ball,'players':{n:{'position':p['position'],'yaw':p['yaw'],'state':s.current_decisions[n].behaviour,'action':s.last_actions[n],'stage':s.navigation_stages.get(n),'target':s.current_decisions[n].target} for n,p in s.players.items()}})
(H/'idle-diagnostics.json').write_text(json.dumps(frames,indent=2));print('idle frames',len(frames));print(json.dumps(frames[:1],indent=2))
